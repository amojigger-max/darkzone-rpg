import asyncio
from html.parser import HTMLParser
import re
import types
import sqlite3
import pytest
from aiogram.exceptions import TelegramRetryAfter,TelegramForbiddenError,TelegramBadRequest
from aiogram.methods import SendMessage
import db
import texts
import htmlsafe
import save_db
from game import notifications,state


class Balanced(HTMLParser):
    def __init__(self):super().__init__();self.stack=[]
    def handle_starttag(self,tag,attrs):self.stack.append(tag)
    def handle_endtag(self,tag):assert self.stack.pop()==tag


@pytest.mark.parametrize('body',[
 '<b>'+('متن 😀 &amp; &lt; &gt; '*3000)+'</b>',
 '<b><i>'+('x'*30000)+'</i></b>',
 '<a href="tg://user?id=8694290031">'+('ایران '*8)+'</a>'+(' ادامه '*1000),
 ''.join(texts.mention(i,'کاربر <&> 😀') for i in range(1,1001)),
 texts.fx('⚓️ ⚓ 🚀 🔥 '+texts.mention(12345,'🚀 نام <&>')),
])
def test_html_pagination_preserves_visible_text_and_balancing(body):
    parts=htmlsafe.split_html(body)
    assert ''.join(htmlsafe.plain_text(p) for p in parts)==htmlsafe.plain_text(body)
    for part in parts:
        assert htmlsafe.units(part)<=3500
        parser=Balanced();parser.feed(part);assert not parser.stack
    before=re.findall(r'tg://user\?id=\d+',body)
    after=re.findall(r'tg://user\?id=\d+',''.join(parts))
    assert before==after


def test_emoji_decoration_is_idempotent_and_never_nested():
    raw=texts.fx('⚓️ ⚓ 🚀',seed=42)
    assert raw==texts.fx(raw,seed=99)
    parser=Balanced();parser.feed(raw);assert not parser.stack
    assert '<tg-emoji' not in re.sub(r'<tg-emoji[^>]*>[^<]*</tg-emoji>','',raw)


def test_ten_thousand_players_are_all_tagged_and_kept_in_outbox(clock):
    with db.world(-10001):
        with db.transaction():
            for uid in range(1,10001):state.ensure(uid,f'کاربر {uid} 😀 <&>')
        ids=list(range(1,10001))
        rows=notifications.emit('📣 خلاصهٔ آپدیت',uids=ids,key='stress:everyone')
        assert len(rows)>100
        bodies=[r['body'] for r in db.q('SELECT body FROM outbox ORDER BY id')]
        got=[int(v) for v in re.findall(r'tg://user\?id=(\d+)',''.join(bodies))]
        assert got==ids and len(set(got))==10000
        assert all(htmlsafe.units(body)<=3500 for body in bodies)
        for body in bodies:
            parser=Balanced();parser.feed(body);assert not parser.stack
        notifications.emit('📣 خلاصهٔ آپدیت',uids=ids,key='stress:everyone')
        assert db.one('SELECT COUNT(*) FROM outbox')[0]==len(rows)


class FakeBot:
    def __init__(self,error=None):self.error=error;self.sent=[]
    async def send_message(self,chat_id,body,**kwargs):
        if self.error:raise self.error
        self.sent.append((chat_id,body));return types.SimpleNamespace(message_id=len(self.sent))


async def test_outbox_commits_delivery_and_does_not_send_twice(clock):
    with db.world(-1):
        notifications.emit('Hello',key='once')
        bot=FakeBot();assert await notifications.drain(bot)==1
        assert await notifications.drain(bot)==0
        assert len(bot.sent)==1
        assert db.one('SELECT status,message_id FROM outbox')[0]=='sent'


@pytest.mark.parametrize('error,status',[(TimeoutError('network ambiguous'),'unknown'),(TelegramForbiddenError(SendMessage(chat_id=-1,text='x'),'forbidden'),'blocked'),(TelegramBadRequest(SendMessage(chat_id=-1,text='x'),'invalid'),'blocked')])
async def test_ambiguous_or_forbidden_delivery_does_not_duplicate(error,status,clock):
    with db.world(-1):
        notifications.emit('Hello',key='blocked')
        await notifications.drain(FakeBot(error))
        assert db.one('SELECT status FROM outbox')[0]==status
        bot=FakeBot();await notifications.drain(bot)
        assert bot.sent==[]


async def test_retry_after_respects_server_delay(clock):
    with db.world(-1):
        notifications.emit('Hello',key='retry')
        bot=FakeBot(TelegramRetryAfter(SendMessage(chat_id=-1,text='x'),'slow',retry_after=30))
        await notifications.drain(bot)
        assert db.one('SELECT status FROM outbox')[0]=='pending'
        bot=FakeBot();await notifications.drain(bot);assert not bot.sent
        clock.advance(31);await notifications.drain(bot);assert len(bot.sent)==1


def test_crashed_sending_is_unknown_not_blindly_replayed(clock):
    with db.world(-1):
        notifications.emit('Hello',key='crash');notifications._claim();notifications.recover()
        assert db.one('SELECT status FROM outbox')[0]=='unknown'


def test_sqlite_snapshot_contains_committed_wal(tmp_path):
    path=tmp_path/'wal.db';c=sqlite3.connect(path)
    c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE data(n INTEGER)');c.execute('INSERT INTO data VALUES(123)');c.commit()
    payload=save_db.checkpoint(path)
    copy=sqlite3.connect(':memory:');copy.deserialize(payload)
    # WAL-mode serialized images may retain WAL mode; deserialize must be converted by writer.
    assert copy.execute('SELECT n FROM data').fetchone()[0]==123
    c.close();copy.close()


def test_autosave_rejects_other_runner_revision(monkeypatch):
    save_db._EXPECTED.clear();save_db._EXPECTED['games/-1.db']='old'
    monkeypatch.setattr(save_db,'_sha',lambda *args:'new')
    with pytest.raises(save_db.SaveConflict):save_db.put('TEST',b'not-sent','games/-1.db')


def test_autosave_rejects_unknown_existing_remote(monkeypatch):
    save_db._EXPECTED.clear();monkeypatch.setattr(save_db,'_sha',lambda *args:'exists')
    with pytest.raises(save_db.SaveConflict):save_db.put('TEST',b'not-sent','games/-99.db')


@pytest.mark.parametrize('path',['/etc/passwd','../outside.db','games/../../x.db','notes.txt'])
def test_autosave_path_validation(path):
    with pytest.raises(ValueError):save_db._remote(path)


def test_news_archive_keeps_complete_events_and_no_duplicate_event(clock):
    with db.world(-10):
        body='خبر '+texts.mention(42,'کاربر')+' '+('ادامه '*2000)
        notifications.emit(body,key='news-once')
        notifications.emit(body,key='news-once')
        assert db.one('SELECT COUNT(*) FROM news')[0]==1
        assert db.one('SELECT text FROM news')[0]==body
