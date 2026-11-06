"""Cálculo de rota via OSRM, com estimativa offline quando o serviço não responde."""

import logging

import polyline
import requests

from . import geo

log = logging.getLogger(__name__)


def calcular_rota(paradas, base, config, sessao=requests):
    """Calcula o circuito loja → paradas → loja.

    Retorna {'pontos': [[lat, lon], ...], 'minutos': int, 'distancia_km': float, 'fonte': 'osrm'|'offline'}.
    """
    if not paradas:
        return {"pontos": [], "minutos": 0, "distancia_km": 0.0, "fonte": "vazio"}

    circuito = [base, *paradas, base]
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in circuito)
    url = f"{config.OSRM_URL.rstrip('/')}/route/v1/driving/{coords}"
    try:
        resp = sessao.get(url, params={"overview": "full"}, timeout=3)
        resp.raise_for_status()
        rota = resp.json()["routes"][0]
        return {
            "pontos": polyline.decode(rota["geometry"]),
            "minutos": int(rota["duration"] * config.FATOR_ATRASO / 60),
            "distancia_km": round(rota["distance"] / 1000, 2),
            "fonte": "osrm",
        }
    except (requests.RequestException, KeyError, IndexError, ValueError) as erro:
        log.warning("OSRM indisponível (%s); usando estimativa offline.", erro)

    km = geo.distancia_circuito_km(base, paradas)
    minutos = int(km / config.VELOCIDADE_MEDIA_OFFLINE_KMH * 60 + len(paradas) * config.MINUTOS_POR_PARADA)
    return {"pontos": [], "minutos": minutos, "distancia_km": round(km, 2), "fonte": "offline"}


def buscar_endereco(texto, config, sessao=requests):
    """Geocodifica um endereço na cidade configurada usando o Nominatim."""
    try:
        resp = sessao.get(
            f"{config.NOMINATIM_URL.rstrip('/')}/search",
            params={"q": f"{texto}, {config.CIDADE_BUSCA}", "format": "json", "limit": 1},
            headers={"User-Agent": "GalviTracks/0.8"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as erro:
        log.warning("Falha na busca de endereço: %s", erro)
        return []
