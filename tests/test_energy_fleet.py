import json
import pytest
import countries
import db
from game import energy,fleet,infra,geo,sea_routes,straits,state,economy,campaign,military,rules


def port(cid):return next(i for i in geo.PORT_NODES[cid] if sea_routes.port_sea(cid,i))


def facility(uid,cid,key,clock,idx=None):
    idx=port(cid) if idx is None else idx
    assert 'شروع شد' in infra.build(uid,key,idx)
    clock.advance(infra.build_seconds(key)+1)
    return idx


def ready_ship(uid,cid,clock,name='آزمون <&>',kind='coastal'):
    idx=facility(uid,cid,'shipyard',clock)
    assert 'سفارش' in fleet.build(uid,idx,kind,name)
    sid=db.one('SELECT MAX(id) FROM tankers')[0]
    clock.advance(fleet.CLASSES[kind][3]+1);fleet.progress_builds(cid)
    assert db.one('SELECT status FROM tankers WHERE id=?',(sid,))[0]=='docked'
    return sid,idx


def offer_trip(seller,buyer,sid,source,dest,srcidx,amount=20,escort=0,cargo='fuel'):
    energy.settle(source,exact=True);energy.settle(dest,exact=True)
    db.ex('UPDATE city_energy SET '+cargo+'_milli=120000 WHERE cid=? AND city=?',(source,srcidx))
    dst=port(dest)
    assert 'پیشنهاد حمل' in fleet.offer(seller,sid,dest,dst,cargo,amount,escort)
    return db.one('SELECT MAX(id) FROM voyages')[0]


def finish_outbound(vid,clock):
    for _ in range(15):
        v=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
        if v['delivered_at']:return v
        clock.advance(max(1,v['leg_due']-clock()))
        fleet.tick_one(vid)
    raise AssertionError('voyage did not deliver')


def total_cash():
    return db.one('SELECT SUM(money) FROM users')[0]+db.one('SELECT COALESCE(SUM(escrow),0) FROM voyages')[0]+sum(straits.get(k)['pot'] for k in straits.CONTROLS)


def test_starting_power_is_seeded_once_and_does_not_heal(player):
    player(1,'ir');n=db.one("SELECT COUNT(*) FROM structures WHERE kind='power_plant'")[0]
    assert n==len(geo.CITIES['ir'])
    infra.damage('ir','power_plant',80,0)
    stock=energy.fuel('ir');infra.ensure('ir');infra.ensure('ir')
    assert db.one("SELECT hp FROM structures WHERE cid='ir' AND city=0 AND kind='power_plant'")[0]==20
    assert energy.fuel('ir')==stock
    assert energy.electricity('ir',0)==40


def test_blackout_changes_real_defense_and_heavy_purchase_gate(player):
    from game import defense
    player(1,'ir');before=defense.effective('ir','ضد موشک')
    for idx in range(len(geo.CITIES['ir'])):infra.damage('ir','power_plant',100,idx)
    assert infra.state_of('ir')['power']==25
    assert defense.effective('ir','ضد موشک')<before
    heavy=next(i for i in countries.COUNTRIES['ir']['items'] if countries.ITEMS[i][5]>=3000)
    assert 'برق' in military.buy(1,heavy)
    assert not geo.colony_of('ir')


def test_upgrading_power_keeps_previous_generation_until_completion(player,clock):
    player(1,'ir')
    assert 'شروع شد' in infra.build(1,'power_plant',0)
    assert energy.electricity('ir',0)==100
    assert db.one("SELECT previous_level FROM structures WHERE cid='ir' AND city=0 AND kind='power_plant'")[0]==1
    clock.advance(infra.build_seconds('power_plant',2)+1)
    infra.damage('ir','power_plant',40,0)
    assert energy.electricity('ir',0)>70


def test_refinery_starts_at_ready_time_and_converts_actual_crude_only(player,clock):
    player(1,'ir');economy._save_holdings(1,{'oil':10})
    assert 'منتقل' in energy.import_crude(1,0,10)
    assert economy.holdings(1).get('oil',0)==0
    assert 'شروع شد' in infra.build(1,'refinery',0)
    clock.advance(infra.build_seconds('refinery')-1);energy.settle('ir',exact=True)
    assert energy.stock('ir',0,'crude')==10000
    clock.advance(3601);energy.settle('ir',exact=True)
    assert energy.stock('ir',0,'crude')==7000
    before=energy.stock('ir',0,'crude');energy.settle('ir',exact=True)
    assert energy.stock('ir',0,'crude')==before


def test_depot_damage_is_local_and_cannot_clear_all_national_resources(player,clock):
    player(1,'ir');facility(1,'ir','fuel_depot',clock,0)
    energy.settle('ir',exact=True)
    db.ex("UPDATE city_energy SET fuel_milli=450000,crude_milli=300000 WHERE cid='ir' AND city=0")
    other=energy.stock('ir',1,'fuel')
    infra.damage('ir','fuel_depot',18,0)
    assert energy.stock('ir',0,'fuel')==369000
    assert energy.stock('ir',0,'crude')==246000
    assert energy.stock('ir',1,'fuel')==other


def test_buy_sell_fuel_has_spread_and_finite_conserved_liquidity(player):
    player(1,'ir');pool=energy._market_fuel();cash=state.get(1)['money'];total=cash+pool['money']
    energy.buy_fuel(1,0,50);energy.sell_fuel(1,0,50)
    assert state.get(1)['money']==cash-100
    assert state.get(1)['money']+economy.market_pool()['money']==total
    assert economy.market_pool()['stock']['fuel']==pool['stock']['fuel']


@pytest.mark.parametrize('amount',[0,-1,True,1.5,201,None])
def test_invalid_fuel_amounts_do_not_spend(amount,player):
    player(1,'ir');cash=state.get(1)['money'];fuel=energy.fuel('ir')
    assert energy.buy_fuel(1,0,amount).startswith('⛔')
    assert state.get(1)['money']==cash and energy.fuel('ir')==fuel


def test_refining_is_independent_of_view_frequency_and_downtime(player,clock):
    t0=clock();results=[]
    for world in (-111,-112):
        clock.value=t0
        with db.world(world):
            countries.init_items();player(1,'ir')
            db.ex("INSERT INTO structures(cid,city,kind,hp,ready_at,created) VALUES('ir',0,'refinery',100,?,?)",(t0,t0))
            db.ex("UPDATE city_energy SET crude_milli=150000 WHERE cid='ir' AND city=0")
            if world==-111:
                clock.advance(6*3600);energy.settle('ir')
            else:
                for _ in range(360):clock.advance(60);energy.settle('ir')
            results.append([(r['crude_milli'],r['fuel_milli']) for r in db.q("SELECT * FROM city_energy WHERE cid='ir' ORDER BY city")])
    assert results[0]==results[1]


def test_every_coastal_port_has_a_real_game_sea_and_landlocked_do_not():
    for cid in countries.COUNTRIES:
        for idx in geo.PORT_NODES.get(cid,[]):
            if geo.coastal(cid):assert sea_routes.port_sea(cid,idx) in sea_routes.SEAS,(cid,idx)
        if not geo.coastal(cid):assert all(sea_routes.port_sea(cid,i) is None for i in range(len(geo.CITIES[cid])))
    assert sea_routes.port_sea('us',2)=='pacific'
    assert sea_routes.port_sea('ir',4)=='gulf'


def test_shipyard_is_required_and_tanker_is_never_ready_immediately(player,clock):
    player(1,'ir');idx=port('ir')
    assert 'کشتی‌سازی' in fleet.build(1,idx)
    facility(1,'ir','shipyard',clock,idx)
    assert 'سفارش' in fleet.build(1,idx,name='نفت‌کش اول')
    s=db.one('SELECT * FROM tankers');assert s['status']=='building'
    fleet.progress_builds('ir');assert db.one('SELECT status FROM tankers')[0]=='building'
    assert 'باید در بندر' in fleet.offer(1,s['id'],'iq',port('iq'),'fuel',20)


def test_shipyard_damage_pauses_without_retroactively_finishing_a_ship(player,clock):
    player(1,'ir');idx=facility(1,'ir','shipyard',clock)
    fleet.build(1,idx);clock.advance(1800);fleet.progress_builds('ir')
    before=db.one('SELECT build_work FROM tankers')[0]
    infra.damage('ir','shipyard',100,idx);clock.advance(7200);fleet.progress_builds('ir')
    assert db.one('SELECT build_work FROM tankers')[0]==before
    assert db.one('SELECT status FROM tankers')[0]=='building'
    infra.repair(1,'shipyard',idx);clock.advance(600);fleet.progress_builds('ir')
    assert db.one('SELECT build_work FROM tankers')[0]<before


def test_shipping_requires_consent_escrow_conserves_cash_and_delivers_once(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx)
    price=db.one('SELECT price FROM voyages')[0];buyer=state.get(2)['money'];cash=total_cash()
    assert db.one('SELECT escrow FROM voyages')[0]==0
    assert 'آغاز شد' in fleet.accept(2,vid)
    assert state.get(2)['money']==buyer-price and total_cash()==cash
    assert 'پاسخ داده' in fleet.accept(2,vid)
    before=state.get(1)['money'];v=finish_outbound(vid,clock)
    assert v['escrow']==0 and v['delivered_at']
    assert state.get(1)['money']==before+price and total_cash()==cash
    fleet.tick_one(vid);assert state.get(1)['money']==before+price


def test_restart_after_deadline_still_delivers_a_trip_that_arrived_on_time(player,clock):
    with db.world(-411):
        countries.init_items()
        player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
        vid=offer_trip(1,2,sid,'de','ir',idx);fleet.accept(2,vid)
        clock.advance(80*3600);db.close_all();fleet.tick_one(vid)
        v=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
        assert v['delivered_at'] and v['outcome']=='تحویل کامل' and v['escrow']==0


def test_acceptance_rolls_back_cargo_cash_and_escorts_together(player,equip,clock,monkeypatch):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    facility(1,'de','naval',clock,idx);equip(1,'دریایی')
    vid=offer_trip(1,2,sid,'de','ir',idx,escort=1)
    cash=state.get(2)['money'];cargo=energy.stock('de',idx,'fuel')
    monkeypatch.setattr(notifications_proxy(),'emit',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('outbox failure')))
    with pytest.raises(RuntimeError):fleet.accept(2,vid)
    assert state.get(2)['money']==cash and energy.stock('de',idx,'fuel')==cargo
    assert db.one('SELECT COUNT(*) FROM naval_escorts')[0]==0
    assert db.one('SELECT status FROM voyages')[0]=='offered'


def notifications_proxy():
    from game import notifications
    return notifications


def test_germany_only_pays_iran_toll_never_collects_it(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    facility(2,'ir','naval',clock);straits.set_fee(2,'hormuz',50)
    vid=offer_trip(1,2,sid,'de','ir',idx)
    cash=state.get(1)['money'];fleet.accept(2,vid)
    assert state.get(1)['money']==cash-50
    assert straits.get('hormuz')['pot']==50
    assert fleet.straits.collect(1,'hormuz').startswith('⛔')
    before=state.get(2)['money'];straits.collect(2,'hormuz')
    assert state.get(2)['money']==before+50


def test_closed_suez_has_a_longer_cape_detour_and_closed_hormuz_traps_gulf(player,clock):
    player(1,'eg');player(2,'ir')
    facility(1,'eg','naval',clock);facility(2,'ir','naval',clock)
    normal=sea_routes.route('atlantic','gulf')
    straits.set_open(1,'suez',False)
    detour=sea_routes.route('atlantic','gulf')
    assert sum(p['seconds'] for p in detour)>sum(p['seconds'] for p in normal)
    assert all(p['gate']!='suez' for p in detour)
    straits.set_open(2,'hormuz',False)
    assert sea_routes.route('atlantic','gulf') is None


def test_gate_closure_delays_only_an_uncrossed_checkpoint_and_reopening_is_early(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    facility(2,'ir','naval',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx);fleet.accept(2,vid)
    straits.set_open(2,'hormuz',False)
    v=dict(db.one('SELECT * FROM voyages'))
    path=json.loads(v['route']);clock.advance(sum(p['seconds'] for p in path))
    fleet.tick_one(vid)
    assert db.one('SELECT status FROM voyages')[0]=='held'
    cash=state.get(1)['money'];straits.set_open(2,'hormuz',True);fleet.tick_one(vid)
    assert db.one('SELECT delivered_at FROM voyages')[0]
    assert state.get(1)['money']>cash


def test_escorted_units_cannot_be_used_or_repaired_while_at_sea(player,equip,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    facility(1,'de','naval',clock,idx);iid=equip(1,'دریایی',qty=3,dur=80)
    vid=offer_trip(1,2,sid,'de','ir',idx,escort=3);fleet.accept(2,vid)
    assert fleet.escort_locked(1,iid)==3
    assert campaign._equipment(1,'دریایی',1) is None
    assert 'اسکورت' in military.upgrade(1,iid)
    before=state.get(1)['money'];military.repair(1)
    assert db.one('SELECT dur FROM inventory WHERE uid=1 AND iid=?',(iid,))[0]==80
    assert state.get(1)['money']==before


def combat_ship(player,equip,clock):
    player(1,'ir');player(2,'iq')
    sid,idx=ready_ship(2,'iq',clock)
    facility(1,'ir','naval',clock);equip(1,'دریایی',qty=5)
    assert 'اعلام جنگ' in campaign.declare(1,'iq');clock.advance(3601)
    return sid,idx


def test_tanker_first_wave_never_sinks_or_damages_the_whole_port(player,equip,clock,monkeypatch):
    sid,idx=combat_ship(player,equip,clock)
    monkeypatch.setattr(fleet.random,'random',lambda:0.99)
    result=fleet.attack(1,sid,'دریایی',3)
    assert 'نفت‌کش' in result
    hp=db.one('SELECT hp FROM tankers')[0]
    assert 80<=hp<100
    assert infra.city_state('iq',idx)['port']==100
    assert db.one('SELECT sea_a FROM campaigns')[0]==0
    assert not geo.colony_of('iq')


def test_missile_against_tanker_is_durable_and_uses_same_hourly_limit(player,equip,clock):
    with db.world(-412):
        countries.init_items()
        sid,_=combat_ship(player,equip,clock);equip(1,'موشکی',qty=5,cid='ir')
        result=fleet.attack(1,sid,'موشکی',3)
        assert 'در راه' in result and db.one('SELECT hp FROM tankers')[0]==100
        m=db.one('SELECT * FROM missions');assert json.loads(m['equipment'])['asset']['id']==sid
        clock.advance(30);db.close_all();campaign.resolve_mission(m['id'])
        assert db.one('SELECT status FROM missions')[0]=='resolved'
        assert db.one('SELECT SUM(shots) FROM missile_launches')[0]==3
        clock.advance(301);equip(1,'موشکی',qty=5,cid='ir');fleet.attack(1,sid,'موشکی',3);clock.advance(301);campaign.tick()
        assert '۶ موشک' in fleet.attack(1,sid,'موشکی',1)


def test_distant_navy_cannot_teleport_to_gulf(player,equip,clock):
    player(1,'de');player(2,'ir');sid,_=ready_ship(2,'ir',clock)
    facility(1,'de','naval',clock);equip(1,'دریایی');campaign.declare(1,'ir');clock.advance(3601)
    before=energy.fuel('de');w=campaign.war_of('de');ammo=db.kv_get(f'ammo:{w["id"]}:de')
    assert 'مستقر نداری' in fleet.attack(1,sid,'دریایی',3)
    assert energy.fuel('de')==before and db.kv_get(f'ammo:{w["id"]}:de')==ammo


def test_partial_cargo_and_sinking_refund_do_not_mint_money(player,equip,clock,monkeypatch):
    player(1,'ir');player(2,'iq');player(3,'de');sid,idx=ready_ship(2,'iq',clock)
    vid=offer_trip(2,3,sid,'iq','de',idx);fleet.accept(3,vid)
    facility(1,'ir','naval',clock);equip(1,'دریایی');campaign.declare(1,'iq');clock.advance(3601)
    monkeypatch.setattr(fleet.random,'random',lambda:0.99)
    # Ship is still in the Gulf at this point only until its first crossing; force a legal docked target for deterministic battle setup.
    db.ex("UPDATE voyages SET region='gulf',leg_due=? WHERE id=?",(clock()+86400,vid))
    db.ex('UPDATE tankers SET hp=10 WHERE id=?',(sid,))
    before=total_cash();buyer=state.get(3)['money'];escrow=db.one('SELECT escrow FROM voyages')[0]
    assert 'غرق شد' in fleet.attack(1,sid,'دریایی',3)
    assert db.one('SELECT status FROM tankers')[0]=='sunk'
    assert db.one('SELECT remaining_milli FROM voyages')[0]==0
    assert db.one('SELECT escrow FROM voyages')[0]==0
    assert state.get(3)['money']==buyer+escrow and total_cash()==before
    fleet.tick_one(vid);assert state.get(3)['money']==buyer+escrow


def test_partial_delivery_pays_only_arrived_cargo_and_refunds_difference(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx);fleet.accept(2,vid)
    v=db.one('SELECT * FROM voyages');price=v['price']
    db.ex('UPDATE voyages SET remaining_milli=remaining_milli/2 WHERE id=?',(vid,))
    seller=state.get(1)['money'];buyer=state.get(2)['money'];cash=total_cash()
    finish_outbound(vid,clock)
    assert state.get(1)['money']==seller+price//2
    assert state.get(2)['money']==buyer+price-price//2
    assert total_cash()==cash and db.one('SELECT escrow FROM voyages')[0]==0


def test_damaged_destination_port_holds_then_refunds_without_teleporting_cargo(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx);fleet.accept(2,vid)
    infra.damage('ir','port',100,port('ir'))
    clock.advance(5*3600);fleet.tick_one(vid)
    assert db.one('SELECT status FROM voyages')[0]=='unloading'
    buyer=state.get(2)['money'];escrow=db.one('SELECT escrow FROM voyages')[0]
    clock.advance(72*3600);fleet.tick_one(vid)
    v=db.one('SELECT * FROM voyages')
    assert v['status']=='returning' and v['remaining_milli']>0
    assert state.get(2)['money']==buyer+escrow and v['escrow']==0
    fleet.tick_one(vid);assert state.get(2)['money']==buyer+escrow


def test_offer_cannot_charge_wrong_buyer_or_old_leader(player,clock):
    player(1,'de');player(2,'ir');player(3,'iq');sid,idx=ready_ship(1,'de',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx)
    before=state.get(3)['money'];assert fleet.accept(3,vid).startswith('⛔')
    assert state.get(3)['money']==before and db.one('SELECT escrow FROM voyages')[0]==0
    db.ex('UPDATE users SET is_leader=0 WHERE uid=1')
    before=state.get(2)['money'];assert 'فروشنده' in fleet.accept(2,vid)
    assert state.get(2)['money']==before


def test_offer_created_before_sanction_cannot_be_accepted_until_lifted(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx)
    economy.apply_sanction(1,'ir')
    before=state.get(2)['money'];assert 'تحریم' in fleet.accept(2,vid)
    assert state.get(2)['money']==before
    economy.lift_sanction(1,'ir')
    assert 'آغاز شد' in fleet.accept(2,vid)


def test_initial_reset_clears_energy_and_voyages_but_keeps_countryless_rule(clock):
    import migrations
    with db.world(-413):
        countries.init_items();state.enlist(1,'ir','A');state.enlist(2,'iq','B')
        assert db.one('SELECT COUNT(*) FROM city_energy')[0]>0
    migrations.reset_game(-413,'marine-reset',confirmed=True,special_rewards=True)
    with db.world(-413):
        assert db.one('SELECT COUNT(*) FROM users WHERE country IS NOT NULL')[0]==0
        for table in ('tankers','voyages','naval_escorts','city_energy','structures'):
            assert db.one(f'SELECT COUNT(*) FROM {table}')[0]==0
        assert state.get(1)['money']==1000


def test_unclaimed_countries_do_not_run_an_npc_fuel_economy(clock):
    infra.ensure('ir');before=energy.fuel('ir')
    clock.advance(30*86400);energy.settle('ir')
    assert energy.fuel('ir')==before
    state.enlist(1,'ir','New leader')
    energy.settle('ir')
    assert energy.fuel('ir')==before
    assert infra.state_of('ir')['power']==100


def test_actual_fuel_exhaustion_requires_refuelling_not_free_restart(player,clock):
    player(1,'ir');clock.advance(61*3600);energy.settle('ir',exact=True)
    assert energy.fuel('ir')==0 and infra.state_of('ir')['power']==25
    infra.ensure('ir');assert energy.fuel('ir')==0
    assert 'ذخیره شد' in energy.buy_fuel(1,0,50)
    assert infra.state_of('ir')['power']==100


def test_supply_shortage_prevents_missile_without_spending_any_launch_budget(active_war,equip):
    equip(1,'موشکی',cid='ir')
    db.ex("UPDATE city_energy SET fuel_milli=0 WHERE cid='ir'")
    ammo=db.kv_get(f'ammo:{active_war["id"]}:ir')
    assert 'سوخت' in campaign.launch_missile(1,3,'1.power')
    assert db.kv_get(f'ammo:{active_war["id"]}:ir')==ammo
    assert db.one('SELECT COUNT(*) FROM missile_launches')[0]==0


def test_local_power_station_affects_local_air_defense_not_another_city(player):
    from game import defense
    player(1,'ir')
    before=defense.effective('ir','ضد موشک',0)
    other=defense.effective('ir','ضد موشک',1)
    infra.damage('ir','power_plant',100,0)
    assert defense.effective('ir','ضد موشک',0)<before
    assert defense.effective('ir','ضد موشک',1)==other


def test_facility_bonus_is_bounded_and_frozen_with_a_missile(active_war,equip,clock):
    for kind in ('command','missile_base'):
        db.ex('INSERT INTO structures(cid,city,kind,level,hp,ready_at,created) VALUES(?,0,?,3,100,?,?)',('ir',kind,clock(),clock()))
    equip(1,'موشکی',cid='ir')
    campaign.launch_missile(1,1,'1.power')
    m=db.one('SELECT * FROM missions');data=json.loads(m['equipment'])
    assert data['facility_mult']==pytest.approx(1.096)
    infra.damage('ir','command',100,0);infra.damage('ir','missile_base',100,0)
    clock.advance(30);campaign.resolve_mission(m['id'])
    assert db.one('SELECT status FROM missions')[0]=='resolved'
    assert json.loads(db.one('SELECT equipment FROM missions')[0])['facility_mult']==pytest.approx(1.096)


def test_toll_price_increase_needs_a_new_offer_not_a_surprise_debit(player,clock):
    player(1,'de');player(2,'ir');sid,idx=ready_ship(1,'de',clock)
    facility(2,'ir','naval',clock)
    vid=offer_trip(1,2,sid,'de','ir',idx)
    straits.set_fee(2,'hormuz',100)
    seller=state.get(1)['money'];buyer=state.get(2)['money']
    assert 'سقف پیشنهاد' in fleet.accept(2,vid)
    assert state.get(1)['money']==seller and state.get(2)['money']==buyer
    assert db.one('SELECT escrow FROM voyages')[0]==0


def test_all_controlled_straits_are_part_of_shipping_and_taiwan_has_a_detour(player,clock):
    assert set(straits.CONTROLS)<={gate for _,_,gate,_ in sea_routes.EDGES if gate}
    player(1,'cn');facility(1,'cn','naval',clock)
    path=sea_routes.route('west_pacific','south_china')
    assert [p['gate'] for p in path]==['taiwan']
    straits.set_open(1,'taiwan',False)
    detour=sea_routes.route('west_pacific','south_china')
    assert detour and all(p['gate']!='taiwan' for p in detour)
    assert sum(p['seconds'] for p in detour)>sum(p['seconds'] for p in path)


def test_additive_migration_of_old_structures_preserves_health_and_level(tmp_path,clock):
    import sqlite3
    from pathlib import Path
    from schema import SCHEMA,UPGRADE_SCHEMA
    path=Path(db.game_path(-415));path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path)
    con.executescript(SCHEMA+UPGRADE_SCHEMA.split('CREATE TABLE IF NOT EXISTS city_energy')[0])
    con.execute("INSERT INTO city_state(cid,city,name,power) VALUES('ir',0,'تهران',91)")
    con.execute("INSERT INTO structures(cid,city,kind,level,hp,ready_at,created) VALUES('ir',0,'base',2,37,?,?)",(clock()-100,clock()-1000))
    con.commit();con.close()
    with db.world(-415):
        r=db.one('SELECT * FROM structures')
        assert r['level']==2 and r['hp']==37 and r['previous_level']==0
        assert db.one('SELECT power FROM city_state')[0]==91
        assert db.one('PRAGMA integrity_check')[0]=='ok'


def test_minor_release_does_not_repeat_previous_cash_award(clock):
    import release
    from game import rewards
    with db.world(-416):
        countries.init_items();state.enlist(55,'de','Player')
        rewards.schedule();rewards.award_pending(55)
        before=state.get(55)['money'];assert before==31000
        db.kv_set('release:v41-advanced-20260907',clock())
        infra.damage('de','power_plant',100,0)
    result=release.apply(-416,confirmed=True)
    assert result['changed'] and result['grant_records_paid']==0
    with db.world(-416):
        assert state.get(55)['money']==before
        assert db.one("SELECT hp FROM structures WHERE cid='de' AND city=0 AND kind='power_plant'")[0]==0
    assert not release.apply(-416,confirmed=True)['changed']


def test_sinking_notification_also_tags_the_neutral_cargo_buyer(player,equip,clock,monkeypatch):
    with db.world(-417):
        countries.init_items();player(1,'ir');player(2,'iq');player(3,'de')
        sid,idx=ready_ship(2,'iq',clock)
        vid=offer_trip(2,3,sid,'iq','de',idx);fleet.accept(3,vid)
        facility(1,'ir','naval',clock);equip(1,'دریایی')
        campaign.declare(1,'iq');clock.advance(3601)
        db.ex("UPDATE voyages SET region='gulf',leg_due=? WHERE id=?",(clock()+86400,vid))
        db.ex('UPDATE tankers SET hp=1 WHERE id=?',(sid,))
        monkeypatch.setattr(fleet.random,'random',lambda:0.99)
        fleet.attack(1,sid,'دریایی',3)
        last=db.one('SELECT body FROM outbox ORDER BY id DESC')[0]
        assert 'tg://user?id=3' in last and 'tg://user?id=1' in last and 'tg://user?id=2' in last
