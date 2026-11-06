"""Funções geográficas puras: distância, velocidade e ordenação de paradas."""

import math

RAIO_TERRA_KM = 6371.0


def haversine(lat1, lon1, lat2, lon2):
    """Distância em km entre dois pontos (fórmula de Haversine)."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    a = max(0.0, min(1.0, a))
    return RAIO_TERRA_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def velocidade_kmh(lat1, lon1, ts1, lat2, lon2, ts2):
    """Velocidade média entre duas leituras. Retorna None se não for calculável."""
    if not ts1 or ts2 <= ts1:
        return None
    horas = (ts2 - ts1) / 3600
    return haversine(lat1, lon1, lat2, lon2) / horas


def vizinho_mais_proximo(origem, paradas):
    """Ordena as paradas pela heurística do vizinho mais próximo.

    origem: dict com 'lat' e 'lon'. paradas: lista de dicts com 'lat' e 'lon'.
    Retorna uma nova lista; a original não é alterada.
    """
    restantes = list(paradas)
    atual = origem
    ordenadas = []
    while restantes:
        proxima = min(restantes, key=lambda p: haversine(atual["lat"], atual["lon"], p["lat"], p["lon"]))
        ordenadas.append(proxima)
        restantes.remove(proxima)
        atual = proxima
    return ordenadas


def distancia_circuito_km(origem, paradas):
    """Distância em linha reta de origem → paradas → origem."""
    total = 0.0
    atual = origem
    for p in paradas:
        total += haversine(atual["lat"], atual["lon"], p["lat"], p["lon"])
        atual = p
    return total + haversine(atual["lat"], atual["lon"], origem["lat"], origem["lon"])


def rumo(lat1, lon1, lat2, lon2):
    """Rumo inicial em graus: norte=0, leste=90 (intervalo [0, 360))."""
    a, b = math.radians(lat1), math.radians(lat2)
    delta = math.radians(lon2 - lon1)
    return math.degrees(math.atan2(math.sin(delta) * math.cos(b),
                                  math.cos(a) * math.sin(b) - math.sin(a) * math.cos(b) * math.cos(delta))) % 360


def simplificar_trilha(pontos, tolerancia_m=5):
    """Douglas-Peucker iterativo, preservando registros completos e extremos.

    Projeção local equiretangular em metros, apropriada para trilhas urbanas.
    A pilha explícita evita exceder a recursão em trilhas longas.
    """
    if len(pontos) <= 2:
        return list(pontos)
    lat_ref = math.radians(pontos[0]["lat"])
    escala = RAIO_TERRA_KM * 1000 * math.pi / 180
    xy = [(p["lon"] * escala * math.cos(lat_ref), p["lat"] * escala) for p in pontos]
    manter = {0, len(pontos) - 1}
    pilha = [(0, len(pontos) - 1)]
    while pilha:
        inicio, fim = pilha.pop()
        ax, ay = xy[inicio]
        bx, by = xy[fim]
        dx, dy = bx - ax, by - ay
        comprimento2 = dx * dx + dy * dy
        maior, indice = tolerancia_m ** 2, None
        for i in range(inicio + 1, fim):
            px, py = xy[i]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / comprimento2)) if comprimento2 else 0
            dist2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if dist2 > maior:
                maior, indice = dist2, i
        if indice is not None:
            manter.add(indice)
            pilha.extend(((inicio, indice), (indice, fim)))
    return [pontos[i] for i in sorted(manter)]
