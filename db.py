"""SQLite WAL, per-thread connections and nestable atomic game operations.

No asynchronous work may be awaited inside transaction(). Domain operations are
synchronous; Telegram and backups are handled only after the transaction commits.
"""
import contextlib
import contextvars
from datetime import datetime, timedelta, timezone
from functools import wraps
import itertools
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

import config
from schema import SCHEMA, UPGRADE_SCHEMA

TZ_OFFSET = 3 * 3600 + 1800
TZ = timezone(timedelta(seconds=TZ_OFFSET), "Tehran")
GAME = contextvars.ContextVar("game", default=None)
ACTOR = contextvars.ContextVar("actor", default=None)
GAMES_DIR = os.environ.get("DZ_GAMES_DIR", "games")
_conns = {}  # preserved public test hook for the main thread
_local = threading.local()
_savepoints = itertools.count(1)


def now() -> int:
    return int(time.time())


def day_index() -> int:
    return (now() + TZ_OFFSET) // 86400


def game_path(chat_id) -> str:
    if isinstance(chat_id, bool):
        raise ValueError("invalid game id")
    cid = int(chat_id)
    return str(Path(GAMES_DIR) / f"{cid}.db")


def list_games():
    root = Path(GAMES_DIR)
    if not root.is_dir():
        return []
    return sorted(int(p.stem) for p in root.glob("*.db")
                  if p.stem.lstrip("-").isdigit())


def _cache():
    if threading.current_thread() is threading.main_thread():
        return _conns
    if not hasattr(_local, "conns"):
        _local.conns = {}
    return _local.conns


def _open_db(c):
    c.executescript(SCHEMA)
    columns = {r[1] for r in c.execute("PRAGMA table_info(users)")}
    if "username" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    c.executescript(UPGRADE_SCHEMA)
    structure_columns={r[1] for r in c.execute('PRAGMA table_info(structures)')}
    if 'previous_level' not in structure_columns:
        c.execute('ALTER TABLE structures ADD COLUMN previous_level INTEGER NOT NULL DEFAULT 0 CHECK(previous_level BETWEEN 0 AND 3)')


def _connection(path):
    cache = _cache()
    if path not in cache:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA foreign_keys=ON")
        _open_db(c)
        cache[path] = c
    return cache[path]


def con():
    g = GAME.get()
    return _connection(game_path(g) if g is not None else config.DB_PATH)


def con_for(chat_id):
    return _connection(game_path(chat_id))


@contextlib.contextmanager
def world(chat_id):
    token = GAME.set(chat_id)
    try:
        yield
    finally:
        GAME.reset(token)


@contextlib.contextmanager
def transaction():
    """BEGIN IMMEDIATE prevents double spending; nested calls use savepoints."""
    c = con()
    nested = c.in_transaction
    sp = f"dz_{next(_savepoints)}"
    c.execute(f"SAVEPOINT {sp}" if nested else "BEGIN IMMEDIATE")
    try:
        yield c
    except BaseException:
        if nested:
            c.execute(f"ROLLBACK TO {sp}")
            c.execute(f"RELEASE {sp}")
        else:
            c.rollback()
        raise
    else:
        c.execute(f"RELEASE {sp}" if nested else "COMMIT")


def atomic(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with transaction():
            return fn(*args, **kwargs)
    return wrapped


def ex(sql, args=()):
    return con().execute(sql, args)


def one(sql, args=()):
    return con().execute(sql, args).fetchone()


def q(sql, args=()):
    return con().execute(sql, args).fetchall()


def kv_set(k, v):
    ex("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))


def kv_del(k):
    ex("DELETE FROM kv WHERE k=?", (k,))


def kv_get(k, d=None):
    r = one("SELECT v FROM kv WHERE k=?", (k,))
    return r["v"] if r else d


def jload(s, d=None):
    try:
        return json.loads(s) if s else d
    except (ValueError, TypeError):
        return d


def integer(value, default=0, lo=None, hi=None):
    try:
        n = int(value)
    except (ValueError, TypeError, OverflowError):
        return default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def debit(uid, amount):
    if type(amount) is not int or amount < 0:
        raise ValueError("invalid amount")
    return ex("UPDATE users SET money=money-? WHERE uid=? AND money>=?",
              (amount, uid, amount)).rowcount == 1


def audit(action, actor=None, **detail):
    ex("INSERT INTO ledger(action,actor,detail,ts) VALUES(?,?,?,?)",
       (action, actor, json.dumps(detail, ensure_ascii=False, sort_keys=True), now()))


def log(level, text):
    with contextlib.suppress(sqlite3.Error):
        ex("INSERT INTO logs(level,text,ts) VALUES(?,?,?)", (level, str(text)[:1000], now()))


def tehran_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M")


def close_all():
    for c in list(_cache().values()):
        with contextlib.suppress(sqlite3.Error):
            c.close()
    _cache().clear()


def _migrate_legacy():
    source = Path(config.DB_PATH)
    if not source.is_file() or list_games():
        return
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as c:
        try:
            r = c.execute("SELECT v FROM kv WHERE k='main_group'").fetchone()
        except sqlite3.Error:
            return
        if not r or not str(r[0]).startswith("-"):
            return
        dest = game_path(int(r[0]))
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(dest) as target:
            c.backup(target)  # includes committed WAL data; source retained as backup


def init(path: str = None):
    if path is not None:
        close_all()
        GAME.set(None)
        config.DB_PATH = path
        con()
        return
    _migrate_legacy()
    for gid in list_games():
        con_for(gid)
