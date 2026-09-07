"""👤 جنگ جهانی — بازیکن: شهروند → سرباز → فرمانده."""
import json
import db
import texts


def active(uid) -> dict:
    import countries
    p=get(uid)
    return p if p and p['country'] in countries.COUNTRIES else None


def get(uid) -> dict:
    r = db.one("SELECT * FROM users WHERE uid=?", (uid,))
    return dict(r) if r else None


@db.atomic
def ensure(uid, name=None, chat_id=None, username=None):
    db.ex("INSERT OR IGNORE INTO users(uid,name,joined,last_active,chat_id,username,money) "
          "VALUES(?,?,?,?,?,?,1000)",
          (uid, texts.esc((name or "")[:32]), db.now(), db.now(), chat_id, username))
    db.ex("UPDATE users SET last_active=?, chat_id=COALESCE(?,chat_id) WHERE uid=?",
          (db.now(), chat_id, uid))
    # نام جای‌نگهدار (PlayerNN) با نام واقعی تازه می‌شود + @آیدی ذخیره
    if name or username:
        row = db.one("SELECT name, username FROM users WHERE uid=?", (uid,))
        if row:
            old = row["name"] or ""
            if name and (not old or old.startswith("Player")):
                db.ex("UPDATE users SET name=? WHERE uid=?", (texts.esc(name[:32]), uid))
            if username and username != (row["username"] or ""):
                db.ex("UPDATE users SET username=? WHERE uid=?", (username, uid))


@db.atomic
def enlist(uid, country: str, name: str) -> bool:
    import countries
    from game import infra,defense,rewards
    if type(uid) is not int or not 0<uid<2**63 or country not in countries.COUNTRIES:
        return False
    p=get(uid)
    if p and p['country']:return False
    if db.one('SELECT 1 FROM users WHERE country=?',(country,)) or db.one('SELECT 1 FROM country_claims WHERE country=?',(country,)):
        return False
    if p:
        db.ex("UPDATE users SET country=?,is_leader=1, name=CASE WHEN name IS NULL OR name='' THEN ? ELSE name END WHERE uid=? AND (country IS NULL OR country='')",(country,texts.esc((name or '')[:32]),uid))
    else:
        db.ex('INSERT INTO users(uid,name,country,is_leader,money,joined,last_active,chat_id) VALUES(?,?,?,1,1000,?,?,?)',(uid,texts.esc((name or '')[:32]),country,db.now(),db.now(),db.GAME.get()))
    db.ex('INSERT INTO country_claims(country,uid,claimed) VALUES(?,?,?)',(country,uid,db.now()))
    db.kv_set(f'claimed:{country}',db.now())
    _starter_kit(uid,country)
    infra.ensure(country);defense.ensure(country)
    rewards.award_pending(uid)
    db.audit('country_selected',uid,country=country)
    return True


def _starter_kit(uid: int, country: str):
    """🎁 سلاحِ شروع — پهپاد شناسایی رایگان؛ با رعایت دورهٔ محافظت و آماده‌سازی جنگ."""
    db.ex("INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100) "
          "ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+1",
          (uid, f"drone_{country}",))


def xp_need(level: int) -> int:
    return 120 + level * 80


@db.atomic
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
    from game import invest as _iv
    _rate = _iv.rate(uid)
    spec, pct, sname = countries.spec_of(p["country"])
    return "\n".join([
        t.hdr("پرونده‌ی نظامی", "🎖"),
        t.row("نام", p["name"]),
        t.row("کشور", f"{c.get('flag', '')} {c.get('name', '—')}"
              + (f" — {politics.regime_of(p['country'])}"
                 if politics.regime_of(p["country"]) else "")),
        t.row("نقش", "👑 رهبر کشور" if p["is_leader"] else "شهروند کشور"),
        t.DASH,
        t.row("تخصص", f"🎖 {sname} — +{t.fa(pct)}٪ {spec}"),
        t.row("شاخه", mil.branch_name(p) or "غیرنظامی"),
        t.row("نقش شاخه", " ".join(mil.role_of(p)[1:]) or "—"),
        t.row("درجه", countries.rank_name(p["level"])),
        t.row("تجربه", f"{t.fa(p['xp'])}/{t.fa(xp_need(p['level']))}"),
        t.DASH,
        t.row("خزانه", f"💰 {t.money(p['country'], p['money'])}"),
        *([t.row("درآمد ساعتی", "🏭 " + t.money(p["country"], _rate))]
          if _rate else []),
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
    if db.kv_get(f"guide_done:{uid}"):
        out.append("📖 دانش‌آموخته")
    return "🏅 " + " · ".join(out) if out else ""


def geo_colony(cid):
    from game import geo
    return geo.colony_of(cid)


def geo_colonies(cid):
    from game import geo
    return geo.colonies_of(cid)


@db.atomic
def ration(uid) -> str:
    """جیره‌ی روزانه + زنجیره‌ی حضور — روزهای پیوسته جایزه‌ی بیشتر."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    day = db.day_index()
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
    from game import military as _mil2
    from game import infra as _ifr2
    from game import welfare as _wl2
    amount = int((200 + min(7, streak) * 60) * _mil2.eco_mult(uid)
                 * _ifr2.output_mult(p["country"])
                 * _wl2.welfare_mult(p["country"]))  # ⚙️ + 🏗 + 😊
    tax_note = ""
    col = geo_colony(p["country"])
    if col and col in countries.COUNTRIES:
        owner=db.one('SELECT uid FROM users WHERE country=? AND is_leader=1',(col,))
        if owner:
            cut=amount*3//10;amount-=cut
            db.ex('UPDATE users SET money=money+? WHERE uid=?',(cut,owner['uid']))
            db.audit('colony_tax',uid,to=owner['uid'],amount=cut)
            tax_note=f"\n⛓ {cut} دلار از همین جیره به خزانهٔ {countries.COUNTRIES[col]['name']} منتقل شد."
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


@db.atomic
def daily(uid) -> str:
    """🎁 جایزه‌ی روزانه با رگه‌ی پیوسته — هر روز بیا، بیشتر ببر."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    day = db.day_index()
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


WORK_CD = 600          # ⏱ هر ۱۰ دقیقه یک شیفت — تاکتیکی، نه اسپمی


@db.atomic
def work(uid) -> str:
    """🔨 کار کن و پول بگیر — رایگان، همیشه در جریان بازی."""
    p = active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    if db.now() - int(db.kv_get(f"work:{uid}", "0")) < WORK_CD:
        left = WORK_CD - (db.now() - int(db.kv_get(f"work:{uid}", "0")))
        return (f"⏳ خسته‌ای! {t.fa(max(1, (left + 59) // 60))} دقیقه دیگر "
                "دوباره کار کن.")
    db.kv_set(f"work:{uid}", str(db.now()))
    from game import quests
    quests.on_event(uid, "کار")
    from game import military as _mil
    from game import infra as _ifr
    from game import welfare as _wl
    pay = int((150 + p["level"] * 12) * _mil.eco_mult(uid)
              * _ifr.output_mult(p["country"]) * _wl.welfare_mult(p["country"]))
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (pay, uid))
    wl = [
        t.hdr("شیفت کاری تمام شد", "🔨"),
        f"💪 کار کردی، پول گرفتی: +{t.money(p['country'], pay)}",
        f"💼 خزانه: {t.money(p['country'], p['money'] + pay)}",
        f"⏱ کار بعدی: {t.fa(WORK_CD // 60)} دقیقه دیگر — سطح بالاتر = پول بیشتر",
    ]
    if _ifr.output_mult(p["country"]) < 1:
        wl.append("🏗 زیرساخت کشور آسیب‌دیده — درآمد ملی کم شده "
                  "(تعمیر: نظامی → زیرساخت)")
    return "\n".join(wl)
