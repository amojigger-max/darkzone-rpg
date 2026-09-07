"""👤 جنگ جهانی — بازیکن: شهروند → سرباز → فرمانده."""
import json
import db
import texts


def active(uid) -> dict:
    """بازیکن ثبت‌نام‌شده با کشور — یا None."""
    p = get(uid)
    return p if p and p["country"] else None


def get(uid) -> dict:
    r = db.one("SELECT * FROM users WHERE uid=?", (uid,))
    return dict(r) if r else None


def ensure(uid, name=None, chat_id=None, username=None):
    db.ex("INSERT OR IGNORE INTO users(uid,name,joined,last_active,chat_id,username,money) "
          "VALUES(?,?,?,?,?,?,1000)",
          (uid, texts.esc(name or "")[:32], db.now(), db.now(), chat_id, username))
    db.ex("UPDATE users SET last_active=?, chat_id=COALESCE(?,chat_id) WHERE uid=?",
          (db.now(), chat_id, uid))
    # نام جای‌نگهدار (PlayerNN) با نام واقعی تازه می‌شود + @آیدی ذخیره
    if name or username:
        row = db.one("SELECT name, username FROM users WHERE uid=?", (uid,))
        if row:
            old = row["name"] or ""
            if name and (not old or old.startswith("Player")):
                db.ex("UPDATE users SET name=? WHERE uid=?", (texts.esc(name)[:32], uid))
            if username and username != (row["username"] or ""):
                db.ex("UPDATE users SET username=? WHERE uid=?", (username, uid))


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
              "money=CASE WHEN money>0 THEN money ELSE 1000 END, "
              "name=CASE WHEN name='' OR name IS NULL THEN ? ELSE name END "
              "WHERE uid=?", (country, texts.esc(name)[:32], uid))
        return True
    db.ex("INSERT INTO users(uid,name,country,money,joined,last_active) VALUES(?,?,?,?,?,?)",
          (uid, texts.esc(name)[:32], country, 1000, db.now(), db.now()))
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
        t.row("کشور", f"{c.get('flag', '')} {c.get('name', '—')}"),
        t.row("نقش", "👑 رهبر کشور" if p["is_leader"] else ("عضو حزب" if party else "شهروند")),
        t.DASH,
        t.row("تخصص", f"🎖 {sname} — +{t.fa(pct)}٪ {spec}"),
        t.row("شاخه", mil.branch_name(p) or "غیرنظامی"),
        t.row("درجه", countries.rank_name(p["level"])),
        t.row("تجربه", f"{t.fa(p['xp'])}/{t.fa(xp_need(p['level']))}"),
        t.DASH,
        t.row("خزانه", f"💰 {t.money(p['country'], p['money'])}"),
        t.row("جان", f"❤️ {t.fa(p['hp'])}/{t.fa(p['max_hp'])}"),
        t.row("سوابق", f"⚔️ {t.fa(p['kills'])} · 🕵 {t.fa(p['spy_ops'])}"),
        t.row("حزب", party["name"] if party else "—"),
    ] + ([t.DASH, medals(uid)] if medals(uid) else []))


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
    amount = 200 + min(7, streak) * 60      # روز ۷+: ۶۲۰
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
    # 🛢 سهم نفت — درآمد واقعی کشور، بین بازیکنانش
    from game import economy as _eco
    oil = _eco.oil_share(p["country"])
    amount += oil
    oil_note = (f"\n🛢 سهم نفت کشورت: +{t.money(p['country'], oil)}"
                if oil >= 10 else "")
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (amount, uid))
    db.kv_set(f"ration:{uid}", str(day))
    db.kv_set(f"streak:{uid}", str(streak))
    from game import quests
    quests.on_event(uid, "جیره")
    # 🎁 صندوق ویژه‌ی حضور — واقعی: ۳۵٪ شانس جایزه برای سربازان وفادار (۳ روز+)
    bonus = ""
    if streak >= 3:
        import random as _r
        if _r.random() < 0.35:
            own = {r["iid"] for r in db.q("SELECT iid FROM inventory WHERE uid=?",
                                          (uid,))}
            cands = [iid for iid in countries.COUNTRIES[p["country"]]["items"]
                     if iid not in own]
            if cands:
                iid = _r.choice(cands)
                db.ex("INSERT OR REPLACE INTO inventory(uid,iid,qty,dur) "
                      "VALUES(?,?,1,100)", (uid, iid))
                it = countries.ITEMS[iid]
                bonus = f"\n🎁 صندوق ویژه‌ی حضور: {it[1]} {it[0]} رایگان رسید!"
            else:
                db.ex("UPDATE users SET money=money+150 WHERE uid=?", (uid,))
                bonus = "\n🎁 صندوق ویژه‌ی حضور: +۱۵۰ سکه‌ی جایزه!"
    cur = texts.money(p["country"], amount)
    return (f"🍞 جیره‌ی روزانه: {cur}{oil_note}\n"
            f"🔥 زنجیره‌ی حضور: {texts.fa(streak)} روز پیوسته\n"
            f"خزانه: {texts.money(p['country'], get(uid)['money'])}{tax_note}{bonus}")


def daily(uid) -> str:
    """🎁 جایزه‌ی روزانه با رگه‌ی پیوسته — هر روز بیا، بیشتر ببر."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    day = db.now() // 86400
    st = db.jload(db.kv_get(f"daily:{uid}"), None) or {}
    last, streak = st.get("day"), int(st.get("streak", 0))
    if last == day:
        nxt = 200 + 150 * min(streak + 1, 7)
        return "\n".join([
            t.hdr("جایزه‌ی روزانه", "🎁"),
            f"⏳ امروز جایزه‌ات را گرفتی — 🔥 رگه: {t.fa(streak)} روز",
            f"💰 فردا: {t.money(p['country'], nxt)}",
            "هر روز بیا تا رگه نشکند!",
        ])
    streak = streak + 1 if last == day - 1 else 1
    prize = 200 + 150 * min(streak, 7)
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (prize, uid))
    db.kv_set(f"daily:{uid}", json.dumps({"day": day, "streak": streak},
                                         ensure_ascii=False))
    lines = [t.hdr("جایزه‌ی روزانه", "🎁"),
             f"🔥 رگه‌ی پیوسته: {t.fa(streak)} روز",
             f"💰 +{t.money(p['country'], prize)} دریافت شد"]
    if last is not None and last < day - 1:
        lines.append("⚠️ رگه‌ات قطع شده بود — از یک شروع شد")
    if streak >= 7:
        lines.append("👑 هفته‌ی کامل! حداکثر جایزه قفل شد")
    lines.append(f"📅 فردا: {t.money(p['country'], 200 + 150 * min(streak + 1, 7))}")
    return "\n".join(lines)


WORK_CD = 300          # ⏱ هر ۵ دقیقه یک کار — درآمد رایگانِ همیشه‌در-دسترس


def work(uid) -> str:
    """🔨 کار کن و پول بگیر — رایگان، همیشه در جریان بازی."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    if db.now() - int(db.kv_get(f"work:{uid}", "0")) < WORK_CD:
        left = WORK_CD - (db.now() - int(db.kv_get(f"work:{uid}", "0")))
        return (f"⏳ خسته‌ای! {t.fa(max(60, (left + 59) // 60))} دقیقه دیگر "
                "دوباره کار کن.")
    db.kv_set(f"work:{uid}", str(db.now()))
    pay = 120 + p["level"] * 10
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (pay, uid))
    return "\n".join([
        t.hdr("شیفت کاری تمام شد", "🔨"),
        f"💪 کار کردی، پول گرفتی: +{t.money(p['country'], pay)}",
        f"💼 خزانه: {t.money(p['country'], p['money'] + pay)}",
        f"⏱ کار بعدی: {t.fa(WORK_CD // 60)} دقیقه دیگر — سطح بالاتر = پول بیشتر",
    ])
