"""Cópia de segurança do banco: data/backup/radar_AAAA-MM-DD.db, mantendo os últimos N dias.

Usa a API de backup do SQLite, que copia o banco de forma consistente mesmo com o
servidor gravando ao mesmo tempo.

Uso:
    python scripts/backup_banco.py                 # uma cópia agora
    python scripts/backup_banco.py --loop          # uma cópia por dia, às 3h (serviço "backup" do compose.yml)
    python scripts/backup_banco.py --manter 30
"""

import argparse
import logging
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar_tracker.config import Config  # noqa: E402

log = logging.getLogger("backup")
HORA = 3


def copiar(db, pasta, manter, hoje=None):
    """Grava a cópia do dia (substitui a de hoje, se já existir) e apaga as mais antigas."""
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"radar_{(hoje or date.today()):%Y-%m-%d}.db"
    temporario = destino.with_name(destino.name + ".tmp")
    origem = sqlite3.connect(db)
    copia = sqlite3.connect(temporario)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    temporario.replace(destino)
    for antigo in sorted(pasta.glob("radar_*.db"))[:-manter]:
        antigo.unlink()
    log.info("Backup gravado em %s (%d KB).", destino, destino.stat().st_size // 1024)
    return destino


def segundos_ate_proxima(agora=None):
    agora = agora or datetime.now()
    proxima = agora.replace(hour=HORA, minute=0, second=0, microsecond=0)
    if proxima <= agora:
        proxima += timedelta(days=1)
    return (proxima - agora).total_seconds()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--loop", action="store_true", help=f"fica rodando e copia todo dia às {HORA}h")
    parser.add_argument("--manter", type=int, default=14, help="quantas cópias diárias guardar (padrão 14)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db, pasta = Config.DB_PATH, Config.PASTA_DADOS / "backup"
    if not args.loop:
        copiar(db, pasta, args.manter)
        return
    while True:
        try:
            if db.exists() and not (pasta / f"radar_{date.today():%Y-%m-%d}.db").exists():
                copiar(db, pasta, args.manter)
        except Exception:  # noqa: BLE001 - o serviço não pode morrer; tenta de novo no próximo ciclo
            log.exception("Falha no backup; nova tentativa no próximo ciclo.")
        time.sleep(min(segundos_ate_proxima(), 3600))


if __name__ == "__main__":
    main()
