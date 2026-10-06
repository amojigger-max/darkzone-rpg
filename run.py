"""DarkZone v41 polling runtime. Boot does not reset, crown or give anyone assets."""
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import config
import db
import handlers
import migrations
from messaging import SafeMessages
from middleware import Guard, world_of, _scrub
from game import campaign, economy, events, notifications, operations, un, fleet, energy

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
LOG=logging.getLogger('darkzone')


class Redact(logging.Filter):
    def filter(self,record):
        record.msg=_scrub(record.getMessage());record.args=()
        return True

class SecretFormatter(logging.Formatter):
    def format(self,record):return _scrub(super().format(record))

for h in logging.getLogger().handlers:
    h.addFilter(Redact())
    h.setFormatter(SecretFormatter('%(asctime)s %(levelname)s %(message)s'))


def build_dispatcher():
    dp=Dispatcher()
    guard=Guard()
    dp.message.outer_middleware(guard)
    dp.callback_query.outer_middleware(guard)
    dp.include_router(handlers.router)
    return dp


async def campaign_loop():
    while True:
        for gid in db.list_games():
            with db.world(gid):
                try:
                    fleet.tick()
                    for c in db.q("SELECT DISTINCT cid FROM city_energy"):energy.settle(c['cid'])
                    campaign.tick();operations.tick();un.tick()
                except Exception as exc:
                    db.log('error',f'campaign loop: {type(exc).__name__}')
                    LOG.error('campaign failed for world %s: %s',gid,type(exc).__name__)
            await asyncio.sleep(0)
        await asyncio.sleep(5)


async def outbox_loop(bot):
    while True:
        for gid in db.list_games():
            with db.world(gid):
                try:await notifications.drain(bot,limit=2)
                except Exception as exc:
                    db.log('error',f'outbox loop: {type(exc).__name__}')
        await asyncio.sleep(1)


async def world_loop(bot=None):
    while True:
        for gid in db.list_games():
            if not events.game_alive(gid):continue
            with db.world(gid):
                try:economy.tick()
                except Exception as exc:db.log('error',f'economy loop: {type(exc).__name__}')
        await asyncio.sleep(60)


async def events_loop(bot=None):
    while True:
        for gid in db.list_games():
            if not events.game_alive(gid):continue
            with db.world(gid):
                try:
                    # No 15-player cap. Every actual recipient is kept and paginated.
                    if not db.kv_get('bl_off') and db.now()-db.integer(db.kv_get('bl_last'))>=1800:
                        with db.transaction():
                            bucket=db.now()//1800
                            notifications.emit(events.bulletin(),all_players=True,key=f'bulletin:{bucket}')
                            db.kv_set('bl_last',db.now())
                    if not db.kv_get('ev_off'):
                        ev=events.maybe_event(gid)
                        if ev:
                            text,word=ev
                            # Text users can answer through the event panel; no lost ephemeral timer.
                            notifications.emit(text+'\nشرکت: /menu → رویدادها',all_players=True,key=f'event:{gid}:{db.kv_get(f"ev_last:{gid}")}')
                except Exception as exc:db.log('error',f'event loop: {type(exc).__name__}')
        await asyncio.sleep(30)


async def autosave_loop():
    if os.environ.get('INLOOP_AUTOSAVE')!='1' or not config.PAT:return
    import save_db
    interval=max(60,db.integer(os.environ.get('AUTOSAVE_MIN'),2,1,30)*60)
    hashes={}
    while True:
        await asyncio.sleep(interval)
        for gid in db.list_games():
            path=db.game_path(gid);remote=f'games/{gid}.db'
            try:
                data=await asyncio.to_thread(save_db.checkpoint,path)
                digest=hashlib.sha256(data).hexdigest()
                if hashes.get(gid)==digest:continue
                await asyncio.to_thread(save_db.put,config.PAT,data,remote)
                hashes[gid]=digest
                LOG.info('autosave ok for world %s',gid)
            except Exception as exc:
                LOG.error('autosave NOT completed for world %s: %s',gid,type(exc).__name__)
                with db.world(gid):db.log('error','autosave: '+type(exc).__name__)


async def health_loop():
    while True:
        data={'version':config.VERSION,'heartbeat':db.now(),'worlds':len(db.list_games())}
        Path('health.json').write_text(json.dumps(data))
        await asyncio.sleep(30)


async def main():
    if not config.TOKEN:raise RuntimeError('BOT_TOKEN is missing; nothing was launched')
    from runtime_lock import exclusive
    with exclusive():
        bot=None
        try:
            if os.environ.get('INLOOP_AUTOSAVE')=='1':
                import save_db
                sources={f'games/{g}.db':db.game_path(g) for g in db.list_games()}
                await asyncio.to_thread(save_db.preflight,config.PAT,sources)
            db.init();migrations.run_all()
            bot=Bot(config.TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            bot.session.middleware(SafeMessages())
            handlers.bot=bot;handlers.WORLD_OF=world_of
            me=await bot.get_me()
            hook=await bot.get_webhook_info()
            if hook.url:
                if os.environ.get('DZ_REPLACE_WEBHOOK')!='1':
                    raise RuntimeError('existing webhook found; explicitly stop it before starting polling')
                await bot.delete_webhook(drop_pending_updates=False)
            if config.STICKER_SET:
                try:
                    sticker_set=await bot.get_sticker_set(config.STICKER_SET)
                    handlers.STICKERS={s.emoji:s.file_id for s in sticker_set.stickers if s.emoji}
                except Exception as exc:LOG.info('optional original sticker pack unavailable: %s',type(exc).__name__)
            await bot.set_my_commands([BotCommand(command=k,description=v) for k,v in [
                ('menu','🎛 منوی اصلی'),('start','🚪 شروع و انتخاب کشور'),('help','📖 راهنما و قوانین'),
                ('attack','⚔️ فرماندهی جنگ'),('cities','🏙 شهرها و پایگاه‌ها'),('supply','🚚 تدارکات جنگ'),
                ('buy','🛒 زرادخانه'),('invest','🏭 سرمایه‌گذاری'),('infra','🏗 زیرساخت'),
                ('trade','💰 تجارت'),('un','🇺🇳 سازمان ملل'),('operations','🧭 ستاد عملیات'),('straits','🌉 گذرگاه‌ها و عوارض'),('fleet','🚢 ناوگان نفت‌کش'),('energy','⛽ انرژی و نیروگاه'),('sanctions','🚫 مدیریت تحریم'),('contracts','📜 پیشنهادهای دریافتی'),('gifts','🎁 وضعیت هدایا'),
                ('profile','👤 پروفایل'),('worlds','🌍 انتخاب جهان در پیوی'),('commands','⌨️ دستورها')]])
            dp=build_dispatcher()
            workers=[asyncio.create_task(fn(),name=label) for label,fn in [
                ('campaigns',campaign_loop),('outbox',lambda:outbox_loop(bot)),('economy',world_loop),
                ('events',events_loop),('autosave',autosave_loop),('health',health_loop)]]
            LOG.info('v%s starting polling as @%s',config.VERSION,me.username)
            try:
                await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types(),close_bot_session=False)
            finally:
                for worker in workers:worker.cancel()
                await asyncio.gather(*workers,return_exceptions=True)
                if config.PAT and os.environ.get('INLOOP_AUTOSAVE')=='1':
                    import save_db
                    try:await asyncio.to_thread(save_db.save_all,config.PAT)
                    except Exception as exc:LOG.error('final save failed: %s',type(exc).__name__)
        finally:
            if bot is not None:await bot.session.close()
            db.close_all()


if __name__=='__main__':asyncio.run(main())
