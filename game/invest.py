"""🏭 سرمایه‌گذاری — دارایی‌های درآمد ساعتی؛ دقیق و واقعی.

هر دارایی درآمد ثابت ساعتی دارد؛ ساعت‌های کامل به‌صورت تنبلانه
محاسبه و با «برداشت» به خزانه واریز می‌شود — دقیقه‌های ناقص
حفظ و به ساعت بعد منتقل می‌شوند. پول: دلار — همه‌جا یکسان.
"""
import json

import db
import texts
from game import state


ASSETS = [
    # (کلید، نام، قیمت، درآمد هر ساعت)
    ("mine", "⛏ معدن طلا", 2500, 110),
    ("oil", "🛢 دکل نفت", 6000, 250),
    ("ref", "🏭 پالایشگاه", 15000, 620),
    ("fac", "🏗 کارخانه‌ی تسلیحات", 40000, 1600),
    ("bank", "🏦 بانک سرمایه", 100000, 3900),
]
_A = {a[0]: a for a in ASSETS}


def _bag(uid) -> dict:
    return db.jload(db.kv_get(f"inv:{uid}"), {}) or {}


def _last(uid) -> int:
    return int(db.kv_get(f"invt:{uid}", "0") or 0)


def rate(uid) -> int:
    """💵 مجموع درآمد ساعتی دارایی‌های بازیکن."""
    bag = _bag(uid)
    return sum(_A[k][3] * q for k, q in bag.items() if k in _A)


def view(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    bag = _bag(uid)
    rt = rate(uid)
    lines = [t.hdr("سرمایه‌گذاری", "🏭"),
             f"💰 خزانه: {t.money(p['country'], p['money'])}"]
    if rt:
        h = (db.now() - _last(uid)) / 3600
        lines += [f"💵 درآمد ساعتی: {t.money(p['country'], rt)}",
                  f"⏱ ساعت‌های انباشته: {t.fa(f'{h:.1f}')} — برداشت در پایان هر ساعت کامل"]
    else:
        lines += ["", "هنوز دارایی نداری — هر دارایی هر ساعت پول می‌دهد:"]
    lines.append(t.DASH)
    for key, name, price, inc in ASSETS:
        own = bag.get(key, 0)
        own_s = f" — ✅ {t.fa(own)}×" if own else ""
        lines.append(f"{name}{own_s}\n   قیمت {t.money(p['country'], price)} · "
                     f"درآمد {t.money(p['country'], inc)} در ساعت")
    lines += [t.DASH,
              "💎 هر ساعتِ کامل که بگذرد، درآمدت انباشته می‌شود — «برداشت» را بزن.",
              "⏳ دقیقه‌های ناقص نمی‌سوزند — به ساعت بعد منتقل می‌شوند."]
    return "\n".join(lines)


def buy(uid, key: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if key not in _A:
        return "⛔ دارایی نامعتبر."
    _, name, price, inc = _A[key]
    if p["money"] < price:
        return (f"💰 پول کافی نداری — {name} {texts.money(p['country'], price)} است؛"
                f" داری {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (price, uid))
    bag = _bag(uid)
    bag[key] = bag.get(key, 0) + 1
    db.kv_set(f"inv:{uid}", json.dumps(bag, ensure_ascii=False))
    if not _last(uid):                      # شمارش درآمد از همین لحظه
        db.kv_set(f"invt:{uid}", str(db.now()))
    return "\n".join([
        texts.hdr("خرید دارایی", "🏭"),
        f"✅ {name} خریده شد — {texts.fa(bag[key])}× داری",
        f"💵 درآمد ساعتی‌ات: {texts.money(p['country'], rate(uid))}",
        f"💰 خزانه: {texts.money(p['country'], p['money'] - price)}"])


def collect(uid) -> str:
    """💰 برداشت درآمد — فقط ساعت‌های کامل؛ باقی دقیقه‌ها حفظ می‌شوند."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    rt = rate(uid)
    if not rt:
        return "🏭 هنوز دارایی نداری — اول یکی بخر!"
    last = _last(uid)
    if not last:
        db.kv_set(f"invt:{uid}", str(db.now()))
        return "⏱ شمارش از همین حالا شروع شد — یک ساعت دیگر بیا."
    hours = (db.now() - last) // 3600
    if hours < 1:
        left = 60 - (db.now() - last) // 60
        return f"⏳ هنوز ساعت کامل نشده — {texts.fa(left)} دقیقه دیگر بیا."
    from game import infra as _ifr
    from game import welfare as _wl
    pay = int(rt * hours * _ifr.output_mult(p["country"])
              * _wl.welfare_mult(p["country"]))
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (pay, uid))
    db.kv_set(f"invt:{uid}", str(last + hours * 3600))   # دقیقه‌های ناقص حفظ
    return "\n".join([
        texts.hdr("برداشت درآمد", "💰"),
        f"⏱ {texts.fa(hours)} ساعت × {texts.money(p['country'], rt)}",
        f"✅ {texts.money(p['country'], pay)} به خزانه واریز شد",
        f"💰 خزانه: {texts.money(p['country'], p['money'] + pay)}"])
