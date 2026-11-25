"""Backup diário do banco (scripts/backup_banco.py), usado no servidor na nuvem."""
import importlib.util
import sqlite3
from datetime import date, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "backup_banco", Path(__file__).resolve().parent.parent / "scripts" / "backup_banco.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_copia_consistente_com_o_banco_em_uso_e_rotacao(app, tmp_path):
    banco = app.extensions["radar"]["banco"]
    banco.registrar_viagem(0, "Ana Teste", "08:00", "08:30", "Oficina A", "123")
    db = app.extensions["radar"]["config"].DB_PATH
    pasta = tmp_path / "backup"
    for dia in range(1, 6):
        backup.copiar(db, pasta, manter=3, hoje=date(2026, 11, dia))
    copias = sorted(p.name for p in pasta.glob("radar_*.db"))
    assert copias == ["radar_2026-11-03.db", "radar_2026-11-04.db", "radar_2026-11-05.db"]
    assert not list(pasta.glob("*.tmp"))
    con = sqlite3.connect(pasta / "radar_2026-11-05.db")
    try:
        assert con.execute("SELECT motoboy, numero_nota FROM historico").fetchall() == [("Ana Teste", "123")]
    finally:
        con.close()


def test_proxima_copia_as_tres_da_manha():
    assert backup.segundos_ate_proxima(datetime(2026, 11, 25, 2, 0)) == 3600
    assert backup.segundos_ate_proxima(datetime(2026, 11, 25, 3, 0)) == 24 * 3600
    assert backup.segundos_ate_proxima(datetime(2026, 11, 25, 22, 30)) == 4.5 * 3600
