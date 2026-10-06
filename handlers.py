"""🎮 جنگ جهانی — رابط کاربری: کاملاً فارسی، دکمه‌ای، تمیز."""

import contextlib
import os
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import countries
import db
import texts
from game import ai, defense, economy, events, geo, guide, infra, invest, military, politics, quests, state, toll, war, welfare, campaign, notifications, rewards, rules
from htmlsafe import split_html
import json

router = Router()


def handlers_bot():
    """نمونه‌ی بات برای ویرایش پیام — از بیرون هم در دسترس."""
    return globals().get("bot")


# 🎛 فقط همین دستورهای متنی زنده‌اند — همه‌چیز دیگر از «منو»
TEST_MODE = False
bot = None  # ← run.py تزریق می‌کند
# دکمه‌هایی که هر کسی می‌تواند بزند (پاسخ اتحاد/صلح/نبرد/رویداد/چرا-نه)
MENU_BYPASS = ("aac:", "pac:", "dac:", "gno:", "evc:", "pm:", "ctac:")


def _own(c,sent,uid):
    chat=getattr(c,'chat',None) or getattr(getattr(c,'message',None),'chat',None)
    if chat and sent and getattr(sent,'message_id',None):
        db.kv_set(f'mown:{chat.id}:{sent.message_id}',uid)


def _menu_locked(c) -> str:
    """اگر دکمه‌ی منوی دیگری باشد، پیام رد؛ وگرنه خالی."""
    d = c.data or ""
    if d.startswith(MENU_BYPASS):
        return ""
    try:
        key = f"mown:{c.message.chat.id}:{c.message.message_id}"
    except AttributeError:
        return ""
    owner = db.kv_get(key)
    if owner and str(owner) != str(c.from_user.id):
        u = state.get(int(owner))
        nm = (u["name"] if u else "") or "بازیکن دیگر"
        return f"⛔ این منوی {nm} است — خودت بنویس «منو» تا منوی خودت بیاید."
    return ""


@router.callback_query.middleware()
async def menu_lock_mw(handler, event: CallbackQuery, data):
    """🔒 هیچ‌کس منوی دیگری را کنترل نمی‌کند."""
    msg = _menu_locked(event)
    if msg:
        with contextlib.suppress(Exception):
            await event.answer(msg[:180])
        return
    return await handler(event, data)


TEXT_ALLOWED = {
    "عملیات", "سازمان‌ملل", "تنگه‌ها", "ناوگان", "انرژی", "تحریم",
    "شروع", "استارت", "منو",                                # بازی
    "راهنما", "تجارت", "پروفایل", "نظامی", "جهان", "جنگ",  # دستورهای فارسی
    "حمله", "نبرد", "خرید", "زرادخانه", "تجهیزات",        # نام‌های رایج
    "دستورها", "دستور", "دستورات", "کمک",                 # فهرست دستورها
    "سرمایه", "سرمایه‌گذاری", "معدن", "دارایی",           # سرمایه‌گذاری
    "زیرساخت", "انقلاب", "شورش",                          # زیرساخت + انقلاب
    "رفاه", "عوارض",                                       # رفاه + تنگه
    "شهرها", "پایگاه", "مهمات", "قراردادها", "هدایا",
    "رهبر", "ثبت", "تغییر", "تنظیم",                      # ابزار مالک
}
bot: Bot = None
WORLD_OF = None   # 💬 حلقه‌ی پیوی → دنیای بازیکن (run.py در بوت ست می‌کند)
STICKERS: dict = {}   # 🎞 پک استیکر دارک‌زون — ایموجی → file_id (run.py پر می‌کند)


async def _sticker(chat, emoji: str):
    """🎞 استیکر مرتبط را می‌فرستد — اگر پک آماده باشد."""
    fid = STICKERS.get(emoji)
    if fid:
        with contextlib.suppress(Exception):
            await chat.send_sticker(fid)


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
        [InlineKeyboardButton(text="📣 اعلام فراخوان", callback_data="ad:callup"),
         InlineKeyboardButton(text="🎖 سربازها", callback_data="ad:troops")],
        [InlineKeyboardButton(text="🧑‍✈️ ثبت بازیکن", callback_data="ad:reg"),
         InlineKeyboardButton(text="🔄 تغییر کشور", callback_data="ad:chg")],
        [InlineKeyboardButton(text="👑 رهبر دادن", callback_data="ad:lead"),
         InlineKeyboardButton(
             text="📰 خبرنامه: " + ("خاموش ❌" if db.kv_get("bl_off") else "روشن ✅"),
             callback_data="ad:tog:bl")],
        [InlineKeyboardButton(
            text="⚡ رویداد گروهی: " + ("خاموش ❌" if db.kv_get("ev_off") else "روشن ✅"),
            callback_data="ad:tog:ev")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def _admin_callup_parts():
    rows=db.q("SELECT uid,name,country FROM users ORDER BY country,uid")
    body=texts.hdr('فراخوان همهٔ بازیکنان','📣')+'\n'
    for r in rows:
        c=countries.COUNTRIES.get(r['country'],{})
        body+=f"\n{c.get('flag','▫️')} {texts.mention(r['uid'],r['name'])} — {c.get('name','بدون کشور')}"
    return split_html(body or 'بازیکنی نیست.')


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
        "خلع بدون دولت خودکار: <code>رهبر خالی آمریکا</code>",
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


@db.atomic
def _admin_change(uid_target,country_name):
    p=state.get(uid_target);cid=_find_country(country_name or '')
    if not p or not cid:return '⛔ حساب یا کشور پیدا نشد.'
    if p['country']==cid:return '✅ کشور تغییری نکرد.'
    if war.war_of(p['country']) or war.war_of(cid):return '⚔️ جابه‌جایی رهبر در زمان جنگ ممنوع است.'
    if db.one('SELECT 1 FROM users WHERE country=?',(cid,)):return '⛔ کشور مقصد از قبل بازیکن دارد.'
    db.ex('DELETE FROM country_claims WHERE uid=?',(uid_target,))
    db.ex('UPDATE users SET country=?,is_leader=1,branch=NULL,party_id=NULL WHERE uid=?',(cid,uid_target))
    db.ex('INSERT INTO country_claims(country,uid,claimed) VALUES(?,?,?)',(cid,uid_target,db.now()))
    db.kv_set(f'claimed:{cid}',db.now());infra.ensure(cid);defense.ensure(cid)
    db.audit('admin_country_change',config.OWNER_ID,uid=uid_target,old=p['country'],new=cid)
    return f"🔄 {texts.mention(uid_target,p['name'])} به {countries.COUNTRIES[cid]['name']} منتقل شد؛ شاخهٔ قبلی پاک شد."


@db.atomic
def _set_leader(uid_t,cname):
    cid=_find_country(cname or '')
    if not cid:return '⛔ کشور نامعتبر.'
    p=state.get(uid_t)
    if p and p['country'] and p['country']!=cid:return '⛔ ابتدا از دستور تغییر کشور استفاده کن.'
    if war.war_of(cid):return '⚔️ تغییر رهبر در میانهٔ جنگ ممنوع است.'
    if not p or not p['country']:
        if not state.enlist(uid_t,cid,f'Player{uid_t%1000}'):return '⛔ کشور قابل واگذاری نیست.'
    db.ex('UPDATE users SET is_leader=0 WHERE country=?',(cid,))
    db.ex('UPDATE users SET is_leader=1 WHERE uid=?',(uid_t,))
    db.ex('DELETE FROM country_claims WHERE country=? OR uid=?',(cid,uid_t))
    db.ex('INSERT INTO country_claims(country,uid,claimed) VALUES(?,?,?)',(cid,uid_t,db.now()))
    db.audit('admin_leader',config.OWNER_ID,uid=uid_t,country=cid)
    return f"👑 {texts.mention(uid_t,(state.get(uid_t) or {}).get('name'))} رهبر {countries.COUNTRIES[cid]['name']} شد."


@db.atomic
def _admin_leader(arg):
    parts=arg.split()
    if parts and parts[0] in ('خالی','-'):
        cid=_find_country(' '.join(parts[1:]))
        if not cid:return '⛔ کشور نامعتبر.'
        if war.war_of(cid):return '⚔️ خلع رهبر در میانهٔ جنگ ممنوع است.'
        db.ex('UPDATE users SET is_leader=0 WHERE country=?',(cid,))
        db.ex('DELETE FROM country_claims WHERE country=?',(cid,))
        return '🕊 کشور بدون رهبر شد؛ هیچ دولت NPC جای آن نمی‌آید. حساب اعضا حذف نشد.'
    if len(parts)>=2 and (uid:=texts.to_int(parts[0])):
        return _set_leader(uid,' '.join(parts[1:]))
    return 'الگو: <code>رهبر آیدی کشور</code> یا <code>رهبر خالی کشور</code>'


@router.callback_query(F.data.startswith("ad:"))
async def cb_admin(c: CallbackQuery):
    if c.from_user.id != config.OWNER_ID:
        await c.answer("👑 فقط مالک!", show_alert=True)
        return
    what = c.data.split(":", 1)[1]
    if what == "stats":
        await _edit(c, _admin_stats(), kb_admin())
    elif what == "players":
        rows = db.q("SELECT uid, name, country, level FROM users "
                    "ORDER BY level DESC,uid")
        lines = [texts.hdr("بازیکنان", "👥"), ""]
        for r in rows:
            cc = countries.COUNTRIES.get(r["country"], {})
            lines.append(f"▫️ {texts.mention(r['uid'],r['name'])} · "
                         f"{cc.get('flag', '')} سطح {r['level']}")
        lines.append("")
        lines.append(texts.DASH)
        await _edit(c, "\n".join(lines), kb_admin())
    elif what == "lead":
        _pend_set(config.OWNER_ID, c.message.chat.id, "alead")
        await _edit(c, "\n".join([
            texts.hdr("تعیین یا خلع رهبر", "👑"), "",
            "✍️ الگو را بفرست:",
            "▫️ <code>آیدی‌عددی نام‌کشور</code> — بازیکن رهبر شود",
            "▫️ <code>خالی نام‌کشور</code> — کشور بدون رهبر و بدون دولت خودکار",
            "", "«لغو» برای انصراف"]), kb_admin())
    elif what == "tog:bl":
        db.kv_set("bl_off", "" if db.kv_get("bl_off") else "1")
        await _edit(c, "\n".join([
            texts.hdr("تنظیمات", "⚙"), "",
            "📰 خبرنامه‌ی گروه: " +
            ("خاموش شد ❌" if db.kv_get("bl_off") else "روشن شد ✅")]), kb_admin())
    elif what == "tog:ev":
        db.kv_set("ev_off", "" if db.kv_get("ev_off") else "1")
        await _edit(c, "\n".join([
            texts.hdr("تنظیمات", "⚙"), "",
            "⚡ رویداد گروهی: " +
            ("خاموش شد ❌" if db.kv_get("ev_off") else "روشن شد ✅")]), kb_admin())
    elif what in ("reg", "chg"):
        _pend_set(config.OWNER_ID, c.message.chat.id,
                  "areg" if what == "reg" else "achg")
        await _edit(c, "\n".join([
            texts.hdr("ثبت یا تغییر کشور بازیکن" if what == "reg"
                      else "تغییر کشور بازیکن", "🛠"), "",
            "✍️ همین الگو را بفرست: <code>آیدی‌عددی نام‌کشور</code>",
            "مثال: <code>123456 ایران</code>",
            "", "«لغو» برای انصراف"]), kb_admin())
    elif what in ("callup", "troops"):
        notifications.emit('📣 فراخوان بازیکنان دارک‌زون؛ از /menu وضعیت کشور و امکانات تازه را ببینید.',uids=[r['uid'] for r in db.q('SELECT uid FROM users ORDER BY uid')])
        await _edit(c,'📣 فراخوان برای تمام حساب‌های همین گروه در صف پایدار ثبت شد؛ وضعیت ارسال از پنل اعلان‌ها.',kb_admin())
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


def kb_main(uid=None) -> InlineKeyboardMarkup:
    """🎛 منوی اصلی — برای مالک ردیف مدیریت هم دارد."""
    rows = [
        [InlineKeyboardButton(text="🪖 نظامی", callback_data="mn:mil"),
         InlineKeyboardButton(text="🏛 سیاست", callback_data="mn:pol")],
        [InlineKeyboardButton(text="🌍 جهان", callback_data="mn:world"),
         InlineKeyboardButton(text="👤 پروفایل", callback_data="mn:me")],
        [InlineKeyboardButton(text="💼 تجارت", callback_data="mn:trade"),
         InlineKeyboardButton(text="🧭 چی بزنم؟", callback_data="mn:howto")],
        [InlineKeyboardButton(text="🎁 جایزه‌ی روزانه", callback_data="dl:"),
         InlineKeyboardButton(text="🔨 کار کن", callback_data="wk:")],
        [InlineKeyboardButton(text="💸 انتقال پول", callback_data="pay:"),
         InlineKeyboardButton(text="⚡ رویدادها", callback_data="mn:events")],
        [InlineKeyboardButton(text="🏭 سرمایه‌گذاری", callback_data="inv:"),
         InlineKeyboardButton(text="🏘 رفاه مردم", callback_data="mn:welf")],
        [InlineKeyboardButton(text="🛃 عوارض تنگه", callback_data="toll:"),
         InlineKeyboardButton(text="📖 راهنما", callback_data="mn:help")]]
    rows.append([InlineKeyboardButton(text="🇺🇳 سازمان ملل",callback_data="un:"),InlineKeyboardButton(text="🧭 عملیات با نام دلخواه",callback_data="ops:")])
    rows.append([InlineKeyboardButton(text="⛽ نیروگاه و سوخت",callback_data="en:"),InlineKeyboardButton(text="🚢 ناوگان نفت‌کش",callback_data="fv:")])
    rows.append([InlineKeyboardButton(text="🌉 گذرگاه‌ها و عوارض",callback_data="sg:"),InlineKeyboardButton(text="🤝 مدیریت اتحادها",callback_data="allymanage:")])
    rows.append([InlineKeyboardButton(text="🏙 شهرها و پایگاه‌ها",callback_data="cities:"),InlineKeyboardButton(text="📜 پیشنهادهای دریافتی",callback_data="contracts:")])
    rows.append([InlineKeyboardButton(text="🎁 وضعیت هدایا",callback_data="gifts:"),InlineKeyboardButton(text="🏕 اجازه پایگاه متحد",callback_data="staging:")])
    if uid == config.OWNER_ID:
        rows.append([InlineKeyboardButton(text="📣 وضعیت اعلان‌ها",callback_data="adout:")])
        rows.append([InlineKeyboardButton(text="🛠 مدیریت", callback_data="ad:stats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_trade(uid) -> InlineKeyboardMarkup:
    """💼 میز تجارت — + واردات (خرید) · − صادرات (فروش)."""
    rows = []
    for gid, nm, em, _ in economy.GOODS:
        rows.append([
            InlineKeyboardButton(text=f"{em} {nm} +۱", callback_data=f"tb:{gid}:1"),
            InlineKeyboardButton(text="+۵", callback_data=f"tb:{gid}:5"),
            InlineKeyboardButton(text="−۱", callback_data=f"ts:{gid}:1"),
            InlineKeyboardButton(text="−۵", callback_data=f"ts:{gid}:5")])
    if state.active(uid):
        rows.append([InlineKeyboardButton(text="📜 قرارداد تجاری", callback_data="tct:")])
    rows.append([InlineKeyboardButton(text="💼 میز تجارت", callback_data="mn:trade"),
                 InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _howto(uid):
    return texts.hdr('قدم بعدی','🧭')+'\n۱) شاخهٔ نظامی → درآمد و تجهیزات\n۲) شهرها → برق، پایگاه و خدمات\n۳) اعلان نوع جنگ با بازیکن واقعی\n۴) تدارکات، زیرساخت هدف و محاصرهٔ چندساعته\n۵) تثبیت شهرها؛ تسلیم کشور مرحلهٔ جداگانه است.\nهمهٔ جزئیات و زمان‌ها در راهنمای جدید آمده‌اند.'


def kb_infra(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🏙 شهرها و پایگاه‌ها',callback_data='cities:')],
        [InlineKeyboardButton(text='🏗 وضعیت ملی',callback_data='mn:infra'),InlineKeyboardButton(text='🏘 رفاه',callback_data='mn:welf')],
        [InlineKeyboardButton(text='🎛 منو',callback_data='mn:main')]])


def kb_revolt(uid) -> InlineKeyboardMarkup:
    """🔥 شورش — آغاز یا حمایت."""
    from game import politics as _po
    from game import state as _st
    p = _st.active(uid)
    rows = []
    if p:
        cid = p["country"]
        if _po._revolt(cid):
            rows.append([InlineKeyboardButton(text="✊ حمایت از شورش",
                                              callback_data="rv:x")])
        else:
            rows.append([InlineKeyboardButton(text="🔥 شورش را آغاز کن",
                                              callback_data="rv:go")])
    rows.append([InlineKeyboardButton(text="🏛 دفتر سیاسی", callback_data="mn:pol"),
                 InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_mil() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 تمرین بدون NPC", callback_data="mn:battle"),
         InlineKeyboardButton(text="🏥 استراحت", callback_data="mn:rest")],
        [InlineKeyboardButton(text="🛒 تجهیزات", callback_data="mn:arsenal"),
         InlineKeyboardButton(text="🔧 تعمیر", callback_data="mn:repair")],
        [InlineKeyboardButton(text="🏗 زیرساخت کشور", callback_data="mn:infra"),
         InlineKeyboardButton(text="🍞 جیره", callback_data="mn:ration")],
        [InlineKeyboardButton(text="🎖 عضویت نظامی", callback_data="mn:branch"),
         InlineKeyboardButton(text="🎯 مأموریت روزانه", callback_data="mn:quest")],
        [InlineKeyboardButton(text="☠ بازار سیاه", callback_data="mn:black"),
         InlineKeyboardButton(text="⬆️ ارتقای تجهیزات", callback_data="mn:upgrade")],
        [InlineKeyboardButton(text="⚔️ نبرد تن‌به‌تن", callback_data="mn:duel"),
         InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])


def kb_pol() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 انقلاب مردمی — تغییر رژیم", callback_data="rv:")],
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


def kb_welfare(uid) -> InlineKeyboardMarkup:
    """🏘 رفاه — ساخت مسجد/کلیسا/معبد/بیمارستان/مسکن."""
    from game import state as _st
    rows = []
    p = _st.active(uid)
    if p:
        nd = welfare.needs(p["country"])
        for k in nd:
            rows.append([InlineKeyboardButton(
                text=f"🏗 ساخت {welfare.NAME[k]} — {texts.fa(welfare.PRICE[k])} دلار",
                callback_data=f"wbuild:{k}")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_toll(uid) -> InlineKeyboardMarkup:
    """🛃 عوارض تنگه — پرداخت / مدیریت ایران."""
    from game import state as _st
    rows = []
    p = _st.active(uid)
    if p and toll.needs_pass(uid):
        rows.append([InlineKeyboardButton(text="💵 پرداخت عوارض امروز",
                                          callback_data="tollpay:")])
    if p and p["country"] == "ir":
        rows.append([InlineKeyboardButton(
            text=("🛃 خاموش کردن عوارض" if toll.is_on()
                  else "🛃 روشن کردن عوارض"),
            callback_data="tolltog:")])
        rows.append([InlineKeyboardButton(text="🏦 برداشت صندوق",
                                          callback_data="tollget:")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_invest(uid) -> InlineKeyboardMarkup:
    """🏭 سرمایه‌گذاری — خرید دارایی + برداشت درآمد ساعتی."""
    rows = []
    for key, name, price, inc in invest.ASSETS:
        rows.append([InlineKeyboardButton(
            text=f"{name} — {texts.fa(price)} دلار",
            callback_data=f"ivb:{key}")])
    rows.append([InlineKeyboardButton(text="💰 برداشت درآمد", callback_data="ivc:")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
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
    ids = [cid for cid in countries.COUNTRIES if cid != own and db.one("SELECT 1 FROM users WHERE country=? AND is_leader=1", (cid,))]
    per = 10
    page = max(0, min(page, max(0,(len(ids) - 1) // per)))
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

STRIKE_KINDS = [("موشکی", "🚀", (1, 3)), ("هوایی", "✈️", (1, 3, 5)),
               ("دریایی", "🚢", (1, 3)), ("زمینی", "🚜", (1, 3)), ("پهپادی", "🛩", (1,3)), ("توپخانه", "💥", (1,3)), ("چندمنظوره", "✈️", (1,3)), ("آبی‌خاکی", "⚓", (1,3))]


def kb_strikes(uid=None) -> InlineKeyboardMarkup:
    """⚔️ دکمه‌های حمله — در جنگ فقط انواع مجازِ جغرافیایی + دکمه‌ی «چرا نه»."""
    rows = []
    p = state.active(uid) if uid else None
    w = war.war_of(p["country"]) if p else None
    for kind, emo, cnts in STRIKE_KINDS:
        ok = True
        if w:
            ok, _ = war.can_strike_kind(p["country"], war._enemy(p["country"], w), kind)
        if ok:
            rows.append([InlineKeyboardButton(text=f"{emo} {kind} {n}×",
                                              callback_data=f"st:{kind}:{n}") for n in cnts])
        else:
            why = "مرز مشترک نیست" if kind == "زمینی" else "دسترسی دریایی نیست"
            gno = "land" if kind == "زمینی" else "sea"
            rows.append([InlineKeyboardButton(text=f"🚫 {kind} — {why}",
                                              callback_data=f"gno:{gno}")])
    rows.append([InlineKeyboardButton(text="🚚 تأمین مهمات",callback_data="supply:"), InlineKeyboardButton(text="🏳 تسلیم / شرایط",callback_data="sur:")])
    rows.append([InlineKeyboardButton(text="🕊 قبول صلح",callback_data="pac:")])
    rows.append([InlineKeyboardButton(text="🎯 حمله‌ی هدفمند — انتخاب بخش",
                                      callback_data="aim:")])
    rows.append([InlineKeyboardButton(text="🗺 جبهه", callback_data="mn:front"),
                 InlineKeyboardButton(text="🛡 پدافند", callback_data="mn:def")])
    rows.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_aims(uid=None):
    p=state.active(uid);w=war.war_of(p['country']) if p else None
    rows=[]
    if w:
        enemy=war._enemy(p['country'],w)
        for i,name in enumerate(geo.CITIES[enemy]):
            if name not in geo.occupied(enemy):rows.append([InlineKeyboardButton(text=f'🏙 {name}',callback_data=f'acity:{i}')])
    rows.append([InlineKeyboardButton(text='↩️ جبهه',callback_data='mn:front')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_aim_kinds(uid, target: str) -> InlineKeyboardMarkup:
    """🎯 نوع و تعداد حمله به بخش انتخابی."""
    rows = []
    p = state.active(uid) if uid else None
    w = war.war_of(p["country"]) if p else None
    for kind, emo, cnts in STRIKE_KINDS:
        ok = True
        if w:
            ok, _ = war.can_strike_kind(p["country"], war._enemy(p["country"], w), kind)
        if ok:
            rows.append([InlineKeyboardButton(text=f"{emo} {kind} {n}×",
                                              callback_data=f"st:{kind}:{n}:{target}")
                         for n in cnts])
    rows.append([InlineKeyboardButton(text="🎯 تغییر هدف", callback_data="aim:"),
                 InlineKeyboardButton(text="🗺 جبهه", callback_data="mn:front")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_duel(uid,page=0):
    n=db.one('SELECT COUNT(*) FROM users WHERE country IS NOT NULL AND branch IS NOT NULL AND uid!=?',(uid,))[0]
    page=max(0,min(page,max(0,(n-1)//10)))
    rows=db.q('SELECT uid,name,country FROM users WHERE country IS NOT NULL AND branch IS NOT NULL AND uid!=? ORDER BY last_active DESC,uid LIMIT 10 OFFSET ?',(uid,page*10))
    keys=[[InlineKeyboardButton(text=f"{countries.COUNTRIES.get(r['country'],{}).get('flag','')} {r['name']}",callback_data=f"du:{r['uid']}")] for r in rows]
    nav=[]
    if page:nav.append(InlineKeyboardButton(text='◀️ قبلی',callback_data=f'dpage:{page-1}'))
    if (page+1)*10<n:nav.append(InlineKeyboardButton(text='بعدی ▶️',callback_data=f'dpage:{page+1}'))
    if nav:keys.append(nav)
    if db.kv_get(f'duel_to:{uid}'):keys.append([InlineKeyboardButton(text='✅ پذیرش چالش دریافتی',callback_data='dac:')])
    keys.append([InlineKeyboardButton(text='🎛 منو',callback_data='mn:main')])
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


def kb_straits():
    from advanced_handlers import strait_keys
    return strait_keys(None)


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


def _pend_set(uid,chat_id,kind,ttl=300):
    db.kv_set(f'input:{uid}:{chat_id}',json.dumps({'kind':kind,'expires':db.now()+ttl}))


@db.atomic
def _pend_pop(uid,chat_id):
    key=f'input:{uid}:{chat_id}';d=db.jload(db.kv_get(key),{}) or {}
    db.kv_del(key)
    return d.get('kind') if d.get('expires',0)>=db.now() else None


# ═══════════ 🚀 شروع ═══════════


def _join_text(gid, uname: str = "") -> str:
    """⚔️ متن خوش‌آمد گروه — یک بار، پین می‌شود."""
    lines = [texts.hdr("جنگ جهانی آغاز شد", "⚔️"), "",
             "🌍 کشورت را انتخاب کن — هر که انتخاب کند 👑 رهبر همان کشور است.",
             "🔒 کشور گرفته‌شده قفل می‌شود — عجله کن!",
             f"🆔 جهان این گروه: <code>{texts.fa(gid) if gid > 0 else texts.fa(-gid)}</code>"]
    if uname:
        lines.append(f"🤖 ربات: @{uname}")
    lines += ["",
              "🛠 اشتباهی کشورت را زدی؟ آیدی عددی‌ات را (از 👤 پروفایل) برای مالک بفرست",
              "   تا کشورت را عوض کند — فقط مالک می‌تواند.",
              "", "🎮 شروع: دکمه‌های زیر یا نوشتن «شروع»"]
    return "\n".join(lines)


async def _group_hello(bt, gid: int, uname: str = ""):
    """⚔️ یک‌بار برای هر گروه: معرفی + انتخاب کشور + پین.

    زمینه‌ی دیتابیس موقتاً به دنیای همین گروه می‌رود و در پایان برمی‌گردد.
    """
    if gid >= 0:
        return
    prev = db.GAME.get()
    try:
        with contextlib.suppress(Exception):
            db.GAME.set(gid)      # چک و نوشتن در دیتابیسِ همین گروه
        if db.kv_get(f"joined:{gid}") or not bt:
            return
        db.kv_set(f"joined:{gid}", "1")
        with contextlib.suppress(Exception):
            sent = await bt.send_message(gid, _join_text(gid, uname),
                                         reply_markup=kb_countries())
            with contextlib.suppress(Exception):
                await bt.pin_chat_message(gid, sent.message_id,
                                          disable_notification=True)
    finally:
        with contextlib.suppress(Exception):
            db.GAME.set(prev)


@router.my_chat_member()
async def on_my_chat_member(ev):
    """🎉 ربات به گروه اضافه شد → خوش‌آمد + پین (یک بار)."""
    st = ""
    with contextlib.suppress(Exception):
        st = ev.new_chat_member.status
    if st in ("member", "administrator") and ev.chat.id < 0:
        uname = ""
        with contextlib.suppress(Exception):
            me = await ev.bot.get_me()
            uname = me.username
        await _group_hello(ev.bot, ev.chat.id, uname)


# ═══════════ 🚀 شروع ═══════════

# ═══ ⌨️ پل دستورهای اسلش — حتی با پرایوسی‌مودِ تلگرام، /دستورها همیشه می‌رسند ═══
_SLASH_MAP = {
    "menu": "منو", "help": "راهنما", "commands": "دستورها", "cmds": "دستورها",
    "buy": "خرید", "shop": "خرید", "arsenal": "زرادخانه",
    "attack": "حمله", "war": "جنگ", "fight": "حمله",
    "military": "نظامی", "trade": "تجارت", "profile": "پروفایل", "me": "پروفایل", "world": "جهان",
    "invest": "سرمایه", "mine": "معدن", "infra": "زیرساخت",
    "revolt": "انقلاب", "welfare": "رفاه", "toll": "عوارض",
    "fleet": "ناوگان", "energy": "انرژی", "sanctions": "تحریم",
    "operations": "عملیات", "un": "سازمان‌ملل", "straits": "تنگه‌ها",
    "cities": "شهرها", "supply": "مهمات", "contracts": "قراردادها", "gifts": "هدایا",
}


@router.message(Command(*list(_SLASH_MAP)))
async def cmd_slash_bridge(m: Message):
    """/menu → منو و ... — همان نتیجه، مسیر همیشه‌سالم."""
    if not m.text:
        return
    name = m.text.split()[0][1:].split("@")[0].lower()
    word = _SLASH_MAP.get(name)
    if not word:
        return
    _pend_pop(m.from_user.id,m.chat.id)  # explicit slash navigation is not a proposed name/payment
    m = m.model_copy(update={'text':word}) if hasattr(m,'model_copy') else m
    if not hasattr(m,'model_copy'):m.text=word
    return await fa_words(m)


@router.message(Command("start"))
@router.message(F.text.in_(["شروع", "استارت", "شروع کن", "شروع بازی", "استارت کن"]))
async def cmd_start(m: Message):
    _pend_pop(m.from_user.id,m.chat.id)
    state.ensure(m.from_user.id, m.from_user.first_name, m.chat.id)
    await _group_hello(bot, m.chat.id)
    if state.active(m.from_user.id):
        sent = await m.answer(state.card(m.from_user.id), parse_mode="HTML",
                              reply_markup=kb_main(m.from_user.id))
        _own(m, sent, m.from_user.id)
        return
    if os.path.exists("assets/img/cover.jpg"):
        with open("assets/img/cover.jpg", "rb"):
            sent = await m.answer_photo(FSInputFile("assets/img/cover.jpg"),
                                        caption=texts.WELCOME, parse_mode="HTML",
                                        reply_markup=kb_countries())
            _own(m, sent, m.from_user.id)
    else:
        sent = await m.answer(texts.WELCOME, parse_mode="HTML",
                              reply_markup=kb_countries())
        _own(m, sent, m.from_user.id)


@router.callback_query(F.data.startswith("cyp:"))
async def cb_cy_page(c: CallbackQuery):
    await c.message.edit_reply_markup(reply_markup=kb_countries(int(c.data.split(":")[1])))
    await c.answer()


@router.callback_query(F.data.startswith("cy:"))
async def cb_country(c):
    uid=c.from_user.id;cid=c.data.split(':',1)[1]
    if not state.enlist(uid,cid,c.from_user.first_name or 'بازیکن'):
        return await c.answer('کشور نامعتبر، گرفته‌شده، یا قبلاً کشور انتخاب کرده‌ای.',show_alert=True)
    await c.answer('✅ ثبت شد')
    msg='✅ کشور انتخاب شد.\n'+state.card(uid)+'\n\n'+rewards.pending_view(uid)
    sent=await c.message.answer(msg,parse_mode='HTML',reply_markup=kb_main(uid))
    _own(c,sent,uid)
    await c.answer('✅ ثبت شد')


# ═══════════ 🎛 منوها ═══════════

async def _edit(c,text,kb=None):
    from aiogram.exceptions import TelegramBadRequest
    text=notifications.personal(c.from_user.id,text)
    with contextlib.suppress(Exception):await c.answer()
    try:
        await c.message.edit_text(text,parse_mode='HTML',reply_markup=kb or kb_main(c.from_user.id))
    except TelegramBadRequest as exc:
        if 'not modified' in str(exc).lower():return
        sent=await c.message.answer(text,parse_mode='HTML',reply_markup=kb or kb_main(c.from_user.id))
        _own(c,sent,c.from_user.id)


@router.callback_query(F.data.startswith("hp:"))
async def cb_helppage(c):
    page=max(1,min(len(texts.HELP_PAGES),db.integer(c.data.split(':',1)[1],1)))
    body=texts.HELP_PAGES[page-1]+guide.mark_read(c.from_user.id,page,len(texts.HELP_PAGES))
    await _edit(c,body,kb_help(page))


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
    _pend_pop(c.from_user.id,c.message.chat.id)
    uid = c.from_user.id
    what = c.data.split(":", 1)[1]
    if not state.active(uid) and what not in ("help",):
        await c.answer("⛔ اول «شروع»", show_alert=True)
        return
    if what == "main":
        await _edit(c, state.card(uid), kb_main(uid))
    elif what == "mil":
        await _edit(c, texts.hdr("فرماندهی نظامی", "🪖") + "\n\nیکی را انتخاب کن:", kb_mil())
    elif what == "infra":
        await _edit(c, infra.view(uid) + "\n\n" + infra.buildings_view(uid),
                    kb_infra(uid))
    elif what == "welf":
        await _edit(c, welfare.view(uid), kb_welfare(uid))
    elif what == "pol":
        await _edit(c, texts.hdr("دفتر سیاسی", "🏛") + "\n\nیکی را انتخاب کن:", kb_pol())
    elif what == "world":
        await _edit(c, texts.hdr("شورای امنیت", "🌍") + "\n\nیکی را انتخاب کن:", kb_world())
    elif what == "me":
        await _edit(c, state.card(uid), kb_main(uid))
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
        c2 = countries.COUNTRIES.get(p["country"]) if (p := state.active(uid)) else None
        blines = []
        if c2:
            for i, b in enumerate(c2["branches"]):
                _k, _rn, _rf = military.role_of({"branch": i, "country": p["country"]})
                blines.append(f"🪖 <b>{b}</b>\n   🎖 {_rn} — {_rf}")
        await _edit(c, texts.hdr("انتخاب شاخه", "🪖") + "\n\nهر شاخه یک اثر واقعی دارد:\n\n"
                    + "\n\n".join(blines), kb_branches(uid))
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
            await _edit(c, war.front(uid), kb_strikes(uid))
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
    elif what == "trade":
        await _edit(c, economy.trade_view(uid), kb_trade(uid))
    elif what == "howto":
        await _edit(c, _howto(uid), kb_main(uid))
    elif what == "events":
        st = db.jload(db.kv_get(f"ev:{c.message.chat.id}"), None) or {}
        if st.get("active") and db.now() < int(st.get("deadline", 0)):
            ev_txt = next((e[0] for e in events.EVENTS
                           if e[1] == st.get("word")), "⚡ رویداد زنده است")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ شرکت در رویداد",
                                      callback_data=f"evc:{st['word']}")],
                [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])
            await _edit(c, texts.hdr("رویداد زنده", "⚡") + "\n\n" + ev_txt, kb)
        else:
            await _edit(c, "\n".join([
                texts.hdr("رویدادهای گروهی", "⚡"), "",
                "⏱ هر ۴۰ دقیقه یک رویداد در گروه می‌آید —",
                "اولین دکمه‌بزن جایزه می‌گیرد:",
                "📦 قرارداد تسلیحاتی 💰۴۰۰ · 🎖 فراخوان رزمی ⭐۱۲۰XP · 📻 رمز 💰۲۰۰",
                "", "چشم انتظار باش!"]), kb_main(uid))
    elif what == "front":
        await _edit(c, war.front(uid), kb_strikes(uid))
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
        from advanced_handlers import upgrade_view
        body,keys=upgrade_view(uid)
        await _edit(c,body,keys)
    elif what == "duel":
        await _edit(c, "\n".join([
            texts.hdr("نبرد تن‌به‌تن", "⚔️"), "",
            "حریفت را انتخاب کن:", "",
            "🏅 تجربهٔ محدود روزانه؛ بدون تولید پول رایگان",
            "🩸 فرسایش واقعی تجهیزات و جان هر دو طرف",
            "⏱ حریف ۵ دقیقه فرصت دارد قبول کند."]), kb_duel(uid))
    elif what == "peace":
        msg = war.peace_request(uid)
        await _edit(c, msg, kb_peace_accept() if "ارسال شد" in msg else kb_pol())
    elif what == "helpally":
        await _edit(c, war.call_help(uid), kb_pol())
    await c.answer()


@router.callback_query(F.data == "aim:")
async def cb_aim(c: CallbackQuery):
    """🎯 انتخاب بخش زیرساخت دشمن."""
    p = state.active(c.from_user.id)
    if not p or not war.war_of(p["country"]):
        return await c.answer("⚔️ اول در جنگ باشی!", show_alert=True)
    await _edit(c, texts.hdr("حمله‌ی هدفمند", "🎯") +
                "\n\nکدام بخشِ زیرساخت دشمن را بزنیم؟\n"
                "ابتدا شهر، سپس بخش و تجهیزات را انتخاب کن؛ یک موج حداکثر ۱۸ واحد درصد خسارت می‌زند.",
                kb_aims(c.from_user.id))


@router.callback_query(F.data.startswith("aimk:"))
async def cb_aim_kind(c: CallbackQuery):
    """🎯 نوع حمله به بخش انتخابی."""
    tgt = c.data.split(":", 1)[1]
    await _edit(c, texts.hdr("حمله‌ی هدفمند", "🎯") + "\n\nنوع و تعداد حمله:",
                kb_aim_kinds(c.from_user.id, tgt))


@router.callback_query(F.data.startswith("rv:"))
async def cb_revolt(c: CallbackQuery):
    """🔥 شورش — آغاز یا حمایت."""
    if c.data == "rv:":
        out = politics.revolt_view(c.from_user.id)
    elif c.data == "rv:s":
        out = politics.revolt_view(c.from_user.id)      # فقط دیدن وضعیت
    elif c.data == "rv:go":
        out = politics.revolt_start(c.from_user.id)
    else:
        out = politics.revolt_support(c.from_user.id)
    await _edit(c, out, kb_revolt(c.from_user.id))
    # 📡 خبر شورش موفق
    bbc = war.bbc_pop()
    if bbc and not TEST_MODE:
        with contextlib.suppress(Exception):
            await c.message.answer(texts.fx(bbc), parse_mode="HTML")
    await c.answer()


# ═══ 🎛 پنل دائمی گروه — دکمه‌ها همیشه کار می‌کنند (حتی با پرایوسی‌مود) ═══
PANEL_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎛 منوی من", callback_data="pm:menu"),
     InlineKeyboardButton(text="📖 راهنما", callback_data="pm:help")],
    [InlineKeyboardButton(text="🏘 رفاه", callback_data="pm:welf"),
     InlineKeyboardButton(text="🛃 عوارض", callback_data="pm:toll"),
     InlineKeyboardButton(text="🏭 سرمایه", callback_data="pm:inv")],
    [InlineKeyboardButton(text="⚔️ حمله و جنگ", callback_data="pm:war")]])


def panel_text() -> str:
    return "\n".join([
        texts.hdr("پنل بازی — همیشه فعال", "🎛"),
        "👈 هر دکمه‌ای را بزنی، <b>منوی خودت</b> همین‌جا پایین چت می‌آید.",
        "این پنل همیشه کار می‌کند — نیازی به دستور متنی نیست.",
        "",
        "⌨️ راه‌های دیگر: دکمه‌ی «/» گوشه‌ی چت · ریپلای به بات · @REDarkZoneBot منو"])


@router.callback_query(F.data.startswith("pm:"))
async def cb_panel(c):
    uid=c.from_user.id;what=c.data.split(':',1)[1]
    if not state.active(uid):
        sent=await c.message.answer(texts.WELCOME,parse_mode='HTML',reply_markup=kb_countries())
    else:
        view={'menu':lambda:(state.card(uid),kb_main(uid)), 'help':lambda:(texts.HELP_PAGES[0],kb_help()),
              'welf':lambda:(welfare.view(uid),kb_welfare(uid)), 'toll':lambda:(toll.status(uid),kb_toll(uid)),
              'inv':lambda:(invest.view(uid),kb_invest(uid)), 'war':lambda:_v_war(uid)}
        txt,kb=view.get(what,view['menu'])()
        sent=await c.message.answer(txt,parse_mode='HTML',reply_markup=kb)
    _own(c,sent,uid)
    await c.answer()


@router.callback_query(F.data.startswith("wbuild:"))
async def cb_welfare_build(c: CallbackQuery):
    """🏗 ساخت اماکن رفاه."""
    await _edit(c, welfare.build(c.from_user.id, c.data.split(":", 1)[1]),
                kb_welfare(c.from_user.id))
    await _send_bbc(c.message.chat.id)


@router.callback_query(F.data == "toll:")
async def cb_toll(c: CallbackQuery):
    """🛃 وضعیت عوارض تنگه."""
    await _edit(c, toll.status(c.from_user.id), kb_toll(c.from_user.id))


@router.callback_query(F.data == "tollpay:")
async def cb_toll_pay(c: CallbackQuery):
    await _edit(c, toll.pay(c.from_user.id), kb_toll(c.from_user.id))


@router.callback_query(F.data == "tolltog:")
async def cb_toll_toggle(c: CallbackQuery):
    msg, ann = toll.toggle(c.from_user.id)
    await _edit(c, msg, kb_toll(c.from_user.id))
    if ann:
        with contextlib.suppress(Exception):
            await c.message.answer(texts.fx(ann), parse_mode="HTML")


@router.callback_query(F.data == "tollget:")
async def cb_toll_get(c: CallbackQuery):
    await _edit(c, toll.collect(c.from_user.id), kb_toll(c.from_user.id))


@router.callback_query(F.data.startswith("ibld:"))
async def cb_infra_build(c: CallbackQuery):
    """🏗 ساخت ساختمان ملی."""
    await _edit(c, infra.build(c.from_user.id, c.data.split(":", 1)[1]),
                kb_infra(c.from_user.id))


@router.callback_query(F.data.startswith("ifix:"))
async def cb_infra_fix(c: CallbackQuery):
    """🔧 تعمیر زیرساخت با دلار."""
    await _edit(c, infra.repair(c.from_user.id, c.data.split(":", 1)[1]),
                kb_infra(c.from_user.id))


@router.callback_query(F.data == "inv:")
async def cb_invest(c: CallbackQuery):
    """🏭 سرمایه‌گذاری — دارایی‌های درآمد ساعتی."""
    await _edit(c, invest.view(c.from_user.id), kb_invest(c.from_user.id))


@router.callback_query(F.data.startswith("ivb:"))
async def cb_invest_buy(c: CallbackQuery):
    await _edit(c, invest.buy(c.from_user.id, c.data.split(":", 1)[1]),
                kb_invest(c.from_user.id))


@router.callback_query(F.data == "ivc:")
async def cb_invest_collect(c: CallbackQuery):
    await _edit(c, invest.collect(c.from_user.id), kb_invest(c.from_user.id))


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
    await c.answer(msg[:180], show_alert=not msg.startswith("🛒"))
    if msg.startswith("🛒"):
        with contextlib.suppress(Exception):
            await c.message.edit_text(military.arsenal(uid), parse_mode="HTML",
                                      reply_markup=kb_arsenal(uid))
        # 🖼 عکس تجهیزات — اختصاصی اگر باشد، وگرنه عکس دسته‌ای
        # 🚦 حداکثر یک عکس در ۹۰ ثانیه — ضدفلود تلگرام
        it = countries.ITEMS.get(iid)
        if it and db.now() - int(db.kv_get(f"bph:{uid}", "0")) > 90:
            db.kv_set(f"bph:{uid}", str(db.now()))
            own = f"assets/img/{it[6]}" if it[6] else ""
            img = own if (own and os.path.exists(own)) else countries.category_img(it[0])
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


async def _send_bbc(chat_id):
    # News is persisted and delivered by the outbox worker, never a global list.
    return None


async def _delayed_missile(chat_id,uid):
    # Compatibility only. The durable campaign worker owns all flight timers.
    return None


@router.callback_query(F.data.startswith("gno:"))
async def cb_geo_no(c: CallbackQuery):
    """توضیح اینکه چرا این نوع حمله جغرافیایی ممکن نیست."""
    why = ("🚫 حمله‌ی زمینی مرز زمینی مشترک می‌خواهد — کشورت و دشمن همسایه نیستند. "
           "از حمله‌ی هوایی، موشکی یا پهپادی استفاده کن." if c.data == "gno:land" else
           "🚫 حمله‌ی دریایی به آب‌های آزاد نیاز دارد — یک طرف به دریا دسترسی ندارد. "
           "از حمله‌ی هوایی، موشکی یا پهپادی استفاده کن.")
    await c.answer(why, show_alert=True)


@router.callback_query(F.data.startswith("st:"))
async def cb_strike(c):
    parts=c.data.split(':')
    if len(parts) not in (3,4):return await c.answer('⛔ دستور ناقص.',show_alert=True)
    count=texts.to_int(parts[2])
    if count is None:return await c.answer('⛔ تعداد نامعتبر.',show_alert=True)
    target=parts[3] if len(parts)==4 else None
    msg=war.strike(c.from_user.id,parts[1],count,target)
    await _edit(c,msg,kb_strikes(c.from_user.id))


# ═══════════ 💰 درآمد و تجارت — کاملاً دکمه‌ای ═══════════


@router.callback_query(F.data == "dl:")
async def cb_daily(c: CallbackQuery):
    await _edit(c, state.daily(c.from_user.id), kb_main(c.from_user.id))
    await c.answer()


@router.callback_query(F.data == "wk:")
async def cb_work(c: CallbackQuery):
    await _edit(c, state.work(c.from_user.id), kb_main(c.from_user.id))
    await c.answer()


@router.callback_query(F.data.startswith("evc:"))
async def cb_evc(c: CallbackQuery):
    """⚡ شرکت در رویداد — روی خود پیام رویداد؛ نتیجه همان‌جا."""
    word = c.data.split(":", 1)[1]
    r = events.claim(c.message.chat.id, c.from_user.id, word)
    if not r:
        return await c.answer("⏳ دیر رسیدی — رویداد تمام شد یا کسی زودتر زد.")
    base = (getattr(c.message, "text", "") or "").strip()
    txt = (base + "\n────\n" + r) if base else r
    with contextlib.suppress(Exception):
        await c.message.edit_text(txt, parse_mode="HTML")
    await c.answer("✅ ثبت شد!")


@router.callback_query(F.data.startswith("tb:"))
async def cb_tbuy(c: CallbackQuery):
    uid = c.from_user.id
    _, gid, q = c.data.split(":")
    msg = economy.trade_buy(uid, gid, int(q))
    if msg.startswith("📥"):
        msg += "\n\n" + economy.trade_view(uid)
    await _edit(c, msg, kb_trade(uid))
    await c.answer()


@router.callback_query(F.data.startswith("ts:"))
async def cb_tsell(c: CallbackQuery):
    uid = c.from_user.id
    _, gid, q = c.data.split(":")
    msg = economy.trade_sell(uid, gid, int(q))
    if msg.startswith("📤"):
        msg += "\n\n" + economy.trade_view(uid)
    await _edit(c, msg, kb_trade(uid))
    await c.answer()


@router.callback_query(F.data == "tct:")
async def cb_tcontract(c: CallbackQuery):
    uid = c.from_user.id
    p = state.active(uid)
    if not p:
        await _edit(c, "⛔ اول «شروع» — کشورت را انتخاب کن.", kb_trade(uid))
    else:
        await _edit(c, texts.hdr("قرارداد تجاری", "📜") + "\n\nبا کدام کشور؟",
                    kb_targets(uid, "ct"))
    await c.answer()


@router.callback_query(F.data.startswith("ct:"))
async def cb_contract(c: CallbackQuery):
    uid = c.from_user.id
    msg = economy.contract(uid, c.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 میز تجارت", callback_data="mn:trade")],
        [InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")]])
    await _edit(c, msg, kb)
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
    if not p:
        await c.answer("⛔ اول «شروع» — کشورت را انتخاب کن.", show_alert=True)
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
async def cb_declare_war(c):
    cid=c.data.split(':',1)[1]
    rows=[[InlineKeyboardButton(text=f'{m.label} · حداقل {m.minimum//3600} ساعت',callback_data=f'wmode:{cid}:{k}')] for k,m in rules.MODES.items()]
    rows.append([InlineKeyboardButton(text='↩️ انصراف',callback_data='mn:war')])
    await _edit(c,'⚔️ نوع جنگ و هزینه را تأیید کن: مرزی ۲۰۰ دلار، سایر حالت‌ها ۵۰۰ دلار مجازی.\nکشور خالی هدف جنگ نیست. انتخاب نوع، اعلان رسمی و آغاز زمان آماده‌سازی است.',InlineKeyboardMarkup(inline_keyboard=rows))


# ═══════════ 📈 اقتصاد: تحریم · تنگه · بازار سیاه ═══════════

@router.callback_query(F.data.startswith("snc:"))
async def cb_sanction(c):
    target=c.data.split(':')[1]
    if not target:return await _edit(c,economy.sanctions_view(c.from_user.id),kb_sanction(c.from_user.id))
    kb=InlineKeyboardMarkup(inline_keyboard=[
       [InlineKeyboardButton(text='🚫 وضع تحریم ۲۴ساعته · $۳۰۰',callback_data=f'sapply:{target}')],
       [InlineKeyboardButton(text='✅ فقط تحریم خودمان را لغو کن',callback_data=f'slift:{target}')],
       [InlineKeyboardButton(text='↩️ بازار',callback_data='mn:market')]])
    await _edit(c,economy.sanctions_view(c.from_user.id)+f"\nکشور انتخاب‌شده: {countries.COUNTRIES[target]['name']}",kb)


@router.callback_query(F.data.startswith("str:"))
async def cb_strait(c):
    from game import straits
    from advanced_handlers import strait_keys
    name=c.data.split(':',1)[1]
    key=next((k for k,v in straits.CONTROLS.items() if v[0]==name),None)
    await _edit(c,straits.view(c.from_user.id,key),strait_keys(c.from_user.id,key))


@router.callback_query(F.data.startswith("bb:"))
async def cb_buy_black(c: CallbackQuery):
    uid = c.from_user.id
    msg = military.buy_black(uid, c.data.split(":")[1])
    ok = "خریداری شد" in msg or "از قبل" in msg
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
    cur = texts.money(p["country"], politics.PARTY_COST) if p else "۱٬۲۰۰"
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
    db.kv_del(f"input:{c.from_user.id}:{c.message.chat.id}")
    await _edit(c, "✋ لغو شد.", kb_pol())
    await c.answer()


# ═══════════ ⚡ رویداد گروهی ═══════════

# ═══════════ 🗣 دستورهای متنی فارسی ═══════════

# ═══════════ ⌨️ دستورهای فارسی بدون اسلش ═══════════
def _v_trade(uid):
    return economy.trade_view(uid), kb_trade(uid)


def _v_me(uid):
    return state.card(uid), kb_main(uid)


def _v_mil(uid):
    return texts.hdr("فرماندهی نظامی", "🪖") + "\n\nیکی را انتخاب کن:", kb_mil()


def _v_world(uid):
    return texts.hdr("شورای امنیت", "🌍") + "\n\nیکی را انتخاب کن:", kb_world()


def _v_war(uid):
    p = state.active(uid)
    if p and war.war_of(p["country"]):
        return war.front(uid), kb_strikes(uid)
    return "\n".join([texts.hdr("فرماندهی جنگ", "⚔️"), "",
                      "🕊 کشورت در جنگ نیست.", "",
                      "کشور هدف را انتخاب کن — 👑 فقط رهبر:"]), kb_declare(uid)


def _v_ars(uid):
    return military.arsenal(uid), kb_arsenal(uid)


def _v_inv(uid):
    return invest.view(uid), kb_invest(uid)


def _v_infra(uid):
    from game import politics
    return (infra.view(uid) + "\n\n" + infra.buildings_view(uid)
            + "\n\n" + politics.revolt_view(uid)), kb_infra(uid)


def _v_revolt(uid):
    from game import politics
    return politics.revolt_view(uid), kb_revolt(uid)


def _v_welf(uid):
    return welfare.view(uid), kb_welfare(uid)


def _v_toll(uid):
    return toll.status(uid), kb_toll(uid)


# ⌨️ روال دستورها: هر کار یک نام اصلی + نام‌های رایج — همه به یک نتیجه
WORD_VIEWS = {
    "تجارت": _v_trade, "پروفایل": _v_me, "نظامی": _v_mil,
    "جهان": _v_world,
    "جنگ": _v_war, "حمله": _v_war, "نبرد": _v_war,
    "خرید": _v_ars, "زرادخانه": _v_ars, "تجهیزات": _v_ars,
    "سرمایه": _v_inv, "سرمایه‌گذاری": _v_inv, "معدن": _v_inv, "دارایی": _v_inv,
    "زیرساخت": _v_infra, "انقلاب": _v_revolt, "شورش": _v_revolt,
    "رفاه": _v_welf, "عوارض": _v_toll,
}


@router.callback_query(F.data == "pay:")
async def cb_transfer_pick(c: CallbackQuery):
    """💸 انتخاب گیرنده‌ی پول."""
    uid = c.from_user.id
    if not state.active(uid):
        return await c.answer("⛔ اول «شروع»", show_alert=True)
    rows = db.q("SELECT uid, name, country FROM users "
                "WHERE country IS NOT NULL AND uid != ? ORDER BY country", (uid,))
    if not rows:
        return await _edit(c, "👥 هنوز بازیکن دیگری نیست — دوستت را دعوت کن!",
                           kb_main())
    kb = [[InlineKeyboardButton(
        text=f"{countries.COUNTRIES[r['country']]['flag']} "
             f"{(r['name'] or 'سرباز')[:14]}",
        callback_data=f"pay:{r['uid']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="🎛 منوی اصلی", callback_data="mn:main")])
    await _edit(c, texts.hdr("انتقال پول", "💸") + "\n\nبه کدام بازیکن؟",
                InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("pay:"))
async def cb_transfer_to(c: CallbackQuery):
    """💸 گرفتن مبلغ — دقیق و بی‌کارمزد."""
    uid = c.from_user.id
    to = int(c.data.split(":", 1)[1])
    dst = db.one("SELECT name FROM users WHERE uid=?", (to,))
    me = db.one("SELECT country, money FROM users WHERE uid=?", (uid,))
    if not dst or not me or to == uid:
        return await c.answer("⛔ گیرنده نامعتبر", show_alert=True)
    _pend_set(uid, c.message.chat.id, f"pay:{to}")
    await _edit(c, "\n".join([
        texts.hdr("انتقال پول", "💸"), "",
        f"👤 گیرنده: {texts.mention(to, dst['name'])}",
        f"💰 موجودی تو: {texts.money(me['country'], me['money'])}", "",
        "✍️ <b>مبلغ را بنویس — فقط عدد</b> (مثلاً ۵۰۰۰۰)",
        "✋ لغو: «لغو»"]), kb_cancel_pol())


async def fa_words(m: Message):
    t = (m.text or "").strip()
    if not t:
        return
    # 💬 منشن بات — حتی با پرایوسی‌مود تلگرام می‌رسد؛ دستور را از دل متن بگیر
    if "@REDarkZoneBot" in t:
        t = t.replace("@REDarkZoneBot", "").strip()
        if not t:
            t = "منو"
        elif not t.isdigit():
            t = next((w for w in t.split() if w in TEXT_ALLOWED), "منو")
    parts = t.split(maxsplit=1)
    w = parts[0]
    if w == "/menu":
        w = "منو"
    arg = parts[1] if len(parts) > 1 else ""
    if w=="سازمان" and arg=="ملل":w="سازمان‌ملل"
    uid = m.from_user.id
    # 💬 پیوی: بازی در گروه، خرید و مدیریت در پیوی — بدون دنیا، راهنما
    if m.chat.type == "private":
        if WORLD_OF is None or not WORLD_OF(uid):
            return await m.answer(texts.PM_GUIDE, parse_mode="HTML")
    state.ensure(uid, m.from_user.first_name,
                 None if m.chat.type == "private" else m.chat.id,
                 getattr(m.from_user, "username", None))
    # ✍️ ورودی در انتظار (بیانیه / حزب) — قبل از فیلتر، بعد از ثبت حضور
    pend = _pend_pop(uid, m.chat.id)
    if w=="منو":pend=None
    if pend:
        if w == "لغو":
            return await m.answer("✋ لغو شد — هر وقت خواستی از منو دوباره شروع کن.",
                                  parse_mode="HTML")
        if pend.startswith("pay:"):
            to = texts.to_int(pend.split(":",1)[1])
            amount = texts.to_int(w)
            return await m.answer(economy.transfer(uid,to,amount),parse_mode="HTML")
        if pend.startswith("shipname:"):
            from game import fleet
            from maritime_handlers import fleet_keys
            _,idx,kind=pend.split(":")
            sent=await m.answer(fleet.build(uid,int(idx),kind,t),parse_mode="HTML",reply_markup=fleet_keys(uid))
            _own(m,sent,uid)
            return sent
        if pend.startswith("opname:"):
            from game import operations
            from advanced_handlers import operation_keys
            _,target,kind,mode=pend.split(":")
            sent=await m.answer(operations.create(uid,target,t,kind,mode),parse_mode="HTML",reply_markup=operation_keys(uid))
            _own(m,sent,uid)
            return sent
        if pend == "stmt":
            sent = await m.answer(politics.statement(uid, t), parse_mode="HTML",
                                  reply_markup=kb_pol())
            _own(m, sent, uid)
            return sent
        if pend == "alead":
            parts2 = t.split()
            if not (len(parts2) >= 2
                    and (parts2[0].isdigit() or parts2[0] in ("خالی", "-"))):
                _pend_set(uid, m.chat.id, "alead")
                sent = await m.answer("🔎 الگو: <code>آیدی‌عددی نام‌کشور</code> "
                                      "یا <code>خالی نام‌کشور</code>",
                                      parse_mode="HTML", reply_markup=kb_admin())
                _own(m, sent, uid)
                return sent
            sent = await m.answer(_admin_leader(t), parse_mode="HTML",
                                  reply_markup=kb_admin())
            _own(m, sent, uid)
            return sent
        if pend in ("areg", "achg"):
            parts2 = t.split()
            if len(parts2) >= 2 and parts2[0].isdigit():
                fn = _admin_register if pend == "areg" else _admin_change
                sent = await m.answer(fn(int(parts2[0]), " ".join(parts2[1:])),
                                      parse_mode="HTML", reply_markup=kb_admin())
                _own(m, sent, uid)
                return sent
            _pend_set(uid, m.chat.id, pend)     # ورودی نامعتبر — دوباره منتظر
            sent = await m.answer("🔎 الگو: <code>آیدی‌عددی نام‌کشور</code> — "
                                  "مثال: <code>123456 ایران</code>",
                                  parse_mode="HTML", reply_markup=kb_admin())
            _own(m, sent, uid)
            return sent
        if pend == "party":
            nm, _, ideo = t.partition("|")
            sent = await m.answer(politics.found(uid, nm.strip(), ideo.strip() or "ملی"),
                                  parse_mode="HTML", reply_markup=kb_pol())
            _own(m, sent, uid)
            return sent
    if w in ("دستورها", "دستور", "دستورات", "کمک", "/commands"):
        sent = await m.answer(texts.COMMANDS, parse_mode="HTML",
                              reply_markup=kb_help(1))
        _own(m, sent, uid)
        return sent
    if w in ("/help", "راهنما"):
        sent = await m.answer(texts.HELP_PAGES[0], parse_mode="HTML",
                              reply_markup=kb_help(1))
        _own(m, sent, uid)
        return sent
    # 🛃 جریمه‌ی روزانه‌ی عوارض — ساکت، دقیق، یک‌بار در روز
    if m.chat.type != "private":
        with contextlib.suppress(Exception):
            toll.enforce(uid)
        # 🔥 شورش خودکارِ رضایت پایین — یک‌بار در روز، با خبر
        _pp = state.active(uid)
        if _pp:
            with contextlib.suppress(Exception):
                _up = welfare.check_uprising(_pp["country"])
                if _up:
                    pass  # persisted outbox owns delivery
    # 🛃 ابزار رهبر ایران: عوارض روشن/خاموش/برداشت — با اعلام عمومی
    if w == "عوارض" and arg:
        p_t = state.active(uid)
        if not p_t or p_t["country"] != "ir":
            return await m.answer("🇮🇷 فقط رهبر ایران عوارض را مدیریت می‌کند.",
                                  parse_mode="HTML")
        if arg in ("روشن", "فعال"):
            msg, ann = toll.toggle(uid) if not toll.is_on() else ("✅ از قبل روشن است.", "")
        elif arg in ("خاموش", "بستن"):
            msg, ann = toll.toggle(uid) if toll.is_on() else ("✅ از قبل خاموش است.", "")
        elif arg == "برداشت":
            msg, ann = toll.collect(uid), ""
        else:
            msg, ann = toll.status(uid), ""
        sent = await m.answer(msg, parse_mode="HTML", reply_markup=kb_toll(uid))
        _own(m, sent, uid)
        if ann:
            with contextlib.suppress(Exception):
                await m.answer(texts.fx(ann), parse_mode="HTML")
        return sent
    # 🎛 گروه تمیز: هر متن دیگری نادیده — همه‌چیز از «منو»
    if not TEST_MODE and w not in TEXT_ALLOWED:
        return
    if w in ("شروع", "استارت", "شروع کن", "شروع بازی", "استارت کن"):
        return await cmd_start(m)
    if w == "منو":
        # ✅ همیشه منوی تازه — بدون کول‌داون و ویرایش پیام قدیمی؛
        # بازیکن هر بار «منو» بزند، پاسخ تازه پایین چت می‌آید.
        act = state.active(uid)
        last = (db.kv_get(f"menu:{uid}", "") or "").split(":")
        sent = await m.answer(state.card(uid) if act else texts.WELCOME,
                              parse_mode="HTML",
                              reply_markup=kb_main(uid) if act else kb_countries())
        # 🧹 منوی قبلی این بازیکن آزاد می‌شود — حافظه کرشدار
        if len(last) == 2:
            with contextlib.suppress(Exception):
                pass  # keep ownership of older menus until the season reset
        _own(m, sent, uid)
        if act:
            db.kv_set(f"menu:{uid}", f"{sent.message_id}:{db.now()}")
        return sent
    # ⌨️ دستورهای فارسی بدون اسلش — همان منو، فقط تایپی
    if w in WORD_VIEWS:
        if not state.active(uid):
            body=rewards.pending_view(uid) if w=="هدایا" else "⛔ ابتدا یک کشور آزاد انتخاب کن؛ این بخش پس از انتخاب کشور فعال می‌شود."
            sent=await m.answer(body,parse_mode="HTML",reply_markup=kb_countries())
            _own(m,sent,uid)
            return sent
        txt, kb = WORD_VIEWS[w](uid)
        sent = await m.answer(txt, parse_mode="HTML", reply_markup=kb)
        _own(m, sent, uid)
        return sent
    # ═══ 👑 ابزارهای متنی مالک (نگهداری) ═══
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
        sent = await m.answer(_admin_leader(arg), parse_mode="HTML",
                              reply_markup=kb_admin())
        _own(m, sent, uid)
        return sent
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


def _find_country(txt):
    def norm(s):return ' '.join((s or '').replace('ي','ی').replace('ك','ک').replace('\u200c',' ').strip().split()).lower()
    t=norm(txt)
    aliases={'امریکا':'us','آمريكا':'us','انگلستان':'gb','کره شمالی':'kp','کره جنوبی':'kr'}
    if t in aliases:return aliases[t]
    for cid,c in countries.COUNTRIES.items():
        if t in (cid,norm(c['name'])):return cid
    return None


router.message()(fa_words)


# ═══ v41 extensions: same router, same menus, city-specific management ═══
def kb_cities(uid):
    p=state.active(uid);rows=[]
    if p:
        for i,name in enumerate(geo.CITIES[p['country']]):
            rows.append([InlineKeyboardButton(text=f'🏙 {name}',callback_data=f'city:{i}')])
    rows.append([InlineKeyboardButton(text='🎛 منو',callback_data='mn:main')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_city(uid,idx):
    p=state.active(uid);rows=[]
    if p and infra.city_index(p['country'],idx) is not None:
        cid=p['country'];s=infra.city_state(cid,idx)
        if s['name'] in geo.occupied(cid):
            rows.append([InlineKeyboardButton(text='🕊 عملیات بازپس‌گیری شهر ×۱',callback_data=f'lib:{idx}')])
        else:
            for key,name,cost,_ in infra.BUILDINGS:
                if key in ('naval','shipyard') and not geo.is_port(cid,idx):continue
                row=db.one('SELECT level,hp,ready_at FROM structures WHERE cid=? AND city=? AND kind=?',(cid,idx,key))
                level=(row['level'] if row else 0)+1
                if not row or (level<=3 and row['hp']==100 and row['ready_at']<=db.now()):
                    rows.append([InlineKeyboardButton(text=f'🏗 {name} · سطح {level} · {cost*level} دلار',callback_data=f'cbld:{idx}:{key}')])
                if row and row['hp']<100:rows.append([InlineKeyboardButton(text=f'🔧 تعمیر {name}',callback_data=f'cfix:{idx}:{key}')])
            for key in ('power','airport','port','industry','garrison'):
                if (key!='port' or geo.is_port(cid,idx)) and s[key]<100:
                    rows.append([InlineKeyboardButton(text=f'🔧 {infra.TARGETS[key]} +۲۰٪',callback_data=f'cfix:{idx}:{key}')])
    rows.append([InlineKeyboardButton(text='⛽ انرژی و سوخت این شهر',callback_data=f'en:{idx}'),InlineKeyboardButton(text='🚢 نفت‌کش‌ها',callback_data='fv:')])
    rows.append([InlineKeyboardButton(text='↩️ شهرها',callback_data='cities:'),InlineKeyboardButton(text='🗺 جبهه',callback_data='mn:front')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data=='cities:')
async def cb_cities(c):
    p=state.active(c.from_user.id)
    await _edit(c,geo.country_map(p['country']) if p else '⛔ اول «شروع»',kb_cities(c.from_user.id))


@router.callback_query(F.data.startswith('city:'))
async def cb_city(c):
    idx=db.integer(c.data.split(':')[1],-1)
    await _edit(c,infra.city_view(c.from_user.id,idx),kb_city(c.from_user.id,idx))


@router.callback_query(F.data.startswith('cbld:'))
async def cb_city_build(c):
    _,idx,key=c.data.split(':');idx=int(idx)
    msg=infra.build(c.from_user.id,key,idx)
    await _edit(c,msg+'\n\n'+infra.city_view(c.from_user.id,idx),kb_city(c.from_user.id,idx))


@router.callback_query(F.data.startswith('cfix:'))
async def cb_city_fix(c):
    _,idx,key=c.data.split(':');idx=int(idx)
    msg=infra.repair(c.from_user.id,key,idx)
    await _edit(c,msg+'\n\n'+infra.city_view(c.from_user.id,idx),kb_city(c.from_user.id,idx))


@router.callback_query(F.data.startswith('acity:'))
async def cb_attack_city(c):
    p=state.active(c.from_user.id);w=war.war_of(p['country']) if p else None
    if not w:return await c.answer('⛔ جنگی نیست.',show_alert=True)
    cid=war._enemy(p['country'],w);idx=infra.city_index(cid,c.data.split(':')[1])
    if idx is None:return await c.answer('⛔ شهر نامعتبر.',show_alert=True)
    rows=[];s=infra.city_state(cid,idx)
    for key,name in infra.TARGETS.items():
        if key=='port' and not geo.is_port(cid,idx):continue
        if key in infra._B and not db.one('SELECT 1 FROM structures WHERE cid=? AND city=? AND kind=?',(cid,idx,key)):continue
        rows.append([InlineKeyboardButton(text=name,callback_data=f'aimk:{idx}.{key}')])
    rows.append([InlineKeyboardButton(text='↩️ انتخاب شهر دیگر',callback_data='aim:')])
    await _edit(c,f"🎯 هدف بعدی در شهر {s['name']}؛ کدام بخش؟\nتخریب هر بخش فقط روی همان شهر اثر مستقیم دارد.",InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith('wmode:'))
async def cb_war_mode(c):
    _,target,mode=c.data.split(':')
    msg=war.declare(c.from_user.id,target,mode)
    await _edit(c,msg,kb_strikes(c.from_user.id))


@router.callback_query(F.data=='supply:')
async def cb_resupply(c):
    await _edit(c,campaign.resupply(c.from_user.id),kb_strikes(c.from_user.id))


@router.callback_query(F.data.startswith('lib:'))
async def cb_liberate(c):
    idx=int(c.data.split(':')[1])
    await _edit(c,campaign.liberate(c.from_user.id,idx),kb_city(c.from_user.id,idx))


@router.callback_query(F.data=='staging:')
async def cb_staging(c):
    await _edit(c,'🏕 فقط به متحد رسمی اجازهٔ ۷۲ ساعتهٔ استفادهٔ تدارکاتی از پایگاه می‌دهی. زدن دوبارهٔ همان متحد، اجازه را لغو می‌کند.',kb_targets(c.from_user.id,'stage'))


@router.callback_query(F.data.startswith('stage:'))
async def cb_staging_grant(c):
    await _edit(c,campaign.allow_staging(c.from_user.id,c.data.split(':')[1]),kb_pol())


def contracts_view(uid):
    p=state.active(uid);rows=[];lines=[texts.hdr('پیشنهادهای دریافتی','📜')]
    if p:
        cid=p['country']
        for r in db.q('SELECT k,v FROM kv WHERE k LIKE ?',(f'contract:%:{cid}',)):
            offer=db.jload(r['v'],{}) or {}
            if offer.get('expires',0)>db.now() and offer.get('buyer')==uid:
                source=r['k'].split(':')[1]
                if source not in countries.COUNTRIES:continue
                lines.append(f"از {countries.COUNTRIES[source]['name']}: {offer['qty']} کالا، {offer['price']} دلار")
                rows.append([InlineKeyboardButton(text=f"✅ خرید از {countries.COUNTRIES[source]['name']}",callback_data=f'ctac:{source}')])
        for r in db.q('SELECT k,v FROM kv WHERE k LIKE ?',(f'alliance_req:%:{cid}',)):
            source=r['k'].split(':')[1]
            if source in countries.COUNTRIES and db.now()-db.integer(r['v'])<=86400:
                rows.append([InlineKeyboardButton(text=f"🤝 قبول اتحاد {countries.COUNTRIES[source]['name']}",callback_data=f'aac:{source}')])
        w=war.war_of(cid)
        if w and db.kv_get(f"peace:{w['id']}")==war._enemy(cid,w):
            rows.append([InlineKeyboardButton(text='🕊 قبول صلح',callback_data='pac:')])
    if not rows:lines.append('پیشنهاد معتبری نیست.')
    rows.append([InlineKeyboardButton(text='🎛 منو',callback_data='mn:main')])
    return '\n'.join(lines),InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data=='contracts:')
async def cb_contracts(c):
    body,kb=contracts_view(c.from_user.id)
    await _edit(c,body,kb)


@router.callback_query(F.data.startswith('ctac:'))
async def cb_contract_accept(c):
    await _edit(c,economy.contract_accept(c.from_user.id,c.data.split(':')[1]),kb_trade(c.from_user.id))


@router.callback_query(F.data=='gifts:')
async def cb_gifts(c):
    from reward_handlers import gift_view,gift_keys
    await _edit(c,gift_view(c.from_user.id),gift_keys(c.from_user.id))


@router.callback_query(F.data=='adout:')
async def cb_outbox(c):
    if c.from_user.id!=config.OWNER_ID:return await c.answer('👑 فقط مالک.',show_alert=True)
    await _edit(c,notifications.status(),kb_admin())


WORD_VIEWS.update({
    'شهرها':lambda uid:(geo.country_map(state.active(uid)['country']),kb_cities(uid)),
    'پایگاه':lambda uid:(geo.country_map(state.active(uid)['country']),kb_cities(uid)),
    'مهمات':lambda uid:(war.front(uid),kb_strikes(uid)),
    'قراردادها':contracts_view,
    'هدایا':lambda uid:(rewards.pending_view(uid),kb_main(uid)),
})


# Register extensions on this same router after the retained handlers are defined.
__import__('advanced_handlers')

__import__("maritime_handlers")
WORD_VIEWS["تحریم"]=lambda uid:(economy.sanctions_view(uid),kb_sanction(uid))

__import__("reward_handlers")
