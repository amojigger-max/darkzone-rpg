import json
import pytest
import countries
import db
from game import state,rewards,military


def prepare_full_us():
    state.enlist(rewards.US_UID,'us','USA')
    plan=rewards.equipment_plan('us',5,True)
    for iid in plan:
        db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,9,40) ON CONFLICT(uid,iid) DO UPDATE SET qty=9,dur=40',(rewards.US_UID,iid))
    rewards.schedule()
    return plan


def test_full_inventory_does_not_block_cash_or_lose_equipment(clock):
    plan=prepare_full_us();uid=rewards.US_UID
    rewards.award_pending(uid)
    assert state.get(uid)['money']==81000
    assert db.one('SELECT SUM(qty) FROM reward_stock WHERE uid=?',(uid,))[0]==6
    for iid in plan:
        row=db.one('SELECT qty,dur FROM inventory WHERE uid=? AND iid=?',(uid,iid))
        assert row['qty']==9 and row['dur']==40
    assert rewards.award_pending(uid)==[]
    assert state.get(uid)['money']==81000
    assert db.one('SELECT SUM(qty) FROM reward_stock WHERE uid=?',(uid,))[0]==6


def test_stock_claim_and_retirement_are_single_use_without_extra_cash(clock):
    plan=prepare_full_us();uid=rewards.US_UID;rewards.award_pending(uid)
    iid=next(iter(plan));money=state.get(uid)['money']
    text,nonce=military.retire_offer(uid,iid)
    assert nonce and 'تأیید' in text
    assert db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))[0]==9
    assert 'حذف شد' in military.retire_confirm(uid,nonce)
    assert 'قبلاً استفاده' in military.retire_confirm(uid,nonce)
    assert db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))[0]==8
    assert 'منتقل شد' in rewards.claim_stock(uid)
    row=db.one('SELECT qty,dur FROM inventory WHERE uid=? AND iid=?',(uid,iid))
    assert row['qty']==9 and row['dur']==(8*40+100)//9
    assert db.one('SELECT qty FROM reward_stock WHERE uid=? AND iid=?',(uid,iid))[0]==0
    rewards.claim_stock(uid)
    assert state.get(uid)['money']==money
    assert db.one('SELECT SUM(qty) FROM reward_stock WHERE uid=?',(uid,))[0]==5


def test_cash_equipment_reserve_and_receipt_rollback_together(clock,monkeypatch):
    uid=rewards.US_UID;prepare_full_us()
    before=state.get(uid)['money']
    monkeypatch.setattr(rewards.notifications,'emit',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('receipt failure')))
    with pytest.raises(RuntimeError):rewards.award_pending(uid)
    assert state.get(uid)['money']==before
    assert db.one('SELECT COUNT(*) FROM reward_stock')[0]==0
    assert db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NOT NULL')[0]==0


def test_retirement_confirmation_is_scoped_to_owner_country_and_expiry(player,equip,clock):
    player(1,'ir');player(2,'iq');iid=equip(1,'زمینی',qty=2)
    _,nonce=military.retire_offer(1,iid)
    assert 'نامعتبر' in military.retire_confirm(2,nonce)
    clock.advance(301)
    assert 'منقضی' in military.retire_confirm(1,nonce)
    assert db.one('SELECT qty FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==2
    _,nonce=military.retire_offer(1,iid)
    db.ex("UPDATE users SET country='de' WHERE uid=1")
    assert 'نامعتبر' in military.retire_confirm(1,nonce)
    assert db.one('SELECT qty FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==2


@pytest.mark.parametrize('qty',[0,-1,True,10,1.5,None])
def test_invalid_retirement_never_removes_gear(player,equip,qty):
    player(1,'ir');iid=equip(1,'زمینی',qty=5)
    _,nonce=military.retire_offer(1,iid,qty)
    assert nonce is None
    assert db.one('SELECT qty FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==5


def test_countryless_still_cannot_claim_fresh_money_or_reserve(clock):
    state.ensure(rewards.US_UID,'USA');rewards.schedule()
    assert rewards.award_pending(rewards.US_UID)==[]
    assert state.get(rewards.US_UID)['money']==1000
    assert db.one('SELECT COUNT(*) FROM reward_stock')[0]==0


def test_stock_is_cleared_by_explicit_full_reset_not_paid_again(clock):
    import migrations
    with db.world(-501):
        countries.init_items();prepare_full_us();rewards.award_pending(rewards.US_UID)
        assert db.one('SELECT SUM(qty) FROM reward_stock')[0]==6
    migrations.reset_game(-501,'new-full-reset',confirmed=True,special_rewards=True)
    with db.world(-501):
        assert db.one('SELECT COUNT(*) FROM reward_stock')[0]==0
        assert state.get(rewards.US_UID)['country'] is None
        assert db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NOT NULL')[0]>0


def test_concurrent_award_does_not_repeat_cash_or_overflow(clock):
    from concurrent.futures import ThreadPoolExecutor
    with db.world(-502):countries.init_items();prepare_full_us()
    def claim():
        with db.world(-502):return rewards.award_pending(rewards.US_UID)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:claim(),range(8)))
    with db.world(-502):
        assert state.get(rewards.US_UID)['money']==81000
        assert db.one('SELECT SUM(qty) FROM reward_stock')[0]==6
        assert db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NOT NULL')[0]==2
