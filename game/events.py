"""⚡ جنگ جهانی — رویداد زنده‌ی هر گروه + حلقه‌ی جهانی."""
import contextlib
import random

import db
import texts

MIN_GAP = 900
MAX_TRIES = 3

# 💡 نکته‌ها — هر بار یکی، آرام و پیوسته
TIPS = [
    ("جهان", "وضعیت همه‌ی کشورها و جنگ‌های فعال را ببین"),
    ("نقشه", "شهرهای اشغال‌شده و مرزهای جبهه‌ها"),
    ("قدرت", "رتبه‌بندی نظامی ۵۰ کشور"),
    ("مستعمره‌ها", "چه کشوری مستعمره‌ی کیست"),
    ("جیره", "دستمزد روزانه‌ات را بگیر"),
    ("رزم", "نبرد کن، غنیمت بگیر، ارتقا بگیر"),
    ("تجهیزات", "زرادخانه‌ی کشورت را ببین"),
    ("پدافند", "سپر ملی ۶ لایه‌ی کشورت"),
    ("اخبار", "آخرین رویدادهای کشورت"),
    ("کمک", "راهنمای کامل بازی"),
]


def bulletin() -> str:
    """📰 پیام خودکار هر ۱۰ دقیقه — کوتاه، تمیز، چرخشی."""
    import countries
    import texts
    from game import economy, geo, war as _war
    t = texts
    idx = int(db.kv_get("bl_idx", "0"))
    db.kv_set("bl_idx", str(idx + 1))
    kind = idx % 5
    # ⚔️ جنگ‌ها
    if kind == 0:
        wars = db.q("SELECT * FROM wars WHERE status='active'")
        lines = [t.hdr("اخبار جنگی", "⚔️"), ""]
        if not wars:
            lines.append("🕊 صلح بر جهان حاکم است... فعلاً.")
        for w in wars[:4]:
            a, b = countries.COUNTRIES.get(w["a"]), countries.COUNTRIES.get(w["b"])
            if a and b:
                lines.append(f"{a['flag']} {a['name']} ↔ {b['flag']} {b['name']}")
        lines += ["", t.DASH]
        return "\n".join(lines)
    # 💱 بازار
    if kind == 1:
        w = economy.world()
        d, o, i = w["dollar"], w["oil"], w["inflation"] * 100
        lines = [t.hdr("بازار جهانی", "💱"), "",
                 t.row("شاخص دلار", f"×{t.fa(f'{d:.2f}')}"),
                 t.row("نفت", f"${t.fa(f'{o:.0f}')}"),
                 t.row("تورم", f"{t.fa(f'{i:.1f}')}٪"),
                 t.row("۱۰۰ سکه", texts.money("ir", 100)),
                 "", t.DASH]
        return "\n".join(lines)
    # 🥇 قدرت‌ها
    if kind == 2:
        return _war.power_rank(top=3) + "\n" + t.DASH
    # ⛓ مستعمره‌ها
    if kind == 3:
        cols = []
        for cid in countries.COUNTRIES:
            oc = geo.colony_of(cid)
            if oc:
                cols.append(f"{countries.COUNTRIES[cid]['flag']} "
                            f"{countries.COUNTRIES[cid]['name']} ⛓ "
                            f"{countries.COUNTRIES[oc]['flag']}")
        lines = [t.hdr("مستعمره‌های جهان", "⛓"), ""]
        lines += cols[:6] if cols else ["🕊 هیچ کشوری مستعمره نیست — همه آزادند."]
        lines += ["", t.DASH]
        return "\n".join(lines)
    # 💡 نکته
    cmd, desc = TIPS[idx % len(TIPS)]
    return "\n".join([t.hdr("نکته", "💡"), "",
                      f"«{cmd}» — {desc}", "", t.DASH])


def active_chats(minutes=45):
    cutoff = db.now() - minutes * 60
    rows = db.q("SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL "
                "AND chat_id < 0 AND last_active > ?", (cutoff,))
    return [r["chat_id"] for r in rows]


def game_alive(gid: int, minutes: int = 45) -> bool:
    """آیا این گروه بیدار است؟ (فعالیت تازه‌ی بازیکن دارد)"""
    import db as _db
    cutoff = _db.now() - minutes * 60
    with contextlib.suppress(Exception):
        r = _db.con_for(gid).execute(
            "SELECT 1 FROM users WHERE last_active > ? LIMIT 1", (cutoff,)).fetchone()
        return bool(r)
    return False


EVENTS = [
    ("📦 قرارداد تسلیحاتی رسید — ۱۰ دقیقه فرصت: بنویس «تحویل» — اولین نفر ۴۰۰ سکه می‌گیرد", "تحویل", 800),
    ("🎖 فراخوان رزمی صادر شد — بنویس «اعزام» و ۱۲۰ XP بگیر", "اعزام", 0),
    ("📻 رادیو بین‌المللی: پیام رمزی شنیده شد — بنویس «رمزگشایی»", "رمزگشایی", 200),
]


def maybe_event(chat_id):
    st = db.jload(db.kv_get(f"ev:{chat_id}"), None)
    if st and st.get("active") and db.now() < st.get("deadline", 0):
        return None
    if db.now() - int(db.kv_get(f"ev_last:{chat_id}", "0")) < MIN_GAP:
        return None
    text, word, prize = random.choice(EVENTS)
    import json
    db.kv_set(f"ev:{chat_id}", json.dumps(
        dict(active=True, word=word, prize=prize, taker=None,
             deadline=db.now() + 120), ensure_ascii=False))
    db.kv_set(f"ev_last:{chat_id}", str(db.now()))
    return text


def claim(chat_id, uid, word) -> str:
    st = db.jload(db.kv_get(f"ev:{chat_id}"), None)
    if not st or not st.get("active") or st.get("word") != word:
        return ""
    if db.now() > st.get("deadline", 0):
        return ""
    p = db.one("SELECT * FROM users WHERE uid=?", (uid,))
    if not p:
        return "⛔ ثبت‌نام نکرده‌ای — «شروع»"
    if st.get("taker"):
        return "✅ کسی زودتر رسید."
    st["taker"] = uid
    import json
    db.kv_set(f"ev:{chat_id}", json.dumps(dict(active=False), ensure_ascii=False))
    prize = st["prize"]
    if prize:
        db.ex("UPDATE users SET money=money+? WHERE uid=?", (prize, uid))
        return f"🎁 {texts.mention(uid, p['name'])} برنده شد: 💰 {texts.fa(prize)}"
    from game import state
    state.gain_xp(uid, 120)
    return f"🎖 {texts.mention(uid, p['name'])} اعزام شد — ⭐ +۱۲۰ XP"
