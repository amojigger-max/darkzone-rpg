import json
import random
import pytest
import countries
import db
import texts
from game import state,military,economy,invest,toll,politics,welfare,guide,catalog


@pytest.mark.parametrize('qty',[1,2,3,4,5])
def test_purchase_charges_for_every_unit(qty,player):
    player(1,'us')
    iid=next(i for i in countries.COUNTRIES['us']['items'] if i not in economy.daily_deals('us'))
    price=countries.ITEMS[iid][5]
    before=state.get(1)['money']
    assert 'خریداری شد' in military.buy(1,iid,qty)
    cost=price*qty*(90 if qty==5 else 100)//100
    assert state.get(1)['money']==before-cost
    assert db.one('SELECT qty FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==qty


@pytest.mark.parametrize('qty',[0,-1,6,2.5,True,'3',None,10**99])
def test_invalid_purchase_is_side_effect_free(qty,player):
    player(1,'us')
    iid='f35';before=state.get(1)['money']
    assert military.buy(1,iid,qty).startswith('⛔')
    assert state.get(1)['money']==before
    assert not db.one('SELECT 1 FROM inventory WHERE uid=1 AND iid=?',(iid,))


def test_new_units_do_not_repair_old_fleet_for_free(player):
    player(1,'us')
    db.ex("INSERT INTO inventory(uid,iid,qty,dur) VALUES(1,'f35',1,20)")
    military.buy(1,'f35',2)
    assert db.one("SELECT dur FROM inventory WHERE uid=1 AND iid='f35'")[0]==73


def test_black_market_does_not_reseed_combat_randomness(player):
    player(1,'us');random.seed(17);before=random.getstate()
    a=military.black_sample(1);b=military.black_sample(1)
    assert a==b
    assert before==random.getstate()
    iid=next(i for i,it in countries.ITEMS.items() if it[2]!='us' and i not in a)
    money=state.get(1)['money']
    assert 'همین ساعت' in military.buy_black(1,iid)
    assert state.get(1)['money']==money


@pytest.mark.parametrize('amount',[0,-1,1.1,True,'10',None,10**99])
def test_bad_money_transfer_rejected(amount,player):
    player(1,'ir');player(2,'iq')
    before=db.one('SELECT SUM(money) FROM users')[0]
    assert economy.transfer(1,2,amount).startswith('⛔')
    assert db.one('SELECT SUM(money) FROM users')[0]==before


def test_transfer_conserves_money_and_denies_self(player):
    player(1,'ir',1000);player(2,'iq',1000)
    assert 'منتقل شد' in economy.transfer(1,2,350)
    assert state.get(1)['money']==650 and state.get(2)['money']==1350
    assert economy.transfer(1,1,100).startswith('⛔')
    assert 'کافی' in economy.transfer(1,2,1000)


def test_investment_no_retroactive_new_asset_income(player,clock):
    player(1,'ir')
    invest.buy(1,'mine')
    clock.advance(2*3600)
    invest.buy(1,'bank')
    before=state.get(1)['money']
    invest.collect(1)
    assert state.get(1)['money']-before==220  # not bank income for those two hours
    clock.advance(1800)
    before=state.get(1)['money']
    invest.collect(1)
    assert state.get(1)['money']-before==2005
    money=state.get(1)['money'];invest.collect(1)
    assert state.get(1)['money']==money


def test_income_preserves_fractional_dollars(player,clock):
    player(1,'ir');invest.buy(1,'mine')
    clock.advance(33)
    invest.collect(1)
    rem=db.one('SELECT micro_dollars FROM invest_accrual WHERE uid=1')[0]
    assert 0<rem<1000000
    clock.advance(33)
    before=state.get(1)['money'];invest.collect(1)
    assert state.get(1)['money']-before==1


def test_contract_requires_real_consent_and_goods(player):
    player(1,'ir');player(2,'iq')
    assert 'ابتدا' in economy.contract(1,'iq')
    gid=economy.GOODS[0][0]
    economy._save_holdings(1,{gid:2})
    before=db.one('SELECT SUM(money) FROM users')[0]
    seller=state.get(1)['money'];buyer=state.get(2)['money']
    assert 'پیشنهاد' in economy.contract(1,'iq')
    assert state.get(1)['money']==seller and state.get(2)['money']==buyer
    assert 'دوطرفه انجام شد' in economy.contract_accept(2,'ir')
    assert economy.holdings(1)[gid]==1 and economy.holdings(2)[gid]==1
    assert db.one('SELECT SUM(money) FROM users')[0]==before
    money=state.get(1)['money']
    assert economy.contract_accept(2,'ir').startswith('⛔')
    assert state.get(1)['money']==money


def test_failed_contract_does_not_move_anything(player):
    player(1,'ir');player(2,'iq',0)
    gid=economy.GOODS[0][0];economy._save_holdings(1,{gid:1})
    economy.contract(1,'iq')
    assert 'کافی' in economy.contract_accept(2,'ir')
    assert economy.holdings(1)[gid]==1
    assert economy.holdings(2)=={}


def test_no_npc_contract_or_spying(player):
    player(1,'ir')
    assert 'خالی' in economy.contract(1,'us')
    assert 'خالی' in politics.spy(1,'us')


def test_other_country_cannot_remove_a_sanction(player):
    player(1,'ir');player(2,'iq');player(3,'us')
    economy.sanction(1,'iq')
    assert economy.sanctioned('iq')
    economy.sanction(3,'iq');economy.sanction(3,'iq')
    assert economy.sanctioned('iq')
    economy.sanction(1,'iq')
    assert not economy.sanctioned('iq')


def test_unrelated_countries_not_fined_by_hormuz(player,clock):
    player(1,'us')
    db.kv_set('toll_on','1')
    before=state.get(1)['money']
    clock.advance(5*86400)
    for _ in range(10):toll.enforce(1)
    assert state.get(1)['money']==before
    assert not toll.needs_pass(1)


def test_toll_pot_conserves_actual_paid_money(player,clock):
    from game import infra,straits,geo
    player(1,'ir',100000);player(2,'ae',1000)
    port=next(i for i in range(len(geo.CITIES['ir'])) if geo.is_port('ir',i))
    infra.build(1,'naval',port);clock.advance(3601)
    db.ex('UPDATE users SET money=1000 WHERE uid=1')
    straits.set_fee(1,'hormuz',50)
    toll.pay(2);toll.pay(2)
    assert state.get(2)['money']==1000-toll.TOLL
    assert straits.get('hormuz')['pot']==toll.TOLL
    toll.collect(1);toll.collect(1)
    assert state.get(1)['money']==1000+toll.TOLL
    assert db.one('SELECT SUM(money) FROM users')[0]==2000


def test_welfare_does_not_invent_coup_or_free_territory(player,clock):
    from game import geo,infra
    player(1,'ir');player(2,'iq')
    db.kv_set('colony:ir','iq')
    geo.occupy('ir','تهران','iq')
    welfare._save('ir',{'sat':10,'b':{},'ts':clock()})
    before=infra.city_state('ir',0)
    assert 'خودکار' in welfare.check_uprising('ir')
    assert geo.colony_of('ir')=='iq'
    assert geo.occupied('ir')==['تهران']
    assert infra.city_state('ir',0)==before
    assert not politics.regime_of('ir')


def test_one_player_revolt_possible_but_not_immediate(player,clock):
    player(1,'ir')
    politics.revolt_start(1)
    assert '۶ ساعت' in politics.revolt_support(1)
    assert not politics.regime_of('ir')
    clock.advance(6*3600+1)
    assert 'تغییر کرد' in politics.revolt_support(1)


def test_guide_reward_requires_every_page(player):
    player(1,'ir');before=state.get(1)['money']
    last=len(texts.HELP_PAGES)
    assert guide.mark_read(1,last,last)==''
    assert state.get(1)['money']==before
    for page in range(1,last):guide.mark_read(1,page,last)
    assert state.get(1)['money']==before+300
    guide.mark_read(1,1,last)
    assert state.get(1)['money']==before+300


def test_training_has_no_npc_loot_or_kills(player):
    player(1,'ir');before=state.get(1)
    assert 'بدون پول' in military.battle(1)
    after=state.get(1)
    assert after['money']==before['money'] and after['kills']==before['kills']
    assert after['xp']>before['xp']


def test_all_country_base_factors_are_close():
    factors=[catalog.country_factor(c) for c in countries.COUNTRIES]
    assert min(factors)>=0.97 and max(factors)<=1.04
    assert max(factors)/min(factors)<1.08
    assert all(6<=countries.spec_of(c)[1]<=10 for c in countries.COUNTRIES)
    assert len({tuple(welfare.needs(c).values()) for c in countries.COUNTRIES})==1


@pytest.mark.parametrize('value',[None,True,'a','-4','9'*5000])
def test_bad_numeric_text_safe(value):assert texts.to_int(value) is None


@pytest.mark.parametrize('value',['۱۲۳','١٢٣','123','۱۲۳٬۴۵۶'])
def test_persian_arabic_numbers(value):assert texts.to_int(value) is not None
