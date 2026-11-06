"""Verificação local real: Waitress + curl -N + simulador --todos, com dados temporários.

Uso: python scripts/verificar_stream.py
Não altera o banco/configuração da loja nem acessa OSRM/Nominatim externos.
"""

import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import requests


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from radar_tracker import create_app  # noqa: E402
from radar_tracker.config import Config  # noqa: E402
from run import criar_servidor  # noqa: E402


def executar():
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise SystemExit("curl não encontrado no PATH.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        porta = sock.getsockname()[1]
    url = f"http://127.0.0.1:{porta}"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    with tempfile.TemporaryDirectory(prefix="radar-stream-") as pasta:
        class ConfigVerificacao(Config):
            HOST = "127.0.0.1"
            THREADS = 24
            STREAM_MAX = 2
            PASTA_DADOS = Path(pasta)
            DB_PATH = Path(pasta) / "teste.db"
            ARQUIVO_SESSAO = Path(pasta) / "sessao.json"
            OWNTRACKS_TOKEN = ""
            OSRM_URL = "http://127.0.0.1:1"

        app = create_app(ConfigVerificacao, motoboys=[
            {"id": i, "tid": str(i), "nome": f"Teste {i}", "cor": "#34495e"} for i in range(4)
        ])
        servidor = criar_servidor(app, porta)
        http = threading.Thread(target=servidor.run, daemon=True)
        http.start()
        # Bloco try/finally garante fechamento do SQLite inclusive no Windows.
        cliente = None
        segunda = None
        try:
            for _ in range(100):
                try:
                    if requests.get(url + "/api/health", timeout=0.2).ok:
                        break
                except requests.RequestException:
                    if not http.is_alive():
                        raise RuntimeError("Waitress não iniciou.")
                time.sleep(0.05)
            else:
                raise RuntimeError("Timeout iniciando Waitress.")

            fila = queue.Queue()
            cliente = subprocess.Popen([curl, "-N", "-sS", "--max-time", "45", url + "/api/stream"],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **flags)

            def consumir():
                for linha in iter(cliente.stdout.readline, b""):
                    if linha.startswith(b"data: "):
                        fila.put((time.perf_counter(), json.loads(linha[6:])))
                    elif linha.startswith(b": ping"):
                        fila.put((time.perf_counter(), "ping"))

            leitor = threading.Thread(target=consumir, daemon=True)
            leitor.start()
            _, primeiro = fila.get(timeout=5)
            assert isinstance(primeiro, dict), "Primeiro evento precisa ser snapshot."
            cadastro = requests.get(url + "/api/motoboys", timeout=2).json()
            mid, tid = str(cadastro[0]["id"]), cadastro[0]["tid"]
            lat, lon = primeiro[mid]["lat_atual"], primeiro[mid]["lon_atual"]
            latencias = []
            for i in range(1, 21):
                inicio = time.perf_counter()
                requests.post(url + "/api/gps/owntracks", timeout=2,
                              json={"_type": "location", "tid": tid, "lat": lat, "lon": lon,
                                    "cog": i, "acc": 8, "tst": int(time.time())}).raise_for_status()
                while True:
                    recebido, dados = fila.get(timeout=3)
                    if isinstance(dados, dict) and dados[mid]["curso"] == i:
                        latencias.append((recebido - inicio) * 1000)
                        break
            assert max(latencias) < 300, f"Latência excessiva: {max(latencias):.1f} ms"

            # Limite real no Waitress e API atendendo com ambas as vagas SSE ocupadas.
            segunda = requests.get(url + "/api/stream", stream=True, timeout=3)
            assert segunda.status_code == 200
            assert requests.get(url + "/api/stream", timeout=3).status_code == 503
            assert requests.get(url + "/api/health", timeout=3).ok

            for m in cadastro:
                requests.post(url + "/api/add", json={"id": m["id"], "nome": "Teste temporário",
                                                      "lat": lat + 0.002, "lon": lon}, timeout=3).raise_for_status()
            simulacao = subprocess.run(
                [sys.executable, "scripts/simular_motoboy.py", "--todos", "--url", url,
                 "--intervalo", "0.1", "--velocidade", "25", "--max-posicoes", "25"],
                cwd=RAIZ, env={**os.environ, "PYTHONUTF8": "1"}, capture_output=True, timeout=20, **flags,
            )
            assert simulacao.returncode == 0, simulacao.stderr.decode("utf-8", errors="replace")
            quantidade = 0
            while not fila.empty():
                _, dados = fila.get_nowait()
                quantidade += isinstance(dados, dict)
            assert quantidade >= 5, "Eventos da frota não chegaram continuamente pelo curl -N."
            trilhas = [requests.get(url + f"/api/tracklog?id={m['id']}", timeout=3).json() for m in cadastro]
            assert all(len(t) >= 20 for t in trilhas), "Algum motoboy não registrou a simulação."
            # Sem mudanças, o comentário chega em 15 s e mantém o túnel vivo.
            prazo = time.monotonic() + 17
            while True:
                _, ping = fila.get(timeout=max(0.1, prazo - time.monotonic()))
                if ping == "ping":
                    break
                assert time.monotonic() < prazo, "Heartbeat não recebido após a simulação."
            print(json.dumps({"waitress": "ok", "curl_N": "ok", "amostras_latencia": len(latencias),
                              "latencia_media_ms": round(sum(latencias)/len(latencias), 1),
                              "latencia_max_ms": round(max(latencias), 1), "motoboys_simulados": len(cadastro),
                              "eventos_durante_simulacao": quantidade,
                              "pontos_por_motoboy": [len(t) for t in trilhas],
                              "limite_503": "ok", "ping_15s": "ok"}, ensure_ascii=False, indent=2))
        finally:
            if segunda is not None:
                segunda.close()
            if cliente is not None:
                if cliente.poll() is None:
                    cliente.terminate()
                cliente.wait(timeout=5)
                leitor.join(timeout=2)
                cliente.stdout.close()
            app.extensions["radar"]["frota"].fechar()
            servidor.task_dispatcher.shutdown()
            servidor.close()
            servidor.asyncore.close_all(map=servidor._map)
            http.join(timeout=2)
            app.extensions["radar"]["fechar"]()


if __name__ == "__main__":
    executar()
