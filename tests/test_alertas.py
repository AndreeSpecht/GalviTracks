import time

import pytest

from radar_tracker import alertas
from radar_tracker.config import Config
from radar_tracker.frota import Frota

from .conftest import MOTOBOYS

BASE = {"lat": -26.5085, "lon": -49.1054}
LONGE = (-26.4700, -49.0700)  # ~5 km da loja, sem cliente por perto
AGORA = 1_000_000


def em_rota(**extra):
    dados = {
        "status": "EM_ROTA", "rota": [], "lat_atual": LONGE[0], "lon_atual": LONGE[1],
        "inicio_ts": AGORA - 30 * 60, "recebido_em": AGORA - 10, "parado_desde": AGORA - 60,
        "bateria": 80, "carregando": False,
    }
    dados.update(extra)
    return dados


def tipos(dados, pontos=(BASE,)):
    return [a["tipo"] for a in alertas.alertas_do_motoboy(dados, list(pontos), Config, AGORA)]


def test_sem_alertas_em_situacao_normal():
    assert tipos(em_rota()) == []


def test_sem_sinal_durante_a_entrega():
    a = alertas.alertas_do_motoboy(em_rota(recebido_em=AGORA - 5 * 60), [BASE], Config, AGORA)
    assert [x["tipo"] for x in a] == ["sem_sinal"]
    assert a[0]["nivel"] == "critico" and "5 min" in a[0]["mensagem"]


def test_sem_sinal_quando_nunca_enviou_desde_a_saida():
    a = alertas.alertas_do_motoboy(em_rota(recebido_em=0, inicio_ts=AGORA - 4 * 60), [BASE], Config, AGORA)
    assert a[0]["tipo"] == "sem_sinal" and "desde a saída" in a[0]["mensagem"]


def test_sem_sinal_ignorado_quando_livre_na_loja():
    assert tipos(em_rota(status="LIVRE", recebido_em=AGORA - 60 * 60)) == []


def test_parado_fora_de_cliente():
    assert tipos(em_rota(parado_desde=AGORA - 15 * 60)) == ["parado"]


def test_parado_no_cliente_nao_alerta():
    cliente = {"lat": LONGE[0] + 0.0003, "lon": LONGE[1]}  # ~33 m
    assert tipos(em_rota(parado_desde=AGORA - 15 * 60), pontos=[BASE, cliente]) == []


def test_bateria_baixa_e_carregando():
    assert tipos(em_rota(bateria=12)) == ["bateria_baixa"]
    assert tipos(em_rota(bateria=12, carregando=True)) == []
    assert tipos(em_rota(status="LIVRE", bateria=5)) == ["bateria_baixa"]  # vale também fora da entrega


def test_ordem_por_gravidade_e_sem_sinal_suprime_parado():
    dados = em_rota(recebido_em=AGORA - 10 * 60, parado_desde=AGORA - 20 * 60, bateria=5)
    assert tipos(dados) == ["sem_sinal", "bateria_baixa"]  # posição congelada não conta como "parado"
    assert tipos(em_rota(parado_desde=AGORA - 20 * 60, bateria=5)) == ["parado", "bateria_baixa"]


def test_duracao_curta_em_texto():
    a = alertas.alertas_do_motoboy(em_rota(recebido_em=AGORA - 200), [BASE], Config, AGORA)
    assert a[0]["mensagem"] == "Sem sinal há 3 min"
    assert alertas._duracao(30) == "menos de 1 min"


def test_frota_conta_tempo_parado_e_reinicia_ao_andar(tmp_path, monkeypatch):
    f = Frota([dict(m) for m in MOTOBOYS], *BASE.values(), tmp_path / "s.json", raio_parado_m=50)
    monkeypatch.setattr("radar_tracker.frota.time.time", lambda: 1000)
    f.atualizar_posicao(0, -26.50, -49.10, ts=1000)
    monkeypatch.setattr("radar_tracker.frota.time.time", lambda: 1300)
    f.atualizar_posicao(0, -26.50001, -49.10, ts=1300)  # ~1 m: continua parado
    assert f.estado[0]["parado_desde"] == 1000
    monkeypatch.setattr("radar_tracker.frota.time.time", lambda: 1330)
    f.atualizar_posicao(0, -26.501, -49.10, ts=1330)  # ~110 m: andou
    assert f.estado[0]["parado_desde"] == 1330


def test_registrar_contato_guarda_bateria(tmp_path):
    f = Frota([dict(m) for m in MOTOBOYS], *BASE.values(), tmp_path / "s.json")
    f.registrar_contato(0, bateria=150, carregando=True, agora=123)
    assert (f.estado[0]["bateria"], f.estado[0]["carregando"], f.estado[0]["recebido_em"]) == (100, True, 123)


@pytest.fixture
def em_entrega(client):
    client.post("/api/add", json={"id": 0, "nome": "Cliente", "lat": -26.49, "lon": -49.08})
    client.post("/api/start", json={"id": 0, "nota": "NF-1"})
    return client


def test_api_bateria_vinda_do_owntracks(em_entrega):
    em_entrega.post("/api/gps/owntracks", json={"_type": "location", "tid": "0", "lat": -26.5085,
                                                "lon": -49.1054, "tst": int(time.time()), "batt": 9, "bs": 1})
    estado = em_entrega.get("/api/estado").json["0"]
    assert estado["bateria"] == 9
    assert [a["tipo"] for a in estado["alertas"]] == ["bateria_baixa"]
    lista = em_entrega.get("/api/alertas").json
    assert lista[0]["motoboy"] == "Ana Teste" and lista[0]["moto_id"] == 0


def test_api_sem_sinal_apos_saida(app, em_entrega):
    frota = app.extensions["radar"]["frota"]
    frota.estado[0]["inicio_ts"] = int(time.time()) - 10 * 60  # saiu há 10 min e nunca enviou posição
    tipos_api = [a["tipo"] for a in em_entrega.get("/api/estado").json["0"]["alertas"]]
    assert "sem_sinal" in tipos_api


def test_api_alertas_vazio_sem_problemas(client):
    assert client.get("/api/alertas").json == []
