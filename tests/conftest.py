import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import config
import countries
import db
from game import catalog,state,rules,campaign


class Clock:
    def __init__(self):self.value=1_800_000_000
    def __call__(self):return self.value
    def advance(self,seconds):self.value+=seconds;return self.value


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    db.close_all();db.GAME.set(None);db.ACTOR.set(None)
    monkeypatch.setattr(db,'GAMES_DIR',str(tmp_path/'games'))
    monkeypatch.setattr(config,'BACKUP_DIR',str(tmp_path/'backups'))
    monkeypatch.setattr(config,'DB_PATH',str(tmp_path/'global.db'))
    monkeypatch.setattr(config,'TOKEN','')
    monkeypatch.setattr(config,'PAT','')
    db.init(':memory:');countries.init_items()
    yield
    db.GAME.set(None);db.ACTOR.set(None);db.close_all()


@pytest.fixture
def clock(monkeypatch):
    clock=Clock();monkeypatch.setattr(db,'now',clock)
    return clock


@pytest.fixture
def player(clock):
    def make(uid,cid,money=1000000):
        assert state.enlist(uid,cid,f'Player {uid} <&>')
        db.ex('UPDATE users SET branch=0,money=? WHERE uid=?',(money,uid))
        db.kv_set(f'claimed:{cid}',clock()-7200)
        return state.get(uid)
    return make


@pytest.fixture
def equip():
    def give(uid,kind,qty=5,dur=100,cid=None):
        pool=[i for i,it in countries.ITEMS.items() if catalog.supports(i,kind) and (cid is None or it[2]==cid)]
        assert pool
        iid=max(pool,key=lambda i:countries.ITEMS[i][3])
        db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qty=excluded.qty,dur=excluded.dur',(uid,iid,qty,dur))
        return iid
    return give


@pytest.fixture
def active_war(player,clock):
    player(1,'ir');player(2,'iq')
    assert 'اعلام جنگ' in campaign.declare(1,'iq')
    clock.advance(rules.MODES['total'].warning+1)
    return dict(campaign.war_of('ir'))
