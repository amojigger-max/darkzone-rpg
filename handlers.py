"""🎮 جنگ جهانی — رابط کاربری: کاملاً فارسی، دکمه‌ای، تمیز."""

import contextlib
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import countries
import db
import texts
from game import economy, events, geo, military, politics, state, war

router = Router()
bot: Bot = None


# ═══════════ 🚫 بازی فقط در گروه ═══════════

@router.message(F.chat.type == "private")
async def pv_only_group(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ افزودن به یک گروه",
                             url="https://t.me/WorldWar3RPGbot?startgroup=true")]])
    await m.answer(texts.PV_ONLY, reply_markup=kb)


@router.callback_query(F.message.chat.type == "private")
async def pv_cb_only_group(c: CallbackQuery):
    await c.answer("🎮 بازی فقط در گروه!", show_alert=True)


# ═══════════ 🧩 کیبوردها ═══════════

def kb_countries(page=0) -> InlineKeyboardMarkup:
    ids = list(countries.COUNTRIES)
    per, p = 10, page
    chunk = ids[p * per:(p + 1) * per]
    rows = []
    for a, b in zip(chunk[::2], chunk[1::2]):
        ca, cb = countries.COUNTRIES[a], countries.COUNTRIES[b]
        rows.append([InlineKeyboardButton(text=f"{ca['flag']} {ca['name']}", callback_data=f"cy:{a}"),
                     InlineKeyboardButton(text=f"{cb['flag']} {cb['name']}", callback_data=f"cy:{b}")])
    if len(chunk) % 2:
        c = countries.COUNTRIES[chunk[-1]]
        rows.append([InlineKeyboardButton(text=f"{c['flag']} {c['name']}", callback_data=f"cy:{chunk[-1]}")])
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
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_pol() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛 احزاب", callback_data="mn:parties"),
         InlineKeyboardButton(text="🚩 شورش", callback_data="mn:rebel")],
        [InlineKeyboardButton(text="🕵 جاسوسی", callback_data="mn:spy"),
         InlineKeyboardButton(text="🤝 اتحاد", callback_data="mn:ally")],
        [InlineKeyboardButton(text="⚔️ جنگ و حمله", callback_data="mn:war"),
         InlineKeyboardButton(text="📰 بیانیه", callback_data="mn:stmt")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_world() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 وضعیت جهان", callback_data="mn:wstat"),
         InlineKeyboardButton(text="🏆 رتبه", callback_data="mn:lb")],
        [InlineKeyboardButton(text="📈 بازار", callback_data="mn:market"),
         InlineKeyboardButton(text="🏙 نقشه‌ی کشور", callback_data="mn:map")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_branches(uid) -> InlineKeyboardMarkup:
    p = state.get(uid)
    c = countries.COUNTRIES.get(p["country"]) if p else None
    rows = []
    if c:
        for i, b in enumerate(c["branches"]):
            rows.append([InlineKeyboardButton(text=f"🪖 {b}", callback_data=f"br:{i}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_arsenal(uid) -> InlineKeyboardMarkup:
    p = state.get(uid)
    c = countries.COUNTRIES.get(p["country"]) if p else None
    rows = []
    if c:
        for iid in c["items"]:
            it = countries.ITEMS[iid]
            own = db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid))
            price = economy.real_price(it[5])
            mark = "✅" if own else f"💰{price // 1000}k"
            rows.append([InlineKeyboardButton(text=f"{it[1]} {it[0]} — {mark}",
                                              callback_data=f"wp:{iid}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_targets(uid, action) -> InlineKeyboardMarkup:
    """لیست ۲۰ کشور برای جاسوسی/اتحاد/جنگ."""
    p = state.get(uid)
    rows = []
    chunk = [cid for cid in countries.COUNTRIES if cid != (p["country"] if p else None)]
    for a, b in zip(chunk[::2], chunk[1::2]):
        rows.append([InlineKeyboardButton(text=countries.COUNTRIES[a]["flag"] + countries.COUNTRIES[a]["name"],
                                          callback_data=f"{action}:{a}"),
                     InlineKeyboardButton(text=countries.COUNTRIES[b]["flag"] + countries.COUNTRIES[b]["name"],
                                          callback_data=f"{action}:{b}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_strikes() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 موشکی", callback_data="st:موشکی"),
         InlineKeyboardButton(text="✈️ هوایی", callback_data="st:هوایی")],
        [InlineKeyboardButton(text="🚢 دریایی", callback_data="st:دریایی"),
         InlineKeyboardButton(text="🚜 زمینی", callback_data="st:زمینی"),
         InlineKeyboardButton(text="🛩 پهپادی", callback_data="st:پهپادی")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


# ═══════════ 🚀 شروع ═══════════

@router.message(Command("start"))
@router.message(F.text.in_(["شروع"]))
async def cmd_start(m: Message):
    state.ensure(m.from_user.id, m.from_user.first_name, m.chat.id)
    if state.get(m.from_user.id):
        await m.answer(state.card(m.from_user.id), parse_mode="HTML", reply_markup=kb_main())
        return
    import os
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
    if state.get(uid):
        await c.answer("قبلاً ثبت‌نام کردی.", show_alert=True)
        return
    cid = c.data.split(":")[1]
    ok = state.enlist(uid, cid, c.from_user.first_name or "سرباز")
    if not ok:
        await c.answer("خطا — دوباره امتحان کن.", show_alert=True)
        return
    co = countries.COUNTRIES[cid]
    t = texts
    await c.message.delete()
    await c.message.answer("\n".join([
        t.hdr("ثبت‌نام تکمیل شد", "🎖"),
        t.row("کشور", f"{co['flag']} {co['name']}"),
        t.row("خزانه", "💰 ۲٬۰۰۰"),
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


@router.callback_query(F.data.startswith("mn:"))
async def cb_menu(c: CallbackQuery):
    uid = c.from_user.id
    what = c.data.split(":", 1)[1]
    if not state.get(uid) and what not in ("help",):
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
    elif what == "help":
        await _edit(c, texts.HELP)
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
        await _edit(c, politics.list_parties(uid), kb_pol())
    elif what == "rebel":
        await _edit(c, politics.rebel(uid), kb_pol())
    elif what == "stmt":
        await _edit(c, "📰 بیانیه‌ی حزب را بنویس:\n<code>بیانیه متن بیانیه</code>\n"
                       "مثال: <code>بیانیه ما برای آبادی این سرزمین می‌جنگیم</code>", kb_pol())
    elif what == "spy":
        await _edit(c, texts.hdr("عملیات جاسوسی", "🕵") + "\nکشور هدف:", kb_targets(uid, "spy"))
    elif what == "ally":
        await _edit(c, texts.hdr("پیشنهاد اتحاد", "🤝") + "\nبا کدام کشور؟", kb_targets(uid, "ally"))
    elif what == "war":
        await _edit(c, texts.hdr("فرماندهی جنگ", "⚔️") + "\nنوع حمله:", kb_strikes())
    elif what == "wstat":
        await _edit(c, war.world_status(), kb_world())
    elif what == "lb":
        await _edit(c, war.leaderboard(), kb_world())
    elif what == "market":
        await _edit(c, economy.market(), kb_world())
    elif what == "map":
        p = state.active(uid)
        await _edit(c, geo.country_map(p["country"]) if p else "⛔ اول «شروع»", kb_world())
    await c.answer()


@router.callback_query(F.data.startswith("br:"))
async def cb_branch(c: CallbackQuery):
    await c.message.edit_text(military.join_branch(c.from_user.id, int(c.data.split(":")[1])),
                              parse_mode="HTML", reply_markup=kb_mil())
    await c.answer()


@router.callback_query(F.data.startswith("wp:"))
async def cb_buy(c: CallbackQuery):
    uid = c.from_user.id
    iid = c.data.split(":")[1]
    it = countries.ITEMS[iid]
    p = state.get(uid)
    price = economy.real_price(it[5])
    if p and p["money"] < price:
        await c.answer(f"💰 پول کم — {price:,} لازم است", show_alert=True)
        return
    if not db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid)):
        db.ex("UPDATE users SET money=money-? WHERE uid=?", (price, uid))
        db.ex("INSERT OR REPLACE INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100)",
              (uid, iid))
        await c.answer(f"🛒 {it[0]} خریداری شد!", show_alert=False)
        # 🖼 عکس سینمایی تجهیزات شاخص
        import os
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
    else:
        await c.answer("✅ از قبل داری", show_alert=True)
    await c.message.edit_text(military.arsenal(uid), parse_mode="HTML",
                              reply_markup=kb_arsenal(uid))


@router.callback_query(F.data.startswith("spy:"))
async def cb_spy(c: CallbackQuery):
    await c.message.edit_text(politics.spy(c.from_user.id, c.data.split(":")[1]),
                              parse_mode="HTML", reply_markup=kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("ally:"))
async def cb_ally(c: CallbackQuery):
    await c.message.edit_text(war.alliance_request(c.from_user.id, c.data.split(":")[1]),
                              parse_mode="HTML", reply_markup=kb_pol())
    await c.answer()


@router.callback_query(F.data.startswith("st:"))
async def cb_strike(c: CallbackQuery):
    await c.message.edit_text(war.strike(c.from_user.id, c.data.split(":")[1]),
                              parse_mode="HTML", reply_markup=kb_strikes())
    await c.answer()


# ═══════════ ⚡ رویداد گروهی ═══════════

async def _ev_claim(m: Message, word: str):
    r = events.claim(m.chat.id, m.from_user.id, word)
    if r:
        await m.answer(r, parse_mode="HTML")


# ═══════════ 🗣 دستورهای متنی فارسی ═══════════

FA = {
    "شروع": cmd_start,
}


async def fa_words(m: Message):
    t = (m.text or "").strip()
    parts = t.split(maxsplit=1)
    w = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    uid = m.from_user.id
    state.ensure(uid, m.from_user.first_name, m.chat.id)
    # رویداد گروهی
    if w in ("تحویل", "اعزام", "رمزگشایی"):
        return await _ev_claim(m, w)
    if w in ("شروع",):
        return await cmd_start(m)
    if w in ("منو",):
        return await m.answer(state.card(uid) if state.get(uid) else texts.WELCOME,
                              parse_mode="HTML", reply_markup=kb_main() if state.get(uid) else kb_countries())
    if w in ("پروفایل", "کارنام", "کارت"):
        return await m.answer(state.card(uid), parse_mode="HTML", reply_markup=kb_main())
    if w in ("ارتچی", "سرباز"):
        return await m.answer(texts.hdr("انتخاب شاخه", "🪖") + "\nشاخه‌ی کشورت:",
                              reply_markup=kb_branches(uid))
    if w in ("تجهیزات", "زرادخانه"):
        return await m.answer(military.arsenal(uid), parse_mode="HTML", reply_markup=kb_arsenal(uid))
    if w == "خرید":
        return await m.answer(military.arsenal(uid), parse_mode="HTML", reply_markup=kb_arsenal(uid))
    if w in ("رزم", "نبرد", "جنگیدن"):
        return await m.answer(military.battle(uid), parse_mode="HTML", reply_markup=kb_mil())
    if w in ("استراحت", "درمان"):
        return await m.answer(military.rest(uid), parse_mode="HTML", reply_markup=kb_mil())
    if w == "تعمیر":
        return await m.answer(military.repair(uid), parse_mode="HTML", reply_markup=kb_mil())
    if w in ("جیره", "دستمزد"):
        return await m.answer(state.ration(uid), parse_mode="HTML", reply_markup=kb_mil())
    if w == "حزب":
        if not arg:
            return await m.answer("🏛 نام حزب را بنویس: <code>حزب نام یدئولوژی</code>\n"
                                  "مثال: <code>حزب میهن‌دوستان ملی</code>", parse_mode="HTML")
        nm, ideo = (arg.split(maxsplit=1) + [""])[:2]
        return await m.answer(politics.found(uid, nm, ideo), parse_mode="HTML", reply_markup=kb_pol())
    if w == "احزاب":
        return await m.answer(politics.list_parties(uid), parse_mode="HTML", reply_markup=kb_pol())
    if w == "عضویت":
        return await m.answer(politics.join(uid, arg), parse_mode="HTML", reply_markup=kb_pol())
    if w == "بیانیه":
        if not arg:
            return await m.answer("📰 متن بیانیه را بنویس: <code>بیانیه متن</code>", parse_mode="HTML")
        return await m.answer(politics.statement(uid, arg), parse_mode="HTML", reply_markup=kb_pol())
    if w == "شورش":
        return await m.answer(politics.rebel(uid), parse_mode="HTML", reply_markup=kb_pol())
    if w == "جاسوسی":
        return await m.answer(texts.hdr("عملیات جاسوسی", "🕵") + "\nکشور هدف:",
                              reply_markup=kb_targets(uid, "spy"))
    if w in ("جنگ", "اعلامجنگ"):
        if arg:
            cid = _find_country(arg)
            return await m.answer(war.declare(uid, cid or arg), parse_mode="HTML", reply_markup=kb_pol())
        return await m.answer("⚔️ کشور هدف را بنویس: <code>جنگ آمریکا</code>\n"
                              "یا از منوی «جنگ و حمله» انواع حمله را بزن.", parse_mode="HTML",
                              reply_markup=kb_strikes())
    if w in ("حمله", "ضربه"):
        if arg:
            return await m.answer(war.strike(uid, arg), parse_mode="HTML", reply_markup=kb_strikes())
        return await m.answer("🎯 نوع حمله: <code>حمله موشکی</code> · <code>حمله هوایی</code> · "
                              "<code>حمله دریایی</code> · <code>حمله زمینی</code> · <code>حمله پهپادی</code>",
                              parse_mode="HTML", reply_markup=kb_strikes())
    if w == "اتحاد":
        if arg:
            cid = _find_country(arg)
            return await m.answer(war.alliance_request(uid, cid or arg), parse_mode="HTML")
        return await m.answer("🤝 کشور را بنویس: <code>اتحاد روسیه</code>", parse_mode="HTML",
                              reply_markup=kb_targets(uid, "ally"))
    if w == "قبول":
        if arg:
            cid = _find_country(arg)
            return await m.answer(war.alliance_accept(uid, cid or arg), parse_mode="HTML")
        return await m.answer("🤝 کشور را بنویس: <code>قبول اتحاد ایران</code>", parse_mode="HTML")
    if w == "کمک":
        return await m.answer(war.call_help(uid), parse_mode="HTML", reply_markup=kb_pol())
    if w == "تحریم":
        if arg:
            cid = _find_country(arg)
            return await m.answer(economy.sanction(uid, cid or arg), parse_mode="HTML")
        return await m.answer("🚫 کشور را بنویس: <code>تحریم ایران</code>", parse_mode="HTML")
    if w == "تنگه":
        return await m.answer(economy.toggle_strait(arg or "؟"), parse_mode="HTML")
    if w in ("بازار", "اقتصاد"):
        return await m.answer(economy.market(), parse_mode="HTML", reply_markup=kb_world())
    if w == "جهان":
        return await m.answer(war.world_status(), parse_mode="HTML", reply_markup=kb_world())
    if w in ("رتبه", "برترین"):
        return await m.answer(war.leaderboard(), parse_mode="HTML", reply_markup=kb_world())
    if w == "نقشه":
        p = state.active(uid)
        return await m.answer(geo.country_map(p["country"]) if p else "⛔ اول «شروع»",
                              parse_mode="HTML", reply_markup=kb_world())
    if w == "راهنما":
        return await m.answer(texts.HELP, parse_mode="HTML", reply_markup=kb_main())


def _find_country(txt: str):
    for cid, c in countries.COUNTRIES.items():
        if txt.strip() in (c["name"], cid) or c["name"] in txt:
            return cid
    return None


router.message()(fa_words)
