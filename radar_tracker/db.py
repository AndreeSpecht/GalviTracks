"""Acesso ao banco SQLite: esquema, migrações leves e consultas."""

import bisect
import copy
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

from . import geo

log = logging.getLogger(__name__)

COR_PADRAO_CLIENTE = "#808080"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    cor TEXT DEFAULT '#808080',
    telefone TEXT DEFAULT '',
    obs TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tracklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    moto_id INTEGER,
    lat REAL,
    lon REAL,
    velocidade REAL,
    timestamp INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tracklog_moto_ts ON tracklog (moto_id, timestamp);
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    motoboy TEXT,
    data_viagem TEXT,
    hora_saida TEXT,
    hora_chegada TEXT,
    destinos TEXT,
    numero_nota TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'operador',
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em INTEGER
);
"""

# Colunas acrescentadas após a primeira versão do banco (protótipo V79)
MIGRACOES = {
    "clientes": {"cor": "TEXT DEFAULT '#808080'", "telefone": "TEXT DEFAULT ''", "obs": "TEXT DEFAULT ''"},
    "historico": {"numero_nota": "TEXT DEFAULT ''", "data_iso": "TEXT", "moto_id": "INTEGER",
                  "inicio_ts": "INTEGER", "fim_ts": "INTEGER", "duracao_min": "REAL"},
    "tracklog": {"curso": "REAL"},
}


class Banco:
    def __init__(self, caminho):
        self.caminho = str(caminho)
        self._local = threading.local()
        self._conexoes = []
        self._conexoes_lock = threading.Lock()
        self._clientes_lock = threading.RLock()
        self._clientes_cache = None
        self._parar = threading.Event()
        self._thread = None

    @contextmanager
    def conexao(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            # O proprietário é a thread; check_same_thread=False só permite fechar
            # todas as conexões no encerramento, depois de parar os workers.
            conn = sqlite3.connect(self.caminho, timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
            with self._conexoes_lock:
                self._conexoes.append(conn)
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def iniciar_retencao(self, dias=90):
        if dias < 1:
            raise ValueError("TRACKLOG_DIAS deve ser maior que zero.")
        self.limpar_trilha(dias)

        def manter():
            try:
                while not self._parar.is_set():
                    agora = datetime.now()
                    amanha = (agora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    if self._parar.wait(max(1, (amanha - agora).total_seconds())):
                        break
                    try:
                        self.limpar_trilha(dias)
                    except sqlite3.Error:
                        log.exception("Falha na retenção diária da trilha.")
            finally:
                self.fechar_thread()

        self._thread = threading.Thread(target=manter, name="radar-retencao", daemon=True)
        self._thread.start()

    def limpar_trilha(self, dias=90, agora=None):
        limite = int(time.time() if agora is None else agora) - dias * 86400
        with self.conexao() as conn:
            return conn.execute("DELETE FROM tracklog WHERE timestamp < ?", (limite,)).rowcount

    def fechar_thread(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            with self._conexoes_lock:
                self._conexoes.remove(conn)
            conn.close()
            del self._local.conn

    def fechar(self):
        self._parar.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join()
        with self._conexoes_lock:
            for conn in self._conexoes:
                conn.close()
            self._conexoes.clear()
        self._local = threading.local()

    def inicializar(self):
        with self.conexao() as conn:
            conn.executescript(ESQUEMA)
            for tabela, colunas in MIGRACOES.items():
                existentes = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")}
                for coluna, tipo in colunas.items():
                    if coluna not in existentes:
                        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            # Preenche data_iso em registros antigos (data_viagem em dd/mm/aaaa)
            for r in conn.execute("SELECT id, data_viagem FROM historico WHERE data_iso IS NULL").fetchall():
                try:
                    iso = datetime.strptime(r["data_viagem"], "%d/%m/%Y").strftime("%Y-%m-%d")
                except (TypeError, ValueError):
                    continue
                conn.execute("UPDATE historico SET data_iso = ? WHERE id = ?", (iso, r["id"]))
            # Antigos horários não tinham data de chegada: assume dia seguinte
            # quando a chegada é menor que a saída. Registros ilegíveis ficam nulos.
            for r in conn.execute("SELECT id, data_viagem, hora_saida, hora_chegada FROM historico "
                                  "WHERE inicio_ts IS NULL OR fim_ts IS NULL").fetchall():
                try:
                    inicio = datetime.strptime(f"{r['data_viagem']} {r['hora_saida']}", "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(f"{r['data_viagem']} {r['hora_chegada']}", "%d/%m/%Y %H:%M")
                    if fim < inicio:
                        fim += timedelta(days=1)
                    inicio_ts, fim_ts = int(inicio.timestamp()), int(fim.timestamp())
                except (TypeError, ValueError, OSError, OverflowError):
                    continue
                conn.execute("UPDATE historico SET inicio_ts=?, fim_ts=?, duracao_min=? WHERE id=?",
                             (inicio_ts, fim_ts, (fim-inicio).total_seconds()/60, r["id"]))
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tracklog_ts ON tracklog(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_historico_data ON historico(data_iso)")
            conn.execute("UPDATE clientes SET cor = ? WHERE cor IS NULL OR cor NOT LIKE '#%'", (COR_PADRAO_CLIENTE,))

    # --- Clientes ---
    def listar_clientes(self):
        with self._clientes_lock:
            if self._clientes_cache is None:
                with self.conexao() as conn:
                    rows = conn.execute(
                        "SELECT id, nome, lat, lon, cor, telefone, obs FROM clientes ORDER BY nome COLLATE NOCASE"
                    ).fetchall()
                    self._clientes_cache = [dict(r) for r in rows]
            return copy.deepcopy(self._clientes_cache)

    def salvar_cliente(self, nome, lat, lon):
        """Insere o cliente se ainda não existir um com o mesmo nome. Retorna o id."""
        with self._clientes_lock, self.conexao() as conn:
            self._clientes_cache = None
            existente = conn.execute(
                "SELECT id FROM clientes WHERE nome = ? COLLATE NOCASE", (nome,)
            ).fetchone()
            if existente:
                return existente["id"]
            cur = conn.execute(
                "INSERT INTO clientes (nome, lat, lon, cor) VALUES (?, ?, ?, ?)",
                (nome, lat, lon, COR_PADRAO_CLIENTE),
            )
            return cur.lastrowid

    def atualizar_cliente(self, cliente_id, nome, telefone):
        with self._clientes_lock, self.conexao() as conn:
            self._clientes_cache = None
            conn.execute("UPDATE clientes SET nome = ?, telefone = ? WHERE id = ?", (nome, telefone, cliente_id))

    def atualizar_cor_cliente(self, cliente_id, cor):
        with self._clientes_lock, self.conexao() as conn:
            self._clientes_cache = None
            conn.execute("UPDATE clientes SET cor = ? WHERE id = ?", (cor, cliente_id))

    def apagar_cliente(self, cliente_id):
        with self._clientes_lock, self.conexao() as conn:
            self._clientes_cache = None
            conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))

    # --- Rastreamento ---
    def registrar_posicao(self, moto_id, lat, lon, velocidade, ts, curso=None):
        with self.conexao() as conn:
            conn.execute(
                "INSERT INTO tracklog (moto_id, lat, lon, velocidade, timestamp, curso) VALUES (?, ?, ?, ?, ?, ?)",
                (moto_id, lat, lon, velocidade, ts, curso),
            )

    def trilha(self, moto_id, ts_inicio, ts_fim):
        with self.conexao() as conn:
            rows = conn.execute(
                "SELECT lat, lon, velocidade, timestamp, curso FROM tracklog "
                "WHERE moto_id = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp, id",
                (moto_id, ts_inicio, ts_fim),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Histórico ---
    def registrar_viagem(self, moto_id, motoboy, hora_saida, hora_chegada, destinos, nota, quando=None,
                         inicio_ts=None, fim_ts=None):
        quando = quando or datetime.now()
        if not inicio_ts:
            inicio = datetime.strptime(f"{quando:%Y-%m-%d} {hora_saida}", "%Y-%m-%d %H:%M")
            inicio_ts = int(inicio.timestamp())
        inicio = datetime.fromtimestamp(inicio_ts)
        if fim_ts is None:
            fim = datetime.strptime(f"{inicio:%Y-%m-%d} {hora_chegada}", "%Y-%m-%d %H:%M")
            if fim.timestamp() < inicio_ts:
                fim += timedelta(days=1)
            fim_ts = int(fim.timestamp())
        duracao = round(max(0, fim_ts - inicio_ts) / 60, 2)
        with self.conexao() as conn:
            conn.execute(
                "INSERT INTO historico (moto_id, motoboy, data_viagem, data_iso, hora_saida, hora_chegada, "
                "destinos, numero_nota, inicio_ts, fim_ts, duracao_min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (moto_id, motoboy, inicio.strftime("%d/%m/%Y"), inicio.strftime("%Y-%m-%d"),
                 hora_saida, hora_chegada, destinos, nota, inicio_ts, fim_ts, duracao),
            )

    def resumo_dia(self, quando=None):
        dia = (quando or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        inicio, fim = int(dia.timestamp()), int((dia + timedelta(days=1)).timestamp())
        km = 0.0
        anterior = None
        with self.conexao() as conn:
            entregas = conn.execute("SELECT COUNT(*) FROM historico WHERE data_iso = ?",
                                    (dia.strftime("%Y-%m-%d"),)).fetchone()[0]
            for p in conn.execute("SELECT moto_id, lat, lon FROM tracklog WHERE timestamp >= ? AND timestamp < ? "
                                  "ORDER BY moto_id, timestamp, id", (inicio, fim)):
                if anterior is not None and anterior["moto_id"] == p["moto_id"]:
                    km += geo.haversine(anterior["lat"], anterior["lon"], p["lat"], p["lon"])
                anterior = p
        return {"entregas_hoje": entregas, "km_hoje": round(km, 3)}

    def historico(self, inicio=None, fim=None):
        """Viagens mais recentes primeiro. inicio/fim no formato AAAA-MM-DD (inclusivos)."""
        sql = (
            "SELECT id, moto_id, data_viagem, motoboy, numero_nota, destinos, hora_saida, hora_chegada, "
            "inicio_ts, fim_ts, duracao_min "
            "FROM historico WHERE 1=1"
        )
        params = []
        if inicio:
            sql += " AND data_iso >= ?"
            params.append(inicio)
        if fim:
            sql += " AND data_iso <= ?"
            params.append(fim)
        sql += " ORDER BY id DESC"
        with self.conexao() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def km_das_viagens(self, viagens):
        """Km de cada viagem pela trilha GPS gravada entre a saída e a chegada: {id_viagem: km}.

        Viagens sem moto_id, sem horários ou com menos de dois pontos na trilha ficam de fora
        (registros antigos, trilha já apagada pela retenção ou celular sem enviar posição).
        """
        por_moto = {}
        for v in viagens:
            if v.get("moto_id") is not None and v.get("inicio_ts") and v.get("fim_ts"):
                por_moto.setdefault(v["moto_id"], []).append(v)
        km = {}
        with self.conexao() as conn:
            for moto_id, lista in por_moto.items():
                pontos = conn.execute(
                    "SELECT timestamp, lat, lon FROM tracklog WHERE moto_id = ? AND timestamp >= ? AND timestamp <= ? "
                    "ORDER BY timestamp, id",
                    (moto_id, min(v["inicio_ts"] for v in lista), max(v["fim_ts"] for v in lista)),
                ).fetchall()
                tempos = [p["timestamp"] for p in pontos]
                for v in lista:
                    trecho = pontos[bisect.bisect_left(tempos, v["inicio_ts"]):bisect.bisect_right(tempos, v["fim_ts"])]
                    if len(trecho) >= 2:
                        km[v["id"]] = sum(geo.haversine(a["lat"], a["lon"], b["lat"], b["lon"])
                                          for a, b in zip(trecho, trecho[1:]))
        return km

    def indicadores(self, inicio=None, fim=None):
        """Indicadores por motoboy no período (mesmos filtros do histórico) e o total da frota.

        Tempo de rota = da saída à chegada. Km = soma da trilha GPS das viagens que têm trilha;
        "viagens_com_km" diz quantas entraram nessa conta.
        """
        viagens = self.historico(inicio, fim)
        km = self.km_das_viagens(viagens)

        def novo(nome):
            return {"motoboy": nome, "viagens": 0, "destinos": 0, "minutos": 0.0, "viagens_com_tempo": 0,
                    "km": 0.0, "viagens_com_km": 0}

        grupos, total = {}, novo("Total")
        for v in viagens:
            nome = (v.get("motoboy") or "").strip() or "Sem nome"
            for g in (grupos.setdefault(nome, novo(nome)), total):
                g["viagens"] += 1
                g["destinos"] += len([d for d in (v.get("destinos") or "").split(",") if d.strip()])
                if v.get("duracao_min") is not None:
                    g["minutos"] += v["duracao_min"]
                    g["viagens_com_tempo"] += 1
                if v["id"] in km:
                    g["km"] += km[v["id"]]
                    g["viagens_com_km"] += 1

        def fechar(g):
            n_tempo, n_km = g.pop("viagens_com_tempo"), g["viagens_com_km"]
            minutos = g.pop("minutos")
            g["tempo_total_min"] = round(minutos)
            g["tempo_medio_min"] = round(minutos / n_tempo, 1) if n_tempo else None
            g["destinos_por_viagem"] = round(g["destinos"] / g["viagens"], 2) if g["viagens"] else None
            g["km"] = round(g["km"], 2) if n_km else None
            g["km_por_viagem"] = round(g["km"] / n_km, 2) if n_km else None
            return g

        motoboys = sorted((fechar(g) for g in grupos.values()), key=lambda g: (-g["viagens"], g["motoboy"]))
        return {"motoboys": motoboys, "total": fechar(total)}

    # --- Usuários do painel (login de operador) ---
    _CAMPOS_USUARIO = "id, usuario, nome, perfil, ativo, criado_em"

    def contar_usuarios(self, perfil=None):
        """Quantidade de usuários ativos (opcionalmente só de um perfil)."""
        sql, params = "SELECT COUNT(*) FROM usuarios WHERE ativo = 1", []
        if perfil:
            sql += " AND perfil = ?"
            params.append(perfil)
        with self.conexao() as conn:
            return conn.execute(sql, params).fetchone()[0]

    def criar_usuario(self, usuario, nome, senha_hash, perfil):
        """Cria o usuário e devolve o id. Lança ValueError se o login já existe."""
        try:
            with self.conexao() as conn:
                cur = conn.execute(
                    "INSERT INTO usuarios (usuario, nome, senha_hash, perfil, ativo, criado_em) VALUES (?, ?, ?, ?, 1, ?)",
                    (usuario, nome, senha_hash, perfil, int(time.time())))
                return cur.lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError("Já existe um usuário com esse login.") from e

    def obter_usuario(self, usuario_id):
        with self.conexao() as conn:
            r = conn.execute(f"SELECT {self._CAMPOS_USUARIO} FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        return dict(r) if r else None

    def usuario_para_login(self, usuario):
        """Usuário (com o hash da senha) pelo login, sem diferenciar maiúsculas."""
        with self.conexao() as conn:
            r = conn.execute(f"SELECT {self._CAMPOS_USUARIO}, senha_hash FROM usuarios WHERE usuario = ? COLLATE NOCASE",
                             (usuario,)).fetchone()
        return dict(r) if r else None

    def listar_usuarios(self):
        with self.conexao() as conn:
            rows = conn.execute(f"SELECT {self._CAMPOS_USUARIO} FROM usuarios WHERE ativo = 1 "
                                "ORDER BY nome COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    def definir_senha(self, usuario_id, senha_hash):
        with self.conexao() as conn:
            return conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ? AND ativo = 1",
                                (senha_hash, usuario_id)).rowcount > 0

    def desativar_usuario(self, usuario_id):
        """Remove o acesso mantendo o registro (o login fica livre para reuso)."""
        with self.conexao() as conn:
            return conn.execute("UPDATE usuarios SET ativo = 0, usuario = usuario || '#removido-' || id "
                                "WHERE id = ? AND ativo = 1", (usuario_id,)).rowcount > 0
