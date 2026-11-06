"""Acesso ao banco SQLite: esquema, migrações leves e consultas."""

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
            "SELECT id, data_viagem, motoboy, numero_nota, destinos, hora_saida, hora_chegada, "
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
