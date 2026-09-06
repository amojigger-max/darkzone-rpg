"""👤 جنگ جهانی — بازیکن: شهروند → سرباز → فرمانده."""
import db
import texts


def active(uid) -> dict:
    """بازیکن ثبت‌نام‌شده با کشور — یا None."""
    p = get(uid)
    return p if p and p["country"] else None


def get(uid) -> dict:
    r = db.one("SELECT * FROM users WHERE uid=?", (uid,))
    return dict(r) if r else None


def ensure(uid, name=None, chat_id=None):
    db.ex("INSERT OR IGNORE INTO users(uid,name,joined,last_active,chat_id) VALUES(?,?,?,?,?)",
          (uid, texts.esc(name or "")[:32], db.now(), db.now(), chat_id))
    db.ex("UPDATE users SET last_active=?, chat_id=COALESCE(?,chat_id) WHERE uid=?",
          (db.now(), chat_id, uid))


def enlist(uid, country: str, name: str) -> bool:
    """ثبت‌نام در کشور — فقط یک بار."""
    if get(uid):
        return False
    import countries
    if country not in countries.COUNTRIES:
        return False
    db.ex("INSERT INTO users(uid,name,country,money,joined,last_active) VALUES(?,?,?,?,?,?)",
          (uid, texts.esc(name)[:32], country, 2000, db.now(), db.now()))
    return True


def xp_need(level: int) -> int:
    return 120 + level * 80


def gain_xp(uid, xp: int):
    p = get(uid)
    if not p:
        return
    lv, x = p["level"], p["xp"] + xp
    while x >= xp_need(lv):
        x -= xp_need(lv)
        lv += 1
    db.ex("UPDATE users SET xp=?, level=? WHERE uid=?", (x, lv, uid))


def card(uid) -> str:
    import countries
    p = get(uid)
    if not p:
        return "⛔ ثبت‌نام نکرده‌ای — «شروع»"
    c = countries.COUNTRIES.get(p["country"], {})
    t = texts
    import game.military as mil
    from game import politics
    party = politics.my_party(uid)
    return "\n".join([
        t.hdr("پرونده‌ی نظامی", "🎖"),
        t.row("نام", p["name"]),
        t.row("کشور", f"{c.get('flag','')} {c.get('name','—')}"),
        t.row("شاخه", mil.branch_name(p) or "غیرنظامی"),
        t.row("درجه", countries.rank_name(p["level"])),
        t.row("سطح / تجربه", f"{p['level']} · {p['xp']}/{xp_need(p['level'])}"),
        t.row("خزانه", f"💰 {p['money']:,}"),
        t.row("جان", f"❤️ {p['hp']}/{p['max_hp']}"),
        t.row("کشته‌ها", p["kills"]),
        t.row("عملیات جاسوسی", p["spy_ops"]),
        t.row("حزب", party["name"] if party else "—"),
        t.row("نقش", "👑 رهبر کشور" if p["is_leader"] else ("عضو حزب" if party else "شهروند")),
    ])


def ration(uid) -> str:
    """جیره‌ی روزانه + زنجیره‌ی حضور — روزهای پیوسته جایزه‌ی بیشتر."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    day = db.now() // 86400
    if db.kv_get(f"ration:{uid}") == str(day):
        return "🍞 جیره‌ی امروز را گرفتی — فردا برگرد."
    streak = int(db.kv_get(f"streak:{uid}", "0"))
    # دیروز گرفته؟ زنجیره ادامه؛ وگرنه ریست
    if db.kv_get(f"ration:{uid}") == str(day - 1):
        streak += 1
    else:
        streak = 1
    amount = 500 + min(7, streak) * 150      # روز ۷+: ۱۵۵۰
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (amount, uid))
    db.kv_set(f"ration:{uid}", str(day))
    db.kv_set(f"streak:{uid}", str(streak))
    import random as _r
    bonus = ""
    if streak >= 3 and _r.random() < 0.35:
        bonus = "\n🎁 صندوق ویژه‌ی حضور: یک تجهیز رایگان شانس داشت! (بگذار شانس بسنجد)"
    return (f"🍞 جیره‌ی روزانه: 💰 +{amount:,}\n"
            f"🔥 زنجیره‌ی حضور: {streak} روز پیوسته\n"
            f"خزانه: {get(uid)['money']:,}{bonus}")
