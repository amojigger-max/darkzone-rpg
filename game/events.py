"""⚡ جنگ جهانی — رویداد زنده‌ی هر گروه + حلقه‌ی جهانی."""
import random

import db
import texts

MIN_GAP = 300
MAX_TRIES = 3


def active_chats(minutes=45):
    cutoff = db.now() - minutes * 60
    rows = db.q("SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL "
                "AND chat_id < 0 AND last_active > ?", (cutoff,))
    return [r["chat_id"] for r in rows]


EVENTS = [
    ("📦 قرارداد تسلیحاتی رسید — ۱۰ دقیقه فرصت: بنویس «تحویل» — اولین نفر ۸۰۰ سکه می‌گیرد", "تحویل", 800),
    ("🎖 فراخوان رزمی صادر شد — بنویس «اعزام» و ۱۲۰ XP بگیر", "اعزام", 0),
    ("📻 رادیو بین‌المللی: پیام رمزی شنیده شد — بنویس «رمزگشایی»", "رمزگشایی", 400),
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
        return f"🎁 {texts.mention(uid, p['name'])} برنده شد: 💰 {prize:,}"
    from game import state
    state.gain_xp(uid, 120)
    return f"🎖 {texts.mention(uid, p['name'])} اعزام شد — ⭐ +۱۲۰ XP"
