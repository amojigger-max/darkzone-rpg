"""🎯 جنگ جهانی — مأموریت‌های روزانه: هدف، پیشرفت، جایزه."""
import random

import db
import texts

POOL = [
    ("رزم", 3, "⚔️ سه نبرد رزمی انجام بده", 400),
    ("پیروزی", 2, "🏆 دو پیروزی رزمی بگیر", 500),
    ("جیره", 1, "🍞 جیره‌ی روزانه را بگیر", 200),
    ("جاسوسی", 1, "🕵 یک عملیات جاسوسی انجام بده", 450),
    ("خرید", 1, "🛒 یک تجهیز بخر", 300),
    ("پدافند", 2, "🛡 دو لایه‌ی سپر ملی را تقویت کن", 350),
    ("حمله", 2, "🚀 دو موج حمله بزن (رهبر)", 450),
]


def quest_state(uid) -> dict:
    day = db.now() // 86400
    st = db.jload(db.kv_get(f"quest:{uid}"), None) or {}
    if st.get("day") != day:
        goals = random.sample(POOL, k=3)
        st = dict(day=day, goals=[dict(key=g[0], need=g[1], label=g[2], prize=g[3],
                                       done=0, claimed=False) for g in goals])
        import json
        db.kv_set(f"quest:{uid}", json.dumps(st, ensure_ascii=False))
    return st


def on_event(uid, key: str):
    """قلاب پیشرفت: از رزم/جاسوسی/خرید/جیره صدا زده می‌شود."""
    st = quest_state(uid)
    ch = False
    for g in st["goals"]:
        if g["key"] == key and g["done"] < g["need"]:
            g["done"] += 1
            ch = True
    if ch:
        import json
        db.kv_set(f"quest:{uid}", json.dumps(st, ensure_ascii=False))


def view(uid) -> str:
    st = quest_state(uid)
    t = texts
    lines = [t.hdr("مأموریت روزانه", "🎯")]
    all_done = True
    for g in st["goals"]:
        mark = "✅" if g["done"] >= g["need"] else "⏳"
        lines.append(f"{mark} {g['label']} — {texts.fa(g['done'])}/{texts.fa(g['need'])}")
        if g["done"] < g["need"]:
            all_done = False
    if all_done:
        total = sum(g["prize"] for g in st["goals"])
        lines.append(f"🎁 آماده! «جایزه» → 💰 {texts.fa(total)}")
    return "\n".join(lines)


FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def claim(uid) -> str:
    st = quest_state(uid)
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    total, any_pending = 0, False
    for g in st["goals"]:
        if g["done"] >= g["need"] and not g["claimed"]:
            g["claimed"] = True
            total += g["prize"]
            any_pending = True
    if not any_pending:
        return "⏳ هنوز هدف کاملی برای دریافت نیست — «مأموریت»"
    import json
    db.kv_set(f"quest:{uid}", json.dumps(st, ensure_ascii=False))
    db.ex("UPDATE users SET money=money+? WHERE uid=?", (total, uid))
    state.gain_xp(uid, total // 3)
    p2 = state.get(uid)
    return (f"🎁 جایزه‌ی مأموریت: 💰 {texts.money(p2['country'], total)}\n"
            f"خزانه: {texts.money(p2['country'], p2['money'])}")
