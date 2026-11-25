"""Login de operador: usuários, sessão e proteção das rotas do painel.

- Todas as rotas exigem login, exceto o login em si, o /api/health, o endpoint do
  OwnTracks (que tem a própria senha, OWNTRACKS_TOKEN) e os arquivos estáticos.
- Sem nenhum usuário cadastrado, a tela de primeiro acesso cria o primeiro gestor,
  mas só para quem está no próprio computador ou na rede da loja.
- Perfis: "gestor" (gerencia usuários) e "operador".
"""

import logging
import secrets
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import (Blueprint, current_app, g, jsonify, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .api import _requisicao_externa

log = logging.getLogger(__name__)
bp = Blueprint("auth", __name__)

PERFIS = ("gestor", "operador")
SENHA_MIN = 6
ROTAS_PUBLICAS = frozenset({"/login", "/logout", "/primeiro-acesso", "/api/health", "/api/gps/owntracks"})
# Hash usado quando o login não existe, para a resposta levar o mesmo tempo
_HASH_FALSO = generate_password_hash(secrets.token_hex(8))

TENTATIVAS_MAX = 5
TENTATIVAS_JANELA_S = 300
_tentativas = {}
_tentativas_lock = threading.Lock()


def _banco():
    return current_app.extensions["radar"]["banco"]


def configurar(app, cfg):
    """Chave da sessão, validade e opções do cookie."""
    app.secret_key = cfg.SECRET_KEY or _chave_persistida(Path(cfg.PASTA_DADOS) / "chave_sessao")
    app.config.update(
        PERMANENT_SESSION_LIFETIME=timedelta(days=cfg.SESSAO_DIAS),
        SESSION_COOKIE_NAME="galvitracks_sessao",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=cfg.COOKIE_SEGURO,
    )


def _chave_persistida(arquivo):
    """Gera a chave na primeira execução e reaproveita depois (as sessões sobrevivem ao reinício)."""
    try:
        chave = arquivo.read_text(encoding="utf-8").strip()
        if len(chave) >= 32:
            return chave
    except OSError:
        pass
    chave = secrets.token_hex(32)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(chave, encoding="utf-8")
    return chave


# --- Senhas e tentativas ---
def gerar_hash(senha):
    return generate_password_hash(senha)


def validar_senha(senha):
    """Mensagem de erro ou None."""
    if len(senha or "") < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    return None


def _bloqueado(ip):
    agora = time.monotonic()
    with _tentativas_lock:
        recentes = [t for t in _tentativas.get(ip, []) if agora - t < TENTATIVAS_JANELA_S]
        _tentativas[ip] = recentes
        return len(recentes) >= TENTATIVAS_MAX


def _registrar_falha(ip):
    with _tentativas_lock:
        _tentativas.setdefault(ip, []).append(time.monotonic())


def _limpar_falhas(ip):
    with _tentativas_lock:
        _tentativas.pop(ip, None)


def _ip():
    """IP do cliente para limitar tentativas. Só confia no X-Forwarded-For quando a conexão
    vem do próprio computador (túnel ou proxy local), que acrescenta o IP real no fim."""
    ip = request.remote_addr or ""
    encaminhado = request.headers.get("X-Forwarded-For", "")
    if encaminhado and ip in ("127.0.0.1", "::1"):
        return encaminhado.split(",")[-1].strip()
    return ip


def autenticar(usuario, senha):
    """Usuário (sem o hash) se login e senha conferem e ele está ativo; senão None."""
    registro = _banco().usuario_para_login((usuario or "").strip())
    if registro is None or not registro["ativo"]:
        check_password_hash(_HASH_FALSO, senha or "")
        return None
    if not check_password_hash(registro["senha_hash"], senha or ""):
        return None
    registro.pop("senha_hash")
    return registro


def _entrar(usuario):
    session.clear()
    session.permanent = True
    session["uid"] = usuario["id"]


def _destino_seguro(prox):
    """Só caminhos do próprio sistema (evita redirecionar para outro site)."""
    if not prox or not prox.startswith("/") or prox.startswith("//") or "\\" in prox:
        return url_for("radar.index")
    partes = urlsplit(prox)
    if partes.scheme or partes.netloc:
        return url_for("radar.index")
    return prox


# --- Proteção das rotas ---
@bp.before_app_request
def _exigir_login():
    g.usuario = None
    uid = session.get("uid")
    if uid is not None:
        usuario = _banco().obter_usuario(uid)
        if usuario and usuario["ativo"]:
            g.usuario = usuario
        else:
            session.clear()

    caminho = request.path
    if request.method == "POST" and caminho != "/api/gps/owntracks" and not _mesma_origem():
        return jsonify({"ok": 0, "erro": "Origem da requisição não permitida."}), 403
    if g.usuario is not None or caminho in ROTAS_PUBLICAS or caminho.startswith("/static/"):
        return None
    if _banco().contar_usuarios() == 0 and not _requisicao_externa():
        if caminho.startswith("/api/") or caminho == "/baixar_excel":
            return jsonify({"ok": 0, "erro": "Crie o primeiro acesso do sistema.", "login": 1}), 401
        return redirect(url_for("auth.primeiro_acesso"))
    if caminho.startswith("/api/") or caminho == "/baixar_excel":
        return jsonify({"ok": 0, "erro": "Sua sessão expirou. Entre novamente.", "login": 1}), 401
    return redirect(url_for("auth.login", prox=request.full_path.rstrip("?")))


def _mesma_origem():
    """Navegadores mandam Origin em POST; se vier de outro site, recusa (proteção CSRF)."""
    origem = request.headers.get("Origin")
    if not origem or origem == "null":
        return True
    return urlsplit(origem).netloc.lower() == request.host.lower()


def exigir_gestor():
    if g.usuario is None or g.usuario["perfil"] != "gestor":
        return jsonify({"ok": 0, "erro": "Apenas o gestor pode fazer isso."}), 403
    return None


# --- Telas de login ---
@bp.route("/login", methods=["GET", "POST"])
def login():
    cfg = current_app.extensions["radar"]["config"]
    prox = request.values.get("prox", "")
    if _banco().contar_usuarios() == 0 and not _requisicao_externa():
        return redirect(url_for("auth.primeiro_acesso"))
    if g.usuario is not None and request.method == "GET":
        return redirect(_destino_seguro(prox))

    erro, usuario_digitado, status = None, "", 200
    if request.method == "POST":
        ip = _ip()
        usuario_digitado = request.form.get("usuario", "").strip()
        if _bloqueado(ip):
            erro, status = "Muitas tentativas. Aguarde alguns minutos e tente de novo.", 429
        else:
            usuario = autenticar(usuario_digitado, request.form.get("senha", ""))
            if usuario:
                _limpar_falhas(ip)
                _entrar(usuario)
                log.info("Login de %s.", usuario["usuario"])
                return redirect(_destino_seguro(prox))
            _registrar_falha(ip)
            log.warning("Login recusado para %r (ip %s).", usuario_digitado, ip)
            erro, status = "Usuário ou senha incorretos.", 401
    return render_template("login.html", modo="login", empresa=cfg.NOME_EMPRESA, erro=erro,
                           usuario=usuario_digitado, prox=prox), status


@bp.route("/primeiro-acesso", methods=["GET", "POST"])
def primeiro_acesso():
    cfg = current_app.extensions["radar"]["config"]
    if _banco().contar_usuarios() > 0:
        return redirect(url_for("auth.login"))
    if _requisicao_externa():
        return ("O primeiro acesso só pode ser criado no computador da loja ou com "
                "scripts/criar_usuario.py no servidor.\n", 403, {"Content-Type": "text/plain; charset=utf-8"})

    erro, dados, status = None, {}, 200
    if request.method == "POST":
        dados = {k: request.form.get(k, "").strip() for k in ("nome", "usuario")}
        senha, confirmacao = request.form.get("senha", ""), request.form.get("confirmacao", "")
        if not dados["nome"] or not dados["usuario"]:
            erro = "Preencha o nome e o usuário."
        elif " " in dados["usuario"]:
            erro = "O usuário não pode ter espaços."
        elif validar_senha(senha):
            erro = validar_senha(senha)
        elif senha != confirmacao:
            erro = "As senhas não conferem."
        else:
            uid = _banco().criar_usuario(dados["usuario"], dados["nome"], gerar_hash(senha), "gestor")
            _entrar(_banco().obter_usuario(uid))
            log.info("Primeiro acesso criado: %s (gestor).", dados["usuario"])
            return redirect(url_for("radar.index"))
        status = 400
    return render_template("login.html", modo="primeiro", empresa=cfg.NOME_EMPRESA, erro=erro,
                           usuario=dados.get("usuario", ""), nome=dados.get("nome", ""), prox=""), status


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": 1})
    return redirect(url_for("auth.login"))


# --- API de usuários ---
def _publico(u):
    return {"id": u["id"], "usuario": u["usuario"], "nome": u["nome"], "perfil": u["perfil"]}


@bp.route("/api/eu")
def eu():
    return jsonify(_publico(g.usuario))


@bp.route("/api/usuarios")
def listar_usuarios():
    recusa = exigir_gestor()
    if recusa:
        return recusa
    return jsonify([_publico(u) for u in _banco().listar_usuarios()])


def _json():
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


@bp.route("/api/usuarios", methods=["POST"])
def criar_usuario():
    recusa = exigir_gestor()
    if recusa:
        return recusa
    d = _json()
    nome, usuario = str(d.get("nome", "")).strip(), str(d.get("usuario", "")).strip()
    senha, perfil = str(d.get("senha", "")), str(d.get("perfil", "operador"))
    if not nome or not usuario:
        return jsonify({"ok": 0, "erro": "Preencha o nome e o usuário."}), 400
    if " " in usuario:
        return jsonify({"ok": 0, "erro": "O usuário não pode ter espaços."}), 400
    if perfil not in PERFIS:
        return jsonify({"ok": 0, "erro": "Perfil inválido."}), 400
    if validar_senha(senha):
        return jsonify({"ok": 0, "erro": validar_senha(senha)}), 400
    try:
        uid = _banco().criar_usuario(usuario, nome, gerar_hash(senha), perfil)
    except ValueError as e:
        return jsonify({"ok": 0, "erro": str(e)}), 400
    log.info("%s criou o usuário %s (%s).", g.usuario["usuario"], usuario, perfil)
    return jsonify({"ok": 1, "id": uid})


@bp.route("/api/usuarios/<int:uid>/senha", methods=["POST"])
def trocar_senha(uid):
    # O gestor troca a senha de qualquer um; cada usuário pode trocar a própria.
    if uid != g.usuario["id"]:
        recusa = exigir_gestor()
        if recusa:
            return recusa
    senha = str(_json().get("senha", ""))
    if validar_senha(senha):
        return jsonify({"ok": 0, "erro": validar_senha(senha)}), 400
    if not _banco().definir_senha(uid, gerar_hash(senha)):
        return jsonify({"ok": 0, "erro": "Usuário não encontrado."}), 404
    return jsonify({"ok": 1})


@bp.route("/api/usuarios/<int:uid>/remover", methods=["POST"])
def remover_usuario(uid):
    recusa = exigir_gestor()
    if recusa:
        return recusa
    if uid == g.usuario["id"]:
        return jsonify({"ok": 0, "erro": "Você não pode remover o próprio acesso."}), 400
    alvo = _banco().obter_usuario(uid)
    if not alvo or not alvo["ativo"]:
        return jsonify({"ok": 0, "erro": "Usuário não encontrado."}), 404
    if alvo["perfil"] == "gestor" and _banco().contar_usuarios("gestor") <= 1:
        return jsonify({"ok": 0, "erro": "O sistema precisa de pelo menos um gestor."}), 400
    _banco().desativar_usuario(uid)
    log.info("%s removeu o usuário %s.", g.usuario["usuario"], alvo["usuario"])
    return jsonify({"ok": 1})
