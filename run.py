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
    if t - _last.get(uid, 0) < 2:
        return True
    _last[uid] = t
    return False


async def world_loop(bot: Bot):
    """🌍 جهان زنده: بازار، نفت، جنگ‌ها، دولت هوشمند."""
    await asyncio.sleep(20)
    print("🌍 world_loop alive", flush=True)
    while True:
        try:
            w = economy.tick()
            economy.oil_income()
            economy.world()
            news = _news(w)
            if news:
                for cid in events.active_chats():
                    with contextlib.suppress(Exception):
                        await bot.send_message(cid, news, parse_mode="HTML")
            for msg in war.settle():
                gid = db.kv_get("main_group")
                if gid:
                    with contextlib.suppress(Exception):
                        await bot.send_message(int(gid), msg, parse_mode="HTML")
            # 🧠 مغز جهان — کشورها مستقل عمل می‌کنند و جهان پاسخ می‌دهد
            for line in ai.tick():
                gid = db.kv_get("main_group")
                targets = {int(gid)} if gid else set()
                targets.update(events.active_chats())
                for cid in targets:
                    with contextlib.suppress(Exception):
                        await bot.send_message(cid, line, parse_mode="HTML")
            # دولت هوشمند: خبرگزاری جهان
            if w["inflation"] > 1.0 and db.now() % 600 < 70:
                gid = db.kv_get("main_group")
                if gid:
                    with contextlib.suppress(Exception):
                        import texts as _t
                        await bot.send_message(
                            int(gid),
                            _t.fa(f"📊 خبرگزاری: تورم جهانی به {w['inflation'] * 100:.0f}٪ رسید — "
                                  f"دلار ×{w['dollar']:.2f} · نفت ${w['oil']:.0f}"),
                            parse_mode="HTML")
            await asyncio.sleep(60)
        except Exception:
            db.log("error", "world_loop: " + traceback.format_exc()[-300:])
            await asyncio.sleep(60)


async def events_loop(bot: Bot):
    """⚡ رویداد آرام گروه + خبرنامه‌ی خودکار هر ۱۰ دقیقه."""
    await asyncio.sleep(35)
    print("⚡ events_loop alive", flush=True)
    while True:
        try:
            now = db.now()
            # 📰 خبرنامه‌ی هر ۱۰ دقیقه — قابل تنظیم توسط مالک: «تنظیم اخبار»
            if (not db.kv_get("bl_off")
                    and now - int(db.kv_get("bl_last", "0")) >= 600):
                db.kv_set("bl_last", str(now))
                bl = events.bulletin()
                targets = set(events.active_chats())
                gid = db.kv_get("main_group")
                if gid:
                    targets.add(int(gid))
                for cid in targets:
                    with contextlib.suppress(Exception):
                        await bot.send_message(cid, bl, parse_mode="HTML")
            if not db.kv_get("ev_off"):
                for cid in events.active_chats():
                    ev = events.maybe_event(cid)
                    if ev:
                        with contextlib.suppress(Exception):
                            await bot.send_message(cid, ev, parse_mode="HTML")
            await asyncio.sleep(45)
        except Exception:
            db.log("error", "events_loop: " + traceback.format_exc()[-300:])
            await asyncio.sleep(45)


async def autosave_loop():
    """💾 ذخیره‌ی دوره‌ی دیتابیس — هر ۵ دقیقه از طریق API گیت‌هاب."""
    if not os.environ.get("INLOOP_AUTOSAVE"):
        return
    import hashlib
    import save_db
    iv = int(os.environ.get("AUTOSAVE_MIN", "5")) * 60
    pat = os.environ.get("PAT", "")
    last = {"h": None}
    while True:
        await asyncio.sleep(iv)
        try:
            data = save_db.checkpoint()
            h = hashlib.sha256(data).hexdigest()
            if h == last["h"]:
                continue                      # تغییری نکرده
            if save_db.put(pat, data):
                last["h"] = h
                db.log("info", "autosave ok")
                print("💾 autosave ok", flush=True)
            else:
                db.log("error", "autosave put failed")
                print("autosave put failed", flush=True)
        except Exception:
            db.log("error", "autosave failed: " + traceback.format_exc()[-200:])
            print("autosave failed:", traceback.format_exc()[-300:], flush=True)


async def main():
    db.init()
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
            who = getattr(event, "from_user", None)
            if who and who.id != config.OWNER_ID and _too_fast(who.id):
                if isinstance(event, Message):
                    await event.answer("⏳ آهسته‌تر — ۲ ثانیه.")
                else:
                    await event.answer("⏳ آهسته‌تر!")
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
            command="start", description="⚔️ شروع جنگ جهانی — ۲۱ کشور، مستعمره، پول زنده")])
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
