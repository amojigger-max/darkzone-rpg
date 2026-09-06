"""🗄 جنگ جهانی — دیتابیس (SQLite WAL + thread-local)."""
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import config

_local = threading.local()
TZ = timezone(timedelta(hours=3), "Tehran")


def now() -> int:
    return int(time.time())


def con():
    c = getattr(_local, "con", None)
    if c is None:
        c = sqlite3.connect(config.DB_PATH, 30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=8000")
        _local.con = c
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    uid INTEGER PRIMARY KEY,
    name TEXT, country TEXT, branch TEXT,
    rank INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
    money INTEGER DEFAULT 2000,
    hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,
    kills INTEGER DEFAULT 0, spy_ops INTEGER DEFAULT 0,
    party_id INTEGER, is_leader INTEGER DEFAULT 0,
    joined INTEGER, last_active INTEGER, chat_id INTEGER
);
CREATE TABLE IF NOT EXISTS items (
    iid TEXT PRIMARY KEY, name TEXT, emoji TEXT, country TEXT,
    atk INTEGER, guard INTEGER, price INTEGER,
    max_dur INTEGER DEFAULT 100, img TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
    uid INTEGER, iid TEXT, qty INTEGER DEFAULT 1, dur INTEGER,
    PRIMARY KEY(uid, iid)
);
CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, country TEXT, ideology TEXT, leader_uid INTEGER,
    members INTEGER DEFAULT 1, power INTEGER DEFAULT 10,
    rebel INTEGER DEFAULT 0, created INTEGER
);
CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    party_id INTEGER, uid INTEGER, title TEXT, body TEXT, ts INTEGER
);
CREATE TABLE IF NOT EXISTS wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a TEXT, b TEXT, status TEXT DEFAULT 'active',
    score_a INTEGER DEFAULT 0, score_b INTEGER DEFAULT 0,
    started INTEGER, ends INTEGER, winner TEXT
);
CREATE TABLE IF NOT EXISTS spyops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER, target TEXT, success INTEGER, info TEXT, ts INTEGER
);
CREATE TABLE IF NOT EXISTS alliances (
    a TEXT, b TEXT, created INTEGER
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT, text TEXT, ts INTEGER
);
"""


def init(path: str = None):
    if path:
        import config as _c
        _c.DB_PATH = path
        config.DB_PATH = path
        if getattr(_local, "con", None):
            _local.con.close()
            _local.con = None
    con().executescript(SCHEMA)
    con().commit()


def ex(sql, args=()):
    con().execute(sql, args)
    con().commit()


def one(sql, args=()):
    return con().execute(sql, args).fetchone()


def q(sql, args=()):
    return con().execute(sql, args).fetchall()


def kv_set(k, v):
    ex("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))


def kv_get(k, d=None):
    r = one("SELECT v FROM kv WHERE k=?", (k,))
    return r["v"] if r else d


def jload(s, d=None):
    if not s:
        return d
    try:
        return json.loads(s)
    except Exception:
        return d


def log(level, text):
    try:
        ex("INSERT INTO logs(level,text,ts) VALUES(?,?,?)", (level, text[:500], now()))
    except Exception:
        pass


def tehran_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M")
