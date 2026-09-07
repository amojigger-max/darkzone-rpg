"""🏛 جنگ جهانی — سیاست: حزب، بیانیه، شورش، رهبری، جاسوسی."""
import random

import db
import countries
import texts
from game import state

PARTY_COST = 1200           # متناسب اقتصاد ۱۰۰۰ (~۵ جیره)
REBEL_POWER = 150           # قدرت لازم برای شورش (بیانیه +۱۰ · عضو +۵)
SPY_COOLDOWN = 300


def my_party(uid) -> dict | None:
    p = db.one("SELECT party_id FROM users WHERE uid=?", (uid,))
    if not p or not p["party_id"]:
        return None
    r = db.one("SELECT * FROM parties WHERE id=?", (p["party_id"],))
    return dict(r) if r else None


def found(uid, name: str, ideology: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if not p["branch"]:
        return "🪖 ساخت حزب نیازمند عضویت نظامی است — «ارتشی»"
    if my_party(uid):
        return "🔒 قبلاً در حزبی هستی."
    if len(name) < 3 or len(name) > 28:
        return "⛔ نام حزب: ۳ تا ۲۸ حرف."
    if p["money"] < PARTY_COST:
        return (f"💰 تأسیس حزب {texts.money(p['country'], PARTY_COST)} می‌ارزد — "
                f"داری: {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (PARTY_COST, uid))
    db.ex("INSERT INTO parties(name,country,ideology,leader_uid,members,power,created) "
          "VALUES(?,?,?,?,1,10,?)", (texts.esc(name), p["country"],
                                     texts.esc(ideology or "ملی")[:24], uid, db.now()))
    pid = db.one("SELECT last_insert_rowid() id")["id"]
    db.ex("UPDATE users SET party_id=? WHERE uid=?", (pid, uid))
    return (f"🏛 حزب <b>{texts.esc(name)}</b> رسماً تأسیس شد!\n"
            f"ایدئولوژی: {texts.esc(ideology or 'ملی')}\n"
            f"عضوگیری: فهرست احزاب — مواضع: دکمه‌ی 📰 بیانیه (منو)")


def list_parties(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    rows = db.q("SELECT * FROM parties WHERE country=? ORDER BY power DESC LIMIT 10",
                (p["country"],))
    c = countries.COUNTRIES[p["country"]]
    lines = [texts.hdr(f"احزاب {c['name']}", "🏛"), ""]
    if not rows:
        lines.append("هنوز حزبی نیست — اولین حزب را تو بساز! ⬇️")
    for r in rows:
        lead = db.one("SELECT name FROM users WHERE uid=?", (r["leader_uid"],))
        tag = " 🔴 شورشی" if r["rebel"] else ""
        lines.append(f"▫️ <b>{r['name']}</b>{tag} — {r['ideology']}")
        lines.append(f"   👥 {r['members']} عضو · ⚡ قدرت {r['power']} · رهبر: {lead['name'] if lead else '—'}")
    lines.append("")
    lines.append("👥 عضویت با دکمه‌های زیر · ➕ حزب جدید هم همان‌جا")
    return "\n".join(lines)


def join(uid, name: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    party = db.one("SELECT * FROM parties WHERE name=? AND country=?",
                   (name, p["country"]))
    if not party:
        return "⛔ حزبی با این نام در کشورت نیست — فهرست احزاب (منو)"
    if p["party_id"] == party["id"]:
        return "🔒 از قبل عضوی."
    db.ex("UPDATE users SET party_id=? WHERE uid=?", (party["id"], uid))
    db.ex("UPDATE parties SET members=members+1, power=power+5 WHERE id=?",
          (party["id"],))
    return (f"🏛 به حزب <b>{party['name']}</b> پیوستی.\n"
            f"⚡ قدرت حزب: {texts.fa(party['power'] + 5)}")


def statement(uid, body: str) -> str:
    """بیانیه‌ی رسمی حزب — ثبت دائمی + قدرت می‌دهد."""
    p = state.active(uid)
    party = my_party(uid)
    if not p or not party:
        return "⛔ بیانیه فقط برای اعضای حزب — اول حزب بساز یا عضو شو (منو → احزاب)."
    if len(body) < 10:
        return "⛔ متن بیانیه کوتاه است — حداقل ۱۰ حرف."
    t = texts
    db.ex("INSERT INTO statements(party_id,uid,body,ts) VALUES(?,?,?,?)",
          (party["id"], uid, texts.esc(body)[:400], db.now()))
    db.ex("UPDATE parties SET power=power+10 WHERE id=?", (party["id"],))
    return "\n".join([
        t.hdr("بیانیه‌ی رسمی", "📰"),
        f"🏛 حزب: <b>{party['name']}</b>",
        f"🗺 کشور: {countries.COUNTRIES[party['country']]['flag']} "
        f"{countries.COUNTRIES[party['country']]['name']}",
        t.K, f"«{texts.esc(body)[:400]}»", t.K,
        "⚡ قدرت حزب +۱۰ — بیانیه‌ها در آرشیو کشور می‌مانند."])


def rebel(uid) -> str:
    """شورش — حزب قدرتمند علیه دولت."""
    p = state.active(uid)
    party = my_party(uid)
    if not p or not party:
        return "⛔ شورش نیازمند حزب است."
    if party["leader_uid"] != uid:
        return "👑 فقط رهبر حزب می‌تواند شورش اعلام کند."
    if party["power"] < REBEL_POWER:
        return f"⚡ قدرت حزب {party['power']}/{REBEL_POWER} — بیانیه بده و عضو جذب کن."
    if party["rebel"]:
        return "🔴 شورش از قبل فعال است."
    db.ex("UPDATE parties SET rebel=1 WHERE id=?", (party["id"],))
    t = texts
    return "\n".join([
        t.hdr("اعلام شورش", "🚩"),
        f"🏛 حزب <b>{party['name']}</b> در "
        f"{countries.COUNTRIES[party['country']]['name']} قیام کرد!",
        t.K,
        "دولت پاسخ خواهد داد — نبرد سرنوشت کشور است.",
        "⚔️ شورشیان: رزم کنید (منو) — هر پیروزی به شورش نزدیک‌تر است."])


# ═══════════ جاسوسی ═══════════

def spy(uid, target: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    tc = countries.COUNTRIES.get(target)
    if not tc or target == p["country"]:
        return "⛔ کشور هدف نامعتبر یا خودت است."
    if db.now() - int(db.kv_get(f"spy:{uid}", "0")) < SPY_COOLDOWN:
        return (f"⏳ شبکه‌ی جاسوسی در حال بازسازی است — "
                f"{texts.fa(SPY_COOLDOWN // 60)} دقیقه.")
    db.kv_set(f"spy:{uid}", str(db.now()))
    my = countries.COUNTRIES[p["country"]]
    chance = max(0.15, 0.35 + (my["tech"] - tc["tech"]) * 0.12)
    db.ex("UPDATE users SET spy_ops=spy_ops+1 WHERE uid=?", (uid,))
    from game import quests
    quests.on_event(uid, "جاسوسی")
    if random.random() < chance:
        from game import defense as _d, geo as _g
        kind = random.choice(["shield", "ammo", "cities", "plan"])
        if kind == "shield":
            _d.ensure(target)
            rr = db.q("SELECT layer, level FROM defense WHERE cid=? "
                      "ORDER BY level DESC LIMIT 3", (target,))
            info = "🛡 سپر ملی‌شان: " + " · ".join(
                f"{r['layer']} {texts.fa(r['level'])}" for r in rr)
        elif kind == "ammo":
            from game import war as _w
            wr = _w.war_of(target)
            if wr:
                am = int(db.kv_get(f"ammo:{wr['id']}:{target}", "0") or 0)
                info = (f"🎯 مهمات {tc['name']} در جنگ جاری: "
                        f"{texts.fa(am)}/{texts.fa(_w._ammo_total(target))}")
            else:
                info = f"🕊 {tc['name']} در هیچ جنگی نیست"
        elif kind == "cities":
            occ = _g.occupied(target)
            info = ("🏚 شهرهای اشغال‌شده‌ی آن‌ها: " + " · ".join(occ)) if occ \
                else "🟢 همه‌ی شهرهایشان آزاد است"
        else:
            info = random.choice([
                f"📅 برنامه‌ی رزمی {tc['name']} لو رفت — حمله در راه است",
                f"💰 خزانه‌ی {tc['name']} در حال خالی شدن است",
                f"🚀 {tc['name']} تجهیزات نو وارد زرادخانه کرده",
                f"🤝 {tc['name']} در حال عقد پیمان پنهانی است",
                f"🔴 در {tc['name']} شورشی در حال شکل‌گیری است",
            ])
        db.ex("INSERT INTO spyops(uid,target,success,info,ts) VALUES(?,?,1,?,?)",
              (uid, target, info, db.now()))
        state.gain_xp(uid, 40)
        return (f"🕵️ <b>عملیات موفق</b> در {tc['flag']} {tc['name']}\n"
                f"└─ {info}\n⭐ +{texts.fa(40)} XP")
    # 💀 شکست: جان و جریمه‌ی واقعی — دیگر فقط حرف نیست
    db.ex("UPDATE users SET hp=MAX(10,hp-20), money=MAX(0,money-300) WHERE uid=?",
          (uid,))
    return (f"🕵️ <b>مأمور دستگیر شد</b> در {tc['flag']} {tc['name']}\n"
            f"└─ ارتباط قطع شد — جان −{texts.fa(20)}\n"
            f"💰 جریمه: {texts.money(p['country'], 300)}")


# ═══ 🔥 شورش — تغییر رژیم، آزادی از دست‌نشانده ═══

REVOLT_COST = 400
REVOLT_WINDOW = 1800          # ۳۰ دقیقه فرصت حمایت

# رژیم‌های ممکن — اولی وضع موجود (خالی)؛ بعدی‌ها با شورش
REGIMES = {
    "ir": ["", "پهلوی", "جمهوری خلق"],
}
_GENERIC = ["", "حکومت مردمی", "دولت نظامی"]


def regime_of(cid) -> str:
    """🏷 رژیم فعلی کشور — خالی یعنی وضع موجود."""
    import db
    i = int(db.kv_get(f"regime_i:{cid}", "0") or 0)
    lst = REGIMES.get(cid, _GENERIC)
    return lst[i % len(lst)] if i else ""


def _revolt(cid) -> dict:
    import db
    d = db.jload(db.kv_get(f"revolt:{cid}"), None) or {}
    if d and db.now() - int(d.get("ts", 0)) > REVOLT_WINDOW:
        db.kv_del(f"revolt:{cid}")
        return {}
    return d


def revolt_view(uid) -> str:
    """🔥 وضعیت شورش کشور."""
    import db
    import texts
    from game import state, geo
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    c = __import__("countries").COUNTRIES[cid]
    t = texts
    rv = _revolt(cid)
    members = db.q("SELECT uid FROM users WHERE country=?", (cid,))
    need = max(2, (len(members) + 1) // 2)
    col = geo.colony_of(cid)
    lines = [t.hdr("شورش مردمی", "🔥"),
             f"🌍 کشور: {c['flag']} {c['name']}"
             + (f" ({regime_of(cid)})" if regime_of(cid) else ""),
             f"🏷 رژیم فعلی: {regime_of(cid) or 'وضع موجود'}"]
    if col:
        lines.append(f"⛓ زیر یوغ دست‌نشانده‌ی "
                     f"{__import__('countries').COUNTRIES[col]['name']} — "
                     "شورش موفق = آزادی!")
    if rv:
        sup = len(rv.get("sup", []))
        left = max(0, int(rv["ts"]) + REVOLT_WINDOW - db.now()) // 60
        lines += [t.DASH,
                  f"🔥 شورش فعال است! رهبر: {texts.mention(int(rv['by']), 'سرباز')}",
                  f"✊ حمایت: {t.fa(sup)}/{t.fa(need)}",
                  f"⏱ {t.fa(left)} دقیقه فرصت",
                  "", "دکمه‌ی «✊ حمایت» را بزن — نیمی از کشور کافی است!"]
    else:
        lines += [t.DASH,
                  f"💰 هزینه‌ی آغاز شورش: {t.money(cid, REVOLT_COST)}",
                  f"✊ لازم: حمایت {t.fa(need)} نفر از اعضای کشور",
                  "🏆 پیروزی = تغییر رژیم" + (" و آزادی از یوغ!" if col else ""),
                  "", "هر شهروندی می‌تواند آغاز کند."]
    return "\n".join(lines)


def revolt_start(uid) -> str:
    """🔥 آغاز شورش — هزینه دارد، ریسک دارد."""
    import json as _json
    import db
    import texts
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    if _revolt(cid):
        return "🔥 شورش از قبل فعال است — همکاری کن!"
    if p["money"] < REVOLT_COST:
        return f"💰 آغاز شورش {texts.money(cid, REVOLT_COST)} می‌خواهد."
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (REVOLT_COST, uid))
    db.kv_set(f"revolt:{cid}", _json.dumps(
        {"by": uid, "ts": db.now(), "sup": [uid]}, ensure_ascii=False))
    return revolt_view(uid) + "\n\n📣 شهروندان! بیایید!"


def revolt_support(uid) -> str:
    """✊ حمایت از شورش فعال."""
    import db
    import texts
    from game import state, geo
    from game import war as _war
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    rv = _revolt(cid)
    if not rv:
        return "🔥 شورشی فعال نیست — اول یکی آغازش کند."
    sup = rv.get("sup", [])
    if uid not in sup:
        sup.append(uid)
    rv["sup"] = sup
    import json as _json
    db.kv_set(f"revolt:{cid}", _json.dumps(rv, ensure_ascii=False))
    members = db.q("SELECT uid FROM users WHERE country=?", (cid,))
    need = max(2, (len(members) + 1) // 2)
    if len(sup) < need:
        return revolt_view(uid)
    # 🏆 پیروزی شورش — رژیم عوض می‌شود، یوغ می‌شکند
    db.kv_del(f"revolt:{cid}")
    i = int(db.kv_get(f"regime_i:{cid}", "0") or 0)
    lst = REGIMES.get(cid, _GENERIC)
    ni = (i + 1) % len(lst)
    db.kv_set(f"regime_i:{cid}", str(ni))
    new_regime = lst[ni] or "وضع موجود"
    was_colony = geo.colony_of(cid)
    geo.free_colony(cid)
    c = __import__("countries").COUNTRIES[cid]
    _war.PENDING_BBC.append("\n".join([
        "📡 <b>خبر فوری — BBC دارک‌زون</b> 🌍",
        f"Breaking: شورش مردمی در {c['flag']} {c['name']} پیروز شد!",
        f"🏷 حکومت تازه: <b>{new_regime}</b>"
        + (f" — آزاد شد از یوغ "
           f"{__import__('countries').COUNTRIES[was_colony]['name']}!" if was_colony else ""),
        "🔥 ملت، تاریخ ساخت!"]))
    return "\n".join([
        texts.hdr("پیروزی شورش", "🏆"),
        f"🔥 شورش مردمی {c['flag']} {c['name']} پیروز شد!",
        f"🏷 رژیم تازه: <b>{new_regime}</b>",
        "⛓ یوغ دست‌نشانده شکست!" if was_colony else "",
        "📣 خبر در گروه پخش شد."])
