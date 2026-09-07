from concurrent.futures import ThreadPoolExecutor
import sqlite3
from pathlib import Path
import pytest
import config
import countries
import db
from game import state,economy


def test_transaction_rolls_back_every_write(player):
    player(1,'ir',5000)
    with pytest.raises(RuntimeError):
        with db.transaction():
            db.debit(1,1000)
            db.kv_set('marker','yes')
            raise RuntimeError('injected failure')
    assert state.get(1)['money']==5000
    assert db.kv_get('marker') is None


def test_nested_savepoint_preserves_outer(player):
    player(1,'ir',5000)
    with db.transaction():
        db.debit(1,100)
        with pytest.raises(ValueError):
            with db.transaction():
                db.debit(1,900)
                raise ValueError()
        db.kv_set('ok',1)
    assert state.get(1)['money']==4900
    assert db.kv_get('ok')=='1'


def test_negative_money_rejected(player):
    player(1,'ir')
    with pytest.raises(sqlite3.IntegrityError):db.ex('UPDATE users SET money=-1 WHERE uid=1')


@pytest.mark.parametrize('gid',['../oops',None,True,'-100/../../x'])
def test_invalid_world_paths(gid):
    with pytest.raises((ValueError,TypeError)):db.game_path(gid)


def test_context_restored_even_on_error():
    token=db.GAME.set(-7)
    try:
        with pytest.raises(RuntimeError):
            with db.world(-9):
                assert db.GAME.get()==-9
                raise RuntimeError()
        assert db.GAME.get()==-7
    finally:db.GAME.reset(token)


def test_time_is_tehran_three_thirty():
    assert db.tehran_date(0).endswith('03:30')


def test_same_country_cannot_be_claimed_concurrently(tmp_path,clock):
    path=str(tmp_path/'concurrent.db');db.init(path);countries.init_items()
    def claim(uid):
        try:return state.enlist(uid,'us',str(uid))
        finally:db.close_all()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(claim,range(1,9)))
    assert sum(results)==1
    assert db.one("SELECT COUNT(*) FROM users WHERE country='us'")[0]==1
    assert db.one('PRAGMA integrity_check')[0]=='ok'


def test_concurrent_transfers_do_not_double_spend(tmp_path,clock):
    path=str(tmp_path/'transfers.db');db.init(path);countries.init_items()
    assert state.enlist(1,'ir','A');assert state.enlist(2,'iq','B')
    def send(_):
        try:return economy.transfer(1,2,700)
        finally:db.close_all()
    with ThreadPoolExecutor(max_workers=4) as pool:
        messages=list(pool.map(send,range(4)))
    assert sum('منتقل شد' in m for m in messages)==1
    assert state.get(1)['money']==300
    assert state.get(2)['money']==1700


def test_list_games_ignores_junk(tmp_path):
    Path(db.GAMES_DIR).mkdir()
    for name in ('notes.db','-123.db','456.db','abc.db-wal'):Path(db.GAMES_DIR,name).touch()
    assert db.list_games()==[-123,456]
