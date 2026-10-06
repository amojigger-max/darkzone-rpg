import json
from pathlib import Path
import sqlite3
import pytest
import countries
import config
import db
import migrations
from game import state,rewards,geo,infra,catalog


def seed(gid,clock):
    with db.world(gid):
        countries.init_items()
        assert state.enlist(rewards.US_UID,'us','USA')
        assert state.enlist(rewards.IR_UID,'ir','IR')
        db.ex('UPDATE users SET money=90000')
        db.kv_set('econ','{"oil":140}')
        db.kv_set('bl_off','1')


def test_boot_never_resets_or_pays(clock):
    seed(-1001,clock)
    migrations.run_all();migrations.run_all()
    with db.world(-1001):
        assert state.get(rewards.US_UID)['country']=='us'
        assert state.get(rewards.US_UID)['money']==90000
        assert db.one('SELECT COUNT(*) FROM reward_grants')[0]==0


def test_reset_is_scoped_backed_up_and_idempotent(clock):
    seed(-1001,clock);seed(-1002,clock)
    with pytest.raises(PermissionError):migrations.reset_game(-1001,'v41')
    result=migrations.reset_game(-1001,'v41',confirmed=True,special_rewards=True)
    assert result['changed']
    assert Path(result['backup']).exists()
    with sqlite3.connect(result['backup']) as c:
        assert c.execute('SELECT COUNT(*) FROM users WHERE country IS NOT NULL').fetchone()[0]==2
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with db.world(-1001):
        assert db.one('SELECT COUNT(*) FROM users WHERE country IS NOT NULL OR is_leader<>0')[0]==0
        assert db.one('SELECT COUNT(*) FROM inventory')[0]==0
        assert db.one('SELECT COUNT(*) FROM structures')[0]==0
        assert db.kv_get('bl_off')=='1'
        assert db.kv_get('econ') is None
        assert db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NULL')[0]==4
        assert db.one('SELECT COUNT(*) FROM outbox')[0]>0
        db.ex('UPDATE users SET money=1234 WHERE uid=?',(rewards.US_UID,))
    second=migrations.reset_game(-1001,'v41',confirmed=True,special_rewards=True)
    assert not second['changed']
    with db.world(-1001):assert state.get(rewards.US_UID)['money']==1234
    with db.world(-1002):assert state.get(rewards.US_UID)['money']==90000


def test_deferred_gifts_correct_identity_and_country(clock):
    seed(-1001,clock)
    migrations.reset_game(-1001,'fresh',confirmed=True,special_rewards=True)
    with db.world(-1001):
        assert state.enlist(rewards.US_UID,'us','USA')
        assert state.enlist(rewards.IR_UID,'ir','IR')
        assert state.get(rewards.US_UID)['money']==81000
        assert state.get(rewards.IR_UID)['money']==91000
        for uid,cid,n in ((rewards.US_UID,'us',6),(rewards.IR_UID,'ir',10)):
            grant=db.one('SELECT * FROM reward_grants WHERE uid=? AND grant_id=?',(uid,rewards.GRANT_ID))
            eq=json.loads(grant['equipment'])
            assert len(eq)==n and sum(eq.values())==n
            assert all(countries.ITEMS[i][2]==cid for i in eq)
            assert grant['awarded_at']
        assert sum(catalog.primary(i)=='پدافندی' for i in json.loads(db.one('SELECT equipment FROM reward_grants WHERE uid=? AND grant_id=?',(rewards.US_UID,rewards.GRANT_ID))['equipment']))==1
        count=db.one("SELECT COUNT(*) FROM outbox WHERE event_key LIKE 'grant:%'")[0]
        before=state.get(rewards.US_UID)['money']
        assert rewards.award_pending(rewards.US_UID)==[]
        assert state.get(rewards.US_UID)['money']==before
        assert db.one("SELECT COUNT(*) FROM outbox WHERE event_key LIKE 'grant:%'")[0]==count


def test_wrong_country_never_gets_special_money(clock):
    with db.world(-1001):
        countries.init_items();rewards.schedule()
        assert state.enlist(rewards.US_UID,'de','Wrong country')
        assert state.get(rewards.US_UID)['money']==31000
        assert db.one('SELECT awarded_at FROM reward_grants WHERE uid=? AND grant_id=?',(rewards.US_UID,rewards.GRANT_ID))[0] is None
        assert state.enlist(98765,'us','Other player')
        assert state.get(98765)['money']==31000


def test_reward_and_announcement_rollback_together(clock,monkeypatch):
    with db.world(-1001):
        countries.init_items();rewards.schedule()
        original=rewards.notifications.emit
        monkeypatch.setattr(rewards.notifications,'emit',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('outbox failure')))
        with pytest.raises(RuntimeError):state.enlist(rewards.US_UID,'us','USA')
        assert state.get(rewards.US_UID) is None
        assert db.one('SELECT awarded_at FROM reward_grants WHERE uid=? AND grant_id=?',(rewards.US_UID,rewards.GRANT_ID))[0] is None
        monkeypatch.setattr(rewards.notifications,'emit',original)
        assert state.enlist(rewards.US_UID,'us','USA')
        assert state.get(rewards.US_UID)['money']==81000


def test_reset_rolls_back_if_grant_plan_fails(clock,monkeypatch):
    seed(-1001,clock)
    monkeypatch.setattr(rewards,'schedule',lambda:(_ for _ in ()).throw(RuntimeError('injected')))
    with pytest.raises(RuntimeError):migrations.reset_game(-1001,'fail',confirmed=True,special_rewards=True)
    with db.world(-1001):
        assert state.get(rewards.US_UID)['country']=='us'
        assert state.get(rewards.US_UID)['money']==90000
        assert not db.one('SELECT 1 FROM reset_history')


def test_rollout_all_worlds_is_explicit_once_and_announces_to_countryless_too(clock):
    import release
    for gid in (-101,-102):
        with db.world(gid):
            countries.init_items();state.enlist(44,'de','German');state.ensure(45,'Waiting')
    with pytest.raises(PermissionError):release.apply(-101)
    result=release.apply(-101,confirmed=True)
    assert result['changed']
    with db.world(-101):
        assert state.get(44)['money']==31000
        assert state.get(45)['country'] is None and state.get(45)['money']==1000
        body=''.join(r['body'] for r in db.q("SELECT body FROM outbox WHERE event_key LIKE 'release:%'"))
        assert 'tg://user?id=44' in body and 'tg://user?id=45' in body
    assert not release.apply(-101,confirmed=True)['changed']
    with db.world(-102):assert state.get(44)['money']==1000


def test_local_runner_lock_blocks_maintenance():
    from runtime_lock import exclusive
    with exclusive():
        with pytest.raises(RuntimeError):
            with exclusive():pass
