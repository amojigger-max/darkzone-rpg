"""SQLite schemas; additive upgrades, never a reset on boot."""

SCHEMA = "\nCREATE TABLE IF NOT EXISTS users (\n    uid INTEGER PRIMARY KEY,\n    name TEXT, country TEXT, branch TEXT,\n    rank INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,\n    money INTEGER DEFAULT 1000,\n    hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,\n    kills INTEGER DEFAULT 0, spy_ops INTEGER DEFAULT 0,\n    party_id INTEGER, is_leader INTEGER DEFAULT 0,\n    joined INTEGER, last_active INTEGER, chat_id INTEGER, username TEXT\n);\nCREATE TABLE IF NOT EXISTS items (\n    iid TEXT PRIMARY KEY, name TEXT, emoji TEXT, country TEXT,\n    atk INTEGER, guard INTEGER, price INTEGER,\n    max_dur INTEGER DEFAULT 100, img TEXT\n);\nCREATE TABLE IF NOT EXISTS inventory (\n    uid INTEGER, iid TEXT, qty INTEGER DEFAULT 1, dur INTEGER,\n    PRIMARY KEY(uid, iid)\n);\nCREATE TABLE IF NOT EXISTS parties (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    name TEXT, country TEXT, ideology TEXT, leader_uid INTEGER,\n    members INTEGER DEFAULT 1, power INTEGER DEFAULT 10,\n    rebel INTEGER DEFAULT 0, created INTEGER\n);\nCREATE TABLE IF NOT EXISTS statements (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    party_id INTEGER, uid INTEGER, title TEXT, body TEXT, ts INTEGER\n);\nCREATE TABLE IF NOT EXISTS wars (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    a TEXT, b TEXT, status TEXT DEFAULT 'active',\n    score_a INTEGER DEFAULT 0, score_b INTEGER DEFAULT 0,\n    started INTEGER, ends INTEGER, winner TEXT\n);\nCREATE TABLE IF NOT EXISTS spyops (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    uid INTEGER, target TEXT, success INTEGER, info TEXT, ts INTEGER\n);\nCREATE TABLE IF NOT EXISTS alliances (\n    a TEXT, b TEXT, created INTEGER\n);\nCREATE TABLE IF NOT EXISTS defense (\n    cid TEXT, layer TEXT, level INTEGER DEFAULT 30, hp INTEGER DEFAULT 100,\n    PRIMARY KEY(cid, layer)\n);\nCREATE TABLE IF NOT EXISTS news (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    text TEXT, ts INTEGER\n);\nCREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);\nCREATE TABLE IF NOT EXISTS logs (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    level TEXT, text TEXT, ts INTEGER\n);\n"

UPGRADE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_versions(version TEXT PRIMARY KEY, applied INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS country_claims(
 country TEXT PRIMARY KEY, uid INTEGER NOT NULL UNIQUE REFERENCES users(uid) ON DELETE CASCADE,
 claimed INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS city_state(
 cid TEXT NOT NULL, city INTEGER NOT NULL, name TEXT NOT NULL,
 power INTEGER NOT NULL DEFAULT 100 CHECK(power BETWEEN 0 AND 100),
 airport INTEGER NOT NULL DEFAULT 100 CHECK(airport BETWEEN 0 AND 100),
 port INTEGER NOT NULL DEFAULT 0 CHECK(port BETWEEN 0 AND 100),
 industry INTEGER NOT NULL DEFAULT 100 CHECK(industry BETWEEN 0 AND 100),
 garrison INTEGER NOT NULL DEFAULT 100 CHECK(garrison BETWEEN 0 AND 100),
 PRIMARY KEY(cid, city)
);
CREATE TABLE IF NOT EXISTS structures(
 cid TEXT NOT NULL, city INTEGER NOT NULL, kind TEXT NOT NULL,
 level INTEGER NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 3),
 hp INTEGER NOT NULL DEFAULT 100 CHECK(hp BETWEEN 0 AND 100),
 ready_at INTEGER NOT NULL, created INTEGER NOT NULL,
 PRIMARY KEY(cid, city, kind),
 FOREIGN KEY(cid, city) REFERENCES city_state(cid, city) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS campaigns(
 war_id INTEGER PRIMARY KEY REFERENCES wars(id) ON DELETE CASCADE,
 mode TEXT NOT NULL CHECK(mode IN ('border','limited','siege','total')),
 ready_at INTEGER NOT NULL, min_end INTEGER NOT NULL,
 rounds_a INTEGER NOT NULL DEFAULT 0, rounds_b INTEGER NOT NULL DEFAULT 0,
 last_a INTEGER NOT NULL DEFAULT 0, last_b INTEGER NOT NULL DEFAULT 0,
 sea_a INTEGER NOT NULL DEFAULT 0, sea_b INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sieges(
 war_id INTEGER NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
 attacker TEXT NOT NULL, defender TEXT NOT NULL, city INTEGER NOT NULL,
 pressure INTEGER NOT NULL DEFAULT 0 CHECK(pressure BETWEEN 0 AND 100),
 rounds INTEGER NOT NULL DEFAULT 0, first_at INTEGER NOT NULL,
 last_at INTEGER NOT NULL, captured_at INTEGER,
 PRIMARY KEY(war_id, attacker, defender, city)
);
CREATE TABLE IF NOT EXISTS missions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 war_id INTEGER NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
 uid INTEGER NOT NULL, attacker TEXT NOT NULL, defender TEXT NOT NULL,
 kind TEXT NOT NULL, shots INTEGER NOT NULL CHECK(shots BETWEEN 1 AND 5),
 city INTEGER NOT NULL, target TEXT NOT NULL, equipment TEXT NOT NULL,
 launched INTEGER NOT NULL, due INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','resolved','cancelled','failed')),
 result TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_missions_due ON missions(status, due);
CREATE TABLE IF NOT EXISTS reward_grants(
 grant_id TEXT NOT NULL, uid INTEGER NOT NULL, country TEXT NOT NULL,
 amount INTEGER NOT NULL CHECK(amount >= 0), equipment TEXT NOT NULL,
 reason TEXT NOT NULL, created INTEGER NOT NULL, awarded_at INTEGER,
 PRIMARY KEY(grant_id, uid)
);
CREATE TABLE IF NOT EXISTS reset_history(
 reset_id TEXT PRIMARY KEY, game_id INTEGER NOT NULL, applied INTEGER NOT NULL,
 backup_path TEXT NOT NULL, backup_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox(
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
 chat_id INTEGER NOT NULL, body TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','unknown','blocked')),
 attempts INTEGER NOT NULL DEFAULT 0, next_at INTEGER NOT NULL DEFAULT 0,
 message_id INTEGER, error TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL, sent_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox(status, next_at, id);
CREATE TABLE IF NOT EXISTS ledger(
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, actor INTEGER,
 detail TEXT NOT NULL, ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ledger_time ON ledger(ts);
CREATE TABLE IF NOT EXISTS invest_accrual(
 uid INTEGER PRIMARY KEY REFERENCES users(uid) ON DELETE CASCADE,
 last_ts INTEGER NOT NULL, micro_dollars INTEGER NOT NULL DEFAULT 0 CHECK(micro_dollars >= 0)
);
CREATE INDEX IF NOT EXISTS ix_users_country ON users(country);
CREATE INDEX IF NOT EXISTS ix_users_active ON users(last_active);
CREATE INDEX IF NOT EXISTS ix_users_level ON users(level DESC);
CREATE INDEX IF NOT EXISTS ix_wars_status ON wars(status);
CREATE INDEX IF NOT EXISTS ix_inv_uid ON inventory(uid);
CREATE TRIGGER IF NOT EXISTS money_nonnegative_update BEFORE UPDATE OF money ON users
 WHEN NEW.money < 0 OR typeof(NEW.money) != 'integer'
 BEGIN SELECT RAISE(ABORT, 'invalid treasury'); END;
CREATE TRIGGER IF NOT EXISTS money_nonnegative_insert BEFORE INSERT ON users
 WHEN NEW.money < 0 OR typeof(NEW.money) != 'integer'
 BEGIN SELECT RAISE(ABORT, 'invalid treasury'); END;
CREATE TRIGGER IF NOT EXISTS inventory_valid_update BEFORE UPDATE ON inventory
 WHEN NEW.qty < 0 OR NEW.dur < 0 OR NEW.dur > 100
 BEGIN SELECT RAISE(ABORT, 'invalid inventory'); END;
CREATE TRIGGER IF NOT EXISTS inventory_valid_insert BEFORE INSERT ON inventory
 WHEN NEW.qty < 0 OR NEW.dur < 0 OR NEW.dur > 100
 BEGIN SELECT RAISE(ABORT, 'invalid inventory'); END;
"""

UPGRADE_SCHEMA += """
CREATE TABLE IF NOT EXISTS operation_plans(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 uid INTEGER NOT NULL REFERENCES users(uid), country TEXT NOT NULL, target TEXT NOT NULL,
 name TEXT NOT NULL, doctrine TEXT NOT NULL, mode TEXT NOT NULL,
 created INTEGER NOT NULL, ready_at INTEGER NOT NULL, expires INTEGER NOT NULL,
 war_id INTEGER REFERENCES wars(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','active','completed','cancelled')),
 uses INTEGER NOT NULL DEFAULT 0 CHECK(uses>=0)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_one_operation_country ON operation_plans(country) WHERE status IN ('planned','active');
CREATE TABLE IF NOT EXISTS missile_launches(
 id INTEGER PRIMARY KEY AUTOINCREMENT, war_id INTEGER NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
 cid TEXT NOT NULL, shots INTEGER NOT NULL CHECK(shots BETWEEN 1 AND 3), ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_missile_budget ON missile_launches(war_id,cid,ts);
CREATE TABLE IF NOT EXISTS un_resolutions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER NOT NULL REFERENCES users(uid),
 kind TEXT NOT NULL, target TEXT NOT NULL, eligible TEXT NOT NULL, data TEXT NOT NULL,
 created INTEGER NOT NULL, expires INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'voting' CHECK(status IN ('voting','passed','rejected','expired')),
 result TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS un_votes(
 resolution_id INTEGER NOT NULL REFERENCES un_resolutions(id) ON DELETE CASCADE,
 country TEXT NOT NULL, uid INTEGER NOT NULL, vote TEXT NOT NULL CHECK(vote IN ('yes','no','abstain')),
 ts INTEGER NOT NULL, PRIMARY KEY(resolution_id,country)
);
"""

UPGRADE_SCHEMA += """
CREATE TABLE IF NOT EXISTS city_energy(
 cid TEXT NOT NULL, city INTEGER NOT NULL,
 crude_milli INTEGER NOT NULL DEFAULT 0 CHECK(crude_milli>=0),
 fuel_milli INTEGER NOT NULL DEFAULT 120000 CHECK(fuel_milli>=0),
 last_ts INTEGER NOT NULL, process_remainder INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(cid,city), FOREIGN KEY(cid,city) REFERENCES city_state(cid,city) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS strait_closures(
 id INTEGER PRIMARY KEY AUTOINCREMENT, gate TEXT NOT NULL,
 started INTEGER NOT NULL, ended INTEGER NOT NULL CHECK(ended>=started)
);
CREATE INDEX IF NOT EXISTS ix_closure_time ON strait_closures(gate,started,ended);
CREATE TABLE IF NOT EXISTS tankers(
 id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT NOT NULL, creator INTEGER NOT NULL,
 name TEXT NOT NULL, class TEXT NOT NULL, home_city INTEGER NOT NULL,
 hp INTEGER NOT NULL DEFAULT 100 CHECK(hp BETWEEN 0 AND 100),
 status TEXT NOT NULL DEFAULT 'building' CHECK(status IN ('building','docked','reserved','sailing','returning','seized','sunk')),
 build_work INTEGER NOT NULL CHECK(build_work>=0), last_build INTEGER NOT NULL,
 repair_at INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tankers_country ON tankers(country,status);
CREATE TABLE IF NOT EXISTS voyages(
 id INTEGER PRIMARY KEY AUTOINCREMENT, ship_id INTEGER NOT NULL REFERENCES tankers(id),
 seller INTEGER NOT NULL, buyer INTEGER NOT NULL,
 source TEXT NOT NULL, source_city INTEGER NOT NULL, dest TEXT NOT NULL, dest_city INTEGER NOT NULL,
 cargo TEXT NOT NULL CHECK(cargo IN ('crude','fuel')), amount INTEGER NOT NULL CHECK(amount>0),
 remaining_milli INTEGER NOT NULL DEFAULT 0 CHECK(remaining_milli>=0),
 price INTEGER NOT NULL CHECK(price>=0), escrow INTEGER NOT NULL DEFAULT 0 CHECK(escrow>=0),
 status TEXT NOT NULL DEFAULT 'offered' CHECK(status IN ('offered','outbound','held','unloading','returning','return_held','returned','cancelled','sunk')),
 outcome TEXT NOT NULL DEFAULT '', offered INTEGER NOT NULL, expires INTEGER NOT NULL,
 started INTEGER, deadline INTEGER, route TEXT NOT NULL DEFAULT '[]',
 leg INTEGER NOT NULL DEFAULT 0, leg_due INTEGER NOT NULL DEFAULT 0,
 region TEXT NOT NULL DEFAULT '', delivered_at INTEGER, completed_at INTEGER,
 fees TEXT NOT NULL DEFAULT '{}', escort_count INTEGER NOT NULL DEFAULT 0 CHECK(escort_count BETWEEN 0 AND 3)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_one_live_voyage ON voyages(ship_id)
 WHERE status IN ('offered','outbound','held','unloading','returning','return_held');
CREATE TABLE IF NOT EXISTS naval_escorts(
 voyage_id INTEGER NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
 uid INTEGER NOT NULL, iid TEXT NOT NULL, units INTEGER NOT NULL CHECK(units>0),
 guard REAL NOT NULL, wear INTEGER NOT NULL DEFAULT 0 CHECK(wear BETWEEN 0 AND 100),
 PRIMARY KEY(voyage_id,iid)
);
"""

UPGRADE_SCHEMA += """
CREATE TABLE IF NOT EXISTS reward_stock(
 grant_id TEXT NOT NULL, uid INTEGER NOT NULL, iid TEXT NOT NULL,
 qty INTEGER NOT NULL CHECK(qty>=0), created INTEGER NOT NULL,
 PRIMARY KEY(grant_id,uid,iid),
 FOREIGN KEY(grant_id,uid) REFERENCES reward_grants(grant_id,uid) ON DELETE CASCADE
);
"""
