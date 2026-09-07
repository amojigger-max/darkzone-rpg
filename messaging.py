"""Safe Telegram output: every mention retained, rate limiting, season-bound keyboards."""
import asyncio
import time

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage

import callbacks
import db
from game import notifications
from htmlsafe import split_html


class SafeMessages(BaseRequestMiddleware):
    def __init__(self,gap=3.4):
        self.gap=gap
        self.locks={}
        self.last={}
        self.answered={}

    async def _deliver(self,make_request,bot,method):
        chat=getattr(method,'chat_id',None)
        if not chat:return await make_request(bot,method)
        lock=self.locks.setdefault(chat,asyncio.Lock())
        async with lock:
            # Keep the lock through dispatch: two callers cannot leave the queue together.
            gap=self.gap if isinstance(chat,int) and chat<0 else 0.08
            wait=gap-(time.monotonic()-self.last.get(chat,0))
            if wait>0:await asyncio.sleep(wait)
            for attempt in range(3):
                try:
                    result=await make_request(bot,method)
                except TelegramRetryAfter as exc:
                    if attempt==2:raise
                    await asyncio.sleep(exc.retry_after+0.5)
                else:
                    self.last[chat]=time.monotonic()
                    return result

    async def __call__(self,make_request,bot,method):
        name=type(method).__name__
        if name=='AnswerCallbackQuery':
            key=method.callback_query_id
            if key in self.answered:return True
            result=await make_request(bot,method)
            self.answered[key]=time.monotonic()
            if len(self.answered)>10000:
                for stale in list(self.answered)[:5000]:self.answered.pop(stale,None)
            return result
        if hasattr(method,'reply_markup'):
            markup=callbacks.sign_markup(method.reply_markup)
            method=method.model_copy(update={'reply_markup':markup})
        field='text' if name in ('SendMessage','EditMessageText') else 'caption' if name in ('SendPhoto','SendVideo','SendDocument','SendAnimation','EditMessageCaption') else None
        if field and getattr(method,field,None):
            body=getattr(method,field)
            # Do not alter explicitly non-HTML traffic owned by another subsystem.
            mode=getattr(method,'parse_mode',None)
            if mode in (None,'HTML') or str(mode).startswith('Default('):
                actor=db.ACTOR.get()
                if actor:body=notifications.personal(actor,body)
                parts=split_html(body,900 if field=='caption' else 3500)
                markup=getattr(method,'reply_markup',None)
                first=method.model_copy(update={field:parts[0],'parse_mode':'HTML'})
                if len(parts)>1 and name.startswith('Send'):
                    first=first.model_copy(update={'reply_markup':None})
                result=await self._deliver(make_request,bot,first)
                for i,part in enumerate(parts[1:],1):
                    message=SendMessage(chat_id=method.chat_id,text=part,parse_mode='HTML',
                         message_thread_id=getattr(method,'message_thread_id',None),
                         reply_markup=markup if i==len(parts)-1 and name.startswith('Send') else None)
                    extra=await self._deliver(make_request,bot,message)
                    if name.startswith('Send'):result=extra
                return result
        if name in ('SendMessage','SendPhoto','SendVideo','SendDocument','SendAnimation','EditMessageText','EditMessageCaption','EditMessageReplyMarkup'):
            return await self._deliver(make_request,bot,method)
        return await make_request(bot,method)
