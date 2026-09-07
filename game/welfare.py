"""🏘 رفاه مردم — رضایت، نیازسنجی دقیق، شورش خودکار.

هر کشور جمعیت واقعی دارد و نیاز جداگانه:
  🕌 مسجد / ⛪ کلیسا / 🛕 معبد — بر اساس دین اکثریت
  🏥 بیمارستان · 🏘 مسکن
رضایت (۰-۱۰۰) به‌صورت تنبلانه و دقیق شبیه‌سازی می‌شود:
  هدف = ۲۰ + ۷۰×پوشش نیازها (جنگ: −۱۰)
  هر ساعت ۲۰٪ به سمت هدف می‌رود: sat = h + (sat-h)×0.8^h
اثر واقعی:
  رضایت ≥ ۸۵ → ۲۰٪ درآمد بیشتر (کار، جیره، سرمایه‌گذاری)
  رضایت < ۳۵ → شورش خودکار: رژیم عوض می‌شود + خسارت زیرساخت
"""
import json
import math

import countries
import db
import texts

# جمعیت (میلیون) — ۵۰ کشور
POP = {
    "ir": 85, "us": 335, "ru": 144, "cn": 1400, "de": 84, "gb": 68,
    "fr": 65, "tr": 85, "il": 9, "kp": 26, "kr": 52, "jp": 124,
    "in": 1430, "pk": 240, "sa": 36, "ae": 10, "iq": 44, "sy": 22,
    "ua": 38, "it": 59, "hz": 11, "br": 215, "mx": 128, "ar": 46,
    "ca": 39, "au": 26, "eg": 106, "za": 60, "ng": 220, "id": 275,
    "my": 34, "th": 72, "vn": 98, "ph": 114, "es": 48, "pt": 10,
    "nl": 18, "be": 12, "se": 10, "no": 6, "dk": 6, "fi": 6,
    "pl": 38, "gr": 10, "ch": 9, "at": 9, "kz": 19, "az": 10,
    "qa": 3, "kw": 4,
}
# دین اکثریت → مکان عبادت
MOSQUE = {"ir", "sa", "ae", "iq", "sy", "eg", "pk", "az", "kz", "qa",
          "kw", "tr", "id", "my", "ng"}
TEMPLE = {"cn", "jp", "in", "th", "vn"}
# بقیه → کلیسا


def faith_of(cid) -> tuple:
    """مکان عبادت کشور — (کلید، نام، ایموجی)."""
    if cid in MOSQUE:
        return ("mosque", "مسجد", "🕌")
    if cid in TEMPLE:
        return ("temple", "معبد", "🛕")
    return ("church", "کلیسا", "⛪")


def needs(cid) -> dict:
    """نیاز دقیق کشور — چند بیمارستان/مکان عبادت/مسکن."""
    p = POP.get(cid, 20)
    fk, fn, fe = faith_of(cid)
    return {"hospital": max(2, math.ceil(p / 12)),
            fk: max(1, math.ceil(p / 20)),
            "housing": max(2, math.ceil(p / 15))}


PRICE = {"hospital": 3500, "mosque": 2000, "church": 2000,
         "temple": 2000, "housing": 2500}
NAME = {"hospital": "🏥 بیمارستان", "mosque": "🕌 مسجد",
        "church": "⛪ کلیسا", "temple": "🛕 معبد", "housing": "🏘 مسکن"}


def _state(cid) -> dict:
    """وضعیت رفاه کشور — sat، ساختمان‌ها، تیکِ ساعت."""
    st = db.jload(db.kv_get(f"welf:{cid}"), None) or {}
    return {"sat": int(st.get("sat", 50)),
            "b": dict(st.get("b", {})),
            "ts": int(st.get("ts", 0))}


def _save(cid, st):
    db.kv_set(f"welf:{cid}", json.dumps(st, ensure_ascii=False))


def _tick(cid) -> dict:
    """⏱ شبیه‌سازی تنبلانه — هر ساعت ۲۰٪ به سمت هدف."""
    st = _state(cid)
    if not st["ts"]:
        st["ts"] = db.now()
        _save(cid, st)
        return st
    hours = min(72, (db.now() - st["ts"]) // 3600)
    if hours < 1:
        return st
    nd = needs(cid)
    cov = sum(min(1.0, st["b"].get(k, 0) / n) for k, n in nd.items()) / len(nd)
    target = 20 + 70 * cov
    from game import war as _w
    if _w.war_of(cid):
        target -= 10
    target = max(5, min(95, target))
    st["sat"] = int(round(target + (st["sat"] - target) * (0.8 ** hours)))
    st["ts"] = db.now()
    _save(cid, st)
    return st


def sat_of(cid) -> int:
    """😊 رضایت فعلی مردم — با تیک تنبلانه."""
    return _tick(cid)["sat"]


def welfare_mult(cid) -> float:
    """😊 رضایت ≥ ۸۵ → ۲۰٪ درآمد بیشتر."""
    return 1.20 if sat_of(cid) >= 85 else 1.0


def check_uprising(cid) -> str:
    """🔥 رضایت < ۳۵ → شورش خودکار — رژیم عوض، خسارت، خبر."""
    st = _tick(cid)
    day = db.day_index()
    if st["sat"] >= 35 or db.kv_get(f"uprising:{cid}:{day}"):
        return ""
    db.kv_set(f"uprising:{cid}:{day}", "1")
    st["sat"] = 55                      # خشم تخلیه شد
    _save(cid, st)
    from game import geo, infra, politics, war
    c = countries.COUNTRIES[cid]
    # خشم مردم: زیرساخت آسیب می‌بیند
    from game import infra as _inf
    import random as _r
    _inf.damage(cid, _r.choice([k for k, _, _ in _inf.INFRA]), _r.randint(10, 20))
    # دست‌نشانده هم آزاد می‌شود
    was = geo.colony_of(cid)
    geo.free_colony(cid)
    i = int(db.kv_get(f"regime_i:{cid}", "0") or 0)
    lst = politics.REGIMES.get(cid, politics._GENERIC)
    ni = (i + 1) % len(lst)
    db.kv_set(f"regime_i:{cid}", str(ni))
    new_r = lst[ni] or "وضع موجود"
    war.PENDING_BBC.append("\n".join([
        "📡 <b>خبر فوری — BBC دارک‌زون</b> 🌍",
        f"Breaking: رضایت مردم {c['flag']} {c['name']} به زیر ۳۵٪ افتاد — "
        "شورش سراسری!",
        f"🏷 رژیم سرنگون شد — حکومت تازه: <b>{new_r}</b>",
        "🏗 زیرساخت آسیب دید · 🔥 خشم مردم تخلیه شد (رضایت ۵۵٪)"
        + (f" · ⛓ از یوغ دست‌نشانده آزاد شد!" if was else "")]))
    return "\n".join([
        texts.hdr("شورش سراسری!", "🔥"),
        f"😠 رضایت مردم {c['flag']} {c['name']} زیر ۳۵٪ بود — مردم شوریدند!",
        f"🏷 رژیم سرنگون شد → <b>{new_r}</b>",
        "🏗 زیرساخت آسیب دید · رضایت به ۵۵٪ برگشت",
        "🏘 بساز تا مردم راضی بمانند: منو → رفاه مردم"])


def view(uid) -> str:
    """🏘 پنل رفاه کشور — رضایت، نیازها، اثرها."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    out = check_uprising(cid)
    if out:
        return out
    st = _tick(cid)
    c = countries.COUNTRIES[cid]
    nd = needs(cid)
    t = texts
    sat = st["sat"]
    mood = ("😍 عالی" if sat >= 85 else "🙂 راضی" if sat >= 60
            else "😐 معمولی" if sat >= 45 else "😟 ناراضی" if sat >= 35
            else "😡 در آستانه‌ی شورش")
    bar = "🟩" if sat >= 85 else "🟨" if sat >= 60 else "🟧" if sat >= 35 else "🟥"
    lines = [t.hdr(f"رفاه مردم {c['name']}", "🏘"),
             f"{bar} <b>رضایت: {t.fa(sat)}٪</b> — {mood}",
             f"👥 جمعیت: {t.fa(POP.get(cid, 20))} میلیون"]
    if sat >= 85:
        lines.append("🎉 رضایت بالا → <b>۲۰٪ درآمد بیشتر</b> برای همه!")
    elif sat < 35:
        lines.append("🔥 هشدار: زیر ۳۵٪ = شورش سراسری!")
    lines += [t.DASH, "📋 <b>نیازسنجی دقیق کشور:</b> (داری/لازم)"]
    for k, n in nd.items():
        own = st["b"].get(k, 0)
        mark = "✅" if own >= n else "❌"
        lines.append(f"{mark} {NAME[k]}: {t.fa(own)}/{t.fa(n)}"
                     + (f" — ساخت {t.money(cid, PRICE[k])}" if own < n else ""))
    lines += [t.DASH,
              "💡 هر عضو کشور می‌تواند بسازد — سود برای همه",
              "📈 رضایت هر ساعت به سمت نیازها حرکت می‌کند"]
    return "\n".join(lines)


def build(uid, key: str) -> str:
    """🏗 ساخت اماکن رفاه."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if key not in PRICE:
        return "⛔ ساختمان نامعتبر."
    cid = p["country"]
    st = _tick(cid)
    price = PRICE[key]
    if p["money"] < price:
        return (f"💰 پول کافی نداری — {NAME[key]}: {texts.money(cid, price)}"
                f" · داری {texts.money(cid, p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (price, uid))
    st["b"][key] = st["b"].get(key, 0) + 1
    _save(cid, st)
    nd = needs(cid)
    own = st["b"][key]
    n = nd.get(key, 0)
    return "\n".join([
        texts.hdr("ساخت اماکن رفاه", "🏗"),
        f"✅ {NAME[key]} ساخته شد — {texts.fa(own)}/{texts.fa(n)}",
        f"💸 هزینه: {texts.money(cid, price)}",
        f"😊 رضایت فعلی: {texts.fa(sat_of(cid))}٪"])
