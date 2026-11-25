"""Cena para as capturas do README: GalviTracks isolado, rotas montadas e motoboys simulados andando.

Usa uma CÓPIA do data/radar.db numa pasta temporária (o banco da loja não é alterado),
cria o gestor temporário "andre" e sobe o servidor em http://127.0.0.1:5098.

Uso: .venv/Scripts/python scripts/docs/cena_demo.py <pasta_temporária>   (Ctrl+C encerra)
Depois, em outro terminal: python scripts/docs/capturas_readme.py docs/img
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from werkzeug.security import generate_password_hash  # noqa: E402
from radar_tracker.db import Banco  # noqa: E402

pasta = Path(sys.argv[1])
shutil.rmtree(pasta, ignore_errors=True)
pasta.mkdir(parents=True)
shutil.copy(RAIZ / "data" / "radar.db", pasta / "t.db")
b = Banco(pasta / "t.db")
b.inicializar()
b.criar_usuario("andre", "André Specht", generate_password_hash("demo-portfolio"), "gestor")
clientes = {c["nome"].strip(): c for c in b.listar_clientes()}
b.fechar()

PY = str(RAIZ / ".venv" / "Scripts" / "python.exe")
URL = "http://127.0.0.1:5098"
env = {**os.environ, "PASTA_DADOS": str(pasta), "DB_PATH": str(pasta / "t.db"),
       "ARQUIVO_SESSAO": str(pasta / "s.json"), "OWNTRACKS_TOKEN": "", "PYTHONUTF8": "1"}
log = open(pasta / "servidor.log", "w")
srv = subprocess.Popen([PY, "run.py", "--no-browser", "--port", "5098"], cwd=RAIZ, env=env, stdout=log, stderr=log)
for _ in range(100):
    try:
        if requests.get(URL + "/api/health", timeout=0.3).ok:
            break
    except requests.RequestException:
        time.sleep(0.1)

s = requests.Session()
assert s.post(URL + "/login", data={"usuario": "andre", "senha": "demo-portfolio"}, allow_redirects=False).status_code == 302


def rota(mid, nomes, nota=None):
    for n in nomes:
        c = clientes[n]
        s.post(URL + "/api/add", json={"id": mid, "nome": c["nome"].strip(), "lat": c["lat"], "lon": c["lon"]}).raise_for_status()
    s.post(URL + "/api/otimizar", json={"id": mid}).raise_for_status()
    if nota:
        assert s.post(URL + "/api/start", json={"id": mid, "nota": nota}).json()["ok"]


rota(0, ["Ferrari", "KN Mecanica", "Gaucho"], "456212, 456213")
rota(1, ["Elite Mecanica", "Cesar Voeltz", "FR Distribuidora", "Welter"], "456214")
rota(3, ["Woltz", "Semaforo", "Alton Race"], "456215")

sims = []
for tid, vel, bat in (("0", 38, 81), ("1", 32, 64), ("3", 28, 17)):
    sims.append(subprocess.Popen([PY, "scripts/simular_motoboy.py", "--tid", tid, "--url", URL, "--intervalo", "1",
                                  "--velocidade", str(vel), "--bateria", str(bat), "--usuario", "andre", "--senha", "demo-portfolio"],
                                 cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=log))
# Paulo fica na loja com a rota montada, ainda sem sair
rota(2, ["Prochnow Mecanica", "Pointer", "Alexandre Feder", "Paiva Mecanica"])
# posição do Paulo na loja (para aparecer "online")
s.post(URL + "/api/gps/owntracks", json={"_type": "location", "tid": "2", "lat": -26.50850, "lon": -49.10540,
                                          "tst": int(time.time()), "acc": 6, "batt": 92, "bs": 2})
print("cena pronta", flush=True)
try:
    while True:
        time.sleep(20)
        s.post(URL + "/api/gps/owntracks", json={"_type": "location", "tid": "2", "lat": -26.50850, "lon": -49.10540,
                                                  "tst": int(time.time()), "acc": 6, "batt": 92, "bs": 2})
finally:
    for p in sims:
        p.terminate()
    srv.terminate()
