"""🪖 جنگ جهانی — نظامی: شاخه‌ها، تجهیزات، تعمیر، رزم."""
import random

import db
import countries
import texts
from game import state


def branch_name(p) -> str:
    c = countries.COUNTRIES.get(p["country"])
    if not c or not p["branch"]:
        return ""
    try:
        return c["branches"][p["branch"]]
    except Exception:
        return ""


def join_branch(uid, idx: int) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if p["branch"]:
        return "🔒 قبلاً عضو شده‌ای."
    c = countries.COUNTRIES[p["country"]]
    if idx < 0 or idx >= len(c["branches"]):
        return "⛔ شاخه نامعتبر."
    db.ex("UPDATE users SET branch=? WHERE uid=?", (idx, uid))
    t = texts
    return "\n".join([
        t.hdr("عضویت نظامی", "🪖"),
        t.row("شاخه", c["branches"][idx]),
        t.row("کشور", f"{c['flag']} {c['name']}"),
        "", "اکنون سرباز این شاخه‌ای — درجه با رزم بالا می‌رود.",
        "🛒 تجهیزات: «تجهیزات» · ⚔️ رزم: «رزم»"])


# ═══════════ تجهیزات ═══════════

def arsenal(uid) -> str:
    """زرادخانه‌ی مخصوص کشور بازیکن."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    c = countries.COUNTRIES[p["country"]]
    lines = [texts.hdr(f"زرادخانه {c['name']}", "🛒"), ""]
    for iid in c["items"]:
        nm, em, _, atk, guard, price, _ = (None,) * 7
        it = countries.ITEMS[iid]
        own = db.one("SELECT qty,dur FROM inventory WHERE uid=? AND iid=?", (uid, iid))
        mark = f"✅ (دوام {own['dur']}٪)" if own else f"💰 {it[5]:,}"
        lines.append(f"{it[1]} <b>{it[0]}</b> — ⚔️{it[3]} 🛡{it[4]} · {mark}")
    lines += ["", "خرید: «خرید نام‌تجهیز» · تعمیر: «تعمیر»"]
    return "\n".join(lines)


def buy(uid, iid: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    it = countries.ITEMS.get(iid)
    if not it or iid not in countries.COUNTRIES[p["country"]]["items"]:
        return "⛔ این تجهیز در زرادخانه‌ی کشورت نیست."
    if db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid)):
        return "✅ از قبل داری."
    if p["money"] < it[5]:
        return f"💰 پول کم داری — لازم: {it[5]:,} · داری: {p['money']:,}"
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (it[5], uid))
    db.ex("INSERT OR REPLACE INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100)", (uid, iid))
    return f"🛒 <b>{it[0]}</b> {it[1]} خریداری شد — دوام ۱۰۰٪"


def repair(uid) -> str:
    """تعمیر همه‌ی تجهیزات خراب — هزینه‌ی واقعی."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    rows = db.q("SELECT i.iid, i.dur FROM inventory i WHERE i.uid=? AND i.dur<100", (uid,))
    if not rows:
        return "🔧 همه‌ی تجهیزات سالم‌اند."
    total = 0
    for r in rows:
        cost = (100 - r["dur"]) * 30
        if p["money"] < total + cost:
            break
        total += cost
        db.ex("UPDATE inventory SET dur=100 WHERE uid=? AND iid=?", (uid, r["iid"]))
    if total == 0:
        return "💰 پول تعمیر کافی نیست — «جیره» بگیر یا رزم کن."
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (total, uid))
    return f"🔧 تعمیر کامل انجام شد — هزینه: 💰 {total:,}"


def loadout(uid):
    """بهترین تجهیز تهاجمی + دفاعی بازیکن → (atk_item, def_item, atk, guard)."""
    rows = db.q("SELECT n.iid, n.dur FROM inventory n WHERE n.uid=? AND n.dur>10", (uid,))
    if not rows:
        return None, None, 0, 0
    best_a = max(rows, key=lambda r: countries.ITEMS[r["iid"]][3] * r["dur"] // 100)
    best_d = max(rows, key=lambda r: countries.ITEMS[r["iid"]][4] * r["dur"] // 100)
    a = countries.ITEMS[best_a["iid"]]
    d = countries.ITEMS[best_d["iid"]]
    return a, d, a[3] * best_a["dur"] // 100, d[4] * best_d["dur"] // 100


# ═══════════ رزم ═══════════

ENEMIES = [("شبه‌نظامی دشمن", 60, 10), ("گروه شناسایی", 90, 14), ("کاروان زرهی", 140, 20),
           ("پایگاه مرزی", 200, 26), ("نیروی ویژه دشمن", 280, 34)]


def battle(uid, tier: int = None) -> str:
    """نبرد خودکار با گزارش کوتاه — تجهیزات واقعی دوام می‌بازند."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if not p["branch"]:
        return "🪖 اول به شاخه‌ای بپیوند — «ارتچی»"
    if db.now() - int(db.kv_get(f"battle:{uid}", "0")) < 20:
        return "⏳ ۲۰ ثانیه بین نبردها صبر کن."
    db.kv_set(f"battle:{uid}", str(db.now()))
    tier = tier if tier is not None else random.randint(0, min(4, p["level"]))
    name, ehp, eatk = ENEMIES[tier]
    a, d, atk, guard = loadout(uid)
    wpn = a[0] if a else "تفنگ سبک"
    log = []
    turn = 0
    while turn < 12 and ehp > 0 and p["hp"] > 0:
        turn += 1
        dmg = max(4, int((atk + 10 + p["level"] * 3) * random.uniform(0.7, 1.3)))
        ehp -= dmg
        log.append(f"⚔️ {wpn} → −{dmg}")
        if ehp <= 0:
            break
        edmg = max(3, int(eatk * random.uniform(0.6, 1.1)) - guard // 2)
        db.ex("UPDATE users SET hp=MAX(0,hp-?) WHERE uid=?", (edmg, uid))
        p = state.active(uid)
        log.append(f"🩸 ضدحمله → −{edmg}")
    # فرسایش دوام تجهیزات استفاده‌شده
    for r in db.q("SELECT iid FROM inventory WHERE uid=? AND dur>10", (uid,)):
        it = countries.ITEMS[r["iid"]]
        if a and it[0] == a[0]:
            db.ex("UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?",
                  (random.randint(4, 10), uid, r["iid"]))
    t = texts
    if ehp <= 0:
        loot = (tier + 1) * 350
        xp = 60 + tier * 40
        db.ex("UPDATE users SET money=money+?, kills=kills+1, hp=MAX(20,hp) WHERE uid=?",
              (loot, uid))
        state.gain_xp(uid, xp)
        return "\n".join([
            t.hdr("پیروزی در رزم", "🏆"),
            t.row("دشمن", name), "",
            *log[:6], "",
            t.row("غنیمت", f"💰 {loot:,} · ⭐ {xp} XP"),
            t.row("جان", f"❤️ {p['hp']}/{p['max_hp']}")])
    db.ex("UPDATE users SET hp=MAX(10,hp) WHERE uid=?", (uid,))
    return "\n".join([
        t.hdr("عقب‌نشینی", "💨"),
        t.row("دشمن", name), "",
        *log[:6], "",
        "جان کم آمد — «استراحت» یا «تعمیر» لازم است."])


def rest(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if db.now() - int(db.kv_get(f"rest:{uid}", "0")) < 120:
        return "⏳ استراحت داده شد — ۲ دقیقه صبر کن."
    db.kv_set(f"rest:{uid}", str(db.now()))
    db.ex("UPDATE users SET hp=max_hp WHERE uid=?", (uid,))
    return f"🏥 جان کامل شد: ❤️ {p['max_hp']}/{p['max_hp']}"
