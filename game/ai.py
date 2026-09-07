"""🧠 گزارشگر بازار — NPC خاموش است.

دکترین ۲۰۲۶ (به‌روز):
• هیچ دولت NPC جنگ نمی‌کند و به جای بازیکن بازی نمی‌کند
• جنگ فقط با اعلانِ رهبرِ بازیکن شروع می‌شود و فقط ضربه‌ی خود بازیکنان امتیاز می‌آورد
• کشورهای خالی منتظر بازیکنند — هر بازیکنی می‌تواند رهبرشان شود
• تنها صدای خودکار: خبر لحظه‌ای بازار.
"""
import random

import countries
import db
import texts
from game import economy

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
    """هر ۶۰ ثانیه — فقط خبر بازار. NPC خاموش است: بازیکن جای دولت می‌نشیند."""
    out = []
    # ۳) خبر اقتصادی مستقل
    if random.random() < 0.08:
        w = economy.world()
        oil, usd, inf = w["oil"], w["dollar"], w["inflation"] * 100
        out.append(f"📡 بازار: نفت ${texts.fa(f'{oil:.0f}')} · "
                   f"دلار ×{texts.fa(f'{usd:.2f}')} · تورم {texts.fa(f'{inf:.1f}')}٪")
    for line in out:
        news_add(line)
    return out


def _has_leader(cid: str) -> bool:
    """کشور با رهبرِ واقعی — دولت NPC دخالت نمی‌کند."""
    return bool(db.one("SELECT 1 FROM users WHERE country=? AND is_leader=1 "
                       "LIMIT 1", (cid,)))


def _allies_flat(cid: str):
    rows = db.q("SELECT a, b FROM alliances WHERE a=? OR b=?", (cid, cid))
    return {r["a"] if r["b"] == cid else r["b"] for r in rows}


def respond_to_strike(attacker: str, defender: str, kind: str, hit: int) -> list:
    """🤖 NPC خاموش — هیچ‌کس به جای بازیکن نمی‌جنگد؛ امتیاز فقط از ضربه‌ی خود بازیکنان."""
    return []
