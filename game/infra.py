"""🏗 زیرساخت ملی — برق، فرودگاه، بندر، صنعت.

جنگ واقعی است: هر برخورد دشمن ممکن است زیرساخت کشورت را بشکند.
زیرساخت آسیب‌دیده درآمد را کم می‌کند و محدودیت می‌سازد:
  ⚡ برق < ۵۰٪ → خرید تجهیزات سنگین ممنوع
  🛫 فرودگاه < ۵۰٪ → ضربت هوایی/پهپادی خودت ۲۰٪ ضعیف‌تر
  🚢 بندر < ۵۰٪ → واردات متوقف
  🏭 صنعت → سهم بزرگ درآمد
تعمیر با دلار — هر عضو کشور می‌تواند کمک کند.
"""
import json

import countries
import db
import texts


INFRA = [
    ("power", "⚡ شبکه برق", 2500),
    ("airport", "🛫 فرودگاه", 3000),
    ("port", "🚢 بندر", 3000),
    ("industry", "🏭 مجتمع صنعتی", 4000),
]
_I = {k: (k, n, p) for k, n, p in INFRA}


def state_of(cid) -> dict:
    """hp هر زیرساخت کشور — پیش‌فرض ۱۰۰."""
    st = db.jload(db.kv_get(f"infra:{cid}"), {}) or {}
    return {k: max(0, min(100, int(st.get(k, 100)))) for k, _, _ in INFRA}


def _save(cid, st):
    db.kv_set(f"infra:{cid}", json.dumps(st, ensure_ascii=False))


def output_mult(cid) -> float:
    """💵 ضریب درآمد ملی — میانگین سلامت زیرساخت + جایزه‌ی شهرک مسکونی."""
    st = state_of(cid)
    base = (sum(st.values()) / (100 * len(st))) if st else 1.0
    return base * 1.10 if built(cid)["housing"] else base


def power_ok(cid) -> bool:
    return state_of(cid)["power"] >= 50


def port_ok(cid) -> bool:
    return state_of(cid)["port"] >= 50


def airport_mult(cid) -> float:
    """✈️ فرودگاه آسیب‌دیده → ضربت هوایی/پهپادی ضعیف‌تر."""
    return 0.8 if state_of(cid)["airport"] < 50 else 1.0


def limit_notes(cid) -> list:
    st = state_of(cid)
    out = []
    if st["power"] < 50:
        out.append("⚡ برق ضعیف — خرید تجهیزات سنگین ممنوع")
    if st["airport"] < 50:
        out.append("🛫 فرودگاه خراب — ضربت هوایی/پهپادی ۲۰٪ ضعیف‌تر")
    if st["port"] < 50:
        out.append("🚢 بندر خراب — واردات متوقف")
    if st["industry"] < 50:
        out.append("🏭 صنعت فروریخته — درآمد ملی افت کرده")
    return out


def damage(cid, key: str, pct: int) -> dict:
    """💥 آسیب به یک زیرساخت — hp جدید برمی‌گردد."""
    st = state_of(cid)
    st[key] = max(0, st[key] - pct)
    _save(cid, st)
    return {"key": key, "hp": st[key]}


def random_damage(cid, rnd) -> dict:
    """🎯 یک زیرساخت تصادفی آسیب می‌بیند (۶–۱۲٪)."""
    key = rnd.choice([k for k, _, _ in INFRA])
    return damage(cid, key, rnd.randint(6, 12))


def _bar(hp) -> str:
    if hp >= 75:
        return "🟩"
    if hp >= 50:
        return "🟨"
    if hp >= 25:
        return "🟧"
    return "🟥"


def view(uid) -> str:
    """🏗 وضعیت زیرساخت کشور + هزینه تعمیر."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    c = countries.COUNTRIES[p["country"]]
    st = state_of(p["country"])
    t = texts
    lines = [t.hdr(f"زیرساخت {c['name']}", "🏗"),
             f"💵 ضریب درآمد ملی: {t.fa(int(output_mult(p['country']) * 100))}٪",
             ""]
    for key, name, price in INFRA:
        lines.append(f"{_bar(st[key])} {name}: {t.fa(st[key])}٪"
                     + (f" — تعمیر کامل {t.money(p['country'], price * (100 - st[key]) // 100)}"
                        if st[key] < 100 else " — ✅ سالم"))
    notes = limit_notes(p["country"])
    if notes:
        lines += ["", "⚠️ <b>محدودیت‌های فعال:</b>"] + [f"▫️ {n}" for n in notes]
    lines += ["", "💰 هر عضو کشور می‌تواند کمک کند — دکمه‌ی تعمیر زیرین."]
    return "\n".join(lines)


def repair(uid, key: str) -> str:
    """🔧 پرداخت و تعمیر — هزینه‌ی متناسب با آسیب، رند به ۱۰."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if key not in _I:
        return "⛔ زیرساخت نامعتبر."
    _, name, full = _I[key]
    st = state_of(p["country"])
    missing = 100 - st[key]
    if missing <= 0:
        return f"✅ {name} سالم است — چیزی برای تعمیر نیست."
    cost = max(10, full * missing // 100 // 10 * 10)
    if p["money"] < cost:
        return (f"💰 پول کافی نداری — تعمیر {name}: {texts.money(p['country'], cost)}"
                f" · داری {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (cost, uid))
    st[key] = 100
    _save(p["country"], st)
    return "\n".join([
        texts.hdr("تعمیر زیرساخت", "🔧"),
        f"✅ {name} کامل تعمیر شد — ۱۰۰٪",
        f"💸 هزینه: {texts.money(p['country'], cost)}",
        f"💵 ضریب درآمد ملی: {texts.fa(int(output_mult(p['country']) * 100))}٪"])


# ═══ 🏗🏗 ساخت‌وساز ملی — هر کشور یک‌بار، سودش برای همه‌ی اعضا ═══
BUILDINGS = [
    ("base", "🏕 پایگاه نظامی", 8000, "+۱۰٪ قدرت ضربت کشور"),
    ("housing", "🏘 شهرک مسکونی", 5000, "+۱۰٪ درآمد ملی"),
    ("bunker", "🛡 پناهگاه ملی", 6000, "−۱۰٪ آسیب بمباران دشمن"),
]
_B = {k: (k, n, p, e) for k, n, p, e in BUILDINGS}


def built(cid) -> dict:
    """چه ساختمان‌هایی ساخته شده."""
    st = db.jload(db.kv_get(f"built:{cid}"), {}) or {}
    return {k: bool(st.get(k)) for k, _, _, _ in BUILDINGS}


def build(uid, key: str) -> str:
    """🏗 ساخت ساختمان ملی — پول می‌دهد، همه‌ی کشور سود می‌برند."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if key not in _B:
        return "⛔ ساختمان نامعتبر."
    _, name, price, eff = _B[key]
    b = built(p["country"])
    if b[key]:
        return f"✅ {name} از قبل ساخته شده — اثرش فعال است."
    if p["money"] < price:
        return (f"💰 پول کافی نداری — {name}: {texts.money(p['country'], price)}"
                f" · داری {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (price, uid))
    b[key] = True
    db.kv_set(f"built:{p['country']}", json.dumps(b, ensure_ascii=False))
    return "\n".join([
        texts.hdr("ساخت‌وساز ملی", "🏗"),
        f"✅ {name} ساخته شد!",
        f"🎁 اثر برای همه‌ی کشور: {eff}",
        f"💸 هزینه: {texts.money(p['country'], price)}"])


def strike_mult(cid) -> float:
    """🏕 پایگاه نظامی → ضربت کشور ۱۰٪ قوی‌تر."""
    return 1.10 if built(cid)["base"] else 1.0


def damage_in_mult(cid) -> float:
    """🛡 پناهگاه ملی → آسیب بمباران ۱۰٪ کمتر."""
    return 0.90 if built(cid)["bunker"] else 1.0


def buildings_view(uid) -> str:
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    b = built(p["country"])
    lines = ["🏗 <b>ساخت‌وساز ملی</b> — یک‌بار برای همیشه، سود برای همه"]
    for key, name, price, eff in BUILDINGS:
        mark = "✅ ساخته شد" if b[key] else f"💰 {texts.money(p['country'], price)}"
        lines.append(f"{name} — {eff}\n   {mark}")
    return "\n".join(lines)
