"""🚀 جنگ جهانی — اجرا: polling + اقتصاد زنده + رویداد گروهی + ذخیره‌سازی."""
import asyncio
import contextlib
import os
import time
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import db
import handlers
from game import ai, economy, events, war

NEWS_TMPL = [
    ("📡 خبرگزاری جهانی: شاخص دلار به ×{dollar:.2f} رسید — تحلیلگران نگران‌اند.", "dollar"),
    ("🛢 قیمت نفت ${oil:.0f} شد — بازارهای جهانی واکنش نشان دادند.", "oil"),
    ("📊 تورم جهانی {inf:.1f}٪ — بانک‌های مرکزی هشدار دادند.", "inflation"),
]


def _news(w) -> str | None:
    import random
    if random.random() > 0.04:          # هر تیک ۶۰ ثانیه → ~۴۰ دقیقه یک خبر
        return None
    tpl, key = random.choice(NEWS_TMPL)
    import texts
    return texts.fa(tpl.format(dollar=w["dollar"], oil=w["oil"],
                               inf=w["inflation"] * 100))

_last = {}


def _too_fast(uid: int, gap: float = 0.5) -> bool:
    """ضداسپم فقط فردی — پیام ۰٫۵ ثانیه، دکمه فقط ۰٫۲۵ (ضد دوضرب)."""
    t = time.time()
    if t - _last.get(uid, 0) < gap:
        return True
    _last[uid] = t
    return False


async def world_loop(bot: Bot):
    """🌍 جهان زنده‌ی هر گروه: بازار، نفت، جنگ‌ها، دولت هوشمند — دنیاهای جدا."""
    await asyncio.sleep(20)
    print("🌍 world_loop alive", flush=True)
    while True:
        try:
            for g in db.list_games():
                db.GAME.set(g)
                if not events.game_alive(g):
                    continue                     # گروه خفته — جهانش هم می‌خوابد
                # 🛃 اعلام روزانه‌ی عوارض تنگه — با تگ همه، فقط یک بار در روز
                from game import toll as _toll
                with contextlib.suppress(Exception):
                    if _toll.daily_announce_needed():
                        import texts as _tx
                        await bot.send_message(g, _tx.fx(_toll.announce_text()),
                                               parse_mode="HTML")
                w = economy.tick()
                economy.world()
                news = _news(w)
                if news:
                    with contextlib.suppress(Exception):
                        await bot.send_message(g, news, parse_mode="HTML")
                for msg in war.settle():
                    with contextlib.suppress(Exception):
                        await bot.send_message(g, msg, parse_mode="HTML")
                # 🧠 مغز جهان — کشورها مستقل عمل می‌کنند
                for line in ai.tick():
                    with contextlib.suppress(Exception):
                        await bot.send_message(g, line, parse_mode="HTML")
                # خبرگزاری تورم
                if w["inflation"] > 1.0 and db.now() % 3600 < 70:
                    with contextlib.suppress(Exception):
                        import texts as _t
                        await bot.send_message(
                            g,
                            _t.fa(f"📊 خبرگزاری: تورم جهانی به {w['inflation'] * 100:.0f}٪ رسید — "
                                  f"دلار ×{w['dollar']:.2f} · نفت ${w['oil']:.0f}"),
                            parse_mode="HTML")
            await asyncio.sleep(60)
        except Exception:
            with contextlib.suppress(Exception):
                db.log("error", "world_loop: " + traceback.format_exc()[-300:])
            await asyncio.sleep(60)


async def events_loop(bot: Bot):
    """⚡ رویداد آرام گروه + خبرنامه‌ی خودکار هر ۱۰ دقیقه."""

    def _tag_all(text: str) -> str:
        """📣 خطاب به همه — تگ بازیکنان فعال دنیای جاری."""
        with contextlib.suppress(Exception):
            rows = db.q("SELECT uid, name FROM users "
                        "WHERE country IS NOT NULL AND last_active > ? "
                        "ORDER BY last_active DESC LIMIT 15",
                        (db.now() - 3 * 86400,))
            if rows:
                import texts as _tx
                tags = " ".join(_tx.mention(r["uid"], (r["name"] or "سرباز")[:16])
                                for r in rows)
                return f"📣 {tags}\n\n{text}"
        return text

    await asyncio.sleep(35)
    print("⚡ events_loop alive", flush=True)
    while True:
        try:
            now = db.now()
            for g in db.list_games():
                if not events.game_alive(g):
                    continue
                db.GAME.set(g)
                # 📰 خبرنامه‌ی هر ۱۰ دقیقه — قابل تنظیم: «تنظیم اخبار»
                if (not db.kv_get("bl_off")
                        and now - int(db.kv_get("bl_last", "0")) >= 1800):
                    db.kv_set("bl_last", str(now))
                    bl = _tag_all(events.bulletin())
                    with contextlib.suppress(Exception):
                        await bot.send_message(g, bl, parse_mode="HTML")
                if not db.kv_get("ev_off"):
                    ev = events.maybe_event(g)
                    if ev:
                        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                        text, word = ev
                        text = _tag_all(text)
                        kb = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⚡ شرکت در رویداد",
                                                 callback_data=f"evc:{word}")]])
                        with contextlib.suppress(Exception):
                            await bot.send_message(g, text, parse_mode="HTML",
                                                   reply_markup=kb)
            await asyncio.sleep(45)
        except Exception:
            with contextlib.suppress(Exception):
                db.log("error", "events_loop: " + traceback.format_exc()[-300:])
            await asyncio.sleep(45)


async def autosave_loop():
    """💾 ذخیره‌ی همه‌ی دنیاها — هر ۵ دقیقه از طریق API گیت‌هاب."""
    if not os.environ.get("INLOOP_AUTOSAVE"):
        return
    import hashlib
    import save_db
    iv = int(os.environ.get("AUTOSAVE_MIN", "5")) * 60
    pat = os.environ.get("PAT", "")
    last = {}
    while True:
        await asyncio.sleep(iv)
        for g in db.list_games():
            try:
                data = save_db.checkpoint(db.game_path(g))
                h = hashlib.sha256(data).hexdigest()
                if last.get(g) == h:
                    continue                  # تغییری نکرده
                if save_db.put(pat, data, db.game_path(g)):
                    last[g] = h
                    print(f"💾 autosave ok {g}", flush=True)
                else:
                    print(f"autosave put failed {g}", flush=True)
            except Exception:
                print("autosave failed:", traceback.format_exc()[-300:], flush=True)


async def main():
    db.init()
    # 🧹 ثبت‌های آزمایشی قدیمی (Player بدون فعالیت) پاک می‌شوند — کشورها به NPC برمی‌گردند
    db.ex("DELETE FROM users WHERE name LIKE 'Player%' AND chat_id IS NULL "
          "AND branch IS NULL")
    # 👑 هر بازیکنِ واقعیِ گروه، رهبر کشور خودش است
    db.ex("UPDATE users SET is_leader=1 WHERE country IS NOT NULL "
          "AND chat_id IS NOT NULL")
    import countries
    countries.init_items()
    # 🎁 پاداش تاج‌گذاری رهبر امریکا (گروه -1003614742240) — فقط یک بار
    # 🎁 مهاجرت‌های یک‌باره‌ی دنیاها: هدیه‌ها + پول شروع مناسب
    import migrations
    migrations.run_all()
    # 🛒 زرادخانه‌ی هر دنیا هم تجهیزات نخبه را بگیرد
    for g in db.list_games():
        db.GAME.set(g)
        countries.init_items()
    db.GAME.set(None)
    handlers.bot = bot = Bot(config.TOKEN,
                             default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # ⌨️ منوی دستورهای اسلش — دکمه‌ی / تلگرام؛ با پرایوسی‌مود هم می‌رسند
    with contextlib.suppress(Exception):
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="menu", description="🎛 منوی اصلی بازی"),
            BotCommand(command="start", description="🚪 شروع / انتخاب کشور"),
            BotCommand(command="attack", description="⚔️ حمله و جنگ"),
            BotCommand(command="buy", description="🛒 زرادخانه و خرید"),
            BotCommand(command="invest", description="🏭 سرمایه‌گذاری"),
            BotCommand(command="infra", description="🏗 زیرساخت و ساخت‌وساز"),
            BotCommand(command="revolt", description="🔥 انقلاب مردمی"),
            BotCommand(command="trade", description="💰 تجارت"),
            BotCommand(command="profile", description="👤 پروفایل"),
            BotCommand(command="help", description="📖 راهنمای کامل"),
            BotCommand(command="commands", description="⌨️ فهرست دستورها"),
        ])

    # 🚦 ضدفلود تلگرام: صف ارسال هر گروه + تلاش دوباره‌ی خودکار بعد از 429
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware
    from aiogram.exceptions import TelegramRetryAfter

    class AntiFlood(BaseRequestMiddleware):
        """حداکثر ~۱۸ ارسال در دقیقه به هر گروه؛ 429 خودکار دوباره تلاش می‌کند."""

        def __init__(self):
            self._last, self._locks = {}, {}

        async def __call__(self, make_request, bot, method):
            name = type(method).__name__
            chat_id = getattr(method, "chat_id", None)
            sends = name in ("SendMessage", "SendPhoto", "SendVideo",
                             "SendDocument", "SendAnimation")
            if sends and chat_id:
                lock = self._locks.setdefault(chat_id, asyncio.Lock())
                async with lock:
                    gap = 3.4 - (time.time() - self._last.get(chat_id, 0))
                    if gap > 0:
                        await asyncio.sleep(gap)
                    self._last[chat_id] = time.time()
            for _ in range(3):
                try:
                    return await make_request(bot, method)
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
            return await make_request(bot, method)

    bot.session.middleware(AntiFlood())
    dp = Dispatcher()
    dp.include_router(handlers.router)

    from aiogram import BaseMiddleware
    from aiogram.types import Message

    _PM_WORLD: dict = {}

    def _world_of(uid: int):
        """💬 دنیای بازیکن برای پیوی — جایی که کشور دارد."""
        hit = _PM_WORLD.get(uid)
        if hit:
            return hit
        for g in db.list_games():
            db.GAME.set(g)
            if db.one("SELECT 1 FROM users WHERE uid=? AND country IS NOT NULL",
                      (uid,)):
                _PM_WORLD[uid] = g
                return g
        return None

    handlers.WORLD_OF = _world_of

    # 🎞 پک استیکر دارک‌زون — در بوت آماده می‌شود
    with contextlib.suppress(Exception):
        ss = await bot.get_sticker_set("darkzone_arsenal_by_REDarkZoneBot")
        handlers.STICKERS = {s.emoji: s.file_id for s in ss.stickers}
        print(f"🎞 sticker pack: {len(handlers.STICKERS)} sticker", flush=True)

    class Guard(BaseMiddleware):
        async def __call__(self, handler, event, data):
            # 🌍 دنیای این پیام = همین گروه — همه‌چیز جدا
            chat = getattr(event, "chat", None)
            if chat is None:
                chat = getattr(getattr(event, "message", None), "chat", None)
            cid = getattr(chat, "id", 0) if chat is not None else 0
            who = getattr(event, "from_user", None)
            if cid < 0:
                # 🌍 دنیای این پیام = همین گروه — همه‌چیز جدا
                db.GAME.set(cid)
            elif who is not None:
                # 💬 پیوی: بازی در گروه، خرید و مدیریت در پیوی
                db.GAME.set(_world_of(who.id))
            if who and who.id != config.OWNER_ID and _too_fast(
                    who.id, 0.5 if isinstance(event, Message) else 0.25):
                # 🤫 گروه تمیز — سریع‌زدن‌ها بی‌سروصدا رد می‌شوند
                if not isinstance(event, Message):
                    with contextlib.suppress(Exception):
                        await event.answer()
                return
            return await handler(event, data)

    dp.message.middleware(Guard())
    dp.callback_query.middleware(Guard())

    from aiogram.types import ErrorEvent

    @dp.error()
    async def on_error(ev: ErrorEvent):
        try:
            etxt = str(ev.exception)
            # 🤫 خطای بی‌اهمیت: توست دکمه دیر شد ولی خود عمل انجام شده
            if ("query is too old" in etxt
                    or "query ID is invalid" in etxt):
                return
            tb = traceback.format_exc()
            db.log("error", tb[-500:])
            with contextlib.suppress(Exception):
                await bot.send_message(config.OWNER_ID,
                                       "🐞 خطا:\n<pre>" +
                                       tb[-300:].replace("&", "&amp;").replace("<", "&lt;") +
                                       "</pre>")
            msg = ev.update.message or (ev.update.callback_query and
                                        ev.update.callback_query.message)
            if msg:
                await msg.answer("⚠️ خطای موقت — دوباره امتحان کن.")
        except Exception:
            pass

    print("boot: pre get_me", flush=True)
    me = await bot.get_me()
    print("boot: get_me ok", flush=True)
    await bot.delete_webhook(drop_pending_updates=False)
    print("boot: webhook ok", flush=True)
    db.log("info", f"boot WW @{me.username}")
    print(f"⚔️ جنگ جهانی online as @{me.username}", flush=True)
    print("boot: starting polling", flush=True)

    t1 = asyncio.create_task(world_loop(bot))
    t2 = asyncio.create_task(events_loop(bot))
    t3 = asyncio.create_task(autosave_loop())
    try:
        await dp.start_polling(bot)
    finally:
        t1.cancel()
        t2.cancel()
        t3.cancel()


if __name__ == "__main__":
    asyncio.run(main())
