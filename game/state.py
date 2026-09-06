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
    """ثبت‌نام در کشور — فقط یک بار (ردیفِ موجود بدون کشور را کامل می‌کند)."""
    import countries
    if country not in countries.COUNTRIES:
        return False
    p = get(uid)
    if p:
        if p["country"]:
            return False
        db.ex("UPDATE users SET country=?, "
              "money=CASE WHEN money>0 THEN money ELSE 2000 END, "
              "name=CASE WHEN name='' OR name IS NULL THEN ? ELSE name END "
              "WHERE uid=?", (country, texts.esc(name)[:32], uid))
        return True
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
    p = active(uid)
    if not p:
        return "⛔ ثبت‌نام نکرده‌ای — «شروع»"
    c = countries.COUNTRIES.get(p["country"], {})
    t = texts
    import game.military as mil
    from game import politics
    party = politics.my_party(uid)
    spec, pct, sname = countries.spec_of(p["country"])
    return "\n".join([
        t.hdr("پرونده‌ی نظامی", "🎖"),
        t.row("نام", p["name"]),
        t.row("کشور", f"{c.get('flag','')} {c.get('name','—')}"),
        t.row("تخصص", f"🎖 {sname} — +{t.fa(pct)}٪ {spec}"),
        t.row("شاخه", mil.branch_name(p) or "غیرنظامی"),
        t.row("درجه", countries.rank_name(p["level"])),
        t.row("سطح", f"{t.fa(p['level'])} · تجربه {t.fa(p['xp'])}/{t.fa(xp_need(p['level']))}"),
        t.row("خزانه", f"💰 {t.money(p['country'], p['money'])}"),
        t.row("جان", f"❤️ {t.fa(p['hp'])}/{t.fa(p['max_hp'])}"),
        t.row("سوابق", f"⚔️ {t.fa(p['kills'])} کشته · 🕵 {t.fa(p['spy_ops'])} جاسوسی"),
        t.row("حزب", party["name"] if party else "—"),
        t.row("نقش", "👑 رهبر کشور" if p["is_leader"] else ("عضو حزب" if party else "شهروند")),
    ] + ([medals(uid)] if medals(uid) else []))


def medals(uid) -> str:
    """نشان‌ها بر اساس دستاورد واقعی."""
    p = get(uid)
    if not p:
        return ""
    out = []
    if p["kills"] >= 10:
        out.append("🥇 نشان شجاعت")
    if p["spy_ops"] >= 5:
        out.append("🕵 نشان جاسوس")
    if p["level"] >= 5:
        out.append("🎖 افسر")
    if p["level"] >= 10:
        out.append("⭐ فرمانده")
    if int(db.kv_get(f"streak:{uid}", "0")) >= 5:
        out.append("🔥 سرباز وفادار")
    return "🏅 " + " · ".join(out) if out else ""


def geo_colony(cid):
    from game import geo
    return geo.colony_of(cid)


def geo_colonies(cid):
    from game import geo
    return geo.colonies_of(cid)


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
    import countries
    t = texts
    amount = 350 + min(7, streak) * 120      # سخت‌تر — روز ۷+: ۱۱۹۰
    tax_note = ""
    col = geo_colony(p["country"])
    if col:                                    # ⛓ زیر یوغ مستعمره
        cut = amount * 3 // 10
        amount -= cut
        tax_note = f"\n⛓ مالیات مستعمره‌ای به {countries.COUNTRIES[col]['name']}: −{t.fa(cut)}"
    mine = geo_colonies(p["country"])
    if mine:                                   # 👑 خراج مستعمره‌ها
        add = amount * len(mine) // 6
        amount += add
        tax_note = f"\n👑 خراج {t.fa(len(mine))} مستعمره: +{t.fa(add)}"
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (amount, uid))
    db.kv_set(f"ration:{uid}", str(day))
    db.kv_set(f"streak:{uid}", str(streak))
    from game import quests
    quests.on_event(uid, "جیره")
    import random as _r
    bonus = ""
    if streak >= 3 and _r.random() < 0.35:
        bonus = "\n🎁 صندوق ویژه‌ی حضور: یک تجهیز رایگان شانس داشت! (بگذار شانس بسنجد)"
    cur = texts.money(p["country"], amount)
    return (f"🍞 جیره‌ی روزانه: {cur}\n"
            f"🔥 زنجیره‌ی حضور: {texts.fa(streak)} روز پیوسته\n"
            f"خزانه: {texts.money(p['country'], get(uid)['money'])}{tax_note}{bonus}")
