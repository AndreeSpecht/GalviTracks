import json
import threading
import time

from radar_tracker import alertas
from radar_tracker.stream import Streams, eventos


def ler_estado(chunk):
    texto = chunk.decode() if isinstance(chunk, bytes) else chunk
    assert "event: estado\n" in texto
    return json.loads(texto.split("data: ", 1)[1].strip())


def test_stream_snapshot_e_atualizacao_por_owntracks(app, client):
    resposta = client.get("/api/stream", buffered=False)
    try:
        assert resposta.content_type == "text/event-stream"
        assert resposta.headers["Cache-Control"] == "no-cache"
        assert resposta.headers["X-Accel-Buffering"] == "no"
        primeiro = next(resposta.response)
        assert primeiro.startswith(b"retry: 3000\n")
        assert ler_estado(primeiro) == client.get("/api/estado").json
        enviado = time.monotonic()
        client.post("/api/gps/owntracks", json={"_type": "location", "tid": "0", "lat": -26.50,
                                               "lon": -49.10, "cog": 90, "acc": 8, "batt": 70})
        novo = ler_estado(next(resposta.response))
        assert time.monotonic() - enviado < 1  # limite de 300 ms é aferido pelo teste HTTP real
        assert novo["0"]["lat_atual"] == -26.50
        assert novo["0"]["curso"] == 90
        assert novo["0"]["online"] is True
        assert novo["0"]["versao"] > ler_estado(primeiro)["0"]["versao"]
    finally:
        resposta.close()


def test_stream_limite_e_liberacao_de_vagas(app, client):
    app.extensions["radar"]["streams"] = Streams(1)
    primeira = client.get("/api/stream", buffered=False)
    try:
        negada = client.get("/api/stream", buffered=False)
        assert negada.status_code == 503
        assert negada.headers["Retry-After"] == "3"
    finally:
        primeira.close()
    nova = client.get("/api/stream", buffered=False)
    assert nova.status_code == 200
    nova.close()


def test_stream_ping_e_fechamento(app):
    f = app.extensions["radar"]["frota"]
    liberado = threading.Event()
    gerador = eventos(f, lambda s: s, liberado.set, ping_s=0.01, intervalo_s=0)
    next(gerador)
    assert next(gerador) == ": ping\n\n"
    gerador.close()
    assert liberado.is_set()


def test_stream_agrupa_mudancas_e_acorda_ao_fechar(app):
    f = app.extensions["radar"]["frota"]
    gerador = eventos(f, lambda s: s, lambda: None, intervalo_s=0.05)
    primeiro = ler_estado(next(gerador))
    for bateria in range(10):
        f.registrar_contato(0, bateria=bateria)
    novo = ler_estado(next(gerador))
    assert novo["0"]["bateria"] == 9
    assert novo["0"]["versao"] >= primeiro["0"]["versao"] + 10
    f.fechar()
    assert list(gerador) == []


def test_stream_recebe_rota_status_e_contato_com_gps_descartado(app, client):
    resposta = client.get("/api/stream", buffered=False)
    try:
        next(resposta.response)
        client.post("/api/add", json={"id": 0, "nome": "Cliente", "lat": -26.5, "lon": -49.1})
        assert ler_estado(next(resposta.response))["0"]["rota"][0]["nome"] == "Cliente"
        client.post("/api/start", json={"id": 0, "nota": "N1"})
        assert ler_estado(next(resposta.response))["0"]["status"] == "EM_ROTA"
        client.post("/api/gps/owntracks", json={"_type": "location", "tid": "0", "lat": -26.5,
                                               "lon": -49.1, "acc": 900, "batt": 7})
        assert ler_estado(next(resposta.response))["0"]["bateria"] == 7
        assert client.get("/api/tracklog?id=0").json == []
    finally:
        resposta.close()


def test_online_expira_sem_novo_gps(app, client, monkeypatch):
    f = app.extensions["radar"]["frota"]
    f.registrar_contato(0, agora=1000)
    monkeypatch.setattr("radar_tracker.alertas.time.time", lambda: 1001)
    online = client.get("/api/estado").json["0"]
    assert online["online"] is True
    monkeypatch.setattr("radar_tracker.alertas.time.time", lambda: 1180)
    offline = client.get("/api/estado").json["0"]
    assert offline["online"] is False
    assert offline["versao"] > online["versao"]


def test_stream_atualiza_online_e_versao_sem_nova_mensagem(app, monkeypatch):
    f = app.extensions["radar"]["frota"]
    cfg = app.extensions["radar"]["config"]
    f.registrar_contato(0, agora=1000)
    monkeypatch.setattr("radar_tracker.alertas.time.time", lambda: 1001)
    def avaliar(snapshot):
        return alertas.avaliar_frota(snapshot, [], f.base, cfg)
    gerador = eventos(f, avaliar, lambda: None, ping_s=0.001, intervalo_s=0)
    try:
        primeiro = ler_estado(next(gerador))["0"]
        monkeypatch.setattr("radar_tracker.alertas.time.time", lambda: 1180)
        offline = ler_estado(next(gerador))["0"]
        assert primeiro["online"] is True and offline["online"] is False
        assert offline["versao"] > primeiro["versao"]
    finally:
        gerador.close()
