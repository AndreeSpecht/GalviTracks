"""Login de operador: proteção das rotas, primeiro acesso, sessão, perfis e gestão de usuários."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from radar_tracker import auth
from tests.conftest import SENHA_TESTE, criar_usuario, entrar

PELO_TUNEL = {"X-Forwarded-For": "203.0.113.7"}
RAIZ = Path(__file__).resolve().parent.parent


def logar(cliente, usuario="gestor", senha=SENHA_TESTE, **extra):
    return cliente.post("/login", data={"usuario": usuario, "senha": senha, **extra})


# --- Rotas protegidas ---
def test_pagina_sem_login_vai_para_o_login(app, anonimo):
    criar_usuario(app)
    resp = anonimo.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].startswith("/login")


@pytest.mark.parametrize("rota", ["/api/estado", "/api/clientes", "/api/get_historico", "/api/stream", "/baixar_excel", "/api/usuarios"])
def test_api_sem_login_responde_401(app, anonimo, rota):
    criar_usuario(app)
    resp = anonimo.get(rota)
    assert resp.status_code == 401 and resp.json["login"] == 1


def test_alteracao_sem_login_nao_acontece(app, anonimo):
    criar_usuario(app)
    assert anonimo.post("/api/save_cli", json={"nome": "X", "lat": -26.5, "lon": -49.1}).status_code == 401
    assert app.extensions["radar"]["banco"].listar_clientes() == []


def test_rotas_publicas(app, anonimo):
    criar_usuario(app)
    assert anonimo.get("/api/health").status_code == 200
    assert anonimo.get("/login").status_code == 200
    assert anonimo.get("/static/css/app.css").status_code == 200
    gps = {"_type": "location", "tid": "0", "lat": -26.5, "lon": -49.1, "tst": 1}
    assert anonimo.post("/api/gps/owntracks", json=gps).status_code == 200


# --- Login e saída ---
def test_login_certo_abre_o_painel(app, anonimo):
    criar_usuario(app)
    resp = logar(anonimo)
    assert resp.status_code == 302 and resp.headers["Location"] == "/"
    painel = anonimo.get("/")
    assert painel.status_code == 200 and b"Gestor" in painel.data
    assert anonimo.get("/api/eu").json["usuario"] == "gestor"


def test_login_nao_diferencia_maiusculas_no_usuario(app, anonimo):
    criar_usuario(app)
    assert logar(anonimo, usuario="GESTOR").status_code == 302


def test_login_errado(app, anonimo):
    criar_usuario(app)
    resp = logar(anonimo, senha="errada")
    assert resp.status_code == 401 and "Usuário ou senha incorretos".encode() in resp.data
    assert logar(anonimo, usuario="ninguem").status_code == 401
    assert anonimo.get("/api/estado").status_code == 401


def test_muitas_tentativas_bloqueiam(app, anonimo):
    criar_usuario(app)
    for _ in range(auth.TENTATIVAS_MAX):
        assert logar(anonimo, senha="errada").status_code == 401
    assert logar(anonimo).status_code == 429  # nem a senha certa passa durante o bloqueio


def test_login_volta_para_a_pagina_pedida_sem_sair_do_site(app, anonimo):
    criar_usuario(app)
    assert logar(anonimo, prox="/?x=1").headers["Location"] == "/?x=1"
    for externo in ("//site-malicioso.com", "https://site-malicioso.com", "/\\site-malicioso.com"):
        anonimo.post("/logout")
        assert logar(anonimo, prox=externo).headers["Location"] == "/"


def test_logout(client):
    assert client.post("/logout", json={}).json == {"ok": 1}
    assert client.get("/api/estado").status_code == 401


def test_usuario_removido_perde_a_sessao(app, client):
    uid = criar_usuario(app, "maria", "operador")
    outro = app.test_client()
    entrar(outro, uid)
    assert outro.get("/api/estado").status_code == 200
    assert client.post(f"/api/usuarios/{uid}/remover", json={}).json["ok"] == 1
    assert outro.get("/api/estado").status_code == 401


def test_post_de_outro_site_e_recusado(client):
    resp = client.post("/api/save_cli", json={"nome": "X", "lat": -26.5, "lon": -49.1},
                       headers={"Origin": "https://site-malicioso.com"})
    assert resp.status_code == 403
    ok = client.post("/api/save_cli", json={"nome": "X", "lat": -26.5, "lon": -49.1}, headers={"Origin": "http://localhost"})
    assert ok.status_code == 200


# --- Primeiro acesso ---
def test_sem_usuarios_abre_o_primeiro_acesso(anonimo):
    assert anonimo.get("/").headers["Location"] == "/primeiro-acesso"
    assert anonimo.get("/login").headers["Location"] == "/primeiro-acesso"
    assert anonimo.get("/primeiro-acesso").status_code == 200


def test_primeiro_acesso_cria_gestor_e_entra(app, anonimo):
    resp = anonimo.post("/primeiro-acesso", data={"nome": "André", "usuario": "andre", "senha": "segredo1", "confirmacao": "segredo1"})
    assert resp.status_code == 302
    assert anonimo.get("/api/eu").json == {"id": 1, "usuario": "andre", "nome": "André", "perfil": "gestor"}
    # Depois do primeiro usuário, a tela some
    assert anonimo.get("/primeiro-acesso").headers["Location"] == "/login"


@pytest.mark.parametrize("dados", [
    {"nome": "", "usuario": "a", "senha": "segredo1", "confirmacao": "segredo1"},
    {"nome": "A", "usuario": "com espaco", "senha": "segredo1", "confirmacao": "segredo1"},
    {"nome": "A", "usuario": "a", "senha": "curta", "confirmacao": "curta"},
    {"nome": "A", "usuario": "a", "senha": "segredo1", "confirmacao": "outra123"},
])
def test_primeiro_acesso_valida(app, anonimo, dados):
    assert anonimo.post("/primeiro-acesso", data=dados).status_code == 400
    assert app.extensions["radar"]["banco"].contar_usuarios() == 0


def test_primeiro_acesso_nao_pode_ser_feito_pela_internet(app, anonimo):
    app.extensions["radar"]["config"].ACESSO_PAINEL_INTERNET = True
    dados = {"nome": "Intruso", "usuario": "x", "senha": "segredo1", "confirmacao": "segredo1"}
    assert anonimo.post("/primeiro-acesso", data=dados, headers=PELO_TUNEL).status_code == 403
    assert anonimo.get("/primeiro-acesso", headers=PELO_TUNEL).status_code == 403
    assert app.extensions["radar"]["banco"].contar_usuarios() == 0


# --- Painel pela internet (nuvem) ---
def test_pela_internet_painel_continua_bloqueado_por_padrao(app, client):
    assert client.get("/login", headers=PELO_TUNEL).status_code == 403
    assert client.get("/api/estado", headers=PELO_TUNEL).status_code == 403


def test_na_nuvem_painel_abre_pela_internet_com_login(app, anonimo):
    app.extensions["radar"]["config"].ACESSO_PAINEL_INTERNET = True
    criar_usuario(app)
    assert anonimo.get("/api/estado", headers=PELO_TUNEL).status_code == 401
    assert anonimo.get("/login", headers=PELO_TUNEL).status_code == 200
    assert anonimo.post("/login", data={"usuario": "gestor", "senha": SENHA_TESTE}, headers=PELO_TUNEL).status_code == 302
    assert anonimo.get("/api/estado", headers=PELO_TUNEL).status_code == 200


# --- Gestão de usuários ---
def test_gestor_cria_lista_e_remove_operador(client):
    novo = {"nome": "Maria Souza", "usuario": "maria", "senha": "segredo1", "perfil": "operador"}
    assert client.post("/api/usuarios", json=novo).json["ok"] == 1
    lista = client.get("/api/usuarios").json
    assert {u["usuario"] for u in lista} == {"gestor", "maria"}
    assert all("senha_hash" not in u for u in lista)
    maria = next(u for u in lista if u["usuario"] == "maria")
    assert client.post(f"/api/usuarios/{maria['id']}/remover", json={}).json["ok"] == 1
    assert [u["usuario"] for u in client.get("/api/usuarios").json] == ["gestor"]
    # O login fica livre para ser usado de novo
    assert client.post("/api/usuarios", json=novo).json["ok"] == 1


@pytest.mark.parametrize("dados, erro", [
    ({"nome": "", "usuario": "x", "senha": "segredo1"}, "Preencha"),
    ({"nome": "X", "usuario": "a b", "senha": "segredo1"}, "espaços"),
    ({"nome": "X", "usuario": "x", "senha": "123"}, "6 caracteres"),
    ({"nome": "X", "usuario": "x", "senha": "segredo1", "perfil": "admin"}, "Perfil"),
    ({"nome": "X", "usuario": "GESTOR", "senha": "segredo1"}, "Já existe"),
])
def test_criacao_de_usuario_valida(client, dados, erro):
    resp = client.post("/api/usuarios", json=dados)
    assert resp.status_code == 400 and erro in resp.json["erro"]


def test_operador_nao_gerencia_usuarios(app, anonimo):
    criar_usuario(app)
    uid = criar_usuario(app, "maria", "operador")
    entrar(anonimo, uid)
    assert anonimo.get("/api/usuarios").status_code == 403
    assert anonimo.post("/api/usuarios", json={"nome": "X", "usuario": "x", "senha": "segredo1"}).status_code == 403
    assert anonimo.post("/api/usuarios/1/remover", json={}).status_code == 403
    assert anonimo.post("/api/usuarios/1/senha", json={"senha": "outra123"}).status_code == 403
    # mas troca a própria senha
    assert anonimo.post(f"/api/usuarios/{uid}/senha", json={"senha": "nova-senha"}).json["ok"] == 1
    anonimo.post("/logout")
    assert logar(anonimo, "maria", "nova-senha").status_code == 302


def test_gestor_nao_remove_a_si_nem_o_ultimo_gestor(app, client):
    assert client.post("/api/usuarios/1/remover", json={}).status_code == 400
    outro = criar_usuario(app, "chefe", "gestor")
    assert client.post(f"/api/usuarios/{outro}/remover", json={}).json["ok"] == 1


def test_gestor_redefine_senha_de_outro(app, client, anonimo):
    uid = criar_usuario(app, "maria", "operador")
    assert client.post(f"/api/usuarios/{uid}/senha", json={"senha": "nova-senha"}).json["ok"] == 1
    assert logar(anonimo, "maria", SENHA_TESTE).status_code == 401
    assert logar(anonimo, "maria", "nova-senha").status_code == 302


# --- Chave da sessão e linha de comando ---
def test_chave_da_sessao_gerada_uma_vez(tmp_path):
    arquivo = tmp_path / "chave_sessao"
    primeira = auth._chave_persistida(arquivo)
    assert len(primeira) == 64 and arquivo.read_text(encoding="utf-8") == primeira
    assert auth._chave_persistida(arquivo) == primeira


def test_script_cria_e_redefine_usuario(tmp_path):
    env = {**os.environ, "PASTA_DADOS": str(tmp_path), "DB_PATH": str(tmp_path / "t.db"),
           "ARQUIVO_SESSAO": str(tmp_path / "s.json")}

    def rodar(*args, senha="segredo1"):
        return subprocess.run([sys.executable, str(RAIZ / "scripts" / "criar_usuario.py"), *args, "--senha-stdin"],
                              input=senha + "\n", capture_output=True, text=True, env=env, timeout=60)

    r = rodar("andre", "--nome", "André", "--perfil", "gestor")
    assert r.returncode == 0, r.stderr
    assert rodar("andre").returncode != 0  # já existe
    assert rodar("maria", senha="123").returncode != 0  # senha curta
    assert rodar("andre", "--redefinir", senha="outra-senha").returncode == 0
    listagem = subprocess.run([sys.executable, str(RAIZ / "scripts" / "criar_usuario.py"), "--listar"],
                              capture_output=True, text=True, env=env, timeout=60)
    assert "andre" in listagem.stdout and "gestor" in listagem.stdout
