"""💰 جنگ جهانی — اقتصاد زنده: نفت، دلار، تورم، تنگه‌ها، تحریم.

هسته‌ی واقعی ۲۰۲۶: قیمت‌ها با دلار و تورم بالا می‌روند؛
بستن تنگه نفت را جهانی می‌کند؛ جنگ و شورش تورم می‌آورد.
"""
import random

import db
import texts
from game import state

# ═══════════ وضعیت جهانی (kv) ═══════════
DEFAULTS = dict(oil=82, dollar=1.0, inflation=0.0, hormuz=1, bab=1, taiwan=1, suez=1)


def world() -> dict:
    w = dict(DEFAULTS)
    w.update(db.jload(db.kv_get("econ"), {}) or {})
    return w


def _save(w: dict):
    import json
    db.kv_set("econ", json.dumps(w, ensure_ascii=False))


def price_factor() -> float:
    """ضریب قیمت: دلار × (۱ + تورم)."""
    w = world()
    return w["dollar"] * (1 + w["inflation"])


def real_price(base: int) -> int:
    return int(base * price_factor())


def tick():
    """هر تیک جهانی — بازار حرکت می‌کند (ربات هوشمند بازار)."""
    w = world()
    # نفت: عرضه/تقاضا + تنگه‌ها
    straits = (w["hormuz"] + w["bab"] + w["taiwan"] + w["suez"]) / 4   # 1=باز
    w["oil"] = max(35, min(240, w["oil"] * (1 + random.uniform(-0.03, 0.03)
                                            + (1 - straits) * 0.06)))
    # دلار: جنگ فعال + بسته‌بودن تنگه‌ها + تورم → دلار قوی
    wars_n = len(db.q("SELECT 1 FROM wars WHERE status='active'"))
    w["dollar"] = max(0.8, min(4.0, w["dollar"] * (1 + random.uniform(-0.01, 0.01)
                                                   + wars_n * 0.004
                                                   + (1 - straits) * 0.01)))
    # تورم: از دلار و جنگ می‌خورد
    w["inflation"] = max(0.0, min(3.0, w["inflation"] + random.uniform(-0.004, 0.006)
                                  + wars_n * 0.003))
    _save(w)
    return w


def sanction_shock(cid: str):
    """تحریم AI — تورم جهانی بالا می‌رود و کشور هدف علامت می‌خورد."""
    w = world()
    w["inflation"] = min(3.0, w["inflation"] + 0.05)
    w["oil"] = min(240, w["oil"] * 1.05)
    _save(w)
    db.kv_set(f"sanction:{cid}", str(db.now()))


def sanctioned(cid: str) -> bool:
    ts = int(db.kv_get(f"sanction:{cid}", "0") or 0)
    return ts and db.now() - ts < 24 * 3600


def on_war_start():
    """جنگ تازه → شوک بازار."""
    w = world()
    w["oil"] = min(240, w["oil"] * 1.15)
    w["dollar"] = min(4.0, w["dollar"] * 1.05)
    _save(w)


def toggle_strait(name: str) -> str:
    """بستن/بازکردن تنگه — فقط رهبر کشور کنترل‌کننده."""
    key = {"هرمز": "hormuz", "باب‌المندب": "bab", "تایوان": "taiwan", "سوئز": "suez"}.get(name)
    if not key:
        return "⛔ تنگه: هرمز · باب‌المندب · تایوان · سوئز"
    w = world()
    w[key] = 0 if w[key] else 1
    _save(w)
    st = "بسته 🚫" if not w[key] else "باز ✅"
    effect = ("نفت جهانی بالا می‌رود — اقتصاد دنیا لرزید!"
              if not w[key] else "عبور آزاد شد — بازار آرام گرفت.")
    return f"🌉 تنگه‌ی <b>{name}</b>: {st}\n└─ {effect}"


# ═══════════ خزانه‌ی کشورها (از نفت) ═══════════
# هر کشور: bpd = بشکه در روز (تقریبی واقعی ۲۰۲۶)
OIL_BPD = {"ir": 1400, "us": 13200, "ru": 9800, "cn": 4000, "de": 20, "gb": 70,
           "fr": 10, "tr": 70, "il": 0, "kp": 10, "kr": 100, "jp": 30, "in": 700,
           "pk": 90, "sa": 9600, "ae": 2800, "iq": 4200, "sy": 100, "ua": 100, "it": 60}


def treasury(cid: str) -> dict:
    t = db.jload(db.kv_get(f"treasury:{cid}"), {}) or {}
    t.setdefault("oil_sold", 0)
    t.setdefault("tax", 0)
    t.setdefault("sanction", 0)
    return t


def oil_income():
    """درآمد روزانه‌ی نفت هر کشور — در تیک جهانی."""
    w = world()
    import countries
    for cid, c in countries.COUNTRIES.items():
        t = treasury(cid)
        bpd = OIL_BPD.get(cid, 0)
        # تنگه بسته + تحریم → فروش کمتر، قیمت بالاتر
        blocked = (w["hormuz"] == 0 and cid in ("ir", "sa", "ae", "iq", "kw" if False else "iq"))
        sold = bpd * (0.35 if blocked else 1.0) * (1 - t["sanction"])
        income = int(sold * w["oil"] / 1000)   # هزار دلار → سکه‌ی بازی
        t["oil_sold"] += income
        import json
        db.kv_set(f"treasury:{cid}", json.dumps(t, ensure_ascii=False))


def sanction(leader_uid: int, target: str) -> str:
    """تحریم کشور — رهبر یک کشور دیگر."""
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبران می‌توانند تحریم اعلام کنند."
    t = treasury(target)
    t["sanction"] = 0.5 if not t["sanction"] else 0
    import json
    db.kv_set(f"treasury:{target}", json.dumps(t, ensure_ascii=False))
    import countries
    tc = countries.COUNTRIES[target]
    if t["sanction"]:
        w = world()
        w["oil"] = min(240, w["oil"] * 1.06)
        _save(w)
        return f"🚫 تحریم {tc['flag']} {tc['name']} — فروش نفت نصف شد."
    return f"✅ تحریم {tc['flag']} {tc['name']} برداشته شد."


def market() -> str:
    """گزارش بازار."""
    w = world()
    t = texts
    straits = [("هرمز", w["hormuz"]), ("باب‌المندب", w["bab"]),
               ("تایوان", w["taiwan"]), ("سوئز", w["suez"])]
    return "\n".join([
        t.hdr("بازار جهانی", "📈"),
        t.row("نفت برنت", f"🛢 ${w['oil']:.0f}"),
        t.row("شاخص دلار", f"💵 ×{w['dollar']:.2f}"),
        t.row("تورم", f"📊 {w['inflation'] * 100:.1f}٪"),
        "", "🌉 <b>تنگه‌ها:</b>",
        *[f"▫️ {n}: {'باز ✅' if v else 'بسته 🚫'}" for n, v in straits],
        t.K,
        f"💰 قیمت واقعی تجهیزات = پایه × {price_factor():.2f}",
        "جنگ و تورم، خزانه‌ات را می‌خورند."])
