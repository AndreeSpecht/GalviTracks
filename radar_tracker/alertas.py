"""Alertas de status dos motoboys: sem sinal, parado fora de cliente e bateria baixa.

Funções puras: recebem o estado da frota (snapshot), os pontos conhecidos
(clientes, paradas e loja) e o horário atual, e devolvem a lista de alertas.
"""

import time

from . import geo

SEM_SINAL = "sem_sinal"
PARADO = "parado"
BATERIA = "bateria_baixa"

# Ordem de gravidade (menor = mais grave), usada para ordenar e colorir no painel
NIVEIS = {SEM_SINAL: ("critico", 0), PARADO: ("alerta", 1), BATERIA: ("aviso", 2)}


def _minutos(segundos):
    return int(segundos // 60)


def _duracao(segundos):
    minutos = _minutos(segundos)
    return f"{minutos} min" if minutos >= 1 else "menos de 1 min"


def _perto_de_algum(lat, lon, pontos, raio_m):
    return any(geo.haversine(lat, lon, p["lat"], p["lon"]) * 1000 <= raio_m for p in pontos)


def alertas_do_motoboy(dados, pontos_conhecidos, cfg, agora=None):
    """Alertas ativos de um motoboy. `dados` é um item do snapshot da frota."""
    agora = int(agora or time.time())
    alertas = []
    em_rota = dados.get("status") == "EM_ROTA"

    # 1) Sem sinal: só faz sentido durante a entrega (na loja o celular pode ficar ocioso)
    if em_rota:
        referencia = max(dados.get("recebido_em") or 0, dados.get("inicio_ts") or 0)
        sem_contato = agora - referencia
        if referencia and sem_contato >= cfg.ALERTA_SEM_SINAL_MIN * 60:
            if dados.get("recebido_em"):
                msg = f"Sem sinal há {_duracao(sem_contato)}"
            else:
                msg = f"Nenhuma posição recebida desde a saída ({_duracao(sem_contato)})"
            alertas.append({"tipo": SEM_SINAL, "mensagem": msg, "minutos": _minutos(sem_contato)})

    # 2) Parado por muito tempo longe de clientes, paradas da rota e da loja.
    #    Sem sinal, a última posição fica "congelada"; nesse caso só vale o alerta de sinal.
    parado_desde = dados.get("parado_desde") or 0
    if em_rota and parado_desde and not alertas:
        parado = agora - parado_desde
        if parado >= cfg.ALERTA_PARADO_MIN * 60 and not _perto_de_algum(
            dados["lat_atual"], dados["lon_atual"], pontos_conhecidos, cfg.ALERTA_RAIO_CLIENTE_M
        ):
            alertas.append({"tipo": PARADO, "mensagem": f"Parado há {_duracao(parado)} fora de um cliente",
                            "minutos": _minutos(parado)})

    # 3) Bateria baixa do celular (ignorada enquanto estiver carregando)
    bateria = dados.get("bateria")
    if bateria is not None and bateria < cfg.ALERTA_BATERIA_MIN and not dados.get("carregando"):
        alertas.append({"tipo": BATERIA, "mensagem": f"Bateria do celular em {bateria}%", "bateria": bateria})

    for a in alertas:
        a["nivel"] = NIVEIS[a["tipo"]][0]
    return sorted(alertas, key=lambda a: NIVEIS[a["tipo"]][1])


def avaliar_frota(snapshot, clientes, base, cfg, agora=None):
    """Acrescenta a chave 'alertas' em cada motoboy do snapshot e o devolve."""
    pontos_fixos = [base, *({"lat": c["lat"], "lon": c["lon"]} for c in clientes)]
    for dados in snapshot.values():
        recebido = dados.get("recebido_em") or 0
        dados["online"] = bool(recebido and 0 <= (int(time.time() if agora is None else agora) - recebido)
                               < cfg.ALERTA_SEM_SINAL_MIN * 60)
        dados["alertas"] = alertas_do_motoboy(dados, pontos_fixos + list(dados.get("rota", [])), cfg, agora)
    return snapshot
