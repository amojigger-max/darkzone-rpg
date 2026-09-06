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
from game import defense, economy, geo, military, state


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
    if target not in countries.COUNTRIES:
        return "⛔ کشور نامعتبر."
    import json
    pend = db.jload(db.kv_get("alliance_pending"), {}) or {}
    pend[str(target)] = p["country"]
    db.kv_set("alliance_pending", json.dumps(pend, ensure_ascii=False))
    tc = countries.COUNTRIES[target]
    mc = countries.COUNTRIES[p["country"]]
    return (f"🤝 پیشنهاد اتحاد {mc['flag']} {mc['name']} → {tc['flag']} {tc['name']} ارسال شد.\n"
            f"رهبر {tc['name']} دکمه‌ی «🤝 قبول اتحاد» را بزند.")


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
        return "🤝 اتحادی نداری — از منو → اتحاد، پیشنهاد بده."
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
            f"رهبر آن کشور دکمه‌ی «🕊 قبول صلح» را بزند.")


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


def surrender(uid) -> str:
    """🏳 تسلیم — پایان جنگ با گران‌ترین بهاء: غرامت سنگین، شهرها می‌ماند، تحقیر."""
    p = state.active(uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور."
    w = war_of(p["country"])
    if not w:
        return "🕊 کشورت در جنگ نیست."
    cid = p["country"]
    enemy = _enemy(cid, w)
    mine = w["score_a"] if w["a"] == cid else w["score_b"]
    theirs = w["score_b"] if w["a"] == cid else w["score_a"]
    if mine >= theirs:
        return "🏆 داری می‌بری! چرا تسلیم؟ صلحِ برابر: منو → درخواست صلح"
    db.ex("UPDATE wars SET status='won', winner=? WHERE id=?", (enemy, w["id"]))
    # 🏳 غرامت جنگ: بازندگان می‌پردازند، برندگان می‌گیرند
    reps = 300 + (theirs - mine) * 20
    for r in db.q("SELECT uid FROM users WHERE country=?", (cid,)):
        db.ex("UPDATE users SET money=MAX(0,money-?) WHERE uid=?", (reps, r["uid"]))
    for r in db.q("SELECT uid FROM users WHERE country=?", (enemy,)):
        db.ex("UPDATE users SET money=money+? WHERE uid=?", (reps, r["uid"]))
        state.gain_xp(r["uid"], reps // 3)
    mc, ec = countries.COUNTRIES[cid], countries.COUNTRIES[enemy]
    t = texts
    lines = [t.hdr("تسلیم", "🏳"),
             f"{mc['flag']} {mc['name']} در برابر {ec['flag']} {ec['name']} تسلیم شد",
             t.K,
             f"💰 غرامت هر سرباز: {t.money(cid, -reps)}",
             f"🏆 برندگان: +{t.money(enemy, reps)} هر سرباز",
             "🏚 شهرهای اشغال‌شده دست برنده می‌ماند."]
    # ⛓ اگر همه‌ی شهرها رفته → مستعمره‌ی رسمی
    from game import geo as _g
    occ = _g.occupied(cid)
    if occ and set(occ) >= set(_g.CITIES.get(cid, [])):
        lines.append("")
        lines.append(_g.colonize(cid, enemy))
    db.ex("DELETE FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)",
          (cid, enemy, enemy, cid))
    return "\n".join(lines)


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
        f"{c['flag']} {t.mention(uid, p['name'] or 'سرباز')} از {c['name']} چالش داد!",
        f"🎯 حریف: <b>{target_name}</b>",
        t.K,
        "حریف دکمه‌ی «⚔️ قبول نبرد» را بزند — تا ۵ دقیقه!"])


def duel_accept(uid) -> str:
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
    _, _, aatk, adef, _, _ = military.loadout(a["uid"])
    _, _, batk, bdef, _, _ = military.loadout(b["uid"])
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
                 f"پیروز شد! 💰 {texts.fa(prize)} · ⭐ {texts.fa(150)} XP")
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
    w2 = db.one("SELECT * FROM wars WHERE a=? AND b=? AND status='active' "
                "ORDER BY id DESC", (p["country"], target))
    if w2:
        _init_ammo(w2)
    defense.ensure(p["country"]), defense.ensure(target)
    economy.on_war_start()          # شوک بازار
    fronts = geo.fronts_of(p["country"], target)
    t = texts
    return "\n".join([
        t.hdr("اعلام جنگ", "⚔️"),
        f"{mc['flag']} <b>{mc['name']}</b> ← حمله ← {tc['flag']} <b>{tc['name']}</b>",
        t.K,
        "🗺 <b>جبهه‌ها:</b> " + " · ".join(fronts),
        "🤝 اتحادها: هر طرف می‌تواند کمک اتحاد بخواهد (منو).",
        f"⏱ {WAR_HOURS} ساعت — سربازان با رزم جبهه را جلو می‌برند.",
        "🛢 اقتصاد جهانی این جنگ را حس خواهد کرد."])


def war_of(cid: str):
    return db.one("SELECT * FROM wars WHERE status='active' AND (a=? OR b=?)", (cid, cid))


# ═══════════ مهمات — محدودیت مستقل هر کشور در هر جنگ ═══════════

def _ammo_key(w, cid: str) -> str:
    return f"ammo:{w['id']}:{cid}"


def _ammo_total(cid: str) -> int:
    """سهم مهمات هر کشور — از قدرت نظامی‌اش."""
    c = countries.COUNTRIES.get(cid)
    return 16 + (c["mil"] * 3 if c else 6)


def _init_ammo(w):
    for cid in (w["a"], w["b"]):
        k = _ammo_key(w, cid)
        if not db.kv_get(k):
            db.kv_set(k, str(_ammo_total(cid)))


def front(uid) -> str:
    """🗺 پنل تمیز جبهه‌ی جنگ کشور بازیکن."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    w = war_of(p["country"])
    t = texts
    if not w:
        return t.hdr("جبهه", "🗺") + "\n🕊 کشورت در جنگ نیست — آماده بمان."
    _init_ammo(w)
    cid = p["country"]
    ecid = _enemy(cid, w)
    mc, ec = countries.COUNTRIES[cid], countries.COUNTRIES[ecid]
    mine = w["score_a"] if w["a"] == cid else w["score_b"]
    theirs = w["score_b"] if w["a"] == cid else w["score_a"]
    hours = max(0, w["ends"] - db.now()) // 3600
    ammo = int(db.kv_get(_ammo_key(w, cid), "0") or 0)
    lines = [t.hdr("جبهه‌ی جنگ", "🗺"),
             f"{mc['flag']} {mc['name']} ⚔️ {ec['flag']} {ec['name']}",
             t.row("امتیاز جبهه", f"{t.fa(mine)} : {t.fa(theirs)}"),
             t.row("زمان مانده", f"{t.fa(hours)} ساعت"),
             t.row("مهمات کشورت", f"{t.fa(ammo)}/{t.fa(_ammo_total(cid))}"),
             "",
             f"🛡 <b>سپر ملی {ec['name']}:</b>"]
    for layer in defense.LAYERS:
        lines.append(f"▫️ {defense.LAYERS[layer]} {layer}: {t.fa(defense.level(ecid, layer))}")
    occ = geo.occupied(ecid)
    if occ:
        lines += ["", "🚩 اشغال‌های ما: " + " · ".join(occ)]
    myocc = geo.occupied(cid)
    if myocc:
        lines.append("💀 شهرهای ازدست‌رفته‌ی ما: " + " · ".join(myocc))
    return "\n".join(lines)


def army(uid) -> str:
    """🪖 ارتش کشور — سربازان، تجهیزات، سپر، محدودیت‌های مستقل."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    c = countries.COUNTRIES[cid]
    t = texts
    n_players = db.one("SELECT COUNT(*) n FROM users WHERE country=?", (cid,))["n"]
    brs = db.q("SELECT branch, COUNT(*) n FROM users "
               "WHERE country=? AND branch IS NOT NULL GROUP BY branch", (cid,))
    bmap = {str(i): b for i, b in enumerate(c["branches"])}
    eq = db.q("SELECT n.iid, n.dur FROM inventory n JOIN users u ON u.uid=n.uid "
              "WHERE u.country=?", (cid,))
    atk = sum(countries.ITEMS[r["iid"]][3] * r["dur"] // 100 for r in eq
              if r["iid"] in countries.ITEMS)
    guard = sum(countries.ITEMS[r["iid"]][4] * r["dur"] // 100 for r in eq
                if r["iid"] in countries.ITEMS)
    defense.ensure(cid)
    davg = db.one("SELECT AVG(level) a FROM defense WHERE cid=?", (cid,))["a"] or 0
    manpower = 100 + c["mil"] * 20 + n_players * 15
    lines = [t.hdr(f"ارتش {c['name']}", "🪖"),
             t.row("سربازان", n_players),
             t.row("قدرت تجهیزات", f"⚔️ {atk} · 🛡 {guard}"),
             t.row("میانگین سپر ملی", f"{davg:.0f}"),
             t.row("نیروی انسانی", manpower)]
    if brs:
        lines.append("▫️ شاخه‌ها: " + " · ".join(
            f"{bmap.get(str(r['branch']), r['branch'])} {texts.fa(r['n'])}"
            for r in brs))
    if economy.sanctioned(cid):
        lines.append("🚫 کشورت تحت تحریم اقتصادی است!")
    col = geo.colony_of(cid)
    if col:
        cc = countries.COUNTRIES[col]
        lines.append(f"⛓ کشورت مستعمره‌ی {cc['flag']} {cc['name']} است — جیره ۳۰٪ مالیات!")
    mine = geo.colonies_of(cid)
    if mine:
        lines.append(f"👑 مستعمره‌های تو: {t.fa(len(mine))} — خراج می‌گیرید")
    w = war_of(cid)
    if w:
        _init_ammo(w)
        ammo = int(db.kv_get(_ammo_key(w, cid), "0") or 0)
        lines.append(t.row("مهمات جنگ", f"{t.fa(ammo)}/{t.fa(_ammo_total(cid))}"))
    else:
        lines.append("🕊 کشورت در صلح است.")
    lines += ["", "⚙️ <b>محدودیت‌های کشورت:</b>",
              "▫️ موج حمله: هر ۴۵ ثانیه",
              "▫️ حداکثر شلیک هر موج: ۵",
              f"▫️ مهمات هر جنگ: {t.fa(_ammo_total(cid))}",
              "▫️ جنگ همزمان: ۱"]
    return "\n".join(lines)


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
    _init_ammo(w)
    ammo = int(db.kv_get(_ammo_key(w, p["country"]), "0") or 0)
    if ammo <= 0:
        return "🎯 مهمات جنگ تمام شد — جبهه را از منو ببین. صلح یا شکست."
    db.kv_set(f"strike:{uid}", str(db.now()))
    from game import quests as _q
    _q.on_event(uid, "حمله")
    count = max(1, min(5, count, ammo))
    rows = db.q("SELECT n.iid, n.dur FROM inventory n WHERE n.uid=?", (uid,))
    have = [r for r in rows if kind_of(r["iid"]) == kind and r["dur"] > 15]
    if not have:
        return f"⛔ تجهیزات <b>{kind}</b> نداری — زرادخانه‌ات را کامل کن (منو)"
    best = max(have, key=lambda r: countries.ITEMS[r["iid"]][3] * r["dur"] // 100
               * military._lvl_mult(uid, r["iid"]) // 100)
    it = countries.ITEMS[best["iid"]]
    ecid = _enemy(p["country"], w)
    ec = countries.COUNTRIES[ecid]
    # 🛡 سپر ملی دشمن — لایه‌ی مقابل + جنگ الکترونیک (فرسایش واقعی)
    chance, dmg_mult, layer, dlevel = defense.absorb(ecid, kind, count)
    espec, epct, _ = countries.spec_of(ecid)
    if espec == "پدافندی":
        chance = min(0.90, chance * (1 + epct / 200))
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
             f"🛡 {layer} دشمن: سطح {texts.fa(dlevel)}",
             t.K]
    score_add = 0
    for n in range(1, count + 1):
        base_dmg = (it[3] * best["dur"] // 100
                    * military._lvl_mult(uid, best["iid"]) // 100) + p["level"] * 2
        dmg = max(4, int(base_dmg * spec_mult * random.uniform(0.7, 1.3) * dmg_mult))
        intercepted = random.random() < chance
        if intercepted:
            lines.append(f"▫️ {texts.fa(n)}. 🛡 دفع شد — پدافند نابودش کرد")
        else:
            lines.append(f"▫️ {texts.fa(n)}. 💥 برخورد! آسیب {texts.fa(dmg)}")
            score_add += 3
        db.ex("UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?",
              (random.randint(6, 14), uid, best["iid"]))
    if score_add:
        col = "score_a" if w["a"] == p["country"] else "score_b"
        db.ex(f"UPDATE wars SET {col}={col}+? WHERE id=?", (score_add, w["id"]))
        lines.append(f"⚔️ امتیاز جبهه: +{texts.fa(score_add)}")
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
    d_now = db.one("SELECT dur FROM inventory WHERE uid=? AND iid=?",
                   (uid, best["iid"]))
    if d_now:
        lines.append(f"🛠 دوام {it[0]}: {texts.fa(d_now['dur'])}٪")
    # 🎯 مصرف مهمات
    db.kv_set(_ammo_key(w, p["country"]), str(ammo - count))
    lines.append(f"🎯 مهمات کشورت: {texts.fa(ammo - count)}/{texts.fa(_ammo_total(p['country']))}")
    # ضدحمله‌ی مستقیم به فرمانده
    if random.random() < 0.4 and score_add:
        edmg = random.randint(8, 25)
        db.ex("UPDATE users SET hp=MAX(15,hp-?) WHERE uid=?", (edmg, uid))
        lines.append(f"⚠️ ضدحمله‌ی {ec['name']}! 🩸 −{texts.fa(edmg)}")
    # 🧠 پاسخ هوشمند جهان — دشمن واقعی جواب می‌دهد
    from game import ai
    for ln in ai.respond_to_strike(p["country"], ecid, kind, score_add):
        lines.append(ln)
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
                       f"({texts.fa(max(w['score_a'], w['score_b']))}—"
                       f"{texts.fa(min(w['score_a'], w['score_b']))}).")
            db.ex("DELETE FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)",
                  (win, lose, lose, win))
            # 🎁 غنیمت جنگ — سربازان برنده پاداش می‌گیرند، بازندگان می‌پردازند
            prize = 400 + int(max(w["score_a"], w["score_b"])) * 35 \
                + len(geo.held_by(win)) * 100 + len(geo.colonies_of(win)) * 150
            for r in db.q("SELECT uid FROM users WHERE country=?", (win,)):
                db.ex("UPDATE users SET money=money+? WHERE uid=?",
                      (prize, r["uid"]))
                state.gain_xp(r["uid"], prize // 4)
            for r in db.q("SELECT uid FROM users WHERE country=?", (lose,)):
                db.ex("UPDATE users SET money=MAX(0,money-?) WHERE uid=?",
                      (150, r["uid"]))
            out.append(f"🎁 غنیمت جنگ: هر سرباز {wc['name']} → "
                       f"💰 {texts.money(win, prize)}")
            # ⛓ مستعمره‌ای که بر ضد اشغال‌گرش پیروز شد → آزاد!
            if geo.colony_of(win) == lose:
                geo.free_colony(win)
                out.append(f"🕊 {wc['flag']} {wc['name']} یوغ مستعمره را شکست — آزاد شد!")
    return out


def world_status() -> str:
    counts = {r["country"]: r["n"] for r in
              db.q("SELECT country, COUNT(*) n FROM users "
                   "WHERE country IS NOT NULL GROUP BY country")}
    t = texts
    lines = [t.hdr("وضعیت جهان", "🌍"),
             "🤖 = دولت NPC — بازیکن ندارد، خودش می‌جنگد و جواب می‌دهد", ""]
    cids = list(countries.COUNTRIES)
    def _cell(cid):
        c = countries.COUNTRIES[cid]
        n = counts.get(cid, 0)
        col = geo.colony_of(cid)
        if col and col in countries.COUNTRIES:
            return f"{c['flag']} {c['name']}: ⛓ {countries.COUNTRIES[col]['flag']}"
        return f"{c['flag']} {c['name']}: {texts.fa(n) if n else '🤖'}"
    for a, b in zip(cids[::2], cids[1::2]):
        lines.append(_cell(a) + " · " + _cell(b))
    if len(cids) % 2:
        lines.append(_cell(cids[-1]))
    wars = db.q("SELECT * FROM wars WHERE status='active'")
    lines += ["", "⚔️ <b>جنگ‌های فعال:</b>"]
    if not wars:
        lines.append("🕊 صلح بر جهان حاکم است... فعلاً.")
    for w in wars:
        a, b = countries.COUNTRIES[w["a"]], countries.COUNTRIES[w["b"]]
        left = max(0, w["ends"] - db.now()) // 3600
        lines.append(f"{a['flag']}{a['name']} ⚔️ {b['flag']}{b['name']} — "
                     f"{texts.fa(w['score_a'])}:{texts.fa(w['score_b'])} · {texts.fa(left)} ساعت")
    return "\n".join(lines)


def colonies() -> str:
    """⛓ نقشه‌ی مستعمره‌های جهان."""
    import countries as _c
    t = texts
    rows = db.q("SELECT k, v FROM kv WHERE k LIKE 'colony:%' AND v != ''")
    if not rows:
        return t.hdr("مستعمره‌های جهان", "⛓") + "\n🕊 مستعمره‌ای نیست — " \
               "جنگ بگیر، همه‌ی شهرهای دشمن را تصرف کن!"
    groups = {}
    for r in rows:
        groups.setdefault(r["v"], []).append(r["k"].split(":")[1])
    lines = [t.hdr("مستعمره‌های جهان", "⛓"), ""]
    for by, cids in sorted(groups.items(), key=lambda x: -len(x[1])):
        b = _c.COUNTRIES.get(by)
        if not b:
            continue
        names = " · ".join(f"{_c.COUNTRIES[c]['flag']} {_c.COUNTRIES[c]['name']}"
                           for c in cids if c in _c.COUNTRIES)
        lines.append(f"👑 {b['flag']} {b['name']} ({t.fa(len(cids))}):\n   {names}")
    lines += ["", "💡 مستعمره: ۳۰٪ مالیات جیره‌ی مردمش · خراج برای اشغال‌گر",
              "🕊 آزادی: مستعمره در جنگ بعدی بر ضد اشغال‌گرش پیروز شود"]
    return "\n".join(lines)


def power_rank(top: int = 10) -> str:
    """🥇 رتبه‌بندی نظامی کشورها — سرباز، تجهیزات، سپر، اشغال، پیروزی."""
    t = texts
    rows = []
    for cid, c in countries.COUNTRIES.items():
        n = db.one("SELECT COUNT(*) n FROM users WHERE country=?", (cid,))["n"]
        eq = db.q("SELECT n.iid, n.dur FROM inventory n JOIN users u ON u.uid=n.uid "
                  "WHERE u.country=?", (cid,))
        atk = sum(countries.ITEMS[r["iid"]][3] * r["dur"] // 100 for r in eq
                  if r["iid"] in countries.ITEMS)
        defense.ensure(cid)
        sh = db.one("SELECT AVG(level) a FROM defense WHERE cid=?", (cid,))["a"] or 0
        held = len(geo.held_by(cid))
        won = db.one("SELECT COUNT(*) n FROM wars WHERE winner=?", (cid,))["n"]
        cols = len(geo.colonies_of(cid)) * 80 - (40 if geo.colony_of(cid) else 0)
        power = n * 12 + atk // 8 + int(sh) * 2 + held * 6 + won * 40 + cols
        rows.append((power, cid, n))
    rows.sort(reverse=True)
    lines = [t.hdr("قدرت نظامی کشورها", "🥇"), ""]
    for i, (pw, cid, n) in enumerate(rows[:top], 1):
        c = countries.COUNTRIES[cid]
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{t.fa(i)}.")
        npc = "" if n else " 🤖"
        lines.append(f"{medal} {c['flag']} {c['name']} — {t.fa(pw)}{npc}")
    return "\n".join(lines)


def leaderboard() -> str:
    rows = db.q("SELECT * FROM users ORDER BY level DESC, kills DESC LIMIT 10")
    t = texts
    lines = [t.hdr("برترین فرماندهان", "🏆"), ""]
    for i, r in enumerate(rows, 1):
        c = countries.COUNTRIES.get(r["country"], {})
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{t.fa(i)}.")
        lines.append(f"{medal} {t.mention(r['uid'], r['name'] or 'سرباز')} — "
                     f"{c.get('flag', '')} سطح {t.fa(r['level'])} · ⚔️ {t.fa(r['kills'])}")
    return "\n".join(lines)
