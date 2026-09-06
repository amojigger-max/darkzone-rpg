"""🛡 جنگ جهانی — سپر ملی: لایه‌های دفاعی مستقل هر کشور.

۶ لایه دقیق:
🚀 ضد موشک — موشک‌ها را در آسمان می‌گیرد
✈️ ضد هوایی — جنگنده‌ها را می‌اندازد
🛩 ضد پهپاد — پهپادها را گمراه می‌کند
🚢 ضد دریایی — ناوها را در آب می‌شکند
🚜 دفاع زمینی — تانک‌ها را در خاک متوقف می‌کند
⚡ جنگ الکترونیک — آسیبِ هر ضربه‌ی عبوری را کم می‌کند

هر کشور سطح خودش را دارد — اعضا با پول تقویتش می‌کنند، حمله‌ی دشمن فرسایشش می‌دهد.
"""
import random

import countries
import db
import texts

LAYERS = {
    "ضد موشک": "🚀",
    "ضد هوایی": "✈️",
    "ضد پهپاد": "🛩",
    "ضد دریایی": "🚢",
    "دفاع زمینی": "🚜",
    "جنگ الکترونیک": "⚡",
}

# نوع حمله → لایه‌ی مقابله‌کننده
KIND_LAYER = {
    "موشکی": "ضد موشک",
    "هوایی": "ضد هوایی",
    "پهپادی": "ضد پهپاد",
    "دریایی": "ضد دریایی",
    "زمینی": "دفاع زمینی",
    "توپخانه": "ضد موشک",
    "پدافندی": "جنگ الکترونیک",
}


def ensure(cid: str):
    """ساخت لایه‌ها در اولین استفاده — سطح پایه از قدرت کشور."""
    c = countries.COUNTRIES.get(cid)
    if not c:
        return
    base = 18 + c["mil"] * 4 + c["tech"] * 3
    spec, pct, _ = countries.spec_of(cid)
    if spec == "پدافندی":
        base += pct // 2          # کشورهای پدافندی‌تخصص از اول قوی‌ترند
    base = min(88, base)
    for layer in LAYERS:
        lv = base + random.randint(-4, 4)
        if layer == "جنگ الکترونیک":
            lv = base - 6
        db.ex("INSERT OR IGNORE INTO defense(cid,layer,level,hp) VALUES(?,?,?,?)",
              (cid, layer, max(8, min(90, lv)), 100))


def level(cid: str, layer: str) -> int:
    ensure(cid)
    r = db.one("SELECT level FROM defense WHERE cid=? AND layer=?", (cid, layer))
    return r["level"] if r else 10


def absorb(cid: str, kind: str, shots: int):
    """(شانس دفع، ضریب کاهش آسیب) — هر شلیک لایه‌ی مقابل را فرسوده می‌کند."""
    layer = KIND_LAYER.get(kind, "دفاع زمینی")
    lvl = level(cid, layer)
    ew = level(cid, "جنگ الکترونیک")
    db.ex("UPDATE defense SET level=MAX(5,level-?), hp=MAX(10,hp-?*3) "
          "WHERE cid=? AND layer=?", (random.randint(1, 3), shots, cid, layer))
    chance = min(0.85, lvl / 115.0)
    dmg_mult = 1.0 - min(0.40, ew / 300.0)
    return chance, dmg_mult, layer, lvl


def restore(cid: str, layer: str, amount: int = 2):
    db.ex("UPDATE defense SET level=MIN(95,level+?), hp=MIN(100,hp+?*4) "
          "WHERE cid=? AND layer=?", (amount, amount, cid, layer))


def strengthen(uid: int, layer: str) -> str:
    """عضو کشور با پول، لایه‌ی دفاعی کشورش را قوی می‌کند."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if layer not in LAYERS:
        return "⛔ لایه نامعتبر."
    cid = p["country"]
    lvl = level(cid, layer)
    cost = 350 + lvl * 9
    if p["money"] < cost:
        return f"💰 پول کم است — نیاز: {cost:,}"
    if lvl >= 95:
        return "🏆 این لایه در اوج است."
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (cost, uid))
    restore(cid, layer, 3)
    c = countries.COUNTRIES[cid]
    return (f"🛡 {LAYERS[layer]} لایه‌ی <b>{layer}</b> کشور {c['flag']} {c['name']} "
            f"تقویت شد!\nسطح: {lvl} ← <b>{level(cid, layer)}</b> · 💰 −{cost:,}\n"
            f"آفرین سرباز — دفاع وطن از تو یاد خواهد کرد.")


def status(cid: str) -> str:
    """پنل تمیز سپر ملی."""
    ensure(cid)
    c = countries.COUNTRIES.get(cid)
    if not c:
        return "⛔ کشور نامعتبر."
    t = texts
    rows = db.q("SELECT layer, level, hp FROM defense WHERE cid=? "
                "ORDER BY layer", (cid,))
    lines = [t.hdr(f"سپر ملی {c['name']}", "🛡"), ""]
    for r in rows:
        bar = "▰" * (r["level"] // 10) + "▱" * (10 - r["level"] // 10)
        lines.append(f"{LAYERS.get(r['layer'], '▪️')} {r['layer']}: "
                     f"<b>{r['level']}</b> {bar}")
    lines += ["", "⚡ جنگ الکترونیک آسیبِ ضربه‌های عبوری را کم می‌کند.",
              "➕ تقویت: دکمه‌های زیر یا «تقویت ضد موشک»"]
    return "\n".join(lines)
