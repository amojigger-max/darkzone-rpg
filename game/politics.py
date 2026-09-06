"""🏛 جنگ جهانی — سیاست: حزب، بیانیه، شورش، رهبری، جاسوسی."""
import random

import db
import countries
import texts
from game import state

PARTY_COST = 5000
REBEL_POWER = 300          # قدرت لازم برای شورش
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
        return "🪖 ساخت حزب نیازمند عضویت نظامی است — «ارتچی»"
    if my_party(uid):
        return "🔒 قبلاً در حزبی هستی."
    if len(name) < 3 or len(name) > 28:
        return "⛔ نام حزب: ۳ تا ۲۸ حرف."
    if p["money"] < PARTY_COST:
        return f"💰 تأسیس حزب {PARTY_COST:,} می‌ارزد — داری: {p['money']:,}"
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (PARTY_COST, uid))
    db.ex("INSERT INTO parties(name,country,ideology,leader_uid,members,power,created) "
          "VALUES(?,?,?,?,1,10,?)", (texts.esc(name), p["country"],
                                     texts.esc(ideology or "ملی")[:24], uid, db.now()))
    pid = db.one("SELECT last_insert_rowid() id")["id"]
    db.ex("UPDATE users SET party_id=? WHERE uid=?", (pid, uid))
    return (f"🏛 حزب <b>{texts.esc(name)}</b> رسماً تأسیس شد!\n"
            f"ایدئولوژی: {texts.esc(ideology or 'ملی')}\n"
            f"برای عضوگیری: «احزاب» — برای اعلام مواضع: «بیانیه متن»")


def list_parties(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    rows = db.q("SELECT * FROM parties WHERE country=? ORDER BY power DESC LIMIT 10",
                (p["country"],))
    c = countries.COUNTRIES[p["country"]]
    lines = [texts.hdr(f"احزاب {c['name']}", "🏛"), ""]
    if not rows:
        lines.append("هنوز حزبی نیست — «حزب نام» بساز!")
    for r in rows:
        lead = db.one("SELECT name FROM users WHERE uid=?", (r["leader_uid"],))
        tag = " 🔴 شورشی" if r["rebel"] else ""
        lines.append(f"▫️ <b>{r['name']}</b>{tag} — {r['ideology']}")
        lines.append(f"   👥 {r['members']} عضو · ⚡ قدرت {r['power']} · رهبر: {lead['name'] if lead else '—'}")
    lines.append("")
    lines.append("عضویت: «عضویت نام‌حزب»")
    return "\n".join(lines)


def join(uid, name: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    party = db.one("SELECT * FROM parties WHERE name=? AND country=?",
                   (name, p["country"]))
    if not party:
        return "⛔ حزبی با این نام در کشورت نیست — «احزاب»"
    if p["party_id"] == party["id"]:
        return "🔒 از قبل عضوی."
    db.ex("UPDATE users SET party_id=? WHERE uid=?", (party["id"], uid))
    db.ex("UPDATE parties SET members=members+1, power=power+5 WHERE id=?",
          (party["id"],))
    return f"🏛 به حزب <b>{party['name']}</b> پیوستی.\nقدرت حزب: ⚡ {party['power'] + 5}"


def statement(uid, body: str) -> str:
    """بیانیه‌ی رسمی حزب — ثبت دائمی + قدرت می‌دهد."""
    p = state.active(uid)
    party = my_party(uid)
    if not p or not party:
        return "⛔ بیانیه فقط برای اعضای حزب — «حزب نام» بساز یا عضو شو."
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
        "⚔️ شورشیان: «رزم» بزنید — هر پیروزی به شورش نزدیک‌تر است."])


# ═══════════ جاسوسی ═══════════

def spy(uid, target: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    tc = countries.COUNTRIES.get(target)
    if not tc or target == p["country"]:
        return "⛔ کشور هدف نامعتبر یا خودت است."
    if db.now() - int(db.kv_get(f"spy:{uid}", "0")) < SPY_COOLDOWN:
        return f"⏳ شبکه‌ی جاسوسی در حال بازسازی است — {SPY_COOLDOWN // 60} دقیقه."
    db.kv_set(f"spy:{uid}", str(db.now()))
    my = countries.COUNTRIES[p["country"]]
    chance = 0.35 + (my["tech"] - tc["tech"]) * 0.12
    db.ex("UPDATE users SET spy_ops=spy_ops+1 WHERE uid=?", (uid,))
    from game import quests
    quests.on_event(uid, "جاسوسی")
    if random.random() < chance:
        info = random.choice([
            f"📅 برنامه‌ی رزمی {tc['name']} لو رفت — حمله در راه است",
            f"💰 خزانه‌ی {tc['name']} در حال خالی شدن است",
            f"🚀 {tc['name']} تجهیزات نو وارد زرادخانه کرده",
            f"🤝 {tc['name']} در حال عقد پیمان پنهانی است",
            f"🔴 در {tc['name']} شورشی در حال شکل‌گیری است",
        ])
        db.ex("INSERT INTO spyops(uid,target,success,info,ts) VALUES(?,?,1,?,?)",
              (uid, target, info, db.now()))
        return (f"🕵️ <b>عملیات موفق</b> در {tc['flag']} {tc['name']}\n"
                f"└─ {info}\n⭐ +۴۰ XP")
    state.gain_xp(uid, 40)
    return (f"🕵️ <b>مأمور دستگیر شد</b> در {tc['flag']} {tc['name']}\n"
            f"└─ ارتباط قطع شد — جان −۲۰\n💰 جریمه: ۳۰۰")
