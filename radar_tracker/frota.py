"""Estado em memória da frota de motoboys, persistido em JSON entre reinícios."""

import copy
import json
import logging
import math
import os
import threading
import time
from datetime import datetime

from . import geo

LIVRE = "LIVRE"
EM_ROTA = "EM_ROTA"
log = logging.getLogger(__name__)


class MotoboyNaoEncontrado(KeyError):
    pass


class Frota:
    def __init__(self, motoboys, base_lat, base_lon, arquivo_sessao, precisao_max_m=100, velocidade_max_kmh=150,
                 raio_parado_m=50, intervalo_salvar=5, velocidade_alpha=0.35):
        self.motoboys = {m["id"]: m for m in motoboys}
        self.por_tid = {str(m["tid"]): m["id"] for m in motoboys}
        self.base = {"lat": base_lat, "lon": base_lon}
        self.arquivo_sessao = str(arquivo_sessao)
        self.precisao_max_m = precisao_max_m
        self.velocidade_max_kmh = velocidade_max_kmh
        self.raio_parado_m = raio_parado_m
        self.intervalo_salvar = max(0.05, float(intervalo_salvar))
        self.velocidade_alpha = max(0, min(1, velocidade_alpha))
        self._lock = threading.RLock()
        self._condicao = threading.Condition(self._lock)
        self._io_lock = threading.Lock()
        self._versao = 0
        self._sujo = False
        self._encerrada = False
        self._thread = None
        self._velocidades_brutas = {}
        self._derivados = {}
        self.estado = {mid: self._estado_inicial() for mid in self.motoboys}

    def _estado_inicial(self):
        return {
            "status": LIVRE,
            "rota": [],
            "nota": "",
            "hora_saida": "",
            "lat_atual": self.base["lat"],
            "lon_atual": self.base["lon"],
            "velocidade": 0,
            "last_ts": 0,
            "curso": None,
            "ts_posicao": 0,
            "precisao": None,
            "versao": 0,
            # Monitoramento (alertas)
            "inicio_ts": 0,  # hora (servidor) em que saiu para a entrega
            "recebido_em": 0,  # hora (servidor) da última mensagem do celular
            "bateria": None,  # % informado pelo OwnTracks
            "carregando": False,
            "parado_desde": 0,  # início do período parado no mesmo lugar
            "parado_lat": None,
            "parado_lon": None,
        }

    # --- Persistência ---
    def carregar(self):
        try:
            with open(self.arquivo_sessao, encoding="utf-8") as f:
                salvo = json.load(f)
            if not isinstance(salvo, dict):
                return
        except (OSError, ValueError):
            return
        with self._lock:
            for chave, dados in salvo.items():
                try:
                    mid = int(chave)
                except (TypeError, ValueError):
                    continue
                if mid in self.estado and isinstance(dados, dict):
                    for campo in self.estado[mid]:
                        if campo in dados:
                            self.estado[mid][campo] = dados[campo]
                    moto = self.estado[mid]
                    ts = self._numero_finito(moto["last_ts"])
                    if ts is None or ts > time.time():
                        moto["last_ts"] = 0
                        self._sujo = True
                    else:
                        moto["last_ts"] = max(0, int(ts))
                    versao = self._numero_finito(moto["versao"])
                    moto["versao"] = max(0, int(versao)) if versao is not None else 0

    def _mudou(self, mid):
        """Chamado com o lock: publica uma revisão e agenda a persistência."""
        self.estado[int(mid)]["versao"] += 1
        self._versao += 1
        self._sujo = True
        self._condicao.notify_all()
        if self._thread is None and not self._encerrada:
            self._thread = threading.Thread(target=self._persistir, name="radar-sessao", daemon=True)
            self._thread.start()

    def notificar(self):
        """Invalida snapshots derivados (ex.: alteração do cadastro de clientes)."""
        with self._condicao:
            self._versao += 1
            self._condicao.notify_all()

    def esperar_mudanca(self, versao, timeout=15):
        with self._condicao:
            self._condicao.wait_for(lambda: self._versao != versao or self._encerrada, timeout)
            return self._versao

    def aguardar_intervalo(self, timeout):
        """Espera só pelo prazo de agrupamento ou pelo encerramento, sem polling."""
        with self._condicao:
            self._condicao.wait_for(lambda: self._encerrada, max(0, timeout))

    @property
    def encerrada(self):
        with self._lock:
            return self._encerrada

    def _persistir(self):
        while True:
            with self._condicao:
                self._condicao.wait_for(lambda: self._sujo or self._encerrada)
                if self._encerrada:
                    return
                # Janela fixa: tráfego contínuo não adia a gravação indefinidamente.
                self._condicao.wait_for(lambda: self._encerrada, self.intervalo_salvar)
                if self._encerrada:
                    return
            self.salvar()

    def salvar(self):
        """Serializa escritores e repete replace bloqueado pelo Windows/OneDrive."""
        with self._io_lock:
            with self._lock:
                if not self._sujo:
                    return True
                conteudo = json.dumps(self.estado, ensure_ascii=False, indent=2, allow_nan=False)
                versao = self._versao
            temporario = self.arquivo_sessao + ".tmp"
            try:
                os.makedirs(os.path.dirname(self.arquivo_sessao) or ".", exist_ok=True)
                with open(temporario, "w", encoding="utf-8") as f:
                    f.write(conteudo)
                for tentativa in range(4):
                    try:
                        os.replace(temporario, self.arquivo_sessao)
                        break
                    except PermissionError:
                        if tentativa == 3:
                            raise
                        log.warning("Sessão bloqueada; nova tentativa de gravação (%s/3).", tentativa + 1)
                        time.sleep(0.05 * (tentativa + 1))
            except OSError:
                log.warning("Não foi possível gravar a sessão; alteração mantida em memória para nova tentativa.",
                            exc_info=True)
                return False
            with self._lock:
                if versao == self._versao:
                    self._sujo = False
            return True

    def fechar(self):
        with self._condicao:
            self._encerrada = True
            self._condicao.notify_all()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join()
        self.salvar()

    # --- Consultas ---
    def _moto(self, mid):
        try:
            return self.estado[int(mid)]
        except (KeyError, TypeError, ValueError):
            raise MotoboyNaoEncontrado(mid) from None

    def id_por_tid(self, tid):
        return self.por_tid.get(str(tid))

    def validar_id(self, mid):
        with self._lock:
            self._moto(mid)

    def snapshot(self):
        return self.snapshot_com_versao()[1]

    def snapshot_com_versao(self, avaliar=None):
        with self._lock:
            snapshot = {
                str(mid): {**copy.deepcopy(dados), "nome": self.motoboys[mid]["nome"],
                           "cor": self.motoboys[mid]["cor"]}
                for mid, dados in self.estado.items()
            }
            if avaliar is not None:
                snapshot = avaliar(snapshot)
                for mid, dados in snapshot.items():
                    assinatura = (dados.get("online"), json.dumps(dados.get("alertas"), sort_keys=True))
                    anterior = self._derivados.get(mid)
                    if anterior is not None and anterior != assinatura:
                        self._mudou(int(mid))
                        dados["versao"] = self.estado[int(mid)]["versao"]
                    self._derivados[mid] = assinatura
            return self._versao, snapshot

    # --- Montagem da rota ---
    def adicionar_parada(self, mid, nome, lat, lon):
        with self._lock:
            moto = self._moto(mid)
            if moto["status"] != LIVRE:
                return False
            moto["rota"].append({"nome": nome, "lat": float(lat), "lon": float(lon)})
            self._mudou(mid)
        self.salvar()
        return True

    def remover_parada(self, mid, indice):
        with self._lock:
            moto = self._moto(mid)
            if moto["status"] != LIVRE or not 0 <= indice < len(moto["rota"]):
                return False
            moto["rota"].pop(indice)
            self._mudou(mid)
        self.salvar()
        return True

    def otimizar(self, mid):
        with self._lock:
            moto = self._moto(mid)
            if moto["status"] != LIVRE or len(moto["rota"]) < 2:
                return False
            origem = {"lat": moto["lat_atual"] or self.base["lat"], "lon": moto["lon_atual"] or self.base["lon"]}
            moto["rota"] = geo.vizinho_mais_proximo(origem, moto["rota"])
            self._mudou(mid)
        self.salvar()
        return True

    # --- Ciclo da entrega ---
    def iniciar(self, mid, nota):
        with self._lock:
            moto = self._moto(mid)
            if moto["status"] != LIVRE or not moto["rota"] or not nota:
                return False
            agora = int(time.time())
            moto.update(status=EM_ROTA, nota=nota, hora_saida=datetime.now().strftime("%H:%M"),
                        inicio_ts=agora, parado_desde=agora,
                        parado_lat=moto["lat_atual"], parado_lon=moto["lon_atual"])
            self._mudou(mid)
        self.salvar()
        return True

    def finalizar(self, mid, registrar=None):
        """Encerra a rota e devolve os dados da viagem para o histórico (ou None)."""
        with self._lock:
            moto = self._moto(mid)
            if moto["status"] != EM_ROTA:
                return None
            fim_ts = int(time.time())
            viagem = {
                "moto_id": int(mid),
                "motoboy": self.motoboys[int(mid)]["nome"],
                "hora_saida": moto["hora_saida"],
                "hora_chegada": datetime.now().strftime("%H:%M"),
                "destinos": ", ".join(p["nome"] for p in moto["rota"]),
                "nota": moto["nota"],
                "inicio_ts": moto["inicio_ts"],
                "fim_ts": fim_ts,
            }
            if registrar:
                registrar(**viagem)  # só libera a rota depois de confirmar a escrita no banco
            moto.update(status=LIVRE, rota=[], nota="", hora_saida="", inicio_ts=0)
            self._mudou(mid)
        self.salvar()
        return viagem

    # --- GPS ---
    def registrar_contato(self, mid, bateria=None, carregando=None, agora=None):
        """Contato usa relógio do servidor, mesmo se o GPS for descartado."""
        with self._lock:
            moto = self._moto(mid)
            contato = {"recebido_em": int(time.time() if agora is None else agora)}
            bateria = self._numero_finito(bateria)
            if bateria is not None:
                contato["bateria"] = max(0, min(100, int(bateria)))
            if carregando is not None:
                contato["carregando"] = bool(carregando)
            if any(moto[k] != v for k, v in contato.items()):
                moto.update(contato)
                self._mudou(mid)

    @staticmethod
    def _numero_finito(valor):
        try:
            numero = float(valor)
            return numero if math.isfinite(numero) else None
        except (TypeError, ValueError, OverflowError):
            return None

    def atualizar_posicao(self, mid, lat, lon, ts=None, precisao_m=None, vel_dispositivo=None,
                          curso=None, detalhes=False):
        """Retorna velocidade BRUTA (compatibilidade), ou registro aceito se detalhes=True.

        Posição/alertas usam hora do servidor; last_ts mantém a hora saneada do GPS.
        Velocidade do snapshot é uma EMA; a trilha recebe o valor bruto.
        """
        agora = int(time.time())
        ts = self._numero_finito(ts)
        ts = int(ts) if ts is not None and 0 < ts <= agora + 300 else agora
        lat, lon = self._numero_finito(lat), self._numero_finito(lon)
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            return None
        precisao_m = self._numero_finito(precisao_m)
        curso = self._numero_finito(curso)
        vel_dispositivo = self._numero_finito(vel_dispositivo)
        with self._lock:
            moto = self._moto(mid)
            if precisao_m is not None and (precisao_m < 0 or precisao_m > self.precisao_max_m):
                return None
            anterior = moto["last_ts"]
            if anterior and ts < anterior:
                return None
            deslocamento = geo.haversine(moto["lat_atual"], moto["lon_atual"], lat, lon) * 1000
            if anterior and ts == anterior:
                # Uma leitura no mesmo segundo pode oscilar; não pode teletransportar.
                if deslocamento > self.velocidade_max_kmh / 3.6:
                    return None
                vel = self._velocidades_brutas.get(int(mid), moto["velocidade"])
            else:
                vel = geo.velocidade_kmh(moto["lat_atual"], moto["lon_atual"], anterior, lat, lon, ts)
                if vel is not None and vel > self.velocidade_max_kmh:
                    return None
            if vel_dispositivo is not None and 0 <= vel_dispositivo <= self.velocidade_max_kmh:
                vel = vel_dispositivo
            if vel is None or vel < 1:
                vel = 0.0
            suavizada = vel if not anterior else self.velocidade_alpha * vel + (1 - self.velocidade_alpha) * moto["velocidade"]
            if curso is not None and 0 <= curso <= 360:
                novo_curso = curso % 360
            elif anterior and deslocamento > 10:
                novo_curso = geo.rumo(moto["lat_atual"], moto["lon_atual"], lat, lon)
            else:
                novo_curso = moto["curso"]
            self._velocidades_brutas[int(mid)] = vel
            moto.update(lat_atual=lat, lon_atual=lon, velocidade=round(suavizada, 1), last_ts=ts,
                        curso=novo_curso, precisao=precisao_m, ts_posicao=agora)
            self._atualizar_parado(moto, lat, lon, agora)
            self._mudou(mid)
            registro = {"moto_id": int(mid), "lat": lat, "lon": lon, "velocidade": vel,
                        "ts": ts, "curso": novo_curso}
        return registro if detalhes else vel

    def _atualizar_parado(self, moto, lat, lon, agora):
        if moto["parado_lat"] is None or geo.haversine(moto["parado_lat"], moto["parado_lon"], lat, lon) * 1000 > self.raio_parado_m:
            moto.update(parado_desde=agora, parado_lat=lat, parado_lon=lon)
