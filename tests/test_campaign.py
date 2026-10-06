import json
import pytest
import countries
import db
from game import campaign,war,catalog,defense,geo,infra,rules,state


@pytest.mark.parametrize('mode',list(rules.MODES))
def test_war_modes_enforce_own_timing(mode,player,clock):
    player(1,'ir');player(2,'iq')
    msg=war.declare(1,'iq',mode)
    assert 'اعلام جنگ' in msg
    w=war.war_of('ir');cp=campaign.ensure_campaign(w)
    assert cp['mode']==mode
    assert cp['ready_at']==w['started']+rules.MODES[mode].warning
    assert cp['min_end']==w['started']+rules.MODES[mode].minimum
    assert w['ends']==w['started']+rules.MODES[mode].maximum


def test_no_npc_or_duplicate_target_wars(player):
    player(1,'ir');player(2,'iq');player(3,'tr')
    assert 'NPC' in war.declare(1,'us')
    assert not war.war_of('ir')
    assert 'اعلام جنگ' in war.declare(1,'iq')
    balance=state.get(3)['money']
    assert 'درگیر' in war.declare(3,'iq')
    assert not war.war_of('tr')
    assert state.get(3)['money']==balance


def test_civilian_cannot_declare(player):
    player(1,'ir');player(2,'iq')
    db.ex('UPDATE users SET is_leader=0 WHERE uid=1')
    assert 'رهبر' in war.declare(1,'iq')
    assert not war.war_of('ir')


def test_new_country_gets_preparation_grace(player,clock):
    player(1,'ir');player(2,'iq')
    db.kv_set('claimed:iq',clock())
    assert 'یک ساعت' in war.declare(1,'iq')
    assert db.one('SELECT COUNT(*) FROM wars')[0]==0


@pytest.mark.parametrize('count',[-999,-1,0,6,10000000,'2',1.2,True,None])
def test_bad_counts_do_not_consume_resources(count,active_war,equip):
    iid=equip(1,'زمینی')
    before=dict(db.one('SELECT * FROM inventory WHERE uid=1 AND iid=?',(iid,)))
    ammo=db.kv_get(f"ammo:{active_war['id']}:ir")
    assert campaign.strike(1,'زمینی',count).startswith('⛔')
    assert dict(db.one('SELECT * FROM inventory WHERE uid=1 AND iid=?',(iid,)))==before
    assert db.kv_get(f"ammo:{active_war['id']}:ir")==ammo
    assert not db.kv_get('strike:1')


@pytest.mark.parametrize('target',['unknown','99.power','-1.power','1.hack','1.portfolio',{},True])
def test_invalid_city_or_target_does_not_spend(target,active_war,equip):
    equip(1,'زمینی')
    before=db.kv_get(f"ammo:{active_war['id']}:ir")
    assert campaign.strike(1,'زمینی',1,target).startswith('⛔')
    assert db.kv_get(f"ammo:{active_war['id']}:ir")==before


def test_one_hit_never_takes_city(active_war,equip,monkeypatch):
    equip(1,'زمینی')
    monkeypatch.setattr(campaign.random,'random',lambda:0.99)
    campaign.strike(1,'زمینی',5,'1.power')
    assert infra.city_state('iq',1)['power']>=82
    assert not geo.occupied('iq') and not geo.colony_of('iq')
    assert state.get(2)['country']=='iq'


def test_air_attacks_never_capture_even_ruined_city(active_war,equip,clock,monkeypatch):
    monkeypatch.setattr(campaign.random,'random',lambda:0.99)
    for i in range(12):
        equip(1,'هوایی')
        campaign.strike(1,'هوایی',5,'1.garrison')
        clock.advance(rules.STRIKE_COOLDOWN)
    assert infra.city_state('iq',1)['garrison']==0
    assert not geo.occupied('iq')
    assert db.one('SELECT COUNT(*) FROM sieges')[0]==0


def test_city_requires_repeat_waves_time_and_multiple_targets(active_war,equip,clock,monkeypatch):
    monkeypatch.setattr(campaign.random,'random',lambda:0.99)
    monkeypatch.setattr(campaign.random,'uniform',lambda a,b:1.0)
    assert 'شروع شد' in infra.build(1,'base',0)
    clock.advance(rules.BUILD_TIME+1)
    equip(1,'زمینی')
    # All requirements except time can be met, yet occupation must not occur.
    for i in range(8):
        target='1.power' if i<3 else '1.garrison'
        campaign.strike(1,'زمینی',5,target)
        clock.advance(rules.STRIKE_COOLDOWN)
    assert infra.city_state('iq',1)['power']<=55
    assert infra.city_state('iq',1)['garrison']<=25
    assert not geo.occupied('iq')
    clock.advance(rules.CITY_MIN_SIEGE)
    equip(1,'زمینی')
    msg=campaign.strike(1,'زمینی',5,'1.garrison')
    assert 'بصره' in geo.occupied('iq')
    assert 'کشور تسلیم نشده' in msg
    assert not geo.colony_of('iq')
    assert state.get(2)['country']=='iq' and state.get(2)['is_leader']==1


def test_national_capitulation_separate_from_city_occupation(active_war,clock):
    for city in geo.CITIES['iq']:geo.occupy('iq',city,'ir')
    assert not geo.colony_of('iq')
    assert not campaign.can_capitulate('iq','ir')[0]
    db.ex('UPDATE campaigns SET rounds_a=12 WHERE war_id=?',(active_war['id'],))
    db.ex("UPDATE city_state SET power=40 WHERE cid='iq'")
    clock.advance(48*3600)
    assert campaign.can_capitulate('iq','ir')[0]
    before=db.one('SELECT SUM(money) FROM users')[0]
    campaign.settle()
    assert geo.colony_of('iq')=='ir'
    assert state.get(2)['country']=='iq'
    assert db.one('SELECT SUM(money) FROM users')[0]==before
    after=state.get(1)['money']
    campaign.settle()
    assert state.get(1)['money']==after


def test_capital_hold_and_infrastructure_are_required(active_war,clock):
    clock.advance(48*3600)
    db.ex('UPDATE campaigns SET rounds_a=99 WHERE war_id=?',(active_war['id'],))
    for city in geo.CITIES['iq']:geo.occupy('iq',city,'ir')
    assert not campaign.can_capitulate('iq','ir')[0]
    clock.advance(rules.CAPITAL_HOLD)
    assert not campaign.can_capitulate('iq','ir')[0]  # electricity/industry untouched
    db.ex("UPDATE city_state SET industry=40 WHERE cid='iq'")
    assert campaign.can_capitulate('iq','ir')[0]


def test_mixed_occupiers_do_not_combine_conquest(active_war,clock,player):
    player(3,'us')
    for i,name in enumerate(geo.CITIES['iq']):geo.occupy('iq',name,'ir' if i<2 else 'us')
    db.ex('UPDATE campaigns SET rounds_a=99 WHERE war_id=?',(active_war['id'],))
    db.ex("UPDATE city_state SET power=1 WHERE cid='iq'")
    clock.advance(50*3600)
    assert not campaign.can_capitulate('iq','ir')[0]
    assert not geo.colony_of('iq')


def test_timer_score_alone_does_not_surrender_country(active_war,clock):
    db.ex('UPDATE wars SET score_a=100000 WHERE id=?',(active_war['id'],))
    clock.advance(8*86400)
    campaign.settle()
    assert db.one('SELECT status,winner FROM wars WHERE id=?',(active_war['id'],))['status']=='armistice'
    assert not geo.colony_of('iq') and not geo.occupied('iq')
    assert state.get(2)['country']=='iq'


def test_surrender_on_first_wave_is_forbidden(active_war):
    db.ex('UPDATE wars SET score_a=5 WHERE id=?',(active_war['id'],))
    assert 'پیش از' in campaign.surrender(2)
    assert war.war_of('iq')
    assert not geo.colony_of('iq')


def test_warning_period_never_consumes_ammo(player,clock,equip):
    player(1,'ir');player(2,'iq');equip(1,'موشکی')
    campaign.declare(1,'iq')
    w=war.war_of('ir')
    assert 'آماده' in campaign.launch_missile(1)
    assert db.kv_get(f"ammo:{w['id']}:ir")==str(rules.AMMO_CAP)
    assert db.one('SELECT COUNT(*) FROM missions')[0]==0


def test_missile_not_early_not_lost_not_resolved_twice(active_war,equip,clock,monkeypatch):
    iid=equip(1,'موشکی')
    monkeypatch.setattr(campaign.random,'random',lambda:0.99)
    assert 'در راه' in campaign.launch_missile(1,3,'1.power')
    mid=db.one('SELECT id FROM missions')[0]
    assert campaign.resolve_mission(mid)==''
    assert db.one('SELECT status FROM missions')[0]=='pending'
    assert infra.city_state('iq',1)['power']==100
    db.ex('UPDATE inventory SET dur=0 WHERE uid=1 AND iid=?',(iid,))
    clock.advance(3600)  # downtime longer than the old 120-second discard window
    assert campaign.resolve_mission(mid)
    hp=infra.city_state('iq',1)['power']
    assert hp<100
    assert campaign.resolve_mission(mid)==''
    assert infra.city_state('iq',1)['power']==hp
    assert db.kv_get(f"ammo:{active_war['id']}:ir")==str(rules.AMMO_CAP-3)


def test_new_war_cannot_receive_old_missile(active_war,equip,clock):
    equip(1,'موشکی');campaign.launch_missile(1,1,'1.power')
    assert 'ارسال شد' in war.peace_request(1)
    assert 'صلح' in war.peace_accept(2)
    clock.advance(3600)
    campaign.tick()
    assert db.one('SELECT status FROM missions')[0]=='cancelled'
    assert infra.city_state('iq',1)['power']==100


def test_insufficient_real_equipment(active_war,equip):
    equip(1,'هوایی',qty=1)
    assert 'واحد تجهیز سالم' in campaign.strike(1,'هوایی',5,'1.power')
    assert not db.kv_get('strike:1')
    assert db.kv_get(f"ammo:{active_war['id']}:ir")==str(rules.AMMO_CAP)


@pytest.mark.parametrize('a,b,yes',[('ir','iq',True),('ir','us',False),('ae','qa',False),('fr','nl',False),('ru','no',True),('no','se',True),('se','fi',True),('ru','se',False)])
def test_symmetric_game_borders(a,b,yes):
    assert geo.is_neighbor(a,b)==yes
    assert geo.is_neighbor(b,a)==yes


@pytest.mark.parametrize('cid',['kz','az','ch','at'])
def test_caspian_is_not_open_ocean(cid):assert not geo.coastal(cid)


def test_artillery_cannot_teleport(player,equip,clock):
    player(1,'ir');player(2,'us');campaign.declare(1,'us');clock.advance(3601)
    equip(1,'توپخانه')
    assert 'مسیر' in campaign.strike(1,'توپخانه',1,'1.power')
    assert not db.kv_get('strike:1')


def test_multirole_requires_completed_airbase(active_war,equip,clock):
    equip(1,'چندمنظوره')
    assert 'پایگاه هوایی' in campaign.strike(1,'چندمنظوره',1,'1.power')
    infra.build(1,'airbase',0)
    assert 'پایگاه هوایی' in campaign.strike(1,'چندمنظوره',1,'1.power')
    clock.advance(3601)
    assert 'گزارش موج' in campaign.strike(1,'چندمنظوره',1,'1.power')


def test_defensive_item_cannot_attack(active_war,equip):
    equip(1,'پدافندی')
    assert 'نامعتبر' in campaign.strike(1,'پدافندی',1)
    assert not db.kv_get('strike:1')


def test_defense_condition_and_aa_inventory_matter(player,equip):
    player(1,'ir')
    base=defense.effective('ir','ضد هوایی')
    equip(1,'پدافندی',qty=1)
    assert defense.effective('ir','ضد هوایی')>base
    db.ex("UPDATE defense SET hp=0 WHERE cid='ir'")
    assert defense.effective('ir','ضد هوایی')<base
    chance,*_=defense.absorb('ir','هوایی',5)
    assert 0.03<=chance<=0.72


def test_base_bonus_tracks_city_hp_and_time(player,clock):
    player(1,'ir')
    before=infra.strike_mult('ir')
    infra.build(1,'base',2)
    assert infra.strike_mult('ir')==before
    clock.advance(rules.BUILD_TIME+1)
    assert infra.strike_mult('ir')>before
    infra.damage('ir','base',100,2)
    assert infra.strike_mult('ir')==before
    assert infra.city_state('ir',0)['power']==100


@pytest.mark.parametrize('key,idx',[('base',99),('unknown',1),('naval',0)])
def test_invalid_construction_does_not_spend(key,idx,player):
    player(1,'ir')
    before=state.get(1)['money']
    original_count=db.one('SELECT COUNT(*) FROM structures')[0]
    infra.build(1,key,idx)
    assert state.get(1)['money']==before
    assert db.one('SELECT COUNT(*) FROM structures')[0]==original_count


def test_repair_is_partial_and_has_per_city_cooldown(player,clock):
    player(1,'ir')
    infra.damage('ir','power',70,1)
    assert '30٪ ← 50٪' in infra.repair(1,'power',1)
    cost=state.get(1)['money']
    assert '۱۰ دقیقه' in infra.repair(1,'power',1)
    assert state.get(1)['money']==cost
    assert infra.city_state('ir',1)['power']==50
    assert infra.city_state('ir',0)['power']==100


def test_empty_building_is_not_valid_bombing_target(active_war,equip):
    equip(1,'هوایی')
    assert 'چنین پایگاهی' in campaign.strike(1,'هوایی',1,'1.base')
    assert not db.kv_get('strike:1')


def test_occupation_rejects_fake_city_and_self():
    with pytest.raises(ValueError):geo.occupy('ir','مرز','us')
    with pytest.raises(ValueError):geo.occupy('ir','تهران','ir')


def test_alliance_help_never_manufactures_score(active_war,player):
    player(3,'us')
    war.alliance_request(1,'us');war.alliance_accept(3,'ir')
    score=dict(db.one('SELECT * FROM wars WHERE id=?',(active_war['id'],)))
    assert 'هیچ امتیازی' in war.call_help(1)
    assert dict(db.one('SELECT * FROM wars WHERE id=?',(active_war['id'],)))==score


def test_resupply_is_shared_and_bounded(active_war,clock):
    key=f"ammo:{active_war['id']}:ir";db.kv_set(key,45)
    money=state.get(1)['money']
    assert 'موجودی 50/50' in campaign.resupply(1)
    assert db.kv_get(key)=='50'
    assert state.get(1)['money']==money-150
    db.kv_set(key,40)
    assert '۳۰ دقیقه' in campaign.resupply(1)
    assert db.kv_get(key)=='40'
