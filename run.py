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
    if random.random() > 0.08:          # هر تیک ۶۰ ثانیه → ~۲۰ دقیقه یک خبر
        return None
    tpl, key = random.choice(NEWS_TMPL)
    import texts
    return texts.fa(tpl.format(dollar=w["dollar"], oil=w["oil"],
                               inf=w["inflation"] * 100))

_last = {}


def _too_fast(uid: int) -> bool:
    """ضداسپم فقط فردی — ۲ ثانیه."""
    t = time.time()
    if t - _last.get(uid, 0) < 1:
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
                w = economy.tick()
                economy.oil_income()
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
                if w["inflation"] > 1.0 and db.now() % 600 < 70:
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
                        and now - int(db.kv_get("bl_last", "0")) >= 600):
                    db.kv_set("bl_last", str(now))
                    bl = events.bulletin()
                    with contextlib.suppress(Exception):
                        await bot.send_message(g, bl, parse_mode="HTML")
                if not db.kv_get("ev_off"):
                    ev = events.maybe_event(g)
                    if ev:
                        with contextlib.suppress(Exception):
                            await bot.send_message(g, ev, parse_mode="HTML")
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
    handlers.bot = bot = Bot(config.TOKEN,
                             default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(handlers.router)

    from aiogram import BaseMiddleware
    from aiogram.types import Message

    class Guard(BaseMiddleware):
        async def __call__(self, handler, event, data):
            # 🌍 دنیای این پیام = همین گروه — همه‌چیز جدا
            chat = getattr(event, "chat", None)
            if chat is None:
                chat = getattr(getattr(event, "message", None), "chat", None)
            if chat is not None and getattr(chat, "id", 0) < 0:
                db.GAME.set(chat.id)
            who = getattr(event, "from_user", None)
            if who and who.id != config.OWNER_ID and _too_fast(who.id):
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

    me = await bot.get_me()
    await bot.delete_webhook(drop_pending_updates=False)
    # 🧹 منوی دستورها همیشه تازه — فقط جنگ جهانی، هیچ دستور قدیمی
    with contextlib.suppress(Exception):
        from aiogram.types import BotCommand
        await bot.set_my_commands([BotCommand(
            command="start", description="⚔️ شروع جنگ جهانی — ۵۰ کشور، مستعمره، پول زنده")])
    db.log("info", f"boot WW @{me.username}")
    print(f"⚔️ جنگ جهانی online as @{me.username}", flush=True)

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
