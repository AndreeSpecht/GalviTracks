"""Sistema de rastreamento em tempo real de motoboys — Galvitech Ltda."""

import atexit
import logging

from flask import Flask

from .config import Config, carregar_motoboys
from .db import Banco
from .frota import Frota
from .stream import Streams

__version__ = "0.8.0"


def create_app(config=None, motoboys=None):
    """Cria a aplicação Flask. `config` pode ser uma classe/objeto que sobrescreve `Config`."""
    cfg = config or Config
    if cfg.THREADS < 5 or not 1 <= cfg.STREAM_MAX <= cfg.THREADS - 4:
        raise ValueError("THREADS deve reservar ao menos 4 threads além de STREAM_MAX (mínimo 1).")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    banco = Banco(cfg.DB_PATH)
    banco.inicializar()

    frota = Frota(
        motoboys or carregar_motoboys(),
        cfg.BASE_LAT,
        cfg.BASE_LON,
        cfg.ARQUIVO_SESSAO,
        precisao_max_m=cfg.GPS_PRECISAO_MAX_M,
        velocidade_max_kmh=cfg.GPS_VELOCIDADE_MAX_KMH,
        raio_parado_m=cfg.ALERTA_RAIO_PARADO_M,
        intervalo_salvar=cfg.SESSAO_INTERVALO_S,
        velocidade_alpha=cfg.GPS_VELOCIDADE_ALPHA,
    )
    frota.carregar()

    app = Flask(__name__)
    app.json.ensure_ascii = False
    banco.iniciar_retencao(cfg.TRACKLOG_DIAS)

    def fechar():
        frota.fechar()
        banco.fechar()
        atexit.unregister(fechar)

    atexit.register(fechar)
    app.extensions["radar"] = {"config": cfg, "banco": banco, "frota": frota,
                               "streams": Streams(cfg.STREAM_MAX), "fechar": fechar}

    from .api import bp

    app.register_blueprint(bp)
    return app
