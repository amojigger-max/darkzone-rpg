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


def fx(cid: str) -> float:
    """💱 نرخ زنده‌ی پول هر کشور — جنگ، تحریم و تورم آن را بالا و پایین می‌برد.

    نرخ بالا = پول ضعیف‌تر (برای هر سکه، پولِ بیشتری می‌شماری).
    """
    import countries
    base = countries.CURRENCIES.get(cid, ("دلار", 1.0))[1]
    mult = 1.0
    w = world()
    mult *= 1 + w["inflation"] * 0.4              # تورم جهانی
    if db.one("SELECT 1 FROM wars WHERE status='active' AND (a=? OR b=?)", (cid, cid)):
        mult *= 1.15                              # جنگ → پول ضعیف
    if sanctioned(cid):
        mult *= 1.20                              # تحریم → پول ضعیف‌تر
    return base * mult


def sanctioned(cid: str) -> bool:
    ts = int(db.kv_get(f"sanction:{cid}", "0") or 0)
    return ts and db.now() - ts < 24 * 3600


def on_war_start():
    """جنگ تازه → شوک بازار."""
    w = world()
    w["oil"] = min(240, w["oil"] * 1.15)
    w["dollar"] = min(4.0, w["dollar"] * 1.05)
    _save(w)


def toggle_strait(uid: int, name: str) -> str:
    """بستن/بازکردن تنگه — فقط رهبران."""
    p = state.active(uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبر کشور می‌تواند تنگه را ببندد یا باز کند."
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


def oil_share(cid: str) -> int:
    """🛢 سهم روزانه‌ی هر بازیکن از درآمد نفت کشورش — واقعی و شفاف.

    بشکه‌درروز × قیمت نفت / ۸۰۰۰ → سهم کل کشور در روز؛
    بسته‌بودن هرمز فروش کشورهای خلیج فارس را ۶۵٪ کم می‌کند،
    تحریم آن را نصف؛ بین بازیکنان کشور تقسیم می‌شود. سقف: ۲۰۰.
    """
    w = world()
    bpd = OIL_BPD.get(cid, 0)
    pot = bpd * w["oil"] / 8000.0
    if w["hormuz"] == 0 and cid in ("ir", "sa", "ae", "iq", "kw"):
        pot *= 0.35                      # تنگه بسته — فروش افت کرد
    if sanctioned(cid):
        pot *= 0.5                       # تحریم — خریدار کمتر پیدا می‌شود
    n = db.one("SELECT COUNT(*) n FROM users WHERE country=?", (cid,))["n"]
    if n <= 0:
        return 0
    return int(min(200, pot / n))


def sanction(leader_uid: int, target: str) -> str:
    """تحریم کشور — رهبر یک کشور دیگر. یک سیستم واحد با تحریم AI:
    نرخ ارز ضعیف‌تر (fx)، سهم نفت نصف، ۲۴ ساعت اعتبار."""
    p = state.active(leader_uid)
    if not p or not p["is_leader"]:
        return "👑 فقط رهبران می‌توانند تحریم اعلام کنند."
    if target == p["country"]:
        return "🤡 کشور خودت را تحریم کنی؟"
    import countries
    tc = countries.COUNTRIES.get(target)
    if not tc:
        return "⛔ کشور نامعتبر."
    if sanctioned(target):
        db.kv_set(f"sanction:{target}", "0")
        return f"✅ تحریم {tc['flag']} {tc['name']} برداشته شد."
    db.kv_set(f"sanction:{target}", str(db.now()))
    w = world()
    w["oil"] = min(240, w["oil"] * 1.06)
    _save(w)
    return (f"🚫 تحریم {tc['flag']} {tc['name']} — "
            f"نفتش نصف فروخته می‌شود و پولش ضعیف شد (۲۴ ساعت).")


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
        f"💰 قیمت تجهیزات = پایه × {texts.fa(f'{price_factor():.2f}')} — جنگ و تورم خزانه را می‌خورند"])
