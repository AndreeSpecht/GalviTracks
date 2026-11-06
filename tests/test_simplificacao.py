import pytest
from datetime import datetime

from radar_tracker.geo import simplificar_trilha


@pytest.mark.parametrize("pontos", [[], [{"lat": 0, "lon": 0}], [{"lat": 0, "lon": 0}]*2])
def test_trilhas_curtas_preservadas(pontos):
    assert simplificar_trilha(pontos) == pontos


def test_douglas_peucker_preserva_extremos_curvas_e_metadados():
    pontos = [{"lat": 0, "lon": i * 0.001, "timestamp": i, "curso": 90} for i in range(100)]
    assert simplificar_trilha(pontos) == [pontos[0], pontos[-1]]
    pontos[50]["lat"] = 0.001
    reduzida = simplificar_trilha(pontos)
    assert pontos[50] in reduzida
    assert reduzida[0] == pontos[0] and reduzida[-1] == pontos[-1]


def test_trilha_simplificada_pela_api_preserva_curso(app, client):
    b = app.extensions["radar"]["banco"]
    ts = int(datetime(2026, 5, 1, 12).timestamp())
    for i in range(5):
        b.registrar_posicao(0, -26.5, -49.1 + i * 0.001, 30, ts+i, curso=90)
    dia = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    normal = client.get(f"/api/tracklog?id=0&data={dia}").json
    reduzida = client.get(f"/api/tracklog?id=0&data={dia}&simplificar=1").json
    assert len(normal) == 5
    assert reduzida == [normal[0], normal[-1]]
    assert reduzida[0]["curso"] == 90
