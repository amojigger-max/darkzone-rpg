"""🛃 عوارض تنگه هرمز — امتیاز ویژه‌ی ایران.

ایران می‌تواند عوارض تنگه را روشن/خاموش کند (رهبر ایران).
وقتی روشن است:
  • هر بازیکن غیرایرانی هر روز ۲۰۰ دلار عوارض می‌دهد («عوارض» یا منو)
  • اگر تا پایان روز ندهد → ۱۰٪ پولش می‌سوزد
  • عوارض‌ها در صندوق جمع می‌شود → رهبر ایران برداشت می‌کند
روشن/خاموش‌کردن و شروع هر روز → اعلام عمومی با تگِ همه‌ی بازیکنان.
"""
import db
import texts

TOLL = 200
PENALTY = 0.10


def is_on() -> bool:
    return db.kv_get("toll_on") == "1"


def toggle(uid) -> tuple:
    """🛃 رهبر ایران: روشن/خاموش — پیام + اعلام عمومی."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»", ""
    if p["country"] != "ir":
        return "🇮🇷 فقط رهبر ایران می‌تواند عوارض تنگه را مدیریت کند.", ""
    new = not is_on()
    db.kv_set("toll_on", "1" if new else "")
    if new:
        db.kv_set("toll_ann_day", str(db.day_index()))   # امروز اعلام شد
        msg = ("\n".join([
            texts.hdr("عوارض تنگه هرمز", "🛃"),
            "✅ <b>عوارض روشن شد!</b>",
            f"💵 هر بازیکن غیرایرانی: {texts.money('ir', TOLL)} در روز",
            "🔥 بدون پرداخت تا پایان روز: ۱۰٪ پولش می‌سوزد!",
            "📣 اعلام عمومی در گروه فرستاده شد."]))
        ann = announce_text()
        return msg, ann
    msg = ("\n".join([
        texts.hdr("عوارض تنگه هرمز", "🛃"),
        "✅ <b>عوارض خاموش شد</b> — تنگه برای همه آزاد است.",
        "📣 اعلام عمومی در گروه فرستاده شد."]))
    return msg, "\n".join([
        "🛃 <b>اعلام رسمی — تنگه‌ی هرمز</b>",
        "🇮🇷 ایران عوارض تنگه را <b>خاموش</b> کرد — عبور آزاد است! 🕊"])


def announce_text() -> str:
    """📣 متن اعلام با تگ همه‌ی بازیکنان غیرایرانی."""
    rows = db.q("SELECT uid, name, country FROM users "
                "WHERE country IS NOT NULL AND country != 'ir'")
    tags = " ".join(texts.mention(int(r["uid"]), r["name"] or "سرباز")
                    for r in rows) or "—"
    return "\n".join([
        "🛃 <b>اعلام رسمی — عوارض تنگه‌ی هرمز</b>",
        f"🇮🇷 ایران عوارض را <b>روشن</b> کرد: هر بازیکن غیرایرانی، هر روز "
        f"{texts.money('ir', TOLL)} عوارض بدهد.",
        "▫️ پرداخت: بنویس «عوارض» یا منو → 🛃 عوارض",
        "🔥 مهلت تا پایان امروز (نیمه‌شب تهران) — وگرنه ۱۰٪ پول می‌سوزد!",
        "",
        f"📣 مخاطبان: {tags}"])


def status(uid) -> str:
    """🛃 وضعیت و پرداخت."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    day = db.day_index()
    on = is_on()
    lines = [t.hdr("عوارض تنگه هرمز", "🛃"),
             f"وضعیت: {'✅ روشن' if on else '❌ خاموش'}"]
    if not on:
        lines.append("🕊 تنگه آزاد است — عوارضی در کار نیست.")
        return "\n".join(lines)
    pot = int(db.kv_get("toll_pot", "0") or 0)
    lines.append(f"🏦 صندوق ایران: {t.money('ir', pot)}")
    if p["country"] == "ir":
        lines += [t.DASH, "👑 ابزار رهبر ایران:",
                  "• «عوارض روشن» / «عوارض خاموش» — تغییر وضعیت با اعلام عمومی",
                  f"• «عوارض برداشت» — برداشت صندوق ({t.money('ir', pot)})"]
        return "\n".join(lines)
    paid = db.kv_get(f"toll_paid:{uid}") == str(day)
    lines += [t.DASH,
              (f"✅ عوارض امروز را داده‌ای — فردا دوباره." if paid else
               f"❌ امروز نداده‌ای — {t.money(p['country'], TOLL)} بده تا "
               "۱۰٪ پولت نسوزد!")]
    return "\n".join(lines)


def pay(uid) -> str:
    """💵 پرداخت عوارض روزانه."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if not is_on():
        return "🛃 عوارض خاموش است — نیازی به پرداخت نیست."
    if p["country"] == "ir":
        return "🇮🇷 بازیکن ایرانی معاف است — عوارض مال غیرایرانی‌هاست!"
    day = db.day_index()
    if db.kv_get(f"toll_paid:{uid}") == str(day):
        return "✅ عوارض امروز را داده‌ای — فردا دوباره."
    if p["money"] < TOLL:
        return (f"💰 پول کافی نداری — عوارض {texts.money(p['country'], TOLL)}"
                f" · داری {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (TOLL, uid))
    pot = int(db.kv_get("toll_pot", "0") or 0) + TOLL
    db.kv_set("toll_pot", str(pot))
    db.kv_set(f"toll_paid:{uid}", str(day))
    return "\n".join([
        texts.hdr("پرداخت عوارض", "🛃"),
        f"✅ {texts.money(p['country'], TOLL)} عوارض تنگه پرداخت شد",
        f"🏦 صندوق ایران: {texts.money('ir', pot)}",
        "🛳 عبور آزاد — امروز امن هستی."])


def collect(uid) -> str:
    """🏦 رهبر ایران: برداشت صندوق عوارض."""
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if p["country"] != "ir":
        return "🇮🇷 فقط رهبر ایران می‌تواند صندوق را بردارد."
    pot = int(db.kv_get("toll_pot", "0") or 0)
    if pot <= 0:
        return "🏦 صندوق خالی است."
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (pot, uid))
    db.kv_set("toll_pot", "0")
    return "\n".join([
        texts.hdr("برداشت عوارض", "🏦"),
        f"✅ {texts.money('ir', pot)} به خزانه‌ی تو واریز شد"])


def enforce(uid) -> None:
    """🔥 جریمه‌ی روزانه — در هر تعامل چک می‌شود؛ فقط یک بار در روز."""
    p = db.one("SELECT country, money FROM users WHERE uid=?", (uid,))
    if not p or p["country"] == "ir" or not is_on():
        return
    day = db.day_index()
    if db.kv_get(f"toll_paid:{uid}") == str(day):
        return
    if db.kv_get(f"toll_pen:{uid}") == str(day):
        return
    db.kv_set(f"toll_pen:{uid}", str(day))
    burn = max(50, int(p["money"] * PENALTY))
    burn = min(burn, p["money"])
    if burn > 0:
        db.ex("UPDATE users SET money=money-? WHERE uid=?", (burn, uid))


def daily_announce_needed() -> bool:
    """📣 اولین لحظه‌ی هر روز که عوارض روشن است — اعلام با تگ."""
    if not is_on():
        return False
    day = db.day_index()
    if db.kv_get("toll_ann_day") == str(day):
        return False
    db.kv_set("toll_ann_day", str(day))
    return True
