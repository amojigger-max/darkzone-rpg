"""🗄 جنگ جهانی — دیتابیس (SQLite WAL + thread-local)."""
import json
import contextlib
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import config

TZ = timezone(timedelta(hours=3), "Tehran")

# 🌍 جداسازی گروه‌ها — هر گروه دنیای خودش: games/<شناسه‌ی گروه>.db
import contextvars
import os

GAME = contextvars.ContextVar("game", default=None)   # شناسه‌ی گروهِ جاری
GAMES_DIR = "games"
_conns = {}                                            # مسیر → اتصال


def now() -> int:
    return int(time.time())


def game_path(chat_id) -> str:
    return f"{GAMES_DIR}/{chat_id}.db"


def list_games():
    """همه‌ی دنیاهای موجود (شناسه‌ی گروه‌ها)."""
    if not os.path.isdir(GAMES_DIR):
        return []
    return sorted(int(f[:-3]) for f in os.listdir(GAMES_DIR) if f.endswith(".db"))


def con():
    g = GAME.get()
    p = game_path(g) if g is not None else config.DB_PATH
    c = _conns.get(p)
    if c is None:
        if g is not None:
            os.makedirs(GAMES_DIR, exist_ok=True)
        c = sqlite3.connect(p, 30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=8000")
        c.execute("PRAGMA temp_store=MEMORY")
        _open_db(c)
        _conns[p] = c
    return c


def _open_db(c):
    """اسکیما + مهاجرت + ایندکس — روی هر دیتابیس."""
    c.executescript(SCHEMA)
    with contextlib.suppress(Exception):
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    c.executescript("""
CREATE INDEX IF NOT EXISTS ix_users_country ON users(country);
CREATE INDEX IF NOT EXISTS ix_users_active ON users(last_active);
CREATE INDEX IF NOT EXISTS ix_users_level ON users(level DESC);
CREATE INDEX IF NOT EXISTS ix_wars_status ON wars(status);
CREATE INDEX IF NOT EXISTS ix_inv_uid ON inventory(uid);
""")
    c.commit()


def _migrate_legacy():
    """دنیای قدیمیِ واحد → دنیای گروه اصلی."""
    if not os.path.exists("worldwar.db") or list_games():
        return
    chat = None
    try:
        lc = sqlite3.connect("worldwar.db")
        r = lc.execute("SELECT v FROM kv WHERE k='main_group'").fetchone()
        if r:
            chat = int(r[0])
        else:
            r = lc.execute("SELECT chat_id FROM users WHERE chat_id IS NOT NULL "
                           "AND chat_id < 0 LIMIT 1").fetchone()
            if r:
                chat = int(r[0])
        lc.close()
    except Exception:
        pass
    if chat is None:
        return
    os.makedirs(GAMES_DIR, exist_ok=True)
    os.replace("worldwar.db", game_path(chat))
    for ext in ("-wal", "-shm"):
        if os.path.exists("worldwar.db" + ext):
            os.replace("worldwar.db" + ext, game_path(chat) + ext)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    uid INTEGER PRIMARY KEY,
    name TEXT, country TEXT, branch TEXT,
    rank INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
    money INTEGER DEFAULT 1000,
    hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,
    kills INTEGER DEFAULT 0, spy_ops INTEGER DEFAULT 0,
    party_id INTEGER, is_leader INTEGER DEFAULT 0,
    joined INTEGER, last_active INTEGER, chat_id INTEGER, username TEXT
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
CREATE TABLE IF NOT EXISTS defense (
    cid TEXT, layer TEXT, level INTEGER DEFAULT 30, hp INTEGER DEFAULT 100,
    PRIMARY KEY(cid, layer)
);
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT, ts INTEGER
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT, text TEXT, ts INTEGER
);
"""


def init(path: str = None):
    if path:                       # تست‌ها: مسیر صریح (تک‌دنیا)
        for p, c in list(_conns.items()):
            with contextlib.suppress(Exception):
                c.close()
        _conns.clear()
        config.DB_PATH = path
    else:                          # بوت تولید: دنیای قدیمی + همه‌ی دنیاها
        _migrate_legacy()
        for g in list_games():
            with contextlib.suppress(Exception):
                _open_db(con_for(g))
    if not path:
        return
    _open_db(con())


def con_for(chat_id):
    """اتصال به دنیای مشخص — برای حلقه‌ها و ذخیره‌سازی."""
    os.makedirs(GAMES_DIR, exist_ok=True)
    p = game_path(chat_id)
    c = _conns.get(p)
    if c is None:
        c = sqlite3.connect(p, 30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=8000")
        c.execute("PRAGMA temp_store=MEMORY")
        _open_db(c)
        _conns[p] = c
    return c


def ex(sql, args=()):
    con().execute(sql, args)
    con().commit()


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
