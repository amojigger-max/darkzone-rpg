import json
import pytest
import countries
import db
from game import straits,infra,geo,economy,state,invest,operations,campaign,un,rules,rewards,war


def naval(uid,cid,clock):
    port=next(i for i in range(len(geo.CITIES[cid])) if geo.is_port(cid,i))
    assert 'شروع شد' in infra.build(uid,'naval',port)
    clock.advance(3601)


@pytest.mark.parametrize('key',list(straits.CONTROLS))
def test_germany_cannot_close_tax_or_collect_someone_elses_strait(key,player):
    player(1,'de')
    r=straits.get(key);r['pot']=500;straits._save(key,r)
    before=state.get(1)['money']
    for result in (straits.set_open(1,key,False),straits.set_fee(1,key,100),straits.collect(1,key)):
        assert result.startswith('⛔')
    assert state.get(1)['money']==before
    assert straits.get(key)['pot']==500


@pytest.mark.parametrize('key',list(straits.CONTROLS))
def test_every_strait_has_its_own_real_controller(key,player,clock):
    cid=straits.CONTROLS[key][1];player(1,cid)
    naval(1,cid,clock)
    assert 'بسته شد' in straits.set_open(1,key,False)
    assert not straits.is_open(key)
    assert 'باز شد' in straits.set_open(1,key,True)  # reopening isn't trapped by close cooldown
    assert straits.is_open(key)
    assert 'تعرفه' in straits.set_fee(1,key,50)


def test_closed_strait_reopens_and_no_fee_charged_while_closed(player,clock):
    player(1,'ir');player(2,'ae');naval(1,'ir',clock)
    straits.set_fee(1,'hormuz',50);straits.set_open(1,'hormuz',False)
    before=state.get(2)['money']
    assert 'بسته' in straits.pay(2,'hormuz')
    assert state.get(2)['money']==before
    clock.advance(straits.CLOSE_MAX+1);straits.tick()
    assert straits.is_open('hormuz')
    straits.pay(2,'hormuz');straits.pay(2,'hormuz')
    assert state.get(2)['money']==before-50


def test_countryless_and_unrelated_accounts_are_not_fined(player,clock):
    player(1,'ir');player(2,'de');naval(1,'ir',clock)
    straits.set_fee(1,'hormuz',100)
    assert 'خارج' in straits.pay(2,'hormuz')
    assert not straits.trade_check(2)


def test_real_trade_blocked_until_required_route_pass_is_paid(player,clock):
    player(1,'ir');player(2,'ae');naval(1,'ir',clock)
    straits.set_fee(1,'hormuz',50)
    assert 'مجوز' in economy.trade_buy(2,'oil',1)
    assert economy.holdings(2)=={}
    straits.pay(2,'hormuz')
    assert 'واردات' in economy.trade_buy(2,'oil',1)
    assert economy.holdings(2)['oil']==1


def test_trade_and_investment_oil_are_different_assets(player,clock):
    player(1,'ir')
    economy.trade_buy(1,'oil',3)
    assert invest.rate(1)==0
    invest.buy(1,'oil')
    assert invest._bag(1)['oil']==1
    assert economy.holdings(1)['oil']==3
    economy.trade_sell(1,'oil',2)
    assert invest._bag(1)['oil']==1
    assert economy.holdings(1)['oil']==1
    invest.buy(1,'mine')
    assert economy.holdings(1)['oil']==1


def test_legacy_portfolio_split_never_doubles_oil(player):
    player(1,'ir')
    db.kv_set('inv:1',json.dumps({'mine':2,'oil':3,'gold':4}))
    assert invest._bag(1)=={'mine':2,'oil':3}
    assert economy.holdings(1)=={'gold':4}
    assert 'oil' not in economy.holdings(1)


def test_buy_sell_conserves_total_cash_and_cannot_loop_free_profit(player):
    player(1,'ir');pool=economy.market_pool()
    before=state.get(1)['money'];total=before+pool['money']
    for _ in range(20):
        economy.trade_buy(1,'oil',5);economy.trade_sell(1,'oil',5)
    assert state.get(1)['money']<before
    assert state.get(1)['money']+economy.market_pool()['money']==total
    assert economy.market_pool()['stock']['oil']==500
    assert not economy.holdings(1)


def test_market_wont_mint_cash_to_fill_an_insolvent_sell(player):
    player(1,'ir');economy._save_holdings(1,{'gold':1})
    p=economy.market_pool();p['money']=0;economy._save_pool(p)
    before=state.get(1)['money']
    assert 'نقدینگی' in economy.trade_sell(1,'gold',1)
    assert state.get(1)['money']==before and economy.holdings(1)['gold']==1


def test_inflation_tick_is_not_message_count_dependent(player,clock):
    player(1,'ir')
    one=economy.tick()
    for _ in range(50):assert economy.tick()==one
    for _ in range(2000):
        clock.advance(600);w=economy.tick()
        assert 45<=w['oil']<=140 and .90<=w['dollar']<=1.25 and 0<=w['inflation']<=.25
    assert economy.world()['inflation']<.05  # peace converges instead of compounding to 300%


def test_explicit_lift_does_not_create_or_erase_somebody_elses_sanction(player,clock):
    player(1,'ir');player(2,'iq');player(3,'us')
    economy.apply_sanction(1,'iq');economy.apply_sanction(3,'iq')
    assert 'سایر' in economy.lift_sanction(1,'iq')
    before=state.get(1)['money']
    assert 'تازه‌ای ایجاد نشد' in economy.lift_sanction(1,'iq')
    assert economy.sanctioned('iq') and state.get(1)['money']==before
    clock.advance(86401);economy.tick()
    assert not economy.sanctioned('iq')


def test_named_operation_needs_preparation_and_no_double_launch(player,clock):
    player(1,'ir');player(2,'iq')
    assert 'ثبت شد' in operations.create(1,'iq','سپیده <نام دلخواه>')
    op=db.one('SELECT id FROM operation_plans')[0]
    assert 'کامل نشده' in operations.activate(1,op)
    assert not campaign.war_of('ir')
    clock.advance(3601)
    assert 'اعلام جنگ' in operations.activate(1,op)
    before=state.get(1)['money']
    assert 'مرحلهٔ آماده' in operations.activate(1,op)
    assert state.get(1)['money']==before
    assert db.one('SELECT COUNT(*) FROM wars')[0]==1


def test_operation_bonus_uses_real_waves_only_and_expires(active_war,equip,clock,monkeypatch):
    assert 'ثبت شد' in operations.create(1,'iq','شش موج آزمایشی')
    clock.advance(3601);op=db.one('SELECT id FROM operation_plans')[0];operations.activate(1,op)
    assert 'متعلق' in operations.activate(2,op)
    assert campaign.strike(1,'زمینی',5,'99.power').startswith('⛔')
    assert db.one('SELECT uses FROM operation_plans')[0]==0
    monkeypatch.setattr(campaign.random,'random',lambda:0.99)
    for i in range(6):
        equip(1,'زمینی')
        msg=campaign.strike(1,'زمینی',1,'1.power')
        assert '۱۰٪ هماهنگی' in msg
        clock.advance(301)
    assert db.one('SELECT uses FROM operation_plans')[0]==6
    equip(1,'زمینی')
    assert '۱۰٪ هماهنگی' not in campaign.strike(1,'زمینی',1,'1.power')


@pytest.mark.parametrize('name',[None,'ab','x'*41,''])
def test_bad_operation_names_dont_charge(name,player):
    player(1,'ir');player(2,'iq');before=state.get(1)['money']
    assert operations.create(1,'iq',name).startswith('⛔')
    assert state.get(1)['money']==before


def test_missile_hourly_limits_are_shared_and_prelaunch(active_war,equip,clock):
    for _ in range(2):
        equip(1,'موشکی')
        assert 'در راه' in campaign.launch_missile(1,3,'1.power')
        clock.advance(301);campaign.tick()
    equip(1,'موشکی');before=db.kv_get(f"ammo:{active_war['id']}:ir")
    assert '۶ موشک' in campaign.launch_missile(1,1,'1.power')
    assert db.kv_get(f"ammo:{active_war['id']}:ir")==before
    assert db.one('SELECT SUM(shots) FROM missile_launches')[0]==6


def test_regional_missile_cannot_teleport_across_globe(player,equip,clock):
    player(1,'ir');player(2,'us');campaign.declare(1,'us');clock.advance(3601)
    # Iranian regional missiles in the game cannot hit another operational continent.
    equip(1,'موشکی',cid='ir')
    assert 'برد مناسب' in campaign.launch_missile(1,1,'1.power')
    assert db.one('SELECT COUNT(*) FROM missile_launches')[0]==0


def test_un_one_vote_per_country_real_quorum_and_sanction_lift(player,clock):
    player(1,'ir');player(2,'iq');player(3,'us')
    economy.apply_sanction(1,'iq')
    assert 'قطعنامه' in un.propose(2,'sanctions','iq')
    rid=db.one('SELECT id FROM un_resolutions')[0]
    un.vote(3,rid,'yes');un.vote(3,rid,'yes')
    assert db.one('SELECT COUNT(*) FROM un_votes')[0]==2
    assert economy.sanctioned('iq')
    clock.advance(un.MIN_DEBATE+1);un.tick()
    assert not economy.sanctioned('iq')
    assert db.one('SELECT status FROM un_resolutions')[0]=='passed'
    assert 'سازمان ملل' in economy.apply_sanction(1,'iq')


def test_un_without_two_real_countries_cannot_create_votes(player):
    player(1,'ir')
    assert 'دو کشور' in un.propose(1,'sanctions','ir')
    assert db.one('SELECT COUNT(*) FROM un_resolutions')[0]==0


def test_un_aid_is_from_fund_and_paid_once(player,clock):
    player(1,'ir');player(2,'iq');player(3,'us')
    before=db.one('SELECT SUM(money) FROM users')[0]
    un.donate(1,3000)
    un.propose(1,'aid','iq');rid=db.one('SELECT id FROM un_resolutions')[0]
    un.vote(2,rid,'yes');clock.advance(601);un.tick()
    assert un.fund()==1150
    assert db.one('SELECT SUM(money) FROM users')[0]+un.fund()==before
    beneficiary=state.get(2)['money'];un.tick()
    assert state.get(2)['money']==beneficiary


def test_un_cannot_end_war_without_both_parties_consent(active_war,player,clock):
    player(3,'us');un.propose(1,'ceasefire','iq');rid=db.one('SELECT id FROM un_resolutions')[0]
    un.vote(3,rid,'yes');clock.advance(601);un.tick()
    assert campaign.war_of('iq')
    assert 'به‌زور' in db.one('SELECT result FROM un_resolutions')[0]


def test_un_can_broker_consensual_peace(active_war,player,clock):
    player(3,'us');un.propose(1,'ceasefire','iq');rid=db.one('SELECT id FROM un_resolutions')[0]
    un.vote(2,rid,'yes');clock.advance(601);un.tick()
    assert not campaign.war_of('iq') and not geo.colony_of('iq')


def test_general_grant_for_all_without_country_preassignment(clock):
    rewards.schedule()
    state.ensure(55,'Player');assert not state.get(55)['country']
    assert rewards.award_pending(55)==[]
    assert state.enlist(55,'de','Germany')
    assert state.get(55)['money']==31000
    assert rewards.award_pending(55)==[]
    assert state.get(55)['money']==31000


def test_alliance_can_end_but_cannot_enable_instant_betrayal(player,clock):
    player(1,'ir');player(2,'iq')
    war.alliance_request(1,'iq');war.alliance_accept(2,'ir')
    db.kv_set('staging:ir:iq',clock()+10000)
    assert '۱۲ ساعت' in war.end_alliance(1,'iq')
    assert war.allies_of('ir')==[] and not db.kv_get('staging:ir:iq')
    assert 'آتش‌بس' in campaign.declare(1,'iq')
    truce=db.kv_get('truce:iq:ir');war.end_alliance(1,'iq')
    assert db.kv_get('truce:iq:ir')==truce


def test_equipment_role_and_range_cannot_be_confused_by_emoji_or_substrings():
    from game import catalog
    assert catalog.primary('dhow')=='دریایی'
    assert not catalog.supports('dhow','زمینی')
    assert catalog.primary('ka52')=='هوایی'
    assert not catalog.supports('ka52','چندمنظوره')
    assert catalog.range_band('bayraktar_ua')==2
    assert catalog.range_band('tb2x')==2
    assert catalog.range_band('b2')==3
    assert catalog.range_band('hwasong18')==3
    assert catalog.supports('f35','چندمنظوره')


def test_every_nation_has_baseline_playable_arms_not_only_a_balance_label():
    from game import catalog
    for cid,c in countries.COUNTRIES.items():
        kinds={catalog.primary(i) for i in c['items']}
        assert {'زمینی','هوایی','موشکی','توپخانه','پهپادی','پدافندی'}<=kinds,cid
        if geo.coastal(cid):assert 'دریایی' in kinds,cid
