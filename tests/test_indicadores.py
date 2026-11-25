"""Indicadores por motoboy (#37) e aba de indicadores no Excel (#39)."""
import io
from datetime import datetime

import pytest
from openpyxl import load_workbook

from radar_tracker import geo

DIA = datetime(2026, 11, 20, 8, 0)
T0 = int(DIA.timestamp())


def viagem(banco, moto_id, nome, inicio_min, duracao_min, destinos, nota="1"):
    ini = T0 + inicio_min * 60
    fim = ini + duracao_min * 60
    banco.registrar_viagem(moto_id, nome, datetime.fromtimestamp(ini).strftime("%H:%M"),
                           datetime.fromtimestamp(fim).strftime("%H:%M"), destinos, nota,
                           inicio_ts=ini, fim_ts=fim)
    return ini, fim


@pytest.fixture
def banco(app):
    return app.extensions["radar"]["banco"]


@pytest.fixture
def cenario(banco):
    """Ana: 2 viagens (30 e 50 min), só a primeira com trilha. Bruno: 1 viagem sem trilha."""
    ini, fim = viagem(banco, 0, "Ana Teste", 0, 30, "Oficina A, Oficina B")
    pontos = [(-26.50, -49.10), (-26.51, -49.10), (-26.52, -49.10)]
    for i, (lat, lon) in enumerate(pontos):
        banco.registrar_posicao(0, lat, lon, 30, ini + 60 + i * 300)
    banco.registrar_posicao(0, -27.0, -49.10, 30, fim + 600)  # depois da chegada: não conta
    viagem(banco, 0, "Ana Teste", 60, 50, "Oficina C")
    viagem(banco, 1, "Bruno Teste", 10, 20, "Oficina D, Oficina E, Oficina F")
    esperado_km = sum(geo.haversine(*a, *b) for a, b in zip(pontos, pontos[1:]))
    return esperado_km


def test_indicadores_por_motoboy(banco, cenario):
    r = banco.indicadores()
    ana, bruno = r["motoboys"]
    assert ana["motoboy"] == "Ana Teste" and bruno["motoboy"] == "Bruno Teste"
    assert (ana["viagens"], ana["destinos"], ana["destinos_por_viagem"]) == (2, 3, 1.5)
    assert ana["tempo_medio_min"] == 40 and ana["tempo_total_min"] == 80
    assert ana["viagens_com_km"] == 1
    assert ana["km"] == pytest.approx(cenario, abs=0.01)
    assert ana["km_por_viagem"] == pytest.approx(cenario, abs=0.01)
    assert bruno["km"] is None and bruno["km_por_viagem"] is None and bruno["viagens_com_km"] == 0
    total = r["total"]
    assert (total["viagens"], total["destinos"], total["tempo_total_min"]) == (3, 6, 100)
    assert total["tempo_medio_min"] == pytest.approx(33.3, abs=0.05)
    assert total["km"] == pytest.approx(cenario, abs=0.01)


def test_indicadores_respeitam_o_periodo(banco, cenario):
    assert banco.indicadores("2026-11-21", "2026-11-30") == {
        "motoboys": [],
        "total": {"motoboy": "Total", "viagens": 0, "destinos": 0, "km": None, "viagens_com_km": 0,
                  "tempo_total_min": 0, "tempo_medio_min": None, "destinos_por_viagem": None, "km_por_viagem": None},
    }
    assert banco.indicadores("2026-11-20", "2026-11-20")["total"]["viagens"] == 3


def test_viagem_antiga_sem_moto_id_entra_sem_km(banco):
    with banco.conexao() as conn:
        conn.execute("INSERT INTO historico (motoboy, data_viagem, data_iso, hora_saida, hora_chegada, destinos, "
                     "numero_nota) VALUES ('Carlos', '23/01/2026', '2026-01-23', '09:00', '09:40', 'X, Y', '10')")
    banco.inicializar()  # migração preenche início, fim e duração dos registros antigos
    g = banco.indicadores()["motoboys"][0]
    assert (g["motoboy"], g["viagens"], g["destinos"], g["km"]) == ("Carlos", 1, 2, None)
    assert g["tempo_medio_min"] == 40


def test_api_indicadores(client, cenario):
    r = client.get("/api/indicadores?inicio=2026-11-20&fim=2026-11-20")
    assert r.status_code == 200
    dados = r.get_json()
    assert [g["motoboy"] for g in dados["motoboys"]] == ["Ana Teste", "Bruno Teste"]
    assert dados["total"]["viagens"] == 3


def test_api_indicadores_exige_login(anonimo):
    assert anonimo.get("/api/indicadores").status_code == 401


def test_excel_tem_aba_de_indicadores(client, cenario):
    r = client.get("/baixar_excel?inicio=2026-11-20&fim=2026-11-20")
    wb = load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames == ["Histórico", "Indicadores"]
    ws = wb["Indicadores"]
    assert "2026-11-20 a 2026-11-20" in ws["A1"].value
    assert ws["A3"].value == "Motoboy" and ws["G3"].value == "Km rodados (GPS)"
    linhas = {ws.cell(r, 1).value: [c.value for c in ws[r]] for r in range(4, 7)}
    assert linhas["Ana Teste"][1:3] == [2, 3]
    assert linhas["Ana Teste"][6] == pytest.approx(cenario, abs=0.01)
    assert linhas["Bruno Teste"][6] == "—"
    assert linhas["Total"][1] == 3
    assert wb["Histórico"].max_row == 4  # cabeçalho + 3 viagens


def test_excel_nao_interpreta_nome_como_formula(client, banco):
    viagem(banco, 0, "=1+1", 0, 10, "A")
    ws = load_workbook(io.BytesIO(client.get("/baixar_excel").data))["Indicadores"]
    assert ws["A4"].value == "'=1+1"
