"""Configuração do sistema, lida de variáveis de ambiente (arquivo .env opcional)."""

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv é opcional em tempo de execução
    load_dotenv = None

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

if load_dotenv:
    load_dotenv(RAIZ_PROJETO / ".env")


def _env(nome, padrao):
    return os.environ.get(nome, padrao)


def _env_float(nome, padrao):
    return float(os.environ.get(nome, padrao))


def carregar_motoboys(caminho=None):
    """Lê a lista de motoboys de config/motoboys.json (ou do arquivo de exemplo).

    Cada item: {"id": 0, "nome": "...", "cor": "#rrggbb", "tid": "0"}.
    O campo "tid" é o Tracker ID configurado no app OwnTracks do motoboy;
    se omitido, assume-se o próprio id como texto.
    """
    pasta = RAIZ_PROJETO / "config"
    candidatos = [Path(caminho)] if caminho else [pasta / "motoboys.json", pasta / "motoboys.example.json"]
    for arquivo in candidatos:
        if arquivo.exists():
            with open(arquivo, encoding="utf-8") as f:
                motoboys = json.load(f)
            for m in motoboys:
                m["id"] = int(m["id"])
                m.setdefault("tid", str(m["id"]))
                m.setdefault("cor", "#34495e")
            return motoboys
    raise FileNotFoundError("Nenhum arquivo de motoboys encontrado em config/.")


class Config:
    NOME_EMPRESA = _env("NOME_EMPRESA", "Radar Auto Peças")

    # Coordenadas da loja (ponto de saída e retorno das rotas)
    BASE_LAT = _env_float("BASE_LAT", "-26.508484936938192")
    BASE_LON = _env_float("BASE_LON", "-49.10542231274289")

    # Cidade anexada às buscas de endereço no Nominatim
    CIDADE_BUSCA = _env("CIDADE_BUSCA", "Jaraguá do Sul, SC")

    # Roteirização
    OSRM_URL = _env("OSRM_URL", "https://router.project-osrm.org")
    NOMINATIM_URL = _env("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
    # Multiplicador sobre o tempo do OSRM (trânsito urbano, paradas, estacionamento)
    FATOR_ATRASO = _env_float("FATOR_ATRASO", "1.6")
    # Parâmetros do modo offline (sem OSRM)
    VELOCIDADE_MEDIA_OFFLINE_KMH = _env_float("VELOCIDADE_MEDIA_OFFLINE_KMH", "25")
    MINUTOS_POR_PARADA = _env_float("MINUTOS_POR_PARADA", "5")

    # Rastreamento GPS
    # Vazio = endpoint aberto só na rede da loja; pela internet (túnel) o token é obrigatório
    OWNTRACKS_TOKEN = _env("OWNTRACKS_TOKEN", "")
    # Domínio do túnel ngrok: requisições com esse Host contam como vindas da internet
    NGROK_DOMAIN = _env("NGROK_DOMAIN", "")
    GPS_PRECISAO_MAX_M = _env_float("GPS_PRECISAO_MAX_M", "100")
    GPS_VELOCIDADE_MAX_KMH = _env_float("GPS_VELOCIDADE_MAX_KMH", "150")
    GPS_VELOCIDADE_ALPHA = _env_float("GPS_VELOCIDADE_ALPHA", "0.35")
    SESSAO_INTERVALO_S = _env_float("SESSAO_INTERVALO_S", "5")
    TRACKLOG_DIAS = int(_env("TRACKLOG_DIAS", "90"))

    # Alertas de status (painel)
    ALERTA_SEM_SINAL_MIN = _env_float("ALERTA_SEM_SINAL_MIN", "3")  # minutos sem mensagem durante a entrega
    ALERTA_PARADO_MIN = _env_float("ALERTA_PARADO_MIN", "10")  # minutos parado fora de cliente
    ALERTA_RAIO_PARADO_M = _env_float("ALERTA_RAIO_PARADO_M", "50")  # deslocamento que conta como "andou"
    ALERTA_RAIO_CLIENTE_M = _env_float("ALERTA_RAIO_CLIENTE_M", "100")  # distância que conta como "no cliente"
    ALERTA_BATERIA_MIN = _env_float("ALERTA_BATERIA_MIN", "20")  # % de bateria do celular

    # Persistência
    PASTA_DADOS = Path(_env("PASTA_DADOS", str(RAIZ_PROJETO / "data")))
    DB_PATH = Path(_env("DB_PATH", str(PASTA_DADOS / "radar.db")))
    ARQUIVO_SESSAO = Path(_env("ARQUIVO_SESSAO", str(PASTA_DADOS / "sessao.json")))

    # Servidor
    HOST = _env("HOST", "0.0.0.0")
    PORT = int(_env("PORT", "5000"))
    THREADS = int(_env("THREADS", "24"))
    STREAM_MAX = int(_env("STREAM_MAX", "10"))
