from datetime import datetime,timezone
from html.parser import HTMLParser
import itertools
import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import Message,Chat,Update
import callbacks
import countries
import db
import handlers
import middleware
import run
from game import state,infra,campaign,operations,straits
from messaging import SafeMessages
from htmlsafe import plain_text,utf16_len


class HtmlCheck(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.stack=[]
    def handle_starttag(self,tag,attrs):
        assert tag in ('b','strong','i','em','u','ins','s','strike','del','span','tg-spoiler','a','code','pre','tg-emoji','blockquote')
        self.stack.append(tag)
    def handle_endtag(self,tag):assert self.stack.pop()==tag


class FakeSession(BaseSession):
    def __init__(self):super().__init__();self.calls=[];self.ids=itertools.count(1)
    async def close(self):pass
    async def stream_content(self,*a,**kw):yield b''
    async def make_request(self,bot,method,timeout=None):
        self.calls.append(method)
        for field,limit in (('text',4096),('caption',1024)):
            body=getattr(method,field,None)
            if not isinstance(body,str) or type(method).__name__=='AnswerCallbackQuery':continue
            assert utf16_len(plain_text(body))<=limit
            h=HtmlCheck();h.feed(body);assert not h.stack
        kb=getattr(method,'reply_markup',None)
        if kb and hasattr(kb,'inline_keyboard'):
            assert sum(len(r) for r in kb.inline_keyboard)<=100
            for row in kb.inline_keyboard:
                for b in row:
                    if b.callback_data:
                        assert len(b.callback_data.encode())<=64
                        raw=callbacks.unwrap(b.callback_data)
                        assert raw and callbacks.valid(raw),b.callback_data
        chat=getattr(method,'chat_id',None)
        if chat is not None:
            return Message(message_id=next(self.ids),date=datetime.now(timezone.utc),chat=Chat(id=chat,type='supergroup' if chat<0 else 'private'),text=getattr(method,'text',None) or '').as_(bot)
        return True


@pytest.fixture
def client(monkeypatch,clock):
    session=FakeSession();session.middleware(SafeMessages(gap=0))
    bot=Bot('123456:OFFLINE_TEST_TOKEN_NOT_A_REAL_SECRET',session=session)
    handlers.router._parent_router=None
    dp=run.build_dispatcher()
    monkeypatch.setattr(handlers,'bot',bot)
    monkeypatch.setattr(handlers,'WORLD_OF',middleware.world_of)
    middleware._LAST.clear()
    seq=itertools.count(1)
    async def feed(text=None,data=None,uid=1,gid=-1001,message_id=900):
        middleware._LAST.clear()
        who={'id':uid,'is_bot':False,'first_name':'Player <&>','username':'player'}
        msg={'message_id':message_id,'date':int(clock()),'chat':{'id':gid,'type':'supergroup' if gid<0 else 'private'},'from':who,'text':text or 'menu'}
        payload={'update_id':next(seq)}
        if data is not None:payload['callback_query']={'id':str(next(seq)),'from':who,'chat_instance':'test','message':msg,'data':data}
        else:payload['message']=msg
        update=Update.model_validate(payload,context={'bot':bot})
        await dp.feed_update(bot,update)
        with db.world(gid if gid<0 else (middleware.world_of(uid) or None)):
            errors=db.q("SELECT text FROM logs WHERE level='error'")
            assert not errors,[r['text'] for r in errors]
        return session.calls
    yield bot,session,feed
    handlers.router._parent_router=None


def seed_world(player,gid=-1001):
    with db.world(gid):
        countries.init_items();player(1,'ir');player(2,'iq')
        db.kv_set(f'hello:{gid}',1)


@pytest.mark.parametrize('command',['/menu','/help','/commands','/profile','/military','/world','/attack','/buy','/trade','/invest','/infra','/welfare','/toll','/cities','/supply','/contracts','/gifts','/un','/operations','/straits'])
async def test_real_aiogram_commands(client,player,command):
    _,session,feed=client;seed_world(player)
    await feed(text=command)
    assert any(type(m).__name__ in ('SendMessage','SendPhoto') for m in session.calls),command
    assert any('tg://user?id=1' in (getattr(m,'text','') or getattr(m,'caption','') or '') for m in session.calls),command


@pytest.mark.parametrize('data',['mn:main','mn:mil','mn:pol','mn:world','mn:me','mn:arsenal','mn:trade','mn:parties','mn:spy','mn:ally','mn:war','mn:wstat','mn:power','mn:colonies','mn:lb','mn:market','mn:map','mn:help','mn:cguide','mn:front','mn:army','mn:def','mn:quest','mn:black','mn:upgrade','mn:duel','mn:infra','mn:welf','cities:','city:0','contracts:','gifts:','ops:','opnew:','un:','unnew:','sg:','sg:hormuz','snc:','snc:iq','dwr:iq'])
async def test_real_callbacks_have_valid_html_and_working_keyboards(client,player,data):
    _,session,feed=client;seed_world(player)
    await feed(data=data)
    assert any(type(m).__name__ in ('SendMessage','EditMessageText','SendPhoto') for m in session.calls),data


async def test_owner_locked_menu_cannot_be_used_by_another_player(client,player):
    _,session,feed=client;seed_world(player)
    with db.world(-1001):
        db.kv_set('mown:-1001:900',1)
        money=state.get(2)['money']
    await feed(data='dl:',uid=2)
    with db.world(-1001):assert state.get(2)['money']==money
    assert any('این منوی' in (getattr(m,'text','') or '') for m in session.calls)


async def test_reset_epoch_rejects_old_destructive_button(client,player):
    _,session,feed=client;seed_world(player)
    with db.world(-1001):
        db.kv_set('season_epoch','abcdef')
        money=state.get(1)['money']
    await feed(data='wp:f35~old123')
    with db.world(-1001):assert state.get(1)['money']==money
    assert any('فصل قبل' in (getattr(m,'text','') or '') for m in session.calls)


@pytest.mark.parametrize('data',['wp:unknown','st:زمینی:-1','df:nope','br:no','city:999999999999999999999999999','sgfee:hormuz:100000','sgact:hormuz:explode','unvote:1:yes:extra','opmode:us:no:total'])
async def test_malformed_callbacks_are_rejected_before_handlers(client,player,data):
    _,session,feed=client;seed_world(player)
    await feed(data=data)
    assert any('نامعتبر' in (getattr(m,'text','') or '') for m in session.calls)


async def test_operation_naming_input_persists_across_pending_dict_clear(client,player,clock):
    _,_,feed=client;seed_world(player)
    await feed(data='opmode:iq:ground:total')
    handlers._pending.clear()
    await feed(text='سپیده <آزمایشی>')
    with db.world(-1001):
        op=db.one('SELECT * FROM operation_plans')
        assert op and op['name']=='سپیده <آزمایشی>'


async def test_private_world_selection_does_not_silently_pick_a_group(client,player):
    _,session,feed=client;seed_world(player,-1001);seed_world(player,-1002)
    await feed(text='/menu',gid=1)
    assert any('کدام جهان' in (getattr(m,'text','') or '') for m in session.calls)
    assert middleware.world_of(1) is None
    await feed(data='gw:-1002~0',gid=1)
    assert middleware.world_of(1)==-1002


async def test_initial_country_selection_with_real_frozen_aiogram_message(client):
    _,session,feed=client
    await feed(text='/start')
    await feed(data='cy:ir')
    with db.world(-1001):assert state.get(1)['country']=='ir'
    assert any('کشور انتخاب شد' in (getattr(m,'text','') or '') for m in session.calls)


@pytest.mark.parametrize('command',['/trade','/gifts'])
async def test_countryless_player_gets_a_useful_response_not_silence(client,command):
    _,session,feed=client
    await feed(text=command)
    assert any(type(m).__name__=='SendMessage' for m in session.calls)
    with db.world(-1001):
        assert state.get(1)['country'] is None
        assert db.one('SELECT COUNT(*) FROM items')[0]==len(countries.ITEMS)


async def test_callback_is_acknowledged_once_not_after_every_edit(client,player):
    _,session,feed=client;seed_world(player)
    await feed(data='mn:main')
    assert sum(type(m).__name__=='AnswerCallbackQuery' for m in session.calls)==1


@pytest.mark.parametrize('command',['/energy','/fleet','/sanctions'])
async def test_maritime_commands_use_same_dispatcher(client,player,command):
    _,session,feed=client;seed_world(player)
    await feed(text=command)
    assert any(type(m).__name__=='SendMessage' for m in session.calls)


@pytest.mark.parametrize('data',['en:','en:0','fv:','fbld:','ftypes:4','finbox:','fipage:0','fet:','ebuy:0:50','esell:0:50','ecrude:0:5','cbld:0:refinery','cbld:0:command','cbld:4:shipyard'])
async def test_energy_and_ship_menus_validate_html_and_callbacks(client,player,data):
    _,session,feed=client;seed_world(player)
    await feed(data=data)
    assert any(type(m).__name__ in ('SendMessage','EditMessageText') for m in session.calls)


async def test_tanker_custom_name_input_and_consent_flow(client,player,clock):
    from game import fleet
    _,_,feed=client;seed_world(player)
    with db.world(-1001):
        infra.build(1,'shipyard',4);clock.advance(infra.build_seconds('shipyard')+1)
    await feed(data='fname:4:coastal')
    handlers._pending.clear()
    await feed(text='سپهر <&> نفت‌کش')
    with db.world(-1001):
        s=db.one('SELECT * FROM tankers');assert s['name']=='سپهر <&> نفت‌کش'
        sid=s['id'];clock.advance(fleet.CLASSES['coastal'][3]+1);fleet.progress_builds('ir')
    for step in (f'fsend:{sid}',f'fcar:{sid}:fuel',f'fdest:{sid}:fuel:iq',f'fport:{sid}:fuel:iq:1',f'foqty:{sid}:fuel:iq:1:20',f'foesc:{sid}:fuel:iq:1:20:0'):
        await feed(data=step)
    with db.world(-1001):
        v=db.one('SELECT * FROM voyages');assert v['status']=='offered';vid=v['id']
        before=state.get(2)['money']
    await feed(data=f'fvr:{vid}',uid=2,message_id=1900)
    await feed(data=f'facc:{vid}',uid=2,message_id=1900)
    with db.world(-1001):
        v=db.one('SELECT * FROM voyages');assert v['status']=='outbound' and v['escrow']>0
        assert state.get(2)['money']==before-v['price']


@pytest.mark.parametrize('bad',['fname:99:coastal','foesc:1:fuel:ir:4:200:3','fat:1:missile:5','fat:1:naval:-1','ebuy:0:-50','facc:1:extra','fdest:1:fuel:xx'])
async def test_malformed_maritime_callback_cannot_spend_money(client,player,bad):
    _,session,feed=client;seed_world(player)
    with db.world(-1001):cash=state.get(1)['money']
    await feed(data=bad)
    with db.world(-1001):assert state.get(1)['money']==cash
    assert any('نامعتبر' in (getattr(m,'text','') or '') for m in session.calls)


@pytest.mark.parametrize('form',['operation','tanker'])
async def test_slash_menu_cancels_name_entry_instead_of_spending_money(client,player,clock,form):
    _,_,feed=client;seed_world(player)
    if form=='tanker':
        with db.world(-1001):
            infra.build(1,'shipyard',4);clock.advance(infra.build_seconds('shipyard')+1)
        await feed(data='fname:4:coastal')
    else:await feed(data='opmode:iq:ground:total')
    with db.world(-1001):cash=state.get(1)['money']
    await feed(text='/menu')
    with db.world(-1001):
        assert state.get(1)['money']==cash
        assert db.one('SELECT COUNT(*) FROM tankers')[0]==0
        assert db.one('SELECT COUNT(*) FROM operation_plans')[0]==0
        assert not db.kv_get('input:1:-1001')


async def test_gift_storage_and_retirement_require_real_confirmation(client,clock):
    from game import rewards
    uid=rewards.US_UID
    _,session,feed=client
    with db.world(-1001):
        countries.init_items();state.enlist(uid,'us','USA')
        plan=rewards.equipment_plan('us',5,True);iid=next(iter(plan))
        for item in plan:
            db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,9,40) ON CONFLICT(uid,iid) DO UPDATE SET qty=9,dur=40',(uid,item))
        rewards.schedule()
    await feed(text='/gifts',uid=uid)
    with db.world(-1001):assert state.get(uid)['money']==81000
    await feed(data='scraps:',uid=uid)
    await feed(data=f'scprep:{iid}',uid=uid)
    with db.world(-1001):
        record=db.jload(db.kv_get(f'retire:{uid}'));nonce=record['nonce']
        assert db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))[0]==9
    await feed(data=f'scrok:{nonce}',uid=uid)
    await feed(data=f'scrok:{nonce}',uid=uid)
    with db.world(-1001):assert db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))[0]==8
    await feed(data='grstock:',uid=uid)
    with db.world(-1001):
        assert db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))[0]==9
        assert state.get(uid)['money']==81000
    assert session.calls


async def test_cancelling_disposal_invalidates_its_old_button(client,player,equip):
    _,_,feed=client;seed_world(player)
    with db.world(-1001):iid=equip(1,'زمینی',qty=2)
    await feed(data=f'scprep:{iid}')
    with db.world(-1001):nonce=db.jload(db.kv_get('retire:1'))['nonce']
    await feed(data='srcancel:')
    await feed(data=f'scrok:{nonce}')
    with db.world(-1001):assert db.one('SELECT qty FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==2


@pytest.mark.parametrize('bad',['scrok:invalid','scprep:unknown','scpage:-1','grstock:123'])
async def test_invalid_gift_storage_buttons_are_rejected(client,player,bad):
    _,session,feed=client;seed_world(player)
    await feed(data=bad)
    assert any('نامعتبر' in (getattr(m,'text','') or '') for m in session.calls)
