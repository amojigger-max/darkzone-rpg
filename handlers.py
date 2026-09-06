"""🎮 جنگ جهانی — رابط کاربری: کاملاً فارسی، دکمه‌ای، تمیز."""

import contextlib
import os
import time
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import countries
import db
import texts
from game import ai, defense, economy, events, geo, guide, military, politics, quests, state, war

router = Router()


def handlers_bot():
    """نمونه‌ی بات برای ویرایش پیام — از بیرون هم در دسترس."""
    return globals().get("bot")


# 🎛 فقط همین دستورهای متنی زنده‌اند — همه‌چیز دیگر از «منو»
TEST_MODE = False
TEXT_ALLOWED = {
    "شروع", "منو",
    "تحویل", "اعزام", "رمزگشایی",               # رویدادهای گروهی
    "رهبر", "ثبت", "تغییر", "تنظیم",             # مالک
    "مدیریت", "ادمین", "اعلام", "سربازها", "توزیع",
}
bot: Bot = None


# ═══════════ 🚫 بازی فقط در گروه ═══════════

@router.message(F.chat.type == "private")
async def pv_only_group(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ افزودن به یک گروه",
                             url="https://t.me/REDarkZoneBot?startgroup=true")]])
    await m.answer(texts.PV_ONLY, reply_markup=kb)


@router.callback_query(F.message.chat.type == "private")
async def pv_cb_only_group(c: CallbackQuery):
    await c.answer("🎮 بازی فقط در گروه!", show_alert=True)


# ═══════════ 👑 پنل مدیریت مالک ═══════════

def kb_help(page: int = 1) -> InlineKeyboardMarkup:
    """📖 راهنمای صفحه‌بندی‌شده — بدون شلوغی."""
    n = len(texts.HELP_PAGES)
    page = max(1, min(n, page))
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"hp:{page-1}"))
    row.append(InlineKeyboardButton(text=f"📖 {page}/{n}",
                                    callback_data=f"hp:{page}"))
    if page < n:
        row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"hp:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text="📖 راهنمای کشور", callback_data="mn:cguide"),
         InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار جهان", callback_data="ad:stats"),
         InlineKeyboardButton(text="👥 بازیکنان", callback_data="ad:players")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def _admin_callup_parts() -> list:
    """📣 اعلام‌نظام — همه‌ی سربازان با تگ، گروه‌بندی با کشور (تکه‌های امن)."""
    rows = db.q("SELECT uid, name, country, level FROM users "
                "WHERE country IS NOT NULL ORDER BY country, level DESC")
    t = texts
    if not rows:
        return ["هنوز بازیکنی ثبت نشده — «ثبت آیدی کشور»"]
    groups = {}
    for r in rows:
        groups.setdefault(r["country"], []).append(r)
    parts, cur = [], [t.hdr("اعلام عمومی سربازان", "📣"),
                      "به میدان بیایید — جنگ جهانی آغاز شده!", ""]
    for cid in sorted(groups, key=lambda c: -len(groups[c])):
        c = countries.COUNTRIES.get(cid)
        if not c:
            continue
        tags = " ".join(t.mention(r["uid"], (r["name"] or "سرباز")[:20])
                        for r in groups[cid])
        block = [f"{c['flag']} <b>{c['name']}</b> ({t.fa(len(groups[cid]))}):",
                 tags, ""]
        if len("\n".join(cur + block)) > 3500:
            parts.append("\n".join(cur))
            cur = []
        cur += block
    cur.append("🎮 در گروه بنویس: «منو»")
    parts.append("\n".join(cur))
    return parts


def _admin_stats() -> str:
    n = db.one("SELECT COUNT(*) c FROM users WHERE country IS NOT NULL")["c"]
    wars = db.one("SELECT COUNT(*) c FROM wars WHERE status='active'")["c"]
    parties = db.one("SELECT COUNT(*) c FROM parties")["c"]
    from game import economy
    w = economy.world()
    return "\n".join([
        texts.hdr("پنل مدیریت", "👑"),
        texts.row("بازیکنان ثبت‌شده", n),
        texts.row("احزاب", parties),
        texts.row("جنگ‌های فعال", wars),
        texts.row("نفت / دلار / تورم",
                  f"${w['oil']:.0f} · ×{w['dollar']:.2f} · {w['inflation']*100:.1f}٪"),
        "",
        "➕ ثبت بازیکن: <code>ثبت آیدی کشور</code>",
        "مثال: <code>ثبت 8694290031 ایران</code>",
        "",
        "👑 رهبر کشور: ریپلای روی پیام بازیکن + «رهبر کشور»",
        "یا: <code>رهبر آیدی کشور</code> · <code>رهبر @آیدی کشور</code>",
        "خلع ← NPC: <code>رهبر خالی آمریکا</code>",
        "",
        "🔄 تغییر کشور: <code>تغییر آیدی کشور</code>",
        "مثال: <code>تغییر 8694290031 روسیه</code>"])


def _admin_register(uid_target: int, country_name: str) -> str:
    cid = _find_country(country_name or "")
    if not cid:
        return "⛔ کشور نامعتبر — مثال: ایران · آمریکا · روسیه"
    p = state.get(uid_target)
    if p and p["country"]:
        return (f"ℹ️ {uid_target} قبلاً ثبت شده — برای تغییر: "
                f"<code>تغییر {uid_target} {countries.COUNTRIES[cid]['name']}</code>")
    if not state.enlist(uid_target, cid, f"Player{uid_target % 1000}"):
        return "⛔ خطا در ثبت."
    c = countries.COUNTRIES[cid]
    return f"✅ بازیکن <code>{uid_target}</code> ثبت شد در {c['flag']} {c['name']}"


def _admin_change(uid_target: int, country_name: str) -> str:
    p = state.get(uid_target)
    if not p:
        return f"⛔ بازیکن {uid_target} ثبت نشده — اول: <code>ثبت {uid_target} کشور</code>"
    cid = _find_country(country_name or "")
    if not cid:
        return "⛔ کشور نامعتبر."
    db.ex("UPDATE users SET country=? WHERE uid=?", (cid, uid_target))
    c = countries.COUNTRIES[cid]
    return f"🔄 کشور بازیکن <code>{uid_target}</code> ← {c['flag']} {c['name']}"


def _set_leader(uid_t: int, cname: str) -> str:
    """👑 رهبر کردن بازیکن مشخص در کشور — ثبت خودکار هم دارد."""
    cid = _find_country(cname or "")
    if not cid:
        return "⛔ کشور نامعتبر — مثال: <code>رهبر آمریکا</code>"
    p = state.get(uid_t)
    if p and p["country"] and p["country"] != cid:
        return (f"⛔ بازیکن در کشور دیگری است — اول: "
                f"<code>تغییر {uid_t} {countries.COUNTRIES[cid]['name']}</code>")
    if not p or not p["country"]:
        if not state.enlist(uid_t, cid, f"Player{uid_t % 1000}"):
            return "⛔ خطا در ثبت."
    db.ex("UPDATE users SET is_leader=0 WHERE country=? AND is_leader=1", (cid,))
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (uid_t,))
    c = countries.COUNTRIES[cid]
    return f"👑 بازیکن <code>{uid_t}</code> رهبر {c['flag']} {c['name']} شد!"""


def _admin_leader(arg: str) -> str:
    """👑 تعیین/خلع رهبر کشور — با آیدی عددی یا «خالی» برای NPC."""
    parts = arg.split()
    # 👑 خلع: رهبر خالی آمریکا → کشور NPC می‌شود
    if parts and parts[0] in ("خالی", "-"):
        cid = _find_country(" ".join(parts[1:]))
        if not cid:
            return "⛔ کشور نامعتبر — مثال: <code>رهبر خالی آمریکا</code>"
        c = countries.COUNTRIES[cid]
        db.ex("UPDATE users SET is_leader=0 WHERE country=? AND is_leader=1", (cid,))
        # 🧹 ثبت‌های اشتباه قدیمی (Player بدون فعالیت) پاک می‌شوند
        db.ex("DELETE FROM users WHERE country=? AND chat_id IS NULL "
              "AND (name LIKE 'Player%') AND branch IS NULL", (cid,))
        return f"♻️ {c['flag']} {c['name']} بدون رهبر شد — دولت NPC."
    if len(parts) >= 2 and parts[0].isdigit():
        return _set_leader(int(parts[0]), " ".join(parts[1:]))
    return ("🔎 الگو: روی پیام بازیکن ریپلای کن و بنویس <code>رهبر کشور</code>\n"
            "یا: <code>رهبر آیدی‌عددی کشور</code> · <code>رهبر @آیدی کشور</code> · "
            "خلع: <code>رهبر خالی کشور</code>")


@router.callback_query(F.data.startswith("ad:"))
async def cb_admin(c: CallbackQuery):
    if c.from_user.id != config.OWNER_ID:
        await c.answer("👑 فقط مالک!", show_alert=True)
        return
    what = c.data.split(":")[1]
    if what == "stats":
        await _edit(c, _admin_stats(), kb_admin())
    elif what == "players":
        rows = db.q("SELECT uid, name, country, level FROM users "
                    "WHERE country IS NOT NULL ORDER BY level DESC LIMIT 15")
        lines = [texts.hdr("بازیکنان", "👥"), ""]
        for r in rows:
            cc = countries.COUNTRIES.get(r["country"], {})
            lines.append(f"▫️ <code>{r['uid']}</code> — {r['name']} · "
                         f"{cc.get('flag', '')} سطح {r['level']}")
        lines.append("")
        lines.append(texts.DASH)
        await _edit(c, "\n".join(lines), kb_admin())
    await c.answer()


# ═══════════ 🧩 کیبوردها ═══════════

def _taken(cid: str) -> bool:
    """آیا این کشور در همین گروه گرفته شده؟ (هر گروه دنیای خودش)"""
    return bool(db.one("SELECT 1 FROM users WHERE country=? LIMIT 1", (cid,)))


def _cy_label(cid: str) -> str:
    c = countries.COUNTRIES[cid]
    mark = " ✓" if _taken(cid) else ""
    return f"{c['flag']} {c['name']}{mark}"


def kb_countries(page=0) -> InlineKeyboardMarkup:
    ids = list(countries.COUNTRIES)
    per, p = 10, page
    chunk = ids[p * per:(p + 1) * per]
    if not chunk:
        return InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    for a, b in zip(chunk[::2], chunk[1::2]):
        rows.append([InlineKeyboardButton(text=_cy_label(a), callback_data=f"cy:{a}"),
                     InlineKeyboardButton(text=_cy_label(b), callback_data=f"cy:{b}")])
    if len(chunk) % 2:
        rows.append([InlineKeyboardButton(text=_cy_label(chunk[-1]),
                                          callback_data=f"cy:{chunk[-1]}")])
    nav = []
    if p > 0:
        nav.append(InlineKeyboardButton(text="◀️ صفحه قبل", callback_data=f"cyp:{p-1}"))
    if (p + 1) * per < len(ids):
        nav.append(InlineKeyboardButton(text="صفحه بعد ▶️", callback_data=f"cyp:{p+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪖 نظامی", callback_data="mn:mil"),
         InlineKeyboardButton(text="🏛 سیاست", callback_data="mn:pol")],
        [InlineKeyboardButton(text="🌍 جهان", callback_data="mn:world"),
         InlineKeyboardButton(text="👤 پروفایل", callback_data="mn:me")],
        [InlineKeyboardButton(text="📖 راهنما", callback_data="mn:help")]])


def kb_mil() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ رزم", callback_data="mn:battle"),
         InlineKeyboardButton(text="🏥 استراحت", callback_data="mn:rest")],
        [InlineKeyboardButton(text="🛒 تجهیزات", callback_data="mn:arsenal"),
         InlineKeyboardButton(text="🔧 تعمیر", callback_data="mn:repair")],
        [InlineKeyboardButton(text="🎖 عضویت نظامی", callback_data="mn:branch"),
         InlineKeyboardButton(text="🍞 جیره", callback_data="mn:ration")],
        [InlineKeyboardButton(text="🎯 مأموریت روزانه", callback_data="mn:quest"),
         InlineKeyboardButton(text="☠ بازار سیاه", callback_data="mn:black")],
        [InlineKeyboardButton(text="⬆️ ارتقای تجهیزات", callback_data="mn:upgrade"),
         InlineKeyboardButton(text="⚔️ نبرد تن‌به‌تن", callback_data="mn:duel")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_pol() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛 احزاب", callback_data="mn:parties"),
         InlineKeyboardButton(text="🚩 شورش", callback_data="mn:rebel")],
        [InlineKeyboardButton(text="🕵 جاسوسی", callback_data="mn:spy"),
         InlineKeyboardButton(text="🤝 اتحاد", callback_data="mn:ally")],
        [InlineKeyboardButton(text="⚔️ جنگ و حمله", callback_data="mn:war"),
         InlineKeyboardButton(text="📰 بیانیه", callback_data="mn:stmt")],
        [InlineKeyboardButton(text="🕊 درخواست صلح", callback_data="mn:peace"),
         InlineKeyboardButton(text="🆘 کمک اتحاد", callback_data="mn:helpally")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_world() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 وضعیت جهان", callback_data="mn:wstat"),
         InlineKeyboardButton(text="🏆 رتبه", callback_data="mn:lb")],
        [InlineKeyboardButton(text="🥇 قدرت کشورها", callback_data="mn:power"),
         InlineKeyboardButton(text="⛓ مستعمره‌ها", callback_data="mn:colonies")],
        [InlineKeyboardButton(text="📈 بازار", callback_data="mn:market"),
         InlineKeyboardButton(text="🏙 نقشه‌ی کشور", callback_data="mn:map")],
        [InlineKeyboardButton(text="📰 اخبار", callback_data="mn:news"),
         InlineKeyboardButton(text="🗺 جبهه", callback_data="mn:front")],
        [InlineKeyboardButton(text="🪖 ارتش کشور", callback_data="mn:army"),
         InlineKeyboardButton(text="🛡 سپر ملی", callback_data="mn:def")],
        [InlineKeyboardButton(text="📖 راهنمای کشور", callback_data="mn:cguide"),
         InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_def() -> InlineKeyboardMarkup:
    """تقویت لایه‌های سپر ملی — هر عضو کشور سهم دارد."""
    L = defense.LAYERS
    keys = list(L)
    rows = []
    for a, b in zip(keys[::2], keys[1::2]):
        rows.append([InlineKeyboardButton(text=f"➕ {L[a]}", callback_data=f"df:{a}"),
                     InlineKeyboardButton(text=f"➕ {L[b]}", callback_data=f"df:{b}")])
    rows.append([InlineKeyboardButton(text="🗺 جبهه", callback_data="mn:front"),
                 InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_branches(uid) -> InlineKeyboardMarkup:
    p = state.active(uid)
    c = countries.COUNTRIES.get(p["country"]) if p else None
    rows = []
    if c:
        for i, b in enumerate(c["branches"]):
            rows.append([InlineKeyboardButton(text=f"🪖 {b}", callback_data=f"br:{i}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_arsenal(uid) -> InlineKeyboardMarkup:
    p = state.active(uid)
    c = countries.COUNTRIES.get(p["country"]) if p else None
    rows = []
    if c:
        for iid in c["items"]:
            it = countries.ITEMS[iid]
            row_ = db.one("SELECT qty FROM inventory WHERE uid=? AND iid=?", (uid, iid))
            have = row_["qty"] if row_ else 0
            mark = f"📦{texts.fa(have)}" if have else "—"
            rows.append([
                InlineKeyboardButton(
                    text=f"{it[1]} {it[0]} · {mark}",
                    callback_data=f"wp:{iid}"),
                InlineKeyboardButton(text="×۵ خرید", callback_data=f"wp5:{iid}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_targets(uid, action, page=0) -> InlineKeyboardMarkup:
    """لیست صفحه‌بندی‌شده‌ی کشورها برای جاسوسی/اتحاد/جنگ/تحریم."""
    p = state.active(uid)
    own = p["country"] if p else None
    ids = [cid for cid in countries.COUNTRIES if cid != own]
    per = 10
    page = max(0, min(page, (len(ids) - 1) // per))
    chunk = ids[page * per:(page + 1) * per]
    rows = []
    for a, b in zip(chunk[::2], chunk[1::2]):
        rows.append([InlineKeyboardButton(
                         text=countries.COUNTRIES[a]["flag"] + " " + countries.COUNTRIES[a]["name"],
                         callback_data=f"{action}:{a}"),
                     InlineKeyboardButton(
                         text=countries.COUNTRIES[b]["flag"] + " " + countries.COUNTRIES[b]["name"],
                         callback_data=f"{action}:{b}")])
    if len(chunk) % 2:
        rows.append([InlineKeyboardButton(
            text=countries.COUNTRIES[chunk[-1]]["flag"] + " " + countries.COUNTRIES[chunk[-1]]["name"],
            callback_data=f"{action}:{chunk[-1]}")])
    n_pages = max(1, (len(ids) + per - 1) // per)
    if n_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ صفحه قبل",
                                            callback_data=f"tp:{action}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"📄 {texts.fa(page+1)}/{texts.fa(n_pages)}",
                                        callback_data=f"tp:{action}:{page}"))
        if (page + 1) * per < len(ids):
            nav.append(InlineKeyboardButton(text="صفحه بعد ▶️",
                                            callback_data=f"tp:{action}:{page+1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_strikes() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 موشکی ۱×", callback_data="st:موشکی:1"),
         InlineKeyboardButton(text="🚀 موشکی ۳×", callback_data="st:موشکی:3"),
         InlineKeyboardButton(text="🚀 موشکی ۵×", callback_data="st:موشکی:5")],
        [InlineKeyboardButton(text="✈️ هوایی ۱×", callback_data="st:هوایی:1"),
         InlineKeyboardButton(text="✈️ هوایی ۳×", callback_data="st:هوایی:3"),
         InlineKeyboardButton(text="✈️ هوایی ۵×", callback_data="st:هوایی:5")],
        [InlineKeyboardButton(text="🚢 دریایی ۱×", callback_data="st:دریایی:1"),
         InlineKeyboardButton(text="🚢 دریایی ۳×", callback_data="st:دریایی:3")],
        [InlineKeyboardButton(text="🚜 زمینی ۱×", callback_data="st:زمینی:1"),
         InlineKeyboardButton(text="🚜 زمینی ۳×", callback_data="st:زمینی:3"),
         InlineKeyboardButton(text="🛩 پهپادی ۱×", callback_data="st:پهپادی:1")],
        [InlineKeyboardButton(text="🗺 جبهه", callback_data="mn:front"),
         InlineKeyboardButton(text="🛡 پدافند", callback_data="mn:def")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_duel(uid) -> InlineKeyboardMarkup:
    """⚔️ انتخاب حریف نبرد تن‌به‌تن — بازیکنان فعالِ همین جهان."""
    rows = db.q("SELECT uid, name, country FROM users "
                "WHERE country IS NOT NULL AND branch IS NOT NULL AND uid!=? "
                "ORDER BY last_active DESC LIMIT 12", (uid,))
    keys = []
    for r in rows:
        cc = countries.COUNTRIES.get(r["country"], {})
        keys.append([InlineKeyboardButton(
            text=f"{cc.get('flag', '')} {r['name'] or 'سرباز'}",
            callback_data=f"du:{r['uid']}")])
    if not keys:
        keys.append([InlineKeyboardButton(text="💤 حریفی نیست — بازیکنان باید عضو شاخه شوند",
                                          callback_data="mn:mil")])
    keys.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=keys)


def kb_duel_accept() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ قبول نبرد", callback_data="dac:")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_peace_accept() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕊 قبول صلح", callback_data="pac:")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_ally_accept(cid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 قبول اتحاد", callback_data=f"aac:{cid}")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_surrender() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏳️ بله، تسلیم می‌شوم", callback_data="sury:")],
        [InlineKeyboardButton(text="↩️ نه، برگشت", callback_data="mn:pol")]])


def kb_declare(uid) -> InlineKeyboardMarkup:
    """⚔️ انتخاب کشور برای اعلام جنگ — صفحه‌بندی‌شده."""
    return kb_targets(uid, "dwr")


def kb_market() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 تحریم کشور", callback_data="snc:"),
         InlineKeyboardButton(text="🌉 تنگه‌ها", callback_data="str:")],
        [InlineKeyboardButton(text="📈 بازار جهانی", callback_data="mn:market"),
         InlineKeyboardButton(text="🌍 شورای امنیت", callback_data="mn:world")]])


def kb_straits() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌉 هرمز", callback_data="str:هرمز"),
         InlineKeyboardButton(text="🌉 باب‌المندب", callback_data="str:باب‌المندب")],
        [InlineKeyboardButton(text="🌉 تایوان", callback_data="str:تایوان"),
         InlineKeyboardButton(text="🌉 سوئز", callback_data="str:سوئز")],
        [InlineKeyboardButton(text="📈 بازار جهانی", callback_data="mn:market"),
         InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_sanction(uid) -> InlineKeyboardMarkup:
    """🚫 انتخاب کشور برای تحریم — صفحه‌بندی‌شده."""
    return kb_targets(uid, "snc")


def kb_black(uid) -> InlineKeyboardMarkup:
    """☠ دکمه‌های خرید قاچاق — همان نمونه‌ی ساعتی بازار سیاه."""
    rows = []
    for iid in military.black_sample(uid):
        it = countries.ITEMS[iid]
        c = countries.COUNTRIES[it[2]]
        own = db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid))
        mark = "✅" if own else "🛒"
        rows.append([InlineKeyboardButton(
            text=f"{it[1]} {it[0]} ({c['flag']}) — {mark}",
            callback_data=f"bb:{iid}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_quests() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 دریافت جایزه", callback_data="qc:")],
        [InlineKeyboardButton(text="🎯 مأموریت‌ها", callback_data="mn:quest"),
         InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_parties(uid) -> InlineKeyboardMarkup:
    """🏛 فهرست احزاب با دکمه‌ی عضویت + حزب جدید."""
    p = state.active(uid)
    rows = []
    if p:
        for r in db.q("SELECT id, name, members FROM parties WHERE country=? "
                      "ORDER BY power DESC LIMIT 10", (p["country"],)):
            rows.append([InlineKeyboardButton(
                text=f"🏛 {r['name']} — 👥{texts.fa(r['members'])}",
                callback_data=f"pj:{r['id']}")])
    rows.append([InlineKeyboardButton(text="➕ حزب جدید", callback_data="pnew:")])
    rows.append([InlineKeyboardButton(text="🏛 دفتر سیاسی", callback_data="mn:pol"),
                 InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cancel_pol() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✋ لغو", callback_data="pcancel:")],
        [InlineKeyboardButton(text="🏛 دفتر سیاسی", callback_data="mn:pol")]])


# ✍️ ورودی آزاد در انتظار: بیانیه / حزب — بعد از دکمه، پیام بعدی کاربر همین می‌شود
_pending: dict = {}


def _pend_set(uid: int, chat_id: int, kind: str, ttl: int = 300):
    _pending[(uid, chat_id)] = (kind, time.time() + ttl)


def _pend_pop(uid: int, chat_id: int):
    kind, exp = _pending.pop((uid, chat_id), (None, 0))
    return kind if kind and time.time() <= exp else None


# ═══════════ 🚀 شروع ═══════════

@router.message(Command("start"))
@router.message(F.text.in_(["شروع"]))
async def cmd_start(m: Message):
    state.ensure(m.from_user.id, m.from_user.first_name, m.chat.id)
    if state.active(m.from_user.id):
        await m.answer(state.card(m.from_user.id), parse_mode="HTML", reply_markup=kb_main())
        return
    if os.path.exists("assets/img/cover.jpg"):
        with open("assets/img/cover.jpg", "rb"):
            await m.answer_photo(FSInputFile("assets/img/cover.jpg"),
                                 caption=texts.WELCOME, parse_mode="HTML",
                                 reply_markup=kb_countries())
    else:
        await m.answer(texts.WELCOME, parse_mode="HTML", reply_markup=kb_countries())


@router.callback_query(F.data.startswith("cyp:"))
async def cb_cy_page(c: CallbackQuery):
    await c.message.edit_reply_markup(reply_markup=kb_countries(int(c.data.split(":")[1])))
    await c.answer()


@router.callback_query(F.data.startswith("cy:"))
async def cb_country(c: CallbackQuery):
    uid = c.from_user.id
    if state.active(uid):
        await c.answer("قبلاً ثبت‌نام کردی.", show_alert=True)
        return
    cid = c.data.split(":")[1]
    if _taken(cid):                       # ✓ کشور گرفته‌شده — در همین گروه
        await c.answer("✓ این کشور قبلاً گرفته شده — کشور دیگری انتخاب کن",
                       show_alert=True)
        return
    ok = state.enlist(uid, cid, c.from_user.first_name or "سرباز")
    if not ok:
        await c.answer("خطا — دوباره امتحان کن.", show_alert=True)
        return
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (uid,))   # 👑 بازیکن = رهبر
    co = countries.COUNTRIES[cid]
    t = texts
    await c.message.delete()
    await c.message.answer("\n".join([
        t.hdr("ثبت‌نام تکمیل شد", "🎖"),
        t.row("کشور", f"{co['flag']} {co['name']}"),
        t.row("نقش", "👑 رهبر کشور"),
        t.row("خزانه", "💰 ۱٬۰۰۰"),
        "", "🪖 اولین قدم: «عضویت نظامی» — سپس تجهیزات بخر.",
        "🎮 منوی اصلی: «منو»"]), parse_mode="HTML", reply_markup=kb_mil())
    await c.answer()


# ═══════════ 🎛 منوها ═══════════

async def _edit(c: CallbackQuery, text: str, kb=None):
    try:
        await c.message.edit_text(text[:4000], parse_mode="HTML",
                                  reply_markup=kb or kb_main())
    except Exception:
        await c.message.answer(text[:4000], parse_mode="HTML",
                               reply_markup=kb or kb_main())


@router.callback_query(F.data.startswith("hp:"))
async def cb_helppage(c: CallbackQuery):
    try:
        page = max(1, min(len(texts.HELP_PAGES), int(c.data.split(":")[1])))
    except ValueError:
        page = 1
    await _edit(c, texts.HELP_PAGES[page - 1], kb_help(page))
    await c.answer()


@router.callback_query(F.data.startswith("df:"))
async def cb_defense(c: CallbackQuery):
    uid = c.from_user.id
    layer = c.data.split(":", 1)[1]
    msg = defense.strengthen(uid, layer)
    p = state.active(uid)
    if p:
        msg += "\n\n" + defense.status(p["country"])
    await _edit(c, msg, kb_def())
    await c.answer()


@router.callback_query(F.data.startswith("mn:"))
async def cb_menu(c: CallbackQuery):
    uid = c.from_user.id
    what = c.data.split(":", 1)[1]
    if not state.active(uid) and what not in ("help",):
        await c.answer("⛔ اول «شروع»", show_alert=True)
        return
    if what == "main":
        await _edit(c, state.card(uid), kb_main())
    elif what == "mil":
        await _edit(c, texts.hdr("فرماندهی نظامی", "🪖") + "\n\nیکی را انتخاب کن:", kb_mil())
    elif what == "pol":
        await _edit(c, texts.hdr("دفتر سیاسی", "🏛") + "\n\nیکی را انتخاب کن:", kb_pol())
    elif what == "world":
        await _edit(c, texts.hdr("شورای امنیت", "🌍") + "\n\nیکی را انتخاب کن:", kb_world())
    elif what == "me":
        await _edit(c, state.card(uid), kb_main())
    elif what == "battle":
        await _edit(c, military.battle(uid), kb_mil())
    elif what == "rest":
        await _edit(c, military.rest(uid), kb_mil())
    elif what == "arsenal":
        await _edit(c, military.arsenal(uid), kb_arsenal(uid))
    elif what == "repair":
        await _edit(c, military.repair(uid), kb_mil())
    elif what == "ration":
        await _edit(c, state.ration(uid), kb_mil())
    elif what == "branch":
        await _edit(c, texts.hdr("انتخاب شاخه", "🪖") + "\n\nشاخه‌ی کشورت:", kb_branches(uid))
    elif what == "parties":
        await _edit(c, politics.list_parties(uid), kb_parties(uid))
    elif what == "rebel":
        await _edit(c, politics.rebel(uid), kb_pol())
    elif what == "stmt":
        _pend_set(uid, c.message.chat.id, "stmt")
        await _edit(c, "\n".join([
            texts.hdr("بیانیه‌ی رسمی", "📰"), "",
            "📝 <b>متن بیانیه را در همین گروه بنویس</b>",
            "هر پیامی که بفرستی، بیانیه‌ی رسمی حزب می‌شود.", "",
            "⛔ حداقل ۱۰ حرف · ثبت دائمی · ⚡ قدرت حزب +۱۰", "",
            "✋ لغو: بنویس «لغو»"]), kb_cancel_pol())
    elif what == "spy":
        await _edit(c, texts.hdr("عملیات جاسوسی", "🕵") + "\n\nکشور هدف را انتخاب کن:",
                    kb_targets(uid, "spy"))
    elif what == "ally":
        await _edit(c, texts.hdr("پیشنهاد اتحاد", "🤝") + "\n\nبا کدام کشور؟",
                    kb_targets(uid, "ally"))
    elif what == "war":
        p = state.active(uid)
        if p and war.war_of(p["country"]):
            await _edit(c, war.front(uid), kb_strikes())
        else:
            await _edit(c, "\n".join([
                texts.hdr("فرماندهی جنگ", "⚔️"), "",
                "🕊 کشورت در جنگ نیست.", "",
                "کشور هدف را انتخاب کن — 👑 فقط رهبر:"]), kb_declare(uid))
    elif what == "wstat":
        await _edit(c, war.world_status(), kb_world())
    elif what == "power":
        await _edit(c, war.power_rank(), kb_world())
    elif what == "colonies":
        await _edit(c, war.colonies(), kb_world())
    elif what == "lb":
        await _edit(c, war.leaderboard(), kb_world())
    elif what == "market":
        await _edit(c, economy.market(), kb_market())
    elif what == "map":
        p = state.active(uid)
        await _edit(c, geo.country_map(p["country"]) if p else "⛔ اول «شروع»", kb_world())
    elif what == "help":
        await _edit(c, texts.HELP_PAGES[0], kb_help(1))
    elif what == "cguide":
        p = state.active(uid)
        await _edit(c, guide.guide(p["country"]) if p else "⛔ اول «شروع»", kb_world())
    elif what == "news":
        await _edit(c, ai.news_feed(), kb_world())
    elif what == "front":
        await _edit(c, war.front(uid), kb_strikes())
    elif what == "army":
        await _edit(c, war.army(uid), kb_world())
    elif what == "def":
        p = state.active(uid)
        await _edit(c, defense.status(p["country"]) if p else "⛔ اول «شروع»", kb_def())
    elif what == "quest":
        await _edit(c, quests.view(uid), kb_quests())
    elif what == "black":
        await _edit(c, military.blackmarket(uid), kb_black(uid))
    elif what == "upgrade":
        p = state.active(uid)
        if not p:
            await _edit(c, "⛔ اول «شروع»", kb_mil())
        else:
            own = db.q("SELECT iid FROM inventory WHERE uid=?", (uid,))
            rows = []
            for r in own:
                it = countries.ITEMS[r["iid"]]
                lvl = military.item_level(uid, r["iid"])
                rows.append([InlineKeyboardButton(
                    text=f"{it[1]} {it[0]} — سطح {texts.fa(lvl)}"
                    + (" (مکس)" if lvl >= 3 else " ⬆️"),
                    callback_data=f"up:{r['iid']}")])
            rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
            await _edit(c, texts.hdr("ارتقای تجهیزات", "⬆️") + "\n\nتجهیزات خودت:",
                        InlineKeyboardMarkup(inline_keyboard=rows))
    elif what == "duel":
        await _edit(c, "\n".join([
            texts.hdr("نبرد تن‌به‌تن", "⚔️"), "",
            "حریفت را انتخاب کن:", "",
            "🏅 برنده: 💰 ۶۰۰ · ⭐ ۱۵۰ XP",
            "🩸 بازنده: −۳۰ جان",
            "⏱ حریف ۵ دقیقه فرصت دارد قبول کند."]), kb_duel(uid))
    elif what == "peace":
        msg = war.peace_request(uid)
        await _edit(c, msg, kb_peace_accept() if "ارسال شد" in msg else kb_pol())
    elif what == "helpally":
        await _edit(c, war.call_help(uid), kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("br:"))
async def cb_branch(c: CallbackQuery):
    await c.message.edit_text(military.join_branch(c.from_user.id, int(c.data.split(":")[1])),
                              parse_mode="HTML", reply_markup=kb_mil())
    await c.answer()


@router.callback_query(F.data.startswith("wp5:"))
@router.callback_query(F.data.startswith("wp:"))
async def cb_buy(c: CallbackQuery):
    uid = c.from_user.id
    qty = 5 if c.data.startswith("wp5:") else 1
    iid = c.data.split(":")[1]
    msg = military.buy(uid, iid, qty)
    await c.answer("خرید انجام شد 🛒" if msg.startswith("🛒") else msg[:180],
                   show_alert=not msg.startswith("🛒"))
    if msg.startswith("🛒"):
        with contextlib.suppress(Exception):
            await c.message.edit_text(military.arsenal(uid), parse_mode="HTML",
                                      reply_markup=kb_arsenal(uid))
        # 🖼 عکس سینمایی تجهیزات شاخص
        it = countries.ITEMS.get(iid)
        if it and it[6]:
            img = f"assets/img/{it[6]}"
            if os.path.exists(img):
                with contextlib.suppress(Exception):
                    with open(img, "rb"):
                        await c.message.answer_photo(
                            FSInputFile(img),
                            caption=(f"{it[1]} <b>{it[0]}</b>\n"
                                     f"⚔️ حمله {it[3]} · 🛡 دفاع {it[4]}\n"
                                     f"🛠 دوام ۱۰۰٪ — حالا قسمت توست."),
                            parse_mode="HTML")
    return


@router.callback_query(F.data.startswith("up:"))
async def cb_upgrade(c: CallbackQuery):
    await c.message.edit_text(military.upgrade(c.from_user.id, c.data.split(":")[1]),
                              parse_mode="HTML", reply_markup=kb_mil())
    await c.answer()


@router.callback_query(F.data.startswith("spy:"))
async def cb_spy(c: CallbackQuery):
    await c.message.edit_text(politics.spy(c.from_user.id, c.data.split(":")[1]),
                              parse_mode="HTML", reply_markup=kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("ally:"))
async def cb_ally(c: CallbackQuery):
    cid = c.data.split(":")[1]
    msg = war.alliance_request(c.from_user.id, cid)
    p = state.active(c.from_user.id)
    # دکمه‌ی قبول باید کشورِ درخواست‌دهنده را ببرد — نه هدف را
    kb = kb_ally_accept(p["country"]) if ("ارسال شد" in msg and p) else kb_pol()
    await c.message.edit_text(msg, parse_mode="HTML", reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.startswith("st:"))
async def cb_strike(c: CallbackQuery):
    parts = c.data.split(":")
    kind = parts[1]
    count = int(parts[2]) if len(parts) > 2 else 1
    await c.message.edit_text(war.strike(c.from_user.id, kind, count),
                              parse_mode="HTML", reply_markup=kb_strikes())
    await c.answer()


# ═══════════ ⚔️ نبرد تن‌به‌تن — کاملاً دکمه‌ای ═══════════

@router.callback_query(F.data.startswith("du:"))
async def cb_duel(c: CallbackQuery):
    uid = c.from_user.id
    try:
        target_uid = int(c.data.split(":")[1])
    except ValueError:
        target_uid = 0
    target = state.get(target_uid)
    if not target:
        await c.answer("⛔ حریف پیدا نشد.", show_alert=True)
        return
    msg = war.duel_request(uid, target["name"] or "سرباز", target_uid)
    await _edit(c, msg, kb_duel_accept() if "چالش" in msg else kb_mil())
    await c.answer()


@router.callback_query(F.data.startswith("dac:"))
async def cb_duel_accept(c: CallbackQuery):
    await _edit(c, war.duel_accept(c.from_user.id), kb_mil())
    await c.answer()


# ═══════════ 🕊 صلح · 🤝 اتحاد · 🏳 تسلیم ═══════════

@router.callback_query(F.data.startswith("pac:"))
async def cb_peace_accept(c: CallbackQuery):
    await _edit(c, war.peace_accept(c.from_user.id), kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("aac:"))
async def cb_ally_accept(c: CallbackQuery):
    await _edit(c, war.alliance_accept(c.from_user.id, c.data.split(":")[1]), kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("sury:"))
async def cb_surrender_yes(c: CallbackQuery):
    await _edit(c, war.surrender(c.from_user.id), kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("sur:"))
async def cb_surrender(c: CallbackQuery):
    p = state.active(c.from_user.id)
    if not p or not p["is_leader"]:
        await c.answer("👑 فقط رهبر کشور.", show_alert=True)
        return
    await _edit(c, "\n".join([
        texts.hdr("تسلیم در جنگ", "🏳"), "",
        "غرامت سنگین می‌دهی، جنگ تمام می‌شود و شهرها می‌مانند.", "",
        "<b>مطمئنی؟</b>"]), kb_surrender())
    await c.answer()


@router.callback_query(F.data.startswith("tp:"))
async def cb_target_page(c: CallbackQuery):
    """📄 صفحه‌بندی پیکر کشورها — جاسوسی/اتحاد/جنگ/تحریم."""
    parts = c.data.split(":")
    action, page = parts[1], (int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0)
    await c.message.edit_reply_markup(reply_markup=kb_targets(c.from_user.id, action, page))
    await c.answer()


# ═══════════ ⚔️ اعلام جنگ — دکمه‌ای ═══════════

@router.callback_query(F.data.startswith("dwr:"))
async def cb_declare_war(c: CallbackQuery):
    uid = c.from_user.id
    msg = war.declare(uid, c.data.split(":")[1])
    p = state.active(uid)
    kb = kb_strikes() if (p and war.war_of(p["country"])) else kb_pol()
    await _edit(c, msg, kb)
    await c.answer()


# ═══════════ 📈 اقتصاد: تحریم · تنگه · بازار سیاه ═══════════

@router.callback_query(F.data.startswith("snc:"))
async def cb_sanction(c: CallbackQuery):
    cid = c.data.split(":")[1]
    if not cid:
        await _edit(c, "\n".join([
            texts.hdr("تحریم اقتصادی", "🚫"), "",
            "کدام کشور؟ — 👑 فقط رهبر:",
            "تحریم یعنی فروش نفتش نصف می‌شود."]), kb_sanction(c.from_user.id))
    else:
        await _edit(c, economy.sanction(c.from_user.id, cid), kb_market())
    await c.answer()


@router.callback_query(F.data.startswith("str:"))
async def cb_strait(c: CallbackQuery):
    name = c.data.split(":", 1)[1]
    if not name:
        await _edit(c, "\n".join([
            texts.hdr("تنگه‌های راهبردی", "🌉"), "",
            "کدام تنگه؟ — 👑 فقط رهبر:",
            "بستن تنگه نفت جهانی را گران می‌کند."]), kb_straits())
    else:
        await _edit(c, economy.toggle_strait(c.from_user.id, name), kb_straits())
    await c.answer()


@router.callback_query(F.data.startswith("bb:"))
async def cb_buy_black(c: CallbackQuery):
    uid = c.from_user.id
    msg = military.buy_black(uid, c.data.split(":")[1])
    ok = "قاچاق شد" in msg or "از قبل" in msg
    await c.answer("☠ قاچاق انجام شد" if ok else msg[:180], show_alert=not ok)
    await _edit(c, military.blackmarket(uid), kb_black(uid))


@router.callback_query(F.data.startswith("qc:"))
async def cb_quest_claim(c: CallbackQuery):
    uid = c.from_user.id
    await _edit(c, quests.claim(uid) + "\n\n" + quests.view(uid), kb_quests())
    await c.answer()


# ═══════════ 🏛 احزاب — کاملاً دکمه‌ای ═══════════

@router.callback_query(F.data.startswith("pj:"))
async def cb_party_join(c: CallbackQuery):
    uid = c.from_user.id
    try:
        pid = int(c.data.split(":")[1])
    except ValueError:
        pid = 0
    party = db.one("SELECT name FROM parties WHERE id=?", (pid,))
    msg = politics.join(uid, party["name"]) if party else "⛔ حزب پیدا نشد."
    await _edit(c, msg + "\n\n" + politics.list_parties(uid), kb_parties(uid))
    await c.answer()


@router.callback_query(F.data == "pnew:")
async def cb_party_new(c: CallbackQuery):
    uid = c.from_user.id
    p = state.active(uid)
    cur = texts.money(p["country"], 5000) if p else "۵٬۰۰۰"
    _pend_set(uid, c.message.chat.id, "party")
    await _edit(c, "\n".join([
        texts.hdr("حزب جدید", "🏛"), "",
        "📝 <b>نام حزب را در همین گروه بنویس</b>", "",
        "با «|» ایدئولوژی هم بده:",
        "<code>میهن‌دوستان | ملی</code>", "",
        f"💰 هزینه: {cur} · ⛔ حداقل ۳ حرف · 🪖 نیازمند عضویت نظامی", "",
        "✋ لغو: بنویس «لغو»"]), kb_cancel_pol())
    await c.answer()


@router.callback_query(F.data.startswith("pcancel:"))
async def cb_pcancel(c: CallbackQuery):
    _pending.pop((c.from_user.id, c.message.chat.id), None)
    await _edit(c, "✋ لغو شد.", kb_pol())
    await c.answer()


# ═══════════ ⚡ رویداد گروهی ═══════════

async def _ev_claim(m: Message, word: str):
    r = events.claim(m.chat.id, m.from_user.id, word)
    if r:
        await m.answer(r, parse_mode="HTML")
    else:
        await m.answer("⚡ رویداد فعالی نیست — چشم انتظار باش.", parse_mode="HTML")


# ═══════════ 🗣 دستورهای متنی فارسی ═══════════

async def fa_words(m: Message):
    t = (m.text or "").strip()
    if not t:
        return
    parts = t.split(maxsplit=1)
    w = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    uid = m.from_user.id
    state.ensure(uid, m.from_user.first_name, m.chat.id,
                 getattr(m.from_user, "username", None))
    # ✍️ ورودی در انتظار (بیانیه / حزب) — قبل از فیلتر، بعد از ثبت حضور
    pend = _pend_pop(uid, m.chat.id)
    if pend:
        if w == "لغو":
            return await m.answer("✋ لغو شد — هر وقت خواستی از منو دوباره شروع کن.",
                                  parse_mode="HTML")
        if pend == "stmt":
            return await m.answer(politics.statement(uid, t), parse_mode="HTML",
                                  reply_markup=kb_pol())
        if pend == "party":
            nm, _, ideo = t.partition("|")
            return await m.answer(politics.found(uid, nm.strip(), ideo.strip() or "ملی"),
                                  parse_mode="HTML", reply_markup=kb_pol())
    # 🎛 گروه تمیز: هر متن دیگری نادیده — همه‌چیز از «منو»
    if not TEST_MODE and w not in TEXT_ALLOWED:
        return
    # ⚡ رویداد گروهی
    if w in ("تحویل", "اعزام", "رمزگشایی"):
        return await _ev_claim(m, w)
    if w == "شروع":
        return await cmd_start(m)
    if w == "منو":
        act = state.active(uid)
        # 🔔 کول‌داون: تا ۱ دقیقه منوی تازه نمی‌آید — تگ روی منوی قبلی
        last = (db.kv_get(f"menu:{uid}", "") or "").split(":")
        if act and len(last) == 2 and db.now() - int(last[1]) < 60:
            card = state.card(uid)
            tag = texts.mention(uid, m.from_user.first_name or "بازیکن")
            ok_edit = False
            if handlers_bot():
                with contextlib.suppress(Exception):
                    await handlers_bot().edit_message_text(
                        chat_id=m.chat.id, message_id=int(last[0]),
                        text=f"🔔 {tag}\n\n{card}"[:4000],
                        parse_mode="HTML", reply_markup=kb_main())
                    ok_edit = True
            if ok_edit:
                return await m.answer("🔔 منوت همین‌جاست — یک دقیقه صبر کن برای منوی تازه",
                                      parse_mode="HTML")
        sent = await m.answer(state.card(uid) if act else texts.WELCOME,
                              parse_mode="HTML",
                              reply_markup=kb_main() if act else kb_countries())
        if act:
            db.kv_set(f"menu:{uid}", f"{sent.message_id}:{db.now()}")
        return sent
    # ═══ 👑 دستورهای مالک ═══
    if w in ("اعلام", "سربازها", "توزیع"):
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        for part in _admin_callup_parts():
            await m.answer(part, parse_mode="HTML")
        return
    if w in ("مدیریت", "ادمین"):
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        return await m.answer(_admin_stats(), parse_mode="HTML", reply_markup=kb_admin())
    if w == "ثبت" and arg:
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        parts3 = arg.split()
        if len(parts3) >= 2 and parts3[0].isdigit():
            return await m.answer(_admin_register(int(parts3[0]), " ".join(parts3[1:])),
                                  parse_mode="HTML", reply_markup=kb_admin())
        return await m.answer("🔎 الگو: <code>ثبت آیدی کشور</code>", parse_mode="HTML")
    if w == "تغییر" and arg:
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        parts3 = arg.split()
        if len(parts3) >= 2 and parts3[0].isdigit():
            return await m.answer(_admin_change(int(parts3[0]), " ".join(parts3[1:])),
                                  parse_mode="HTML", reply_markup=kb_admin())
        return await m.answer("🔎 الگو: <code>تغییر آیدی کشور</code>", parse_mode="HTML")
    if w == "رهبر":
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        parts_l = arg.split() if arg else []
        # 📌 ریپلای روی پیام بازیکن + «رهبر کشور»
        ru = getattr(m.reply_to_message, "from_user", None) if m.reply_to_message else None
        if ru and parts_l and parts_l[0] not in ("خالی", "-"):
            return await m.answer(_set_leader(ru.id, " ".join(parts_l)),
                                  parse_mode="HTML", reply_markup=kb_admin())
        # @آیدی بازیکنی که در گروه دیده‌ایم
        if parts_l and parts_l[0].startswith("@") and parts_l[0][1:]:
            r = db.one("SELECT uid FROM users WHERE username=? COLLATE NOCASE",
                       (parts_l[0][1:],))
            if r:
                return await m.answer(_set_leader(r["uid"], " ".join(parts_l[1:])),
                                      parse_mode="HTML", reply_markup=kb_admin())
            return await m.answer(
                "⛔ این @آیدی را ندیده‌ام — بازیکن یک بار در گروه پیام بدهد، "
                "یا روی پیامش ریپلای کن و بنویس: <code>رهبر کشور</code>",
                parse_mode="HTML")
        if not arg:
            return await m.answer(
                "🔎 روی پیام بازیکن ریپلای کن و بنویس: <code>رهبر کشور</code>\n"
                "یا: <code>رهبر آیدی‌عددی کشور</code> · <code>رهبر @آیدی کشور</code> · "
                "خلع: <code>رهبر خالی کشور</code>", parse_mode="HTML")
        return await m.answer(_admin_leader(arg), parse_mode="HTML", reply_markup=kb_admin())
    if w == "تنظیم":
        if uid != config.OWNER_ID:
            return await m.answer("👑 فقط مالک!", parse_mode="HTML")
        if arg in ("اخبار", "خبرنامه"):
            db.kv_set("bl_off", "" if db.kv_get("bl_off") else "1")
        elif arg in ("رویداد", "رویدادها"):
            db.kv_set("ev_off", "" if db.kv_get("ev_off") else "1")
        bl = "خاموش ❌" if db.kv_get("bl_off") else "روشن ✅"
        ev = "خاموش ❌" if db.kv_get("ev_off") else "روشن ✅"
        return await m.answer("\n".join([
            texts.hdr("تنظیمات ربات", "🎛"),
            f"📰 خبرنامه‌ی هر ۱۰ دقیقه: <b>{bl}</b> — «تنظیم اخبار»",
            f"⚡ رویداد گروهی: <b>{ev}</b> — «تنظیم رویداد»"]),
            parse_mode="HTML", reply_markup=kb_admin())


def _find_country(txt: str):
    """کشور را دقیق پیدا کن — نیم‌فاصله و ی/ک عربی نرمال می‌شود."""
    def _n(s):
        return (s or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک").strip()
    t = _n(txt)
    if not t:
        return None
    for cid, c in countries.COUNTRIES.items():
        if t in (c["name"], cid) or _n(c["name"]) == t:
            return cid
    for cid, c in countries.COUNTRIES.items():
        cn = _n(c["name"])
        if cn and (t in cn or cn in t):
            return cid
    return None


router.message()(fa_words)
