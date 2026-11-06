"""Acesso pela internet (túnel): só o endpoint do OwnTracks, e somente com token."""

import time

import pytest

PELO_TUNEL = {"X-Forwarded-For": "203.0.113.7"}


def posicao(lat=-26.5085):
    return {"_type": "location", "tid": "0", "lat": lat, "lon": -49.1054, "tst": int(time.time())}


@pytest.fixture
def com_token(app):
    app.extensions["radar"]["config"].OWNTRACKS_TOKEN = "segredo"


@pytest.mark.parametrize("rota", ["/", "/api/estado", "/api/clientes", "/api/get_historico",
                                  "/baixar_excel", "/api/stream", "/static/js/main.js"])
def test_painel_e_api_bloqueados_pelo_tunel(client, rota):
    resp = client.get(rota, headers=PELO_TUNEL)
    assert resp.status_code == 403


def test_alteracoes_bloqueadas_pelo_tunel(client):
    resp = client.post("/api/save_cli", json={"nome": "X", "lat": -26.5, "lon": -49.1}, headers=PELO_TUNEL)
    assert resp.status_code == 403
    assert client.get("/api/clientes").json == []


def test_api_bloqueada_responde_json(client):
    assert client.get("/api/estado", headers=PELO_TUNEL).json["erro"]


def test_health_liberado_pelo_tunel(client):
    assert client.get("/api/health", headers=PELO_TUNEL).status_code == 200


def test_gps_pelo_tunel_exige_token_configurado(client):
    resp = client.post("/api/gps/owntracks", json=posicao(), headers=PELO_TUNEL)
    assert resp.status_code == 403
    assert "lat_atual" not in client.get("/api/estado").json["0"] or \
        client.get("/api/estado").json["0"]["lat_atual"] != -26.5085


def test_gps_pelo_tunel_com_token(client, com_token):
    assert client.post("/api/gps/owntracks", json=posicao(), headers=PELO_TUNEL).status_code == 401
    ok = client.post("/api/gps/owntracks", json=posicao(), headers=PELO_TUNEL, auth=("moto", "segredo"))
    assert ok.status_code == 200
    assert client.get("/api/estado").json["0"]["lat_atual"] == -26.5085


def test_ip_publico_sem_proxy_conta_como_externo(client):
    publico = {"REMOTE_ADDR": "8.8.8.8"}
    assert client.get("/api/estado", environ_base=publico).status_code == 403
    assert client.get("/api/health", environ_base=publico).status_code == 200


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1", "192.168.0.15", "10.1.2.3", "172.16.4.4", "::ffff:192.168.0.9"])
def test_rede_local_continua_com_acesso(client, ip):
    assert client.get("/api/estado", environ_base={"REMOTE_ADDR": ip}).status_code == 200


def test_rede_local_envia_gps_sem_token(client):
    assert client.post("/api/gps/owntracks", json=posicao()).status_code == 200


def test_host_do_dominio_ngrok_conta_como_externo(app, client):
    app.extensions["radar"]["config"].NGROK_DOMAIN = "radar.ngrok.app"
    assert client.get("/api/estado", headers={"Host": "radar.ngrok.app"}).status_code == 403
    assert client.get("/api/estado", headers={"Host": "127.0.0.1:5000"}).status_code == 200


def test_waitress_repassa_cabecalho_do_tunel(app):
    """O waitress apaga cabeçalhos de proxy por padrão; o servidor real precisa mantê-los."""
    import http.client
    import threading

    from run import criar_servidor

    app.extensions["radar"]["config"].HOST = "127.0.0.1"
    servidor = criar_servidor(app, 0)
    porta = servidor.effective_port
    threading.Thread(target=servidor.run, daemon=True).start()
    try:
        def status(caminho, cabecalhos):
            conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
            conexao.request("GET", caminho, headers=cabecalhos)
            codigo = conexao.getresponse().status
            conexao.close()
            return codigo

        assert status("/api/estado", PELO_TUNEL) == 403
        assert status("/", PELO_TUNEL) == 403
        assert status("/api/health", PELO_TUNEL) == 200
        assert status("/api/estado", {}) == 200
    finally:
        servidor.close()
        servidor.task_dispatcher.shutdown()
