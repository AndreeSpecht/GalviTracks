import io
import json
import sqlite3
import threading
import time
from datetime import datetime
from unittest.mock import patch

import pytest
from openpyxl import load_workbook

from radar_tracker.db import Banco
from radar_tracker.frota import Frota
from .conftest import MOTOBOYS


def frota(tmp_path, **kwargs):
    return Frota([dict(m) for m in MOTOBOYS], -26.5, -49.1, tmp_path / "s.json", **kwargs)


def test_gps_nao_grava_por_posicao_e_flush_no_encerramento(tmp_path):
    f = frota(tmp_path, intervalo_salvar=60)
    with patch("radar_tracker.frota.os.replace", wraps=__import__("os").replace) as replace:
        for i in range(20):
            f.atualizar_posicao(0, -26.5, -49.1, ts=1000+i)
        assert replace.call_count == 0
        f.fechar()
        assert replace.call_count == 1
    assert json.loads((tmp_path / "s.json").read_text())["0"]["last_ts"] == 1019


def test_debounce_worker_grava_e_rota_grava_imediatamente(tmp_path):
    f = frota(tmp_path, intervalo_salvar=0.05)
    gravou = threading.Event()
    original = __import__("os").replace

    def substituir(a, b):
        original(a, b)
        gravou.set()

    with patch("radar_tracker.frota.os.replace", side_effect=substituir):
        f.atualizar_posicao(0, -26.5, -49.1, ts=1000)
        assert gravou.wait(2)
        f.adicionar_parada(0, "Cliente", -26.49, -49.1)
    assert json.loads((tmp_path / "s.json").read_text())["0"]["rota"]


def test_gravacao_bloqueada_e_retentativa(tmp_path, monkeypatch, caplog):
    f = frota(tmp_path, intervalo_salvar=60)
    f.atualizar_posicao(0, -26.5, -49.1, ts=1000)
    original = __import__("os").replace
    monkeypatch.setattr("radar_tracker.frota.time.sleep", lambda _: None)
    with patch("radar_tracker.frota.os.replace", side_effect=[PermissionError(), PermissionError(), None]) as trocar:
        assert f.salvar()
        assert trocar.call_count == 3
    f.atualizar_posicao(0, -26.5, -49.1, ts=1001)
    with patch("radar_tracker.frota.os.replace", side_effect=PermissionError()):
        assert not f.salvar()
    assert "mantida em memória" in caplog.text
    with patch("radar_tracker.frota.os.replace", side_effect=original):
        assert f.salvar()
    assert json.loads((tmp_path / "s.json").read_text())["0"]["last_ts"] == 1001


@pytest.mark.parametrize("tst", ["abc", "NaN", float("inf"), None, -10, 10**100])
def test_timestamp_invalido_nao_causa_500(client, tst):
    antes = int(time.time())
    r = client.post("/api/gps/owntracks", json={"_type": "location", "tid": "0", "lat": -26.5,
                                               "lon": -49.1, "tst": tst})
    assert r.status_code == 200
    estado = client.get("/api/estado").json["0"]
    assert antes <= estado["last_ts"] <= int(time.time())
    assert estado["ts_posicao"] >= antes
    assert client.get("/api/tracklog?id=0").json[0]["timestamp"] == estado["last_ts"]


def test_timestamp_futuro_nao_bloqueia_proximas_leituras(client):
    agora = int(time.time())
    msg = {"_type": "location", "tid": "0", "lat": -26.5, "lon": -49.1, "tst": agora + 3600}
    client.post("/api/gps/owntracks", json=msg)
    assert client.get("/api/estado").json["0"]["last_ts"] <= int(time.time())
    client.post("/api/gps/owntracks", json={**msg, "tst": agora})
    assert len(client.get("/api/tracklog?id=0").json) == 2


def test_sessao_futura_e_sessao_antiga(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps({"0": {"last_ts": int(time.time()) + 3600}}))
    f = frota(tmp_path)
    f.carregar()
    assert f.snapshot()["0"]["last_ts"] == 0
    assert f.snapshot()["0"]["curso"] is None
    assert f.atualizar_posicao(0, -26.5, -49.1) == 0


@pytest.mark.parametrize("corpo", [[1], {"_type": "location", "tid": "0", "lat": 999, "lon": 0},
                                      {"_type": "location", "tid": "0", "lat": "NaN", "lon": 0}])
def test_gps_malformado_ignorado(client, corpo):
    assert client.post("/api/gps/owntracks", json=corpo).status_code == 200
    assert client.get("/api/tracklog?id=0").json == []


@pytest.mark.parametrize("lat", ["NaN", "Infinity", 999])
def test_coordenada_invalida_nao_corrompe_sessao(client, lat):
    assert client.post("/api/add", json={"id": 0, "nome": "Cliente", "lat": lat, "lon": -49.1}).status_code == 400
    assert client.get("/api/estado").json["0"]["rota"] == []


def test_curso_precisao_ema_e_velocidade_bruta(tmp_path):
    f = frota(tmp_path)
    assert f.atualizar_posicao(0, -26.5, -49.1, ts=1000, vel_dispositivo=40) == 40
    assert f.atualizar_posicao(0, -26.4998, -49.1, ts=1010, precisao_m=7, vel_dispositivo=60) == 60
    m = f.snapshot()["0"]
    assert m["curso"] == pytest.approx(0)
    assert m["precisao"] == 7
    assert m["velocidade"] == pytest.approx(47)
    f.atualizar_posicao(0, -26.4998, -49.1, ts=1020, curso=270)
    assert f.snapshot()["0"]["curso"] == 270
    assert f.atualizar_posicao(0, 0, 0, ts=1020) is None


def test_alertas_usam_relogio_servidor(tmp_path, monkeypatch):
    f = frota(tmp_path)
    monkeypatch.setattr("radar_tracker.frota.time.time", lambda: 10000)
    f.atualizar_posicao(0, -26.5, -49.1, ts=1000)
    assert f.snapshot()["0"]["parado_desde"] == 10000
    monkeypatch.setattr("radar_tracker.frota.time.time", lambda: 10030)
    f.atualizar_posicao(0, -26.499, -49.1, ts=1030)
    m = f.snapshot()["0"]
    assert m["parado_desde"] == m["ts_posicao"] == 10030


def test_tracklog_id_inexistente(client):
    assert client.get("/api/tracklog?id=999").status_code == 404
    assert client.get("/api/tracklog?id=abc").status_code == 400


def test_resumo_soma_distancias_por_motoboy_e_so_do_dia(app, client):
    b = app.extensions["radar"]["banco"]
    agora = int(datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp())
    for mid in (0, 1):
        b.registrar_posicao(mid, -26.5, -49.1, 0, agora - 10)
        b.registrar_posicao(mid, -26.49, -49.1, 10, agora)
    b.registrar_posicao(0, 0, 0, 0, agora - 86400)
    client.post("/api/add", json={"id": 0, "nome": "Cliente", "lat": -26.5, "lon": -49.1})
    client.post("/api/start", json={"id": 0, "nota": "1"})
    assert client.get("/api/resumo").json["em_rota"] == 1
    client.post("/api/end", json={"id": 0})
    r = client.get("/api/resumo").json
    assert r == {"em_rota": 0, "livres": 2, "com_alerta": 0, "entregas_hoje": 1,
                 "km_hoje": pytest.approx(2.224, abs=0.002)}


@pytest.mark.parametrize("prefixo", ["=", "+", "-", "@"])
def test_excel_nao_exporta_formulas(app, client, prefixo):
    b = app.extensions["radar"]["banco"]
    texto = prefixo + "SUM(1,2)"
    b.registrar_viagem(0, texto, "10:00", "10:15", texto, texto)
    wb = load_workbook(io.BytesIO(client.get("/baixar_excel").data), data_only=False)
    for coluna in (2, 3, 4):
        c = wb.active.cell(2, coluna)
        assert c.value == "'" + texto
        assert c.data_type == "s"
    wb.close()


def test_migracao_historico_antigo_e_viagem_virando_dia(tmp_path):
    caminho = tmp_path / "antigo.db"
    with sqlite3.connect(caminho) as conn:
        conn.execute("CREATE TABLE historico (id INTEGER PRIMARY KEY, motoboy TEXT, data_viagem TEXT, "
                     "hora_saida TEXT, hora_chegada TEXT, destinos TEXT)")
        conn.execute("INSERT INTO historico VALUES (1, 'Ana', '01/01/2026', '23:50', '00:20', 'Cliente')")
    b = Banco(caminho)
    try:
        b.inicializar()
        b.inicializar()  # migração idempotente
        antigo = b.historico()[0]
        assert antigo["duracao_min"] == 30
        inicio = int(datetime(2026, 5, 1, 23, 50).timestamp())
        b.registrar_viagem(0, "Ana", "23:50", "00:20", "Cliente", "NF1", inicio_ts=inicio, fim_ts=inicio + 1800)
        novo = b.historico("2026-05-01", "2026-05-01")[0]
        assert novo["data_viagem"] == "01/05/2026"
        assert novo["duracao_min"] == 30
        assert novo["fim_ts"] - novo["inicio_ts"] == 1800
    finally:
        b.fechar()


def test_falha_db_ao_finalizar_preserva_rota(app, client, monkeypatch):
    client.post("/api/add", json={"id": 0, "nome": "Cliente", "lat": -26.5, "lon": -49.1})
    client.post("/api/start", json={"id": 0, "nota": "NF1"})
    with monkeypatch.context() as m:
        def falhar(**kwargs):
            raise sqlite3.OperationalError("falha simulada")
        m.setattr(app.extensions["radar"]["banco"], "registrar_viagem", falhar)
        assert client.post("/api/end", json={"id": 0}).status_code == 500
    assert client.get("/api/estado").json["0"]["status"] == "EM_ROTA"
    assert client.post("/api/end", json={"id": 0}).json["ok"] == 1
    assert len(client.get("/api/get_historico").json) == 1


def test_conexoes_por_thread_wal_cache_e_retencao(app):
    b = app.extensions["radar"]["banco"]
    with b.conexao() as primeira:
        assert primeira.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert primeira.execute("PRAGMA synchronous").fetchone()[0] == 1
    with b.conexao() as segunda:
        assert primeira is segunda
    vistas = []
    def consultar():
        with b.conexao() as outra:
            vistas.append(outra is primeira)
        b.fechar_thread()
    t = threading.Thread(target=consultar)
    t.start()
    t.join()
    assert vistas == [False]
    assert b.listar_clientes() == []
    cid = b.salvar_cliente("Nome", -26.5, -49.1)
    lista = b.listar_clientes()
    lista[0]["nome"] = "mutação externa"
    assert b.listar_clientes()[0]["nome"] == "Nome"
    b.atualizar_cliente(cid, "Novo", "123")
    assert b.listar_clientes()[0]["nome"] == "Novo"
    b.atualizar_cor_cliente(cid, "#ffffff")
    assert b.listar_clientes()[0]["cor"] == "#ffffff"
    b.apagar_cliente(cid)
    assert b.listar_clientes() == []
    b.registrar_posicao(0, 0, 0, 0, 1)
    b.registrar_posicao(0, 0, 0, 0, int(time.time()))
    assert b.limpar_trilha(90) == 1
