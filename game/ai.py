"""🧠 جنگ جهانی — مغز جهان: هر کشور مستقل فکر می‌کند، دشمنی می‌کند و پاسخ می‌دهد.

دکترین ۲۰۲۶:
• کشورها رقیب تاریخی خود را می‌شناسند و بی‌پروا به آن حمله می‌کنند
• هر جنگ فعال را خودشان پیش می‌برند — حتی وقتی بازیکن خواب است
• به حمله‌ی هر بازیکن پاسخ فوری می‌دهند: ضدحمله، فرسایش سپر، تحریم، کمک متحد
• جهان هیچ‌وقت ساکت نمی‌ماند.
"""
import random

import countries
import db
import texts
from game import defense, economy, geo

# رقابت‌های واقعی ۲۰۲۶ — (مهاجم بالقوه، هدف)
RIVALS = [
    ("us", "ru"), ("us", "cn"), ("us", "kp"),
    ("il", "ir"), ("il", "hz"), ("il", "sy"),
    ("ru", "ua"), ("kp", "kr"), ("in", "pk"),
    ("sa", "ir"), ("sa", "hz"), ("tr", "ru"),
    ("cn", "in"), ("gb", "ru"), ("fr", "ru"),
]

MAX_AI_WARS = 3


def _flag(cid: str) -> str:
    c = countries.COUNTRIES.get(cid)
    return f"{c['flag']} {c['name']}" if c else cid


def news_add(text: str):
    db.ex("INSERT INTO news(text,ts) VALUES(?,?)", (text, db.now()))
    db.ex("DELETE FROM news WHERE id NOT IN (SELECT id FROM news "
          "ORDER BY id DESC LIMIT 40)")


def news_feed() -> str:
    rows = db.q("SELECT text, ts FROM news ORDER BY id DESC LIMIT 5")
    t = texts
    lines = [t.hdr("اخبار جهان", "📰"), ""]
    if not rows:
        lines.append("🕊 خبر مهمی نیست — جهان نفس تازه می‌کند.")
    for r in rows:
        lines.append(f"▫️ {r['text']}")
    return "\n".join(lines)


def _in_war(cid: str) -> bool:
    return bool(db.one("SELECT 1 FROM wars WHERE status='active' AND (a=? OR b=?)",
                       (cid, cid)))


def _ai_strike(w):
    """یک موج AI در جبهه — قدرت لحظه‌ای برنده را تعیین می‌کند."""
    ca, cb = countries.COUNTRIES.get(w["a"]), countries.COUNTRIES.get(w["b"])
    if not ca or not cb:
        return None
    pa = (ca["mil"] + ca["tech"]) * random.uniform(0.6, 1.4)
    pb = (cb["mil"] + cb["tech"]) * random.uniform(0.6, 1.4)
    side = "a" if pa >= pb else "b"
    gain = random.randint(1, 4)
    return side, gain


def tick() -> list:
    """هر ۶۰ ثانیه — جهان زنده. خبرهای جدید را برمی‌گرداند."""
    out = []
    wars = db.q("SELECT * FROM wars WHERE status='active'")
    # ۱) پیشروی جبهه‌ها توسط خود کشورها
    for w in wars:
        if random.random() > 0.45:
            continue
        r = _ai_strike(w)
        if not r:
            continue
        side, gain = r
        col = "score_a" if side == "a" else "score_b"
        db.ex(f"UPDATE wars SET {col}={col}+? WHERE id=?", (gain, w["id"]))
        cid = w[side]
        ecid = w["b"] if side == "a" else w["a"]
        defense.ensure(ecid)
        db.ex("UPDATE defense SET level=MAX(5,level-1) WHERE cid=?", (ecid,))
        score = db.one(f"SELECT {col} s FROM wars WHERE id=?", (w["id"],))["s"]
        if score and score % 6 < gain:
            free = [c for c in geo.CITIES.get(ecid, []) if c not in geo.occupied(ecid)]
            if free:
                city = random.choice(free)
                if geo.occupy(ecid, city, cid):
                    out.append(f"🚩 {_flag(cid)} شهر <b>{city}</b>ِ {_flag(ecid)} را گرفت!")
    # ۲) اعلان جنگ تازه توسط یک رقیب بی‌جنگ
    if len(wars) < MAX_AI_WARS and random.random() < 0.12:
        free_pairs = [(a, b) for a, b in RIVALS
                      if not _in_war(a) and not _in_war(b)
                      and b not in _allies_flat(a)]
        if free_pairs:
            a, b = random.choice(free_pairs)
            db.ex("INSERT INTO wars(a,b,started,ends) VALUES(?,?,?,?)",
                  (a, b, db.now(), db.now() + 24 * 3600))
            from game import war as _war
            w2 = db.one("SELECT * FROM wars WHERE a=? AND b=? AND status='active' "
                        "ORDER BY id DESC", (a, b))
            if w2:
                _war._init_ammo(w2)
            economy.on_war_start()
            defense.ensure(a), defense.ensure(b)
            out.append(f"⚔️ {_flag(a)} به {_flag(b)} اعلان جنگ داد — جهان در آتش است!")
    # ۳) خبر اقتصادی مستقل
    if random.random() < 0.25:
        w = economy.world()
        out.append(f"📡 بازار: نفت ${w['oil']:.0f} · دلار ×{w['dollar']:.2f} · "
                   f"تورم {w['inflation'] * 100:.1f}٪")
    for line in out:
        news_add(line)
    return out


def _allies_flat(cid: str):
    rows = db.q("SELECT a, b FROM alliances WHERE a=? OR b=?", (cid, cid))
    return {r["a"] if r["b"] == cid else r["b"] for r in rows}


def respond_to_strike(attacker: str, defender: str, kind: str, hit: int) -> list:
    """پاسخ فوری کشورِ مورد حمله — در همان پیام حمله ظاهر می‌شود."""
    out = []
    dc = countries.COUNTRIES.get(defender)
    ac = countries.COUNTRIES.get(attacker)
    if not dc or not ac:
        return out
    w = db.one("SELECT * FROM wars WHERE status='active' AND "
               "((a=? AND b=?) OR (a=? AND b=?))",
               (attacker, defender, defender, attacker))
    if not w:
        return out
    # ضدحمله‌ی سازمان‌یافته: دشمن جبهه را پس می‌گیرد
    if hit and random.random() < 0.75:
        col = "score_a" if w["a"] == defender else "score_b"
        gain = random.randint(2, 5) + dc["mil"] // 2
        db.ex(f"UPDATE wars SET {col}={col}+? WHERE id=?", (gain, w["id"]))
        out.append(f"⚠️ پاسخ سریع {dc['name']}! جبهه +{gain} برای دشمن")
    # فرسایش سپر مهاجم با آتش متقابل
    layer = defense.KIND_LAYER.get(kind, "دفاع زمینی")
    if random.random() < 0.5:
        db.ex("UPDATE defense SET level=MAX(5,level-2) WHERE cid=? AND layer=?",
              (attacker, layer))
        out.append(f"💥 آتش متقابل — لایه‌ی {layer} کشورت آسیب دید («پدافند»)")
    # متحدینِ مدافع وارد می‌شوند
    for ally in _allies_flat(defender):
        if ally != attacker and random.random() < 0.5:
            col = "score_a" if w["a"] == defender else "score_b"
            db.ex(f"UPDATE wars SET {col}={col}+2 WHERE id=?", (w["id"],))
            out.append(f"🤝 {_flag(ally)} متحدش را یاری کرد: +2 دشمن")
            break
    # گاهی تحریم اقتصادی مهاجم
    if hit and random.random() < 0.15:
        economy.sanction_shock(attacker)
        out.append(f"🚫 {dc['name']} اقتصاد کشورت را تحریم کرد — تورم بالا رفت!")
        news_add(f"🚫 {dc['name']} علیه {ac['name']} تحریم اقتصادی اعلام کرد.")
    return out
