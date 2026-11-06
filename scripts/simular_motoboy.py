"""Simula o app OwnTracks de um motoboy percorrendo a rota montada no painel.

Envia uma posição a cada INTERVALO segundos para /api/gps/owntracks, seguindo
o traçado calculado pelo OSRM (ou linha reta entre as paradas, se offline).

Uso:
    python scripts/simular_motoboy.py --tid 0
    python scripts/simular_motoboy.py --tid 1 --url http://192.168.0.10:5000 --intervalo 2 --velocidade 35 --token segredo

Demonstração dos alertas do painel:
    python scripts/simular_motoboy.py --tid 0 --bateria 15          # bateria baixa
    python scripts/simular_motoboy.py --tid 0 --parar-por 12        # parado 12 min no meio da rota
    python scripts/simular_motoboy.py --tid 0 --cair-sinal          # para de enviar no meio da rota
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar_tracker.geo import haversine, rumo  # noqa: E402


def interpolar(pontos, passo_m):
    """Reamostra o traçado em passos de ~passo_m metros, para um movimento contínuo e realista."""
    saida = []
    for (lat1, lon1), (lat2, lon2) in zip(pontos, pontos[1:]):
        n = max(1, round(haversine(lat1, lon1, lat2, lon2) * 1000 / passo_m))
        saida.extend((lat1 + (lat2 - lat1) * i / n, lon1 + (lon2 - lon1) * i / n) for i in range(n))
    saida.append(pontos[-1])
    return saida


def simular(args, mid, tid, dados, parar):
    """Cada motoboy tem sua conexão HTTP e seu relógio de envio."""
    with requests.Session() as sessao:
        calc_resp = sessao.post(f"{args.url}/api/calc", json={"stops": dados["rota"]}, timeout=10)
        calc_resp.raise_for_status()
        calc = calc_resp.json()
        base = (dados["lat_atual"], dados["lon_atual"])
        pontos = calc["pontos"] or [base, *[(p["lat"], p["lon"]) for p in dados["rota"]], base]
        trajeto = interpolar(pontos, passo_m=args.velocidade / 3.6 * args.intervalo)
        if args.max_posicoes:
            trajeto = trajeto[:args.max_posicoes]
        auth = ("motoboy", args.token) if args.token else None

        def enviar(lat, lon, vel, curso, indice):
            msg = {"_type": "location", "tid": tid, "lat": lat, "lon": lon, "tst": int(time.time()),
                   "acc": 5 + indice % 7, "cog": round(curso, 1), "vel": int(vel),
                   "batt": args.bateria, "bs": 1}
            resposta = sessao.post(f"{args.url}/api/gps/owntracks", json=msg, auth=auth, timeout=5)
            resposta.raise_for_status()

        ponto_evento = max(1, int(len(trajeto) * min(max(args.em, 0), 1)))
        print(f"Simulando {dados['nome']} (id={mid}, tid={tid}) com {len(trajeto)} posições ({calc['fonte']}).", flush=True)
        curso = 0
        for i, (lat, lon) in enumerate(trajeto, 1):
            if parar.is_set():
                break
            if i == ponto_evento and args.cair_sinal:
                print(f"{dados['nome']}: sinal cortado.", flush=True)
                return
            if i < len(trajeto):
                curso = rumo(lat, lon, *trajeto[i])
            enviar(lat, lon, args.velocidade, curso, i)
            print(f"{dados['nome']}: {i}/{len(trajeto)} {lat:.5f}, {lon:.5f}", flush=True)
            if parar.wait(args.intervalo):
                break
            if i == ponto_evento and args.parar_por > 0:
                fim = time.monotonic() + args.parar_por * 60
                while time.monotonic() < fim and not parar.is_set():
                    enviar(lat, lon, 0, curso, i)
                    parar.wait(max(args.intervalo, 5))
        print(f"{dados['nome']}: simulação encerrada.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tid", default="0", help="Tracker ID do motoboy (config/motoboys.json)")
    parser.add_argument("--id", type=int, help="id do motoboy no painel (padrão: igual ao tid)")
    parser.add_argument("--todos", action="store_true", help="simula simultaneamente todos os motoboys com rota")
    parser.add_argument("--max-posicoes", type=int, default=0, help="limita a demonstração (0 = trajeto completo)")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--intervalo", type=float, default=2.0, help="segundos entre posições")
    parser.add_argument("--velocidade", type=float, default=40, help="velocidade simulada em km/h")
    parser.add_argument("--token", default="", help="OWNTRACKS_TOKEN, se configurado no servidor")
    parser.add_argument("--bateria", type=int, default=85, help="bateria do celular informada (%%)")
    parser.add_argument("--parar-por", type=float, default=0, metavar="MIN",
                        help="fica parado MIN minutos no ponto --em do trajeto (alerta de parada)")
    parser.add_argument("--cair-sinal", action="store_true", help="para de enviar no ponto --em (alerta de sem sinal)")
    parser.add_argument("--em", type=float, default=0.4, help="fração do trajeto onde ocorre o evento (0 a 1)")
    args = parser.parse_args()
    if args.intervalo <= 0 or args.velocidade <= 0 or args.max_posicoes < 0:
        parser.error("Intervalo/velocidade devem ser positivos e max-posicoes não negativo.")
    estado_resp = requests.get(f"{args.url}/api/estado", timeout=5)
    estado_resp.raise_for_status()
    estado = estado_resp.json()
    cadastro_resp = requests.get(f"{args.url}/api/motoboys", timeout=5)
    cadastro_resp.raise_for_status()
    cadastro = cadastro_resp.json()
    if args.todos:
        alvos = [(str(m["id"]), str(m["tid"])) for m in cadastro if estado[str(m["id"])]["rota"]]
    else:
        encontrado = next((m for m in cadastro if str(m.get("tid", m["id"])) == args.tid), None)
        mid = str(args.id if args.id is not None else encontrado["id"] if encontrado else args.tid)
        alvos = [(mid, args.tid)] if mid in estado and estado[mid]["rota"] else []
    if not alvos:
        raise SystemExit("Nenhum motoboy selecionado com rota. Monte as rotas no painel primeiro.")
    parar = threading.Event()
    with ThreadPoolExecutor(max_workers=len(alvos), thread_name_prefix="simular") as executor:
        tarefas = [executor.submit(simular, args, mid, tid, estado[mid], parar) for mid, tid in alvos]
        try:
            for tarefa in as_completed(tarefas):
                tarefa.result()
        except KeyboardInterrupt:
            parar.set()
        except Exception:
            parar.set()
            raise


if __name__ == "__main__":
    main()
