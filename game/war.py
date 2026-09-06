"""⚔️ جنگ جهانی — سیستم جنگ کامل: انواع حمله، پدافند، جبهه، اشغال، اتحاد.

سلسله‌مراتب ۲۰۲۶:
🚀 موشکی → پدافند دشمن شانس دفع دارد
✈️ هوایی → برتری هوایی = امتیاز پایدار
🚢 دریایی → تنگه‌ها و آب‌های ساحلی
🚜 زمینی → پیشروی جبهه = اشغال شهر
پدافند دشمن + اتحادها + دولت هوشمند (پاسخ خودکار) همه واقعی‌اند.
"""
import random

import db
import countries
import texts
from game import economy, geo, state


FA_D = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

WAR_HOURS = 24

EMOJI_KIND = {"🚀": "موشکی", "🛩": "پهپادی", "🚢": "دریایی", "🤿": "دریایی",
              "🚜": "زمینی", "🛻": "زمینی", "💥": "توپخانه", "🛡": "پدافندی", "✈️": "هوایی"}


def kind_of(iid: str) -> str:
    return EMOJI_KIND.get(countries.ITEMS[iid][1], "زمینی")


# ═══════════ اتحادها ═══════════

def alliance_request(leader_uid: int, target: str) -> str:
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور می‌تواند اتحاد پیشنهاد کند."
    if target == p["country"]:
        return "⛔ با خودت؟"
    import json
    pend = db.jload(db.kv_get("alliance_pending"), {}) or {}
    pend[str(target)] = p["country"]
    db.kv_set("alliance_pending", json.dumps(pend, ensure_ascii=False))
    tc = countries.COUNTRIES[target]
    mc = countries.COUNTRIES[p["country"]]
    return (f"🤝 پیشنهاد اتحاد {mc['flag']} {mc['name']} → {tc['flag']} {tc['name']} ارسال شد.\n"
            f"رهبر {tc['name']} باید «قبول اتحاد {p['country']}» بزند.")


def alliance_accept(leader_uid: int, cid: str) -> str:
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    import json
    pend = db.jload(db.kv_get("alliance_pending"), {}) or {}
    if pend.get(str(p["country"])) != cid:
        return "⛔ درخواست اتحادی از این کشور نیست."
    del pend[str(p["country"])]
    db.kv_set("alliance_pending", json.dumps(pend, ensure_ascii=False))
    db.ex("INSERT INTO alliances(a,b) VALUES(?,?)", (cid, p["country"]))
    a, b = countries.COUNTRIES[cid], countries.COUNTRIES[p["country"]]
    return (f"🤝 <b>اتحاد رسمی!</b>\n{a['flag']} {a['name']} ⇄ {b['flag']} {b['name']}\n"
            f"اگر یکی در جنگ شود، دیگری وارد می‌شود.")


def allies_of(cid: str):
    rows = db.q("SELECT a, b FROM alliances WHERE a=? OR b=?", (cid, cid))
    return list({r["a"] if r["b"] == cid else r["b"] for r in rows})


def call_help(leader_uid: int) -> str:
    """رهبرِ درگیر جنگ → درخواست کمک از اتحاد."""
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    w = db.one("SELECT * FROM wars WHERE status='active' AND (a=? OR b=?)",
               (p["country"], p["country"]))
    if not w:
        return "🕊 کشورت در جنگ نیست."
    al = allies_of(p["country"])
    if not al:
        return "🤝 اتحادی نداری — «اتحاد کشور» پیشنهاد بده."
    col = "score_a" if w["a"] == p["country"] else "score_b"
    boost = 2 * len(al)
    db.ex(f"UPDATE wars SET {col}={col}+? WHERE id=?", (boost, w["id"]))
    names = " · ".join(f"{countries.COUNTRIES[c]['flag']} {countries.COUNTRIES[c]['name']}" for c in al)
    return f"🆘 اتحاد پاسخ داد!\n{names}\n⚔️ +{boost} امتیاز جبهه — اتحادیان وارد شدند."


# ═══════════ صلح ═══════════

def peace_request(uid) -> str:
    p = state.active(uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    wr = war_of(p["country"])
    if not wr:
        return "🕊 کشورت در جنگ نیست."
    db.kv_set(f"peace:{wr['id']}", p["country"])
    other = _enemy(p["country"], wr)
    oc = countries.COUNTRIES[other]
    return (f"🕊 درخواست صلح به {oc['flag']} {oc['name']} ارسال شد.\n"
            f"رهبر آن کشور باید بنویسد: <code>قبول صلح</code>")


def peace_accept(uid) -> str:
    p = state.active(uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    wr = war_of(p["country"])
    if not wr:
        return "🕊 جنگی نیست."
    if db.kv_get(f"peace:{wr['id']}") != _enemy(p["country"], wr):
        return "⛔ درخواست صلحی از طرف مقابل نیست."
    db.ex("UPDATE wars SET status='peace' WHERE id=?", (wr["id"],))
    db.kv_set(f"peace:{wr['id']}", "")
    a, b = countries.COUNTRIES[wr["a"]], countries.COUNTRIES[wr["b"]]
    return (f"🕊 <b>پیمان صلح!</b>\n{a['flag']} {a['name']} ⇄ {b['flag']} {b['name']}\n"
            f"جنگ پایان یافت — بازار نفس کشید.")


# ═══════════ نبرد تن‌به‌تن (PvP) ═══════════

def duel_request(uid, target_name, target_uid=None) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if target_uid and target_uid == uid:
        return "🤡 با خودت؟"
    c = countries.COUNTRIES[p["country"]]
    import json
    db.kv_set(f"duel:{'last'}", json.dumps(dict(a=uid, b=target_uid,
                                                ts=db.now()), ensure_ascii=False))
    t = texts
    return "\n".join([
        t.hdr("چالش نبرد", "⚔️"),
        f"🇮🇷 {t.mention(uid, p['name'] or 'سرباز')} از {c['name']} چالش داد!",
        f"🎯 حریف: <b>{target_name}</b>",
        t.K,
        "حریف باید بنویسد: «قبول نبرد» — تا ۵ دقیقه!"])


def duel_accept(uid) -> str:
    import json
    d = db.jload(db.kv_get("duel:last"), None)
    if not d or d.get("b") not in (None, uid) or db.now() - d.get("ts", 0) > 300:
        return "⛔ چالشی در کار نیست (یا مهلتش گذشت)."
    if d["a"] == uid:
        return "🤡 خودت چالش دادی!"
    from game import military
    a, b = state.active(d["a"]), state.active(uid)
    if not a or not b:
        return "⛔ یکی از طرف‌ها سرباز نیست."
    if not a["branch"] or not b["branch"]:
        return "🪖 هر دو باید عضو شاخه نظامی باشند."
    ca, cb = countries.COUNTRIES[a["country"]], countries.COUNTRIES[b["country"]]
    _, _, aatk, adef = military.loadout(a["uid"])
    _, _, batk, bdef = military.loadout(b["uid"])
    ahp, bhp = a["hp"], b["hp"]
    t = texts
    lines = [t.hdr("نبرد تن‌به‌تن", "⚔️"),
             f"{ca['flag']} {t.mention(a['uid'], a['name'] or 'سرباز')} ⚔️ "
             f"{cb['flag']} {t.mention(b['uid'], b['name'] or 'سرباز')}",
             f"⚔️ {aatk + 10} و 🛡 {adef + 9} ← VS → ⚔️ {batk + 10} و 🛡 {bdef + 9}",
             t.K]
    turn = 0
    while turn < 10 and ahp > 0 and bhp > 0:
        turn += 1
        da = max(4, int((aatk + 10 + a["level"] * 2) * random.uniform(0.7, 1.2)) - bdef // 2)
        db_ = max(4, int((batk + 10 + b["level"] * 2) * random.uniform(0.7, 1.2)) - adef // 2)
        bhp -= da
        ahp -= db_
        lines.append(f"{turn}. ⚔️ −{da} | 🛡 −{db_}")
    winner, loser = (a, b) if bhp <= 0 < ahp or ahp > bhp else (b, a)
    if ahp <= 0 and bhp <= 0:
        lines.append("💀 هر دو زمین خوردند — مساوی!")
        db.kv_set("duel:last", "")
        return "\n".join(lines)
    prize = 600
    db.ex("UPDATE users SET money=money+?, kills=kills+1 WHERE uid=?", (prize, winner["uid"]))
    db.ex("UPDATE users SET hp=MAX(15,hp-30) WHERE uid=?", (loser["uid"],))
    state.gain_xp(winner["uid"], 150)
    wc = countries.COUNTRIES[winner["country"]]
    lines.append(f"🏆 {wc['flag']} {t.mention(winner['uid'], winner['name'] or 'سرباز')} "
                 f"پیروز شد! 💰 {prize:,} · ⭐ ۱۵۰ XP")
    db.kv_set("duel:last", "")
    return "\n".join(lines)


# ═══════════ جنگ ═══════════

def declare(leader_uid: int, target: str) -> str:
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور می‌تواند جنگ اعلام کند."
    tc = countries.COUNTRIES.get(target)
    if not tc or target == p["country"]:
        return "⛔ کشور هدف نامعتبر."
    act = db.one("SELECT * FROM wars WHERE status='active' AND (a=? OR b=?)",
                 (p["country"], p["country"]))
    if act:
        other = act["b"] if act["a"] == p["country"] else act["a"]
        return f"⚔️ کشورت درگیر است با {countries.COUNTRIES[other]['name']}."
    if target in allies_of(p["country"]):
        return "🤝 با این کشور متحدی!"
    mc = countries.COUNTRIES[p["country"]]
    db.ex("INSERT INTO wars(a,b,started,ends) VALUES(?,?,?,?)",
          (p["country"], target, db.now(), db.now() + WAR_HOURS * 3600))
    economy.on_war_start()          # شوک بازار
    fronts = geo.fronts_of(p["country"], target)
    t = texts
    return "\n".join([
        t.hdr("اعلام جنگ", "⚔️"),
        f"{mc['flag']} <b>{mc['name']}</b> ← حمله ← {tc['flag']} <b>{tc['name']}</b>",
        t.K,
        "🗺 <b>جبهه‌ها:</b> " + " · ".join(fronts),
        "🤝 اتحادها: هر طرف می‌تواند «کمک» بخواهد.",
        f"⏱ {WAR_HOURS} ساعت — سربازان با «رزم» جبهه را جلو می‌برند.",
        "🛢 اقتصاد جهانی این جنگ را حس خواهد کرد."])


def war_of(cid: str):
    return db.one("SELECT * FROM wars WHERE status='active' AND (a=? OR b=?)", (cid, cid))


def _enemy(cid: str, w) -> str:
    return w["b"] if w["a"] == cid else w["a"]


def strike(uid, kind: str, count: int = 1) -> str:
    """رهبر: حمله‌ی خاص با تعداد — هر شلیک جدا دفع یا برخورد می‌خورد."""
    p = state.active(uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    w = war_of(p["country"])
    if not w:
        return "🕊 کشورت در جنگ نیست."
    if db.now() - int(db.kv_get(f"strike:{uid}", "0")) < 45:
        return "⏳ ۴۵ ثانیه بین موج حمله."
    db.kv_set(f"strike:{uid}", str(db.now()))
    count = max(1, min(5, count))
    rows = db.q("SELECT n.iid, n.dur FROM inventory n WHERE n.uid=?", (uid,))
    have = [r for r in rows if kind_of(r["iid"]) == kind and r["dur"] > 15]
    if not have:
        return f"⛔ تجهیزات <b>{kind}</b> نداری — «تجهیزات»"
    best = max(have, key=lambda r: countries.ITEMS[r["iid"]][3] * r["dur"] // 100)
    it = countries.ITEMS[best["iid"]]
    ecid = _enemy(p["country"], w)
    ec = countries.COUNTRIES[ecid]
    def_rows = db.q("SELECT n.iid, n.dur FROM inventory n JOIN users u ON u.uid=n.uid "
                    "WHERE u.country=?", (ecid,))
    def_pwr = sum(countries.ITEMS[r["iid"]][4] * r["dur"] // 100
                  for r in def_rows if kind_of(r["iid"]) == "پدافندی") + ec["mil"] * 6
    # 🎖 تخصص پدافندیِ کشور دشمن
    espec, epct, _ = countries.spec_of(ecid)
    if espec == "پدافندی":
        def_pwr = int(def_pwr * (1 + epct / 100))
    # 🎖 تخصص کشور مهاجم در همین نوع حمله
    mspec, mpct, _ = countries.spec_of(p["country"])
    spec_mark = ""
    spec_mult = 1
    if mspec == kind:
        spec_mark = f" 🎖 تخصص {countries.COUNTRIES[p['country']]['name']} فعال!"
        spec_mult = 1 + mpct / 100
    t = texts
    lines = [t.hdr(f"موج حمله‌ی {kind}", {"موشکی": "🚀", "هوایی": "✈️", "دریایی": "🚢",
                                          "زمینی": "🚜", "پهپادی": "🛩"}.get(kind, "💥")),
             f"{ec['flag']} {ec['name']} ← {str(count).translate(FA_D)}× {it[0]} {it[1]}{spec_mark}",
             t.K]
    score_add = 0
    for n in range(1, count + 1):
        base_dmg = it[3] * best["dur"] // 100 + p["level"] * 2
        dmg = max(4, int(base_dmg * spec_mult * random.uniform(0.7, 1.3)))
        intercepted = random.random() < min(0.75, def_pwr / (def_pwr + dmg))
        if intercepted:
            lines.append(f"  {n}. 🛡 دفع شد — پدافند در آسمان نابودش کرد")
        else:
            lines.append(f"  {n}. 💥 برخورد! آسیب {dmg}")
            score_add += 3
        db.ex("UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?",
              (random.randint(6, 14), uid, best["iid"]))
    if score_add:
        col = "score_a" if w["a"] == p["country"] else "score_b"
        db.ex(f"UPDATE wars SET {col}={col}+? WHERE id=?", (score_add, w["id"]))
        lines.append(f"⚔️ امتیاز جبهه: +{score_add}")
        # هر ۵ امتیاز یک شهر می‌افتد
        score = db.one(f"SELECT {col} s FROM wars WHERE id=?", (w["id"],))["s"]
        if score and score % 5 < count:
            city = random.choice([c for c in geo.CITIES.get(ecid, [])
                                  if c not in geo.occupied(ecid)] or ["مرز"])
            msg = geo.occupy(ecid, city, p["country"])
            if msg:
                lines.append(f"🚩 <b>{city} سقوط کرد!</b>")
    else:
        lines.append("💀 همه دفع شد — پدافند دشمن بیدار است.")
    lines.append(f"🛠 دوام {it[0]}: −{str(count * 10).translate(FA_D)}٪")
    # ضدحمله‌ی هوشمند دشمن
    if random.random() < 0.4 and score_add:
        edmg = random.randint(8, 25)
        db.ex("UPDATE users SET hp=MAX(15,hp-?) WHERE uid=?", (edmg, uid))
        lines.append(f"⚠️ ضدحمله‌ی {ec['name']}! 🩸 −{edmg}")
    return "\n".join(lines)


def settle():
    """پایان جنگ‌های سررسیده."""
    out = []
    for w in db.q("SELECT * FROM wars WHERE status='active' AND ends<=?", (db.now(),)):
        if w["score_a"] == w["score_b"]:
            db.ex("UPDATE wars SET status='draw' WHERE id=?", (w["id"],))
            out.append("🕊 جنگ مساوی تمام شد.")
        else:
            win = w["a"] if w["score_a"] > w["score_b"] else w["b"]
            lose = w["b"] if win == w["a"] else w["a"]
            db.ex("UPDATE wars SET status='won', winner=? WHERE id=?", (win, w["id"]))
            wc = countries.COUNTRIES[win]
            out.append(f"🏆 {wc['flag']} <b>{wc['name']}</b> پیروز شد "
                       f"({max(w['score_a'], w['score_b'])}—{min(w['score_a'], w['score_b'])}).")
            db.ex("DELETE FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)",
                  (win, lose, lose, win))
    return out


def world_status() -> str:
    rows = db.q("SELECT country, COUNT(*) n FROM users GROUP BY country ORDER BY n DESC")
    t = texts
    lines = [t.hdr("وضعیت جهان", "🌍"), "👥 <b>سربازان:</b>", ""]
    for r in rows:
        c = countries.COUNTRIES.get(r["country"])
        if c:
            lines.append(f"{c['flag']} {c['name']} — {r['n']}")
    wars = db.q("SELECT * FROM wars WHERE status='active'")
    lines += ["", "⚔️ <b>جنگ‌های فعال:</b>"]
    if not wars:
        lines.append("🕊 صلح بر جهان حاکم است... فعلاً.")
    for w in wars:
        a, b = countries.COUNTRIES[w["a"]], countries.COUNTRIES[w["b"]]
        left = max(0, w["ends"] - db.now()) // 3600
        lines.append(f"{a['flag']}{a['name']} ⚔️ {b['flag']}{b['name']} — "
                     f"{w['score_a']}:{w['score_b']} · {left} ساعت")
    return "\n".join(lines)


def leaderboard() -> str:
    rows = db.q("SELECT * FROM users ORDER BY level DESC, kills DESC LIMIT 10")
    t = texts
    lines = [t.hdr("برترین فرماندهان", "🏆"), ""]
    for i, r in enumerate(rows, 1):
        c = countries.COUNTRIES.get(r["country"], {})
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"{medal} {t.mention(r['uid'], r['name'] or 'سرباز')} — "
                     f"{c.get('flag', '')} سطح {r['level']} · ⚔️ {r['kills']}")
    return "\n".join(lines)
