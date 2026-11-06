"""Rotas HTTP: interface web, API REST do painel e endpoint do OwnTracks."""

import hmac
import io
import ipaddress
import logging
import math
import time
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from . import alertas, geo, roteamento
from .frota import MotoboyNaoEncontrado
from .stream import eventos

log = logging.getLogger(__name__)
bp = Blueprint("radar", __name__)


def _frota():
    return current_app.extensions["radar"]["frota"]


def _banco():
    return current_app.extensions["radar"]["banco"]


def _cfg():
    return current_app.extensions["radar"]["config"]


def _json():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        abort(400, description="Corpo JSON inválido.")
    return dados


def _campo(dados, nome, tipo=str):
    try:
        valor = tipo(dados[nome])
    except (KeyError, TypeError, ValueError):
        abort(400, description=f"Campo '{nome}' ausente ou inválido.")
    if tipo is str:
        valor = valor.strip()
        if not valor:
            abort(400, description=f"Campo '{nome}' não pode ser vazio.")
    if tipo is float and (not math.isfinite(valor) or (nome == "lat" and not -90 <= valor <= 90)
                          or (nome == "lon" and not -180 <= valor <= 180)):
        abort(400, description=f"Campo '{nome}' fora da faixa válida.")
    return valor


@bp.errorhandler(MotoboyNaoEncontrado)
def _motoboy_inexistente(_erro):
    return jsonify({"ok": 0, "erro": "Motoboy não encontrado."}), 404


@bp.app_errorhandler(400)
def _requisicao_invalida(erro):
    return jsonify({"ok": 0, "erro": erro.description}), 400


# --- Acesso pela internet (túnel ngrok/cloudflared) ---
# Pelo túnel só os celulares precisam entrar: o painel e o resto da API ficam na rede da loja.
ROTAS_EXTERNAS = frozenset({"/api/gps/owntracks", "/api/health"})
_CABECALHOS_PROXY = ("X-Forwarded-For", "Forwarded", "X-Real-IP", "CF-Connecting-IP")


def _requisicao_externa():
    """Verdadeiro se a requisição veio da internet (por túnel/proxy ou de um IP público).

    Os túneis repassam a conexão a partir do próprio computador (127.0.0.1), por isso o
    endereço de origem não basta: eles sempre acrescentam X-Forwarded-For. Um cliente não
    consegue retirar esse cabeçalho; acrescentá-lo só restringe o próprio acesso.
    """
    if any(nome in request.headers for nome in _CABECALHOS_PROXY):
        return True
    dominio = _cfg().NGROK_DOMAIN.strip().lower()
    if dominio and request.host.split(":")[0].lower() == dominio:
        return True
    try:
        ip = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return True
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return not (ip.is_loopback or ip.is_private or ip.is_link_local)


@bp.before_app_request
def _proteger_acesso_externo():
    if not _requisicao_externa():
        return None
    if request.path not in ROTAS_EXTERNAS:
        log.warning("Acesso externo bloqueado: %s %s", request.method, request.path)
        if request.path.startswith("/api/"):
            return jsonify({"ok": 0, "erro": "Disponível somente na rede da loja."}), 403
        return Response("O painel do GalviTracks está disponível somente na rede da loja.\n",
                        status=403, mimetype="text/plain")
    if request.path == "/api/gps/owntracks" and not _cfg().OWNTRACKS_TOKEN:
        log.warning("Posição recebida pela internet sem OWNTRACKS_TOKEN definido: recusada.")
        return jsonify({"erro": "Defina OWNTRACKS_TOKEN no servidor para receber posições pela internet."}), 403
    return None


# --- Interface ---
@bp.route("/")
def index():
    cfg = _cfg()
    return render_template("index.html", empresa=cfg.NOME_EMPRESA, base_lat=cfg.BASE_LAT, base_lon=cfg.BASE_LON)


@bp.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@bp.route("/api/motoboys")
def motoboys():
    return jsonify([{"id": m["id"], "nome": m["nome"], "cor": m["cor"], "tid": str(m["tid"])}
                    for m in _frota().motoboys.values()])


# --- Frota / rota ---
def _avaliar_estado(snapshot, banco, cfg):
    base = {"lat": cfg.BASE_LAT, "lon": cfg.BASE_LON}
    return alertas.avaliar_frota(snapshot, banco.listar_clientes(), base, cfg)


def _estado_com_alertas():
    frota, banco, cfg = _frota(), _banco(), _cfg()
    return frota.snapshot_com_versao(lambda dados: _avaliar_estado(dados, banco, cfg))[1]


@bp.route("/api/estado")
def estado():
    return jsonify(_estado_com_alertas())


@bp.route("/api/stream")
def stream():
    frota, banco, cfg = _frota(), _banco(), _cfg()
    liberar = current_app.extensions["radar"]["streams"].reservar()
    if liberar is None:
        return jsonify({"erro": "Limite de streams atingido; use /api/estado."}), 503, {"Retry-After": "3"}
    resposta = Response(
        eventos(frota, lambda dados: _avaliar_estado(dados, banco, cfg), liberar,
                desconectado=request.environ.get("waitress.client_disconnected", lambda: False)),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    resposta.call_on_close(liberar)  # cobre inclusive gerador fechado antes do primeiro next()
    return resposta


@bp.route("/api/resumo")
def resumo():
    snapshot = _estado_com_alertas()
    return jsonify({"em_rota": sum(m["status"] == "EM_ROTA" for m in snapshot.values()),
                    "livres": sum(m["status"] == "LIVRE" for m in snapshot.values()),
                    "com_alerta": sum(bool(m["alertas"]) for m in snapshot.values()),
                    **_banco().resumo_dia()})


@bp.route("/api/alertas")
def lista_alertas():
    """Alertas ativos de toda a frota, do mais grave para o mais leve."""
    saida = [
        {**a, "moto_id": int(mid), "motoboy": dados["nome"]}
        for mid, dados in _estado_com_alertas().items()
        for a in dados["alertas"]
    ]
    ordem = {nivel: i for i, nivel in enumerate(("critico", "alerta", "aviso"))}
    return jsonify(sorted(saida, key=lambda a: ordem[a["nivel"]]))


@bp.route("/api/add", methods=["POST"])
def adicionar_parada():
    d = _json()
    ok = _frota().adicionar_parada(_campo(d, "id", int), _campo(d, "nome"), _campo(d, "lat", float), _campo(d, "lon", float))
    return jsonify({"ok": int(ok)})


@bp.route("/api/rm", methods=["POST"])
def remover_parada():
    d = _json()
    ok = _frota().remover_parada(_campo(d, "id", int), _campo(d, "idx", int))
    return jsonify({"ok": int(ok)})


@bp.route("/api/otimizar", methods=["POST"])
def otimizar():
    ok = _frota().otimizar(_campo(_json(), "id", int))
    return jsonify({"ok": int(ok)})


@bp.route("/api/start", methods=["POST"])
def iniciar():
    d = _json()
    ok = _frota().iniciar(_campo(d, "id", int), str(d.get("nota", "")).strip())
    return jsonify({"ok": int(ok)})


@bp.route("/api/end", methods=["POST"])
def finalizar():
    viagem = _frota().finalizar(_campo(_json(), "id", int), registrar=_banco().registrar_viagem)
    return jsonify({"ok": int(bool(viagem))})


@bp.route("/api/calc", methods=["POST"])
def calcular():
    paradas = _json().get("stops", [])
    try:
        paradas = [{"lat": float(p["lat"]), "lon": float(p["lon"])} for p in paradas]
        if any(not -90 <= p["lat"] <= 90 or not -180 <= p["lon"] <= 180 for p in paradas):
            raise ValueError("Coordenadas inválidas")
    except (KeyError, TypeError, ValueError):
        abort(400, description="Lista de paradas inválida.")
    cfg = _cfg()
    return jsonify(roteamento.calcular_rota(paradas, {"lat": cfg.BASE_LAT, "lon": cfg.BASE_LON}, cfg))


@bp.route("/api/buscar")
def buscar():
    q = request.args.get("q", "").strip()
    return jsonify(roteamento.buscar_endereco(q, _cfg()) if q else [])


# --- GPS (OwnTracks, modo HTTP) ---
def _owntracks_autorizado():
    """Se OWNTRACKS_TOKEN estiver definido, exige-o como senha (HTTP Basic) ou header X-Token."""
    token = _cfg().OWNTRACKS_TOKEN
    if not token:
        return True
    auth = request.authorization
    enviado = (auth.password if auth else None) or request.headers.get("X-Token", "")
    return hmac.compare_digest(str(enviado), token)


def _numero(valor):
    try:
        numero = float(valor)
        return numero if math.isfinite(numero) else None
    except (TypeError, ValueError, OverflowError):
        return None


@bp.route("/api/gps/owntracks", methods=["POST"])
def gps_owntracks():
    if not _owntracks_autorizado():
        return jsonify({"erro": "Não autorizado."}), 401
    d = request.get_json(silent=True) or {}
    if not isinstance(d, dict) or d.get("_type") != "location":
        return jsonify([])  # OwnTracks espera uma lista (vazia) como resposta
    frota = _frota()
    mid = frota.id_por_tid(d.get("tid", ""))
    lat, lon = _numero(d.get("lat")), _numero(d.get("lon"))
    if mid is None or lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        log.info("OwnTracks: leitura ignorada (tid=%r).", d.get("tid"))
        return jsonify([])
    # bs (battery status) do OwnTracks: 2 = carregando, 3 = carga completa (na tomada)
    status_bateria = _numero(d.get("bs"))
    frota.registrar_contato(
        mid,
        bateria=_numero(d.get("batt")),
        carregando=None if status_bateria is None else status_bateria in (2, 3),
    )
    registro = frota.atualizar_posicao(mid, lat, lon, d.get("tst"), precisao_m=_numero(d.get("acc")),
                                       vel_dispositivo=_numero(d.get("vel")), curso=_numero(d.get("cog")), detalhes=True)
    if registro is None:
        log.info("OwnTracks: leitura descartada pelo filtro (moto %s, acc=%s).", mid, d.get("acc"))
    else:
        _banco().registrar_posicao(**registro)
    return jsonify([])


@bp.route("/api/tracklog")
def tracklog():
    try:
        mid = int(request.args.get("id", 0))
    except ValueError:
        abort(400, description="ID inválido.")
    _frota().validar_id(mid)
    data = request.args.get("data")
    if data:
        try:
            inicio = datetime.strptime(data, "%Y-%m-%d")
            ts_inicio, ts_fim = int(inicio.timestamp()), int((inicio + timedelta(days=1)).timestamp())
        except (ValueError, OSError, OverflowError):
            abort(400, description="Data inválida (use AAAA-MM-DD).")
    else:
        ts_fim = int(time.time()) + 1
        ts_inicio = ts_fim - 86400
    pontos = _banco().trilha(mid, ts_inicio, ts_fim)
    return jsonify(geo.simplificar_trilha(pontos) if request.args.get("simplificar") == "1" else pontos)


# --- Clientes ---
@bp.route("/api/clientes")
def clientes():
    return jsonify(_banco().listar_clientes())


@bp.route("/api/save_cli", methods=["POST"])
def salvar_cliente():
    d = _json()
    cid = _banco().salvar_cliente(_campo(d, "nome"), _campo(d, "lat", float), _campo(d, "lon", float))
    _frota().notificar()
    return jsonify({"ok": 1, "id": cid})


@bp.route("/api/update_client", methods=["POST"])
def atualizar_cliente():
    d = _json()
    _banco().atualizar_cliente(_campo(d, "id", int), _campo(d, "nome"), str(d.get("telefone", "")).strip())
    _frota().notificar()
    return jsonify({"ok": 1})


@bp.route("/api/update_color", methods=["POST"])
def atualizar_cor():
    d = _json()
    cor = _campo(d, "cor")
    if not (cor.startswith("#") and len(cor) == 7):
        abort(400, description="Cor deve estar no formato #rrggbb.")
    _banco().atualizar_cor_cliente(_campo(d, "id", int), cor)
    _frota().notificar()
    return jsonify({"ok": 1})


@bp.route("/api/apagar_cliente", methods=["POST"])
def apagar_cliente():
    _banco().apagar_cliente(_campo(_json(), "id", int))
    _frota().notificar()
    return jsonify({"ok": 1})


# --- Histórico e relatórios ---
@bp.route("/api/get_historico")
def historico():
    return jsonify(_banco().historico(request.args.get("inicio"), request.args.get("fim")))


@bp.route("/baixar_excel")
def baixar_excel():
    linhas = _banco().historico(request.args.get("inicio"), request.args.get("fim"))
    colunas = [
        ("data_viagem", "Data"),
        ("motoboy", "Motoboy"),
        ("numero_nota", "Nota / Pedido"),
        ("destinos", "Destinos"),
        ("hora_saida", "Saída"),
        ("hora_chegada", "Chegada"),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Histórico"
    ws.append([titulo for _, titulo in colunas])
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="2C3E50")
    for linha in linhas:
        valores = [linha.get(chave) or "" for chave, _ in colunas]
        ws.append(["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in valores])
    for letra, largura in zip("ABCDEF", (12, 20, 16, 60, 10, 10)):
        ws.column_dimensions[letra].width = largura
    ws.freeze_panes = "A2"

    saida = io.BytesIO()
    wb.save(saida)
    saida.seek(0)
    nome = f"historico_entregas_{datetime.now():%Y%m%d}.xlsx"
    return send_file(
        saida,
        as_attachment=True,
        download_name=nome,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
