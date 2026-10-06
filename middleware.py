"""World isolation, unambiguous private-world selection, callback validation and safety."""
import contextlib
import re
import time
import uuid

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import callbacks
import db
from game import state

_LAST={}


def worlds_for(uid):
    result=[]
    for gid in db.list_games():
        with db.world(gid):
            if state.get(uid):result.append(gid)
    return result


def world_of(uid):
    known=worlds_for(uid)
    with db.world(None):preferred=db.integer(db.kv_get(f'pm_world:{uid}'))
    if preferred in known:return preferred
    return known[0] if len(known)==1 else None


def choose_world(uid,gid):
    if gid not in worlds_for(uid):return False
    with db.world(None):db.kv_set(f'pm_world:{uid}',gid)
    return True


def _clone(event,**values):
    return event.model_copy(update=values) if hasattr(event,'model_copy') else event


def _scrub(text):
    text=re.sub(r'\b\d{7,12}:[A-Za-z0-9_-]{20,}','[BOT_TOKEN]',str(text))
    return re.sub(r'(?:gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)','[GITHUB_TOKEN]',text)


class Guard(BaseMiddleware):
    async def __call__(self,handler,event,data):
        who=getattr(event,'from_user',None)
        if who is None or getattr(who,'is_bot',False):return None
        message=event.message if isinstance(event,CallbackQuery) else event
        chat=getattr(message,'chat',None)
        if chat is None:
            if isinstance(event,CallbackQuery):
                with contextlib.suppress(Exception):await event.answer('این دکمه پیام قابل دسترسی ندارد؛ /menu را بزن.')
            return None
        cid=chat.id
        raw=getattr(event,'data','') or ''
        # Choosing a private world never allows arbitrary access to another group's data.
        if cid>0 and (raw.startswith('gw:') or getattr(event,'text','')=='/worlds'):
            if raw.startswith('gw:'):
                plain=raw.split('~',1)[0]
                if not callbacks.valid(plain) or not choose_world(who.id,int(plain.split(':')[1])):
                    return await event.answer('⛔ این جهان متعلق به حساب تو نیست.',show_alert=True)
                return await message.answer('✅ جهان انتخاب شد؛ /menu را بزن.')
            return await self._chooser(message,who.id)
        game=cid if cid<0 else world_of(who.id)
        if game is None and cid>0:
            return await self._chooser(message,who.id)
        wt=db.GAME.set(game);at=db.ACTOR.set(who.id)
        try:
            if isinstance(event,CallbackQuery):
                plain=callbacks.unwrap(raw)
                if plain is None or not callbacks.valid(plain):
                    return await event.answer('⏳ دکمه نامعتبر یا مربوط به فصل قبل است؛ /menu را بزن.',show_alert=True)
                event=_clone(event,data=plain)
                # Display helpers acknowledge before queued output; validation errors above answer directly.
            now=time.monotonic();key=(game,who.id)
            if now-_LAST.get(key,0)<0.25:return None
            _LAST[key]=now
            if len(_LAST)>20000:
                stale=[k for k,t in _LAST.items() if now-t>600]
                for k in stale:_LAST.pop(k,None)
            if not db.kv_get("catalog:v41"):
                import countries
                with db.transaction():
                    countries.init_items();db.kv_set("catalog:v41",1)
            state.ensure(who.id,who.first_name,cid if cid<0 else None,getattr(who,'username',None))
            return await handler(event,data)
        except Exception as exc:
            ref=uuid.uuid4().hex[:8]
            db.log('error',f'{ref} {type(exc).__name__}: '+_scrub(exc)[:500])
            with contextlib.suppress(Exception):
                await message.answer(f'⚠️ این عملیات با خطای فنی روبه‌رو شد؛ شناسهٔ بررسی: {ref}. وضعیت را از /menu بررسی کن و تراکنش مالی را کورکورانه تکرار نکن.')
            return None
        finally:
            db.ACTOR.reset(at);db.GAME.reset(wt)

    async def _chooser(self,message,uid):
        known=worlds_for(uid)
        if not known:
            return await message.answer('🎮 ابتدا در گروه بازی «شروع» را بزن. در پیوی، جهان بدون انتخاب ساخته نمی‌شود.')
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'🌍 گروه {g}',callback_data=f'gw:{g}')] for g in known])
        with db.world(None):
            return await message.answer('🌍 کدام جهان؟ انتخاب پیوی روی گروه‌های دیگر اثر ندارد.',reply_markup=kb)
