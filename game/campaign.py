"""Persistent, player-driven campaigns; city control is not national surrender.

All mutations are synchronous SQLite transactions. Combat uses bounded fictional
game stats, not real-world weapon ranges, targeting advice or military simulation.
"""
import json
import math
import random

import countries
import db
import texts
from game import catalog, defense, economy, geo, infra, notifications, rules, state


def _leader(uid):
    p=state.active(uid)
    if not p:return None,'⛔ اول «شروع»؛ کشور را انتخاب کن.'
    if not p['is_leader']:return None,'👑 این تصمیم فقط با رهبر کشور است.'
    return p,None


def war_of(cid):
    return db.one("SELECT * FROM wars WHERE status='active' AND (a=? OR b=?) ORDER BY id LIMIT 1",(cid,cid))


def enemy(cid,w):
    return w['b'] if w['a']==cid else w['a']


def _side(w,cid):
    if cid not in (w['a'],w['b']):raise ValueError('country not in war')
    return 'a' if w['a']==cid else 'b'


def _claim_age(cid):
    return db.now()-db.integer(db.kv_get(f'claimed:{cid}'))


@db.atomic
def ensure_campaign(w):
    if not db.one('SELECT 1 FROM campaigns WHERE war_id=?',(w['id'],)):
        mode=rules.MODES['total']
        started=w['started'] or db.now()
        db.ex('INSERT INTO campaigns(war_id,mode,ready_at,min_end) VALUES(?,?,?,?)',
              (w['id'],'total',started+mode.warning,started+mode.minimum))
        db.ex('UPDATE wars SET ends=MAX(ends,?) WHERE id=?',(started+mode.maximum,w['id']))
    for cid in (w['a'],w['b']):
        if db.kv_get(f"ammo:{w['id']}:{cid}") is None:
            db.kv_set(f"ammo:{w['id']}:{cid}",rules.AMMO_CAP)
    return dict(db.one('SELECT * FROM campaigns WHERE war_id=?',(w['id'],)))


@db.atomic
def declare(uid,target,mode='total'):
    p,err=_leader(uid)
    if err:return err
    cid=p['country']
    if target not in countries.COUNTRIES or target==cid:return '⛔ کشور هدف نامعتبر.'
    if mode not in rules.MODES:return '⛔ نوع جنگ نامعتبر.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(target,)):
        return '🕊 کشور بدون رهبر بازیکن قابل حمله نیست؛ هیچ دولت NPC وجود ندارد.'
    if war_of(cid) or war_of(target):return '🚫 یکی از دو کشور از قبل درگیر جنگ است؛ هر کشور فقط یک جنگ هم‌زمان.'
    if db.one('SELECT 1 FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)',(cid,target,target,cid)):
        return '🤝 ابتدا از مدیریت اتحادها پیمان را پایان بده و آتش‌بس ۱۲ساعته را رعایت کن؛ حمله به متحد مجاز نیست.'
    if geo.colony_of(cid) and geo.colony_of(cid)!=target:return '⛓ کشور تابع فقط می‌تواند جنگ آزادی‌بخش علیه اشغال‌گر آغاز کند.'
    pair=':'.join(sorted((cid,target)))
    if db.integer(db.kv_get(f'truce:{pair}'))>db.now():return '🕊 آتش‌بس ۱۲ ساعتهٔ این دو کشور هنوز برقرار است.'
    if _claim_age(target)<3600 or _claim_age(cid)<3600:return '🛡 کشور تازه‌انتخاب‌شده یک ساعت فرصت آماده‌سازی دارد.'
    if mode=='border' and not geo.is_neighbor(cid,target):return '🗺 درگیری مرزی فقط با مرز زمینی مشترک ممکن است.'
    cost=200 if mode=='border' else 500
    if not db.debit(uid,cost):return f'💰 هزینهٔ آماده‌سازی جنگ: {texts.money(cid,cost)}'
    m=rules.MODES[mode];now=db.now()
    cur=db.ex('INSERT INTO wars(a,b,started,ends) VALUES(?,?,?,?)',(cid,target,now,now+m.maximum))
    wid=cur.lastrowid
    db.ex('INSERT INTO campaigns(war_id,mode,ready_at,min_end) VALUES(?,?,?,?)',(wid,mode,now+m.warning,now+m.minimum))
    for c in (cid,target):
        db.kv_set(f'ammo:{wid}:{c}',rules.AMMO_CAP)
        infra.ensure(c);defense.ensure(c)
    economy.on_war_start()
    db.audit('war_declaration',uid,war=wid,mode=mode,target=target,cost=cost)
    msg='\n'.join([texts.hdr('اعلام جنگ','⚔️'),
        f"{countries.COUNTRIES[cid]['flag']} {countries.COUNTRIES[cid]['name']} ↔ {countries.COUNTRIES[target]['flag']} {countries.COUNTRIES[target]['name']}",
        f'نوع: {m.label} · شمارهٔ جنگ: {wid}',
        f'⏳ آماده‌سازی: {m.warning//60} دقیقه؛ تا آن زمان هیچ حمله‌ای مجاز نیست.',
        f'⏱ حداقل نتیجهٔ نظامی: {m.minimum//3600} ساعت و {m.min_rounds} موج؛ سقف {m.maximum//3600} ساعت.',
        '🏙 تخریب زیرساخت ≠ تصرف شهر. فقط نیروی زمینی/آبی‌خاکی با محاصرهٔ پایدار شهر می‌گیرد.',
        '🏳 اتمام زمان یا یک حمله، کشور را تسلیم نمی‌کند. صلح نیازمند قبول رهبر طرف مقابل است.'])
    notifications.emit(msg,cids=[cid,target],uids=[uid],key=f'war:{wid}:declared')
    return msg


def _bridgehead(w,cid):
    return bool(db.kv_get(f"bridgehead:{w['id']}:{cid}")) and infra.structure_strength(cid,'naval')>0 and infra.port_ok(cid)


def _staging_route(cid,target):
    """An allied base needs explicit, unexpired permission; alliances are not free attacks."""
    for host in sorted(geo.NEIGHBORS.get(target,())):
        permission=db.integer(db.kv_get(f'staging:{host}:{cid}'))
        allied=db.one('SELECT 1 FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)',(host,cid,cid,host))
        if permission>db.now() and allied and infra.structure_strength(host,'base')>0:
            return True
    return False


def can_strike_kind(a,b,kind):
    if a not in geo.CITIES or b not in geo.CITIES or a==b:return False,'⛔ کشور نامعتبر.'
    if kind not in catalog.KINDS:return False,'⛔ نوع حمله نامعتبر؛ پدافند ابزار حمله نیست.'
    w=war_of(a)
    if kind in ('زمینی','توپخانه'):
        route=geo.is_neighbor(a,b) or _staging_route(a,b) or (w and _bridgehead(w,a))
        if not route:return False,'🗺 مسیر زمینی ندارید؛ مرز مشترک، پایگاه متحد با اجازه، یا سرپل دریایی فعال لازم است.'
    if kind in ('دریایی','آبی‌خاکی'):
        if not (geo.coastal(a) and geo.coastal(b)):
            return False,'🌊 هر دو طرف باید به آب‌های آزاد دسترسی داشته باشند؛ خزر کافی نیست.'
        if not infra.port_ok(a):return False,'⚓ بندر خودی ازکارافتاده؛ ابتدا تعمیر کن.'
    return True,''


def _parse_target(cid,target,city):
    if target and isinstance(target,str) and '.' in target:
        city,target=target.split('.',1)
    if target is not None and not isinstance(target,str):return None,None
    idx=infra.city_index(cid,city if city is not None else (1 if len(geo.CITIES.get(cid,[]))>1 else 0))
    asset=target or 'garrison'
    return (idx,asset) if asset in infra.TARGETS else (None,None)


def _equipment(uid,kind,shots,target=None,required_range=None):
    from game import military
    use_kind='زمینی' if kind=='آبی‌خاکی' else kind
    from game import fleet
    rows=[dict(r) for r in db.q('SELECT iid,qty,dur FROM inventory WHERE uid=? AND qty>0 AND dur>=20',(uid,))]
    for row in rows:
        row['owned_qty']=row['qty'];row['qty']=max(0,row['qty']-fleet.escort_locked(uid,row['iid']))
    valid=[r for r in rows if r['qty']>0 and catalog.supports(r['iid'],use_kind)]
    if target and kind in ('موشکی','هوایی','چندمنظوره','پهپادی'):
        actor=state.active(uid)
        required=required_range if required_range is not None else geo.range_level(actor['country'],target)
        from game import war
        if required_range is None and kind!='موشکی' and any(db.integer(db.kv_get(f"staging:{host}:{actor['country']}"))>db.now() and geo.range_level(host,target)<=2 and infra.structure_strength(host,'airbase')>0 for host in war.allies_of(actor['country'])):required=2
        valid=[r for r in valid if catalog.range_band(r['iid'])>=required]
    if sum(r['qty'] for r in valid)<shots:return None
    valid.sort(key=lambda r:countries.ITEMS[r['iid']][3]*r['dur']*military._lvl_mult(uid,r['iid']),reverse=True)
    equipment=[];left=shots
    for r in valid:
        take=min(left,r['qty']);it=countries.ITEMS[r['iid']]
        equipment.append({'iid':r['iid'],'units':take,'qty':r['owned_qty'],'dur':r['dur'],
                          'power':it[3]*r['dur']/100*military._lvl_mult(uid,r['iid'])/100})
        left-=take
        if not left:break
    return equipment


def _prepare(uid,kind,count,target=None,city=None,reclaim=False,maritime=None):
    # NO resource write before every check below succeeds.
    p,err=_leader(uid)
    if err:return None,err
    if type(count) is not int or not 1<=count<=rules.MAX_SHOTS:return None,'⛔ تعداد موج باید عدد صحیح ۱ تا ۵ باشد.'
    if kind not in catalog.KINDS:return None,'⛔ نوع عملیات نامعتبر.'
    w=war_of(p['country'])
    if not w:return None,'🕊 کشورت در جنگ نیست.'
    cp=ensure_campaign(w);cid=p['country'];ecid=enemy(cid,w);side=_side(w,cid)
    if db.now()<cp['ready_at']:return None,'⏳ دورهٔ آماده‌سازی جنگ تمام نشده است.'
    if db.now()>=w['ends']:return None,'🕊 زمان این جنگ تمام شده؛ تسویهٔ آتش‌بس در حال پردازش است.'
    if p['hp']<20:return None,'🏥 جان فرمانده کمتر از ۲۰ است؛ ابتدا استراحت کن.'
    if p['branch'] in (None,''):return None,'🪖 ابتدا یک شاخهٔ نظامی انتخاب کن.'
    if db.now()-db.integer(db.kv_get(f'strike:{uid}'))<rules.STRIKE_COOLDOWN:return None,'⏳ بین موج‌های هر فرمانده ۵ دقیقه فاصله لازم است.'
    if db.now()-cp[f'last_{side}']<rules.COUNTRY_COOLDOWN:return None,'⏳ ستاد کشور هنوز در حال هماهنگی موج قبلی است.'
    if db.one("SELECT 1 FROM missions WHERE war_id=? AND uid=? AND status='pending'",(w['id'],uid)):
        return None,'🚀 ابتدا نتیجهٔ موشک در راه را دریافت کن؛ پرتاب معلق جایگزین نمی‌شود.'
    target_cid=cid if reclaim else ecid
    idx,asset=_parse_target(target_cid,target,city)
    if idx is None:return None,'⛔ شهر یا بخش هدف نامعتبر.'
    s=infra.city_state(target_cid,idx)
    occ=next((o for o in geo.held_by(ecid if reclaim else cid) if o['cid']==target_cid and o['city']==s['name']),None)
    if reclaim:
        if not occ:return None,'🕊 این شهر در اشغال طرف مقابل جنگ نیست.'
    elif not maritime and s['name'] in geo.occupied(ecid):
        return None,'🚩 این شهر از قبل اشغال شده؛ شهر آزاد دیگری یا عملیات آزادسازی انتخاب کن.'
    if asset=='port' and not geo.is_port(target_cid,idx):return None,'🚫 شهر هدف بندر ندارد.'
    if asset in infra._B and not db.one('SELECT 1 FROM structures WHERE cid=? AND city=? AND kind=?',(target_cid,idx,asset)):
        return None,'🚫 چنین پایگاهی در شهر هدف ساخته نشده؛ مهمات مصرف نشد.'
    if not reclaim:
        if not maritime and kind in ('دریایی','آبی‌خاکی') and not geo.is_port(target_cid,idx):return None,'⚓ آتش مستقیم دریایی فقط به شهر بندری می‌رسد؛ شهر داخلی هدف هوایی/موشکی یا زمینی می‌خواهد.'
        ok,why=can_strike_kind(cid,ecid,kind)
        if not ok:return None,why
        if kind in ('زمینی','توپخانه'):
            access=geo.accessible_city(cid,ecid,idx) or _staging_route(cid,ecid) or (_bridgehead(w,cid) and idx!=0)
            if not access:return None,'🗺 ابتدا یک شهر پیرامونی و مسیر تدارکات بگیر؛ پایتخت اولین هدف زمینی نیست.'
    if kind in ('هوایی','چندمنظوره','پهپادی') and infra.state_of(cid)['airport']<30:
        return None,'🛫 سلامت فرودگاه خودی باید دست‌کم ۳۰٪ باشد.'
    if kind=='چندمنظوره' and infra.structure_strength(cid,'airbase')<=0:
        return None,'✈️ عملیات چندمنظوره به پایگاه هوایی تکمیل‌شده نیاز دارد.'
    if kind=='آبی‌خاکی':
        if not geo.is_port(target_cid,idx):return None,'⚓ عملیات آبی‌خاکی فقط در شهر بندری ممکن است.'
        if infra.structure_strength(cid,'naval')<=0:return None,'⚓ پایگاه دریایی آماده لازم است.'
        if cp[f'sea_{side}']<4:return None,'🌊 دست‌کم ۴ موج موفق دریایی برای آماده‌سازی سرپل لازم است.'
        if not _equipment(uid,'دریایی',1):return None,'🚢 یک شناور سالم برای پشتیبانی و تجهیزات زمینی لازم است.'
    equipment=_equipment(uid,kind,count,ecid,maritime.get('required_range') if maritime else None)
    if not equipment:return None,f'🛒 برای این موج به {count} واحد تجهیز سالمِ {kind} با برد مناسب نیاز داری؛ تعداد، دوام و پهنهٔ عملیاتی مهم‌اند.'
    if kind=='موشکی':
        if count>rules.MISSILE_SALVO:return None,'⛔ هر نوبت حداکثر ۳ موشک.'
        used=db.one('SELECT COALESCE(SUM(shots),0) n FROM missile_launches WHERE war_id=? AND cid=?',(w['id'],cid))['n']
        recent=db.one('SELECT COALESCE(SUM(shots),0) n FROM missile_launches WHERE war_id=? AND cid=? AND ts>?',(w['id'],cid,db.now()-3600))['n']
        if used+count>rules.MISSILES_PER_WAR:return None,'🚀 سهمیهٔ ۲۰ موشک این جنگ تمام شده است.'
        if recent+count>rules.MISSILES_PER_HOUR:return None,'⏳ سقف کشور در یک ساعت شناور ۶ موشک است.'
    ammo_key=f"ammo:{w['id']}:{cid}";ammo=db.integer(db.kv_get(ammo_key))
    if count>ammo:return None,'🎯 مهمات کافی نیست؛ از «تأمین مهمات» استفاده کن.'
    from game import energy
    energy.settle(cid)
    fuel_cost=rules.FUEL_PER_SHOT[kind]*count*1000
    if energy.fuel(cid)<fuel_cost:return None,'⛽ سوخت ملی کافی نیست؛ از بخش انرژی سوخت بخر یا نفت خام را پالایش کن.'
    ctx={'p':p,'w':dict(w),'cp':cp,'ecid':ecid,'target_cid':target_cid,'city':idx,
         'target':asset,'kind':kind,'count':count,'equipment':equipment,'reclaim':reclaim}
    ctx['facility_mult']=1+0.03*infra.structure_strength(cid,'command')+(0.05*infra.structure_strength(cid,'missile_base') if kind=='موشکی' else 0)
    from game import operations
    ctx['operation_mult'],ctx['operation_name']=operations.reserve(uid,w['id'],ecid,kind)
    if kind=='موشکی':db.ex('INSERT INTO missile_launches(war_id,cid,shots,ts) VALUES(?,?,?,?)',(w['id'],cid,count,db.now()))
    if not energy._take_fuel(cid,fuel_cost):raise RuntimeError('fuel changed within launch transaction')
    ctx['fuel_used']=fuel_cost//1000
    db.kv_set(ammo_key,ammo-count)
    db.kv_set(f'strike:{uid}',db.now())
    db.ex(f'UPDATE campaigns SET last_{side}=? WHERE war_id=?',(db.now(),w['id']))
    for item in equipment:
        wear=max(1,math.ceil(8*item['units']/item['qty']))
        db.ex('UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?',(wear,uid,item['iid']))
    if kind=='آبی‌خاکی':
        naval=_equipment(uid,'دریایی',1)
        if naval:db.ex('UPDATE inventory SET dur=MAX(0,dur-4) WHERE uid=? AND iid=?',(uid,naval[0]['iid']))
    from game import quests
    quests.on_event(uid,'حمله')
    db.audit('wave_launch',uid,war=w['id'],kind=kind,shots=count,city=idx,target=asset,reclaim=reclaim)
    return ctx,None


def _city_capture(ctx,hits,damage):
    if not hits or ctx['kind'] not in ('زمینی','آبی‌خاکی'):return ''
    w=ctx['w'];a=ctx['p']['country'];d=ctx['target_cid'];idx=ctx['city'];cp=ctx['cp']
    mode=rules.MODES[cp['mode']]
    if not mode.captures and not ctx['reclaim']:return ''
    if ctx['kind']=='آبی‌خاکی':db.kv_set(f"bridgehead:{w['id']}:{a}",str(idx+1))
    db.ex('INSERT OR IGNORE INTO sieges(war_id,attacker,defender,city,first_at,last_at) VALUES(?,?,?,?,?,?)',(w['id'],a,d,idx,db.now(),db.now()))
    pressure=min(rules.CITY_MAX_PRESSURE,8+hits+damage//4)
    db.ex('UPDATE sieges SET pressure=MIN(100,pressure+?),rounds=rounds+1,last_at=? WHERE war_id=? AND attacker=? AND defender=? AND city=?',
          (pressure,db.now(),w['id'],a,d,idx))
    siege=db.one('SELECT * FROM sieges WHERE war_id=? AND attacker=? AND defender=? AND city=?',(w['id'],a,d,idx))
    s=infra.city_state(d,idx)
    blockers=[]
    if siege['rounds']<rules.CITY_MIN_ROUNDS:blockers.append(f"{rules.CITY_MIN_ROUNDS} موج زمینی موفق")
    if db.now()-siege['first_at']<rules.CITY_MIN_SIEGE:blockers.append('۶ ساعت محاصره')
    if siege['pressure']<100:blockers.append('فشار محاصره ۱۰۰٪')
    from game import energy
    if energy.electricity(d,idx,s['power'])>55:blockers.append('برق همین شهر ≤۵۵٪')
    if s['garrison']>25:blockers.append('پادگان همین شهر ≤۲۵٪')
    bases=db.q("SELECT hp FROM structures WHERE cid=? AND city=? AND kind IN ('base','radar','sam_base','bunker') AND (ready_at<=? OR previous_level>0)",(d,idx,db.now()))
    if any(r['hp']>30 for r in bases):blockers.append('پایگاه/پدافند همین شهر ≤۳۰٪')
    if not ctx['reclaim']:
        if infra.structure_strength(a,'base')<=0:blockers.append('پایگاه زمینی خودی عملیاتی')
        if idx==0 and not any(o['cid']==d and o['city']!=s['name'] for o in geo.held_by(a)):
            blockers.append('کنترل دست‌کم یک شهر دیگر پیش از پایتخت')
        if cp['mode']=='border' and (idx==0 or any(o['cid']==d for o in geo.held_by(a))):
            blockers.append('جنگ مرزی حداکثر یک شهر غیرپایتخت را می‌گیرد')
    if blockers:
        return f"🏙 {s['name']}: فشار {siege['pressure']}٪ · موج موفق {siege['rounds']}\nهنوز لازم: "+'؛ '.join(blockers)
    energy.before_change(d)
    if ctx['reclaim']:
        geo.release_city(d,s['name'])
        msg=f"🕊 شهر {s['name']} با عملیات بازیکن آزاد شد؛ سایر شهرها خودکار آزاد نمی‌شوند."
        if geo.colony_of(d)==ctx['ecid'] and not geo.occupied(d):
            geo.free_colony(d)
            msg+='\n🇺🇳 همهٔ شهرها بازپس گرفته شدند؛ استقلال کشور بازگشت.'
    else:
        msg=geo.occupy(d,s['name'],a) or ''
    db.ex('UPDATE sieges SET captured_at=? WHERE war_id=? AND attacker=? AND defender=? AND city=?',(db.now(),w['id'],a,d,idx))
    # Occupation establishes a local guard, not an NPC government taking turns.
    db.ex('UPDATE city_state SET garrison=60 WHERE cid=? AND city=?',(d,idx))
    return msg


def _resolve(ctx):
    from game import military
    uid=ctx['p']['uid'];cid=ctx['p']['country'];w=ctx['w'];kind=ctx['kind'];n=ctx['count'];d=ctx['target_cid'];idx=ctx['city']
    side=_side(w,cid)
    chance,reduction,layer,eff=defense.absorb(ctx['ecid'],kind,n,idx if not ctx['reclaim'] else None)
    spec,pct,_=countries.spec_of(cid)
    specialized=spec==kind or (kind=='چندمنظوره' and spec=='هوایی')
    role,_=military.atk_mult(ctx['p'],'هوایی' if kind=='چندمنظوره' else kind)
    air=infra.airport_mult(cid) if kind in ('هوایی','چندمنظوره','پهپادی') else 1.0
    multiplier=catalog.country_factor(cid)*(1+pct/100 if specialized else 1)*role*air*infra.strike_mult(cid)
    multiplier*=ctx.get('facility_mult',1.0)
    multiplier*=military.def_mult(ctx['ecid'])*infra.damage_in_mult(d,idx)*reduction
    multiplier*=max(1.0,min(1.10,ctx.get('operation_mult',1.0)))
    total=0;hits=0
    for item in ctx['equipment']:
        for _ in range(item['units']):
            if random.random()>=chance:
                hits+=1
                total+=item['power']*multiplier*random.uniform(0.90,1.10)
    # An entire five-unit wave can never zero a pristine city facility.
    points=min(18,max(1,int(total/8))) if hits else 0
    asset=ctx['target']
    before=infra.city_state(d,idx)
    if asset in infra._B:
        rr=db.one('SELECT hp FROM structures WHERE cid=? AND city=? AND kind=?',(d,idx,asset))
        old=rr['hp'] if rr else 0
    else:old=before[asset]
    hit=infra.damage(d,asset,points,idx) if points else {'hp':old}
    actual=old-hit['hp']
    db.ex(f'UPDATE wars SET score_{side}=score_{side}+? WHERE id=?',(max(0,actual),w['id']))
    db.ex(f'UPDATE campaigns SET rounds_{side}=rounds_{side}+1 WHERE war_id=?',(w['id'],))
    if kind=='دریایی' and hits:
        db.ex(f'UPDATE campaigns SET sea_{side}=sea_{side}+1 WHERE war_id=?',(w['id'],))
    capture=_city_capture(ctx,hits,actual)
    target_name=geo.CITIES[d][idx]
    lines=[texts.hdr(f'گزارش موج {kind}','⚔️'),
           f"{countries.COUNTRIES[cid]['flag']} → {countries.COUNTRIES[ctx['ecid']]['flag']} · شهر {target_name}",
           f"هدف: {infra.TARGETS[asset]} · واحدهای اعزامی {n}",
           f"🛡 {layer}: توان مؤثر {eff} · رهگیری {n-hits} / برخورد {hits}",
           f"🏗 سلامت هدف: {old}٪ ← {hit['hp']}٪ · امتیاز واقعی +{actual}",
           f"🎯 مهمات باقی‌مانده: {db.kv_get(f'ammo:{w["id"]}:{cid}')} / {rules.AMMO_CAP}"]
    if ctx.get('fuel_used'):lines.append(f"⛽ سوخت این موج: {ctx['fuel_used']} واحد")
    if ctx.get('operation_name'):lines.append(f"🧭 عملیات «{texts.esc(ctx['operation_name'])}»: +۱۰٪ هماهنگی؛ سقف خسارت ثابت.")
    if capture:lines.extend(['',capture])
    lines.append('هیچ ضدحملهٔ NPC یا امتیاز ساختگی اعمال نشد؛ تخریب به‌تنهایی کشور را تسلیم نمی‌کند.')
    msg='\n'.join(lines)
    db.audit('wave_resolved',uid,war=w['id'],kind=kind,hits=hits,damage=actual,target=asset,city=idx)
    notifications.emit(msg,cids=[cid,ctx['ecid']],uids=[uid])
    return msg


@db.atomic
def strike(uid,kind,count=1,target=None,city=None):
    if kind=='موشکی':return launch_missile(uid,count,target,city)
    ctx,err=_prepare(uid,kind,count,target,city)
    return err or _resolve(ctx)


@db.atomic
def liberate(uid,city,count=1):
    ctx,err=_prepare(uid,'زمینی',count,'garrison',city,reclaim=True)
    return err or _resolve(ctx)


@db.atomic
def launch_missile(uid,count=1,target=None,city=None):
    ctx,err=_prepare(uid,'موشکی',count,target,city)
    if err:return err
    return store_missile(ctx)


@db.atomic
def store_missile(ctx,asset=None):
    uid=ctx['p']['uid'];count=ctx['count']
    payload={'equipment':ctx['equipment'],'source_country':ctx['p']['country'],'level':ctx['p']['level'],'branch':ctx['p']['branch'],'operation_mult':ctx.get('operation_mult',1.0),'operation_name':ctx.get('operation_name',''),'fuel_used':ctx.get('fuel_used',0),'facility_mult':ctx.get('facility_mult',1.0),'asset':asset}
    cur=db.ex('INSERT INTO missions(war_id,uid,attacker,defender,kind,shots,city,target,equipment,launched,due) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
              (ctx['w']['id'],uid,ctx['p']['country'],ctx['ecid'],'موشکی',count,ctx['city'],ctx['target'],json.dumps(payload),db.now(),db.now()+rules.MISSILE_FLIGHT))
    mid=cur.lastrowid
    msg=f"🚀 <b>موج موشکی در راه</b> · مأموریت {mid}\nهدف بازی: {geo.CITIES[ctx['ecid']][ctx['city']]} / {infra.TARGETS[ctx['target']]}\n⏱ {rules.MISSILE_FLIGHT} ثانیه تا برخورد؛ پدافند لحظهٔ برخورد محاسبه می‌شود.\n💾 مأموریت ذخیره شد؛ با راه‌اندازی مجدد گم نمی‌شود."
    if asset:
        ship=db.one('SELECT name FROM tankers WHERE id=?',(asset['id'],))
        msg=f"🚀 موج موشکی در راه نفت‌کش «{texts.esc(ship['name'])}» · مأموریت {mid}.\nپرواز {rules.MISSILE_FLIGHT} ثانیه؛ ثبت پایدار، محدودیت برد و سهمیه و مصرف سوخت رعایت شد."
    notifications.emit(msg,cids=[ctx['p']['country'],ctx['ecid']],uids=[uid],key=f'mission:{mid}:launch')
    return msg


@db.atomic
def resolve_mission(mid):
    m=db.one("SELECT * FROM missions WHERE id=? AND status='pending'",(mid,))
    if not m or db.now()<m['due']:return ''
    w=db.one("SELECT * FROM wars WHERE id=? AND status='active'",(m['war_id'],))
    p=state.active(m['uid'])
    if not w or not p or p['country']!=m['attacker'] or db.now()>=w['ends']:
        db.ex("UPDATE missions SET status='cancelled',result='جنگ/فرمانده تغییر کرده است' WHERE id=?",(mid,))
        msg=f'🕊 مأموریت {mid} لغو شد؛ جنگ پایان یافته یا فرمانده تغییر کرده است. مهمات شلیک‌شده بازنمی‌گردد.'
        notifications.emit(msg,cids=[m['attacker'],m['defender']],key=f'mission:{mid}:cancelled')
        return msg
    payload=db.jload(m['equipment'],{})
    cp=ensure_campaign(w)
    ctx={'p':p,'w':dict(w),'cp':cp,'ecid':m['defender'],'target_cid':m['defender'],
         'city':m['city'],'target':m['target'],'kind':m['kind'],'count':m['shots'],
         'equipment':payload['equipment'],'reclaim':False,'facility_mult':payload.get('facility_mult',1.0),'fuel_used':payload.get('fuel_used',0),'operation_mult':payload.get('operation_mult',1.0),'operation_name':payload.get('operation_name','')}
    # Weapon condition/power are frozen at launch; defense stays live at impact.
    ctx['p']=dict(p,level=payload['level'],branch=payload['branch'])
    asset=payload.get('asset')
    if asset and asset.get('type')=='tanker':
        from game import fleet
        ship_voyage=fleet.live_voyage(asset['id'])
        if ship_voyage:fleet.tick_one(ship_voyage['id'])
        result=fleet.resolve_attack(ctx,asset['id'])
    else:result=_resolve(ctx)
    db.ex("UPDATE missions SET status='resolved',result=? WHERE id=? AND status='pending'",(result,mid))
    return result


def resolve_missile(uid):
    results=[]
    for r in db.q("SELECT id FROM missions WHERE uid=? AND status='pending' AND due<=? ORDER BY id",(uid,db.now())):
        msg=resolve_mission(r['id'])
        if msg:results.append(msg)
    return '\n\n'.join(results)


@db.atomic
def resupply(uid):
    p,err=_leader(uid)
    if err:return err
    cid=p['country'];w=war_of(cid)
    if not w:return '🕊 جنگی نیست؛ مهمات هنگام اعلان جنگ تخصیص می‌یابد.'
    ensure_campaign(w);key=f"ammo:{w['id']}:{cid}";ammo=db.integer(db.kv_get(key),0,0,rules.AMMO_CAP)
    if ammo>=rules.AMMO_CAP:return '✅ انبار مهمات پر است؛ هزینه‌ای کسر نشد.'
    cd=f"resupply:{w['id']}:{cid}"
    if db.now()-db.integer(db.kv_get(cd))<rules.RESUPPLY_COOLDOWN:return '⏳ تدارکات هر کشور هر ۳۰ دقیقه یک بار می‌رسد.'
    if infra.state_of(cid)['industry']<40 and infra.structure_strength(cid,'logistics')<=0:
        return '🚚 صنعت دست‌کم ۴۰٪ یا انبار تدارکات عملیاتی لازم است.'
    qty=min(rules.RESUPPLY_QTY,rules.AMMO_CAP-ammo)
    cost=rules.RESUPPLY_COST*qty//rules.RESUPPLY_QTY
    if not db.debit(uid,cost):return f'💰 هزینهٔ مهمات: {texts.money(cid,cost)}'
    db.kv_set(key,ammo+qty);db.kv_set(cd,db.now())
    db.audit('resupply',uid,war=w['id'],quantity=qty,cost=cost)
    msg=f'🚚 {qty} واحد مهمات رسید؛ موجودی {ammo+qty}/{rules.AMMO_CAP}\n💰 هزینه: {texts.money(cid,cost)}'
    notifications.emit(msg,cids=[cid],uids=[uid])
    return msg


def can_capitulate(loser,winner):
    w=war_of(loser)
    if not w or winner not in (w['a'],w['b']) or winner==loser:return False,'جنگ فعال متناظر وجود ندارد.'
    cp=ensure_campaign(w)
    if cp['mode']!='total':return False,'این نوع جنگ اجازهٔ تابع‌کردن کشور را نمی‌دهد.'
    if geo.colony_of(winner):return False,'کشور تابع نمی‌تواند کشور تابع دیگری داشته باشد.'
    if db.now()<cp['min_end']:return False,'حداقل ۴۸ ساعت جنگ فراگیر لازم است.'
    side=_side(w,winner)
    if cp[f'rounds_{side}']<rules.MODES['total'].min_rounds:return False,'موج‌های لازم تکمیل نشده است.'
    held=[o for o in geo.held_by(winner) if o['cid']==loser]
    capital=geo.CITIES[loser][0]
    cap=next((o for o in held if o['city']==capital),None)
    if not cap or len(held)<math.ceil(0.8*len(geo.CITIES[loser])):return False,'پایتخت و دست‌کم ۸۰٪ شهرها باید در کنترل یک مهاجم باشند.'
    if db.now()-cap['ts']<rules.CAPITAL_HOLD:return False,'کنترل پایتخت باید ۶ ساعت پیوسته تثبیت شود.'
    rows=db.q('SELECT city,power,industry FROM city_state WHERE cid=?',(loser,))
    if not rows:return False,'زیرساخت مشخص نیست.'
    from game import energy
    power=sum(energy.electricity(loser,r['city'],r['power'],physical=True) for r in rows)/len(rows);industry=sum(r['industry'] for r in rows)/len(rows)
    if power>45 and industry>45:return False,'شبکهٔ برق یا صنعت کشور هنوز بیش از ۴۵٪ توان دارد.'
    return True,'شرایط تسلیم مرحله‌ای تکمیل شده است.'


@db.atomic
def finish(w,status='armistice',winner=None,colonial=False):
    live=db.one("SELECT * FROM wars WHERE id=? AND status='active'",(w['id'],))
    if not live:return ''
    extra=''
    if colonial:
        loser=enemy(winner,w)
        extra=geo.colonize(loser,winner)
    paid=0
    if winner:
        loser=enemy(winner,w)
        # Actual conserved reparations: no money is minted for each alliance/member.
        losers=db.q('SELECT uid,money FROM users WHERE country=? ORDER BY uid',(loser,))
        winners=db.q('SELECT uid FROM users WHERE country=? ORDER BY uid',(winner,))
        if winners:
            for r in losers:
                cut=min(2500,r['money']//5)
                if cut and db.debit(r['uid'],cut):paid+=cut
            share,rem=divmod(paid,len(winners))
            for i,r in enumerate(winners):
                db.ex('UPDATE users SET money=money+? WHERE uid=?',(share+(i<rem),r['uid']))
                state.gain_xp(r['uid'],100)
    db.ex('UPDATE wars SET status=?,winner=? WHERE id=?',(status,winner,w['id']))
    db.ex("UPDATE missions SET status='cancelled',result='جنگ پایان یافت' WHERE war_id=? AND status='pending'",(w['id'],))
    pair=':'.join(sorted((w['a'],w['b'])))
    db.kv_set(f'truce:{pair}',db.now()+rules.TRUCE_TIME)
    db.kv_del(f"peace:{w['id']}")
    msg=f"🕊 جنگ {w['id']} پایان یافت: "+({'peace':'صلح دوطرفه','armistice':'آتش‌بس بدون تسلیم خودکار','won':'نتیجهٔ نظامی ثبت شد'}.get(status,status))
    if winner:msg+=f"\nبرنده: {countries.COUNTRIES[winner]['name']} · غرامت واقعی کل: {texts.money(winner,paid)}"
    if extra:msg+='\n'+extra
    msg+='\n۱۲ ساعت آتش‌بس؛ کنترل شهرها جدا از مالکیت حساب رهبر باقی می‌ماند.'
    db.audit('war_finished',war=w['id'],winner=winner,status=status,reparations=paid,colonial=colonial)
    notifications.emit(msg,cids=[w['a'],w['b']],key=f"war:{w['id']}:finished")
    return msg


def settle():
    results=[]
    for w in db.q("SELECT * FROM wars WHERE status='active' ORDER BY id"):
        with db.transaction():
            cp=ensure_campaign(w);mode=rules.MODES[cp['mode']]
            winner=None;colonial=False
            for a,b in ((w['a'],w['b']),(w['b'],w['a'])):
                if mode.colony and can_capitulate(b,a)[0]:winner=a;colonial=True;break
                if not mode.colony and db.now()>=cp['min_end'] and cp[f'rounds_{_side(w,a)}']>=mode.min_rounds:
                    held=[o for o in geo.held_by(a) if o['cid']==b]
                    score=w['score_a'] if w['a']==a else w['score_b']
                    other=w['score_b'] if w['a']==a else w['score_a']
                    if (mode.captures and held) or (not mode.captures and score>=60 and score-other>=30):winner=a;break
            if winner:results.append(finish(w,'won',winner,colonial))
            elif db.now()>=w['ends']:results.append(finish(w))
    return [m for m in results if m]


@db.atomic
def surrender(uid):
    p,err=_leader(uid)
    if err:return err
    w=war_of(p['country'])
    if not w:return '🕊 کشورت در جنگ نیست.'
    cp=ensure_campaign(w);mode=rules.MODES[cp['mode']]
    if db.now()<cp['min_end'] or max(cp['rounds_a'],cp['rounds_b'])<mode.min_rounds:
        return f'🏳 تسلیم نظامی پیش از {mode.minimum//3600} ساعت و {mode.min_rounds} موج ممکن نیست؛ برای پایان زودتر درخواست صلح بده.'
    winner=enemy(p['country'],w)
    myscore=w['score_a'] if w['a']==p['country'] else w['score_b']
    theirscore=w['score_b'] if w['a']==p['country'] else w['score_a']
    if theirscore<=myscore:return '🕊 برای پایان برابر از صلح استفاده کن؛ کشور برتر خودکار تابع نمی‌شود.'
    colonial=can_capitulate(p['country'],winner)[0]
    return finish(w,'won',winner,colonial)


def tick():
    """Run for all worlds, even an idle group; restart does not lose due impacts."""
    for r in db.q("SELECT id FROM missions WHERE status='pending' AND due<=? ORDER BY id LIMIT 100",(db.now(),)):
        try:
            resolve_mission(r['id'])
        except Exception as exc:
            db.ex("UPDATE missions SET status='failed',error=? WHERE id=? AND status='pending'",(type(exc).__name__,r['id']))
            db.log('error',f"mission {r['id']} failed: {type(exc).__name__}")
            notifications.emit(f"⚠️ مأموریت {r['id']} با خطای فنی متوقف شد؛ برای بررسی در گزارش ثبت شد.",all_players=True,key=f"mission:{r['id']}:failed")
    settle()


@db.atomic
def allow_staging(uid,guest):
    p,err=_leader(uid)
    if err:return err
    cid=p['country']
    allied=db.one('SELECT 1 FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)',(cid,guest,guest,cid))
    if guest not in countries.COUNTRIES or not allied:return '🤝 اجازهٔ پایگاه فقط برای متحد رسمی ممکن است.'
    key=f'staging:{cid}:{guest}'
    if db.integer(db.kv_get(key))>db.now():
        db.kv_del(key);msg='🚫 اجازهٔ استفاده از پایگاه برای متحد لغو شد.'
    else:
        if max(infra.structure_strength(cid,k) for k in ('base','airbase','naval'))<=0:return '🏕 ابتدا یک پایگاه زمینی، هوایی یا دریایی عملیاتی بساز.'
        db.kv_set(key,db.now()+72*3600)
        msg=f"🏕 به {countries.COUNTRIES[guest]['name']} اجازهٔ ۷۲ ساعتهٔ استفادهٔ تدارکاتی از پایگاه داده شد؛ مالکیت شهر منتقل نمی‌شود."
    notifications.emit(msg,cids=[cid,guest],uids=[uid])
    return msg
