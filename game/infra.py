"""City-level infrastructure, timed bases and repair logistics.

National summaries are derived from the cities; damaging electricity or a base
never transfers ownership. All numbers are abstract game percentages.
"""
import math

import countries
import db
import texts
from game import geo, rules

INFRA = [("power", "⚡ شبکه برق", 2500), ("airport", "🛫 فرودگاه", 3000),
         ("port", "🚢 بندر", 3000), ("industry", "🏭 مجتمع صنعتی", 4000)]
_I = {k:(k,n,p) for k,n,p in INFRA}
TARGETS = dict((k,n) for k,n,_ in INFRA)
TARGETS.update(garrison="🪖 پادگان", base="🏕 پایگاه زمینی", airbase="✈️ پایگاه هوایی",
               naval="⚓ پایگاه دریایی", logistics="🚚 انبار تدارکات", radar="📡 سامانهٔ پدافند")
BUILDINGS = [
    ("base", "🏕 پایگاه زمینی", 8000, "تا ۸٪ تقویت ضربت؛ متناسب با سلامت"),
    ("airbase", "✈️ پایگاه هوایی", 8000, "عملیات چندمنظوره و پشتیبانی هوایی"),
    ("naval", "⚓ پایگاه دریایی", 8500, "تدارک عملیات آبی‌خاکی"),
    ("logistics", "🚚 انبار تدارکات", 5000, "تأمین مهمات با صنعت ضعیف"),
    ("radar", "📡 سایت پدافندی", 6000, "تا ۹٫۶ امتیاز دفاع مؤثر؛ درصد نهایی به سایر لایه‌ها هم وابسته است"),
    ("housing", "🏘 شهرک مسکونی", 5000, "تا ۸٪ افزایش درآمد ملی"),
    ("bunker", "🛡 پناهگاه", 6000, "تا ۱۰٪ کاهش آسیب همان شهر"),
    ("missile_base", "🚀 پایگاه موشکی / سیلو", 9000, "تا ۶٪ هماهنگی موشکی؛ سهمیهٔ موشک عوض نمی‌شود"),
    ("sam_base", "🛡 پایگاه پدافند یکپارچه", 9000, "تقویت محلی رهگیری؛ همچنان زیر سقف ۷۲٪"),
    ("command", "🧭 مرکز فرماندهی مشترک", 7500, "تا ۳٫۶٪ هماهنگی موج؛ قابل تخریب"),
    ("power_plant", "⚡ نیروگاه گازی / سیکل ترکیبی", 7000, "تولید برق با سوخت؛ ارتقا ظرفیت پشتیبان می‌دهد"),
    ("fuel_depot", "⛽ انبار سوخت و مخزن نفت", 4500, "۲۵۰ واحد ظرفیت اضافه در هر سطح؛ آسیب یعنی اتلاف محلی ذخیره"),
    ("refinery", "🏭 پالایشگاه شهری", 6500, "هر ساعت تا ۳ نفت خام به ۱۲ سوخت در سطح یک"),
    ("shipyard", "🛠 کارخانهٔ کشتی‌سازی / حوض خشک", 7000, "ساخت و تعمیر نفت‌کش؛ فقط بندر دارای آب آزاد"),
]
_B={k:(k,n,p,e) for k,n,p,e in BUILDINGS}
TARGETS.update({k:n for k,n,_,_ in BUILDINGS if k!='housing'})
BUILD_SECONDS={'missile_base':7200,'sam_base':7200,'command':7200,'power_plant':7200,'fuel_depot':3600,'refinery':7200,'shipyard':10800}

def build_seconds(kind,level=1):return BUILD_SECONDS.get(kind,rules.BUILD_TIME)*level


def city_index(cid, city=None):
    cities=geo.CITIES.get(cid, [])
    if city is None:
        return 0 if cities else None
    if not isinstance(city,(int,str)) or isinstance(city,bool):
        return None
    if isinstance(city, str) and city in cities:
        return cities.index(city)
    try:
        idx=int(city)
    except (TypeError,ValueError):
        return None
    return idx if 0 <= idx < len(cities) else None


@db.atomic
def ensure(cid):
    if cid not in geo.CITIES:
        raise ValueError('invalid country')
    legacy=db.jload(db.kv_get(f'infra:{cid}'), {}) or {}
    for i,name in enumerate(geo.CITIES[cid]):
        vals=[db.integer(legacy.get(k,100),100,0,100) for k,_,_ in INFRA]
        if not geo.is_port(cid,i):
            vals[2]=0
        db.ex('INSERT OR IGNORE INTO city_state(cid,city,name,power,airport,port,industry) VALUES(?,?,?,?,?,?,?)',
              (cid,i,name,*vals))
    if not db.kv_get(f'cities_imported:{cid}'):
        old=db.jload(db.kv_get(f'built:{cid}'), {}) or {}
        for kind,value in old.items():
            if kind in _B and value:
                db.ex('INSERT OR IGNORE INTO structures(cid,city,kind,hp,ready_at,created) VALUES(?,0,?,100,?,?)',
                      (cid,kind,db.now(),db.now()))
        db.kv_set(f'cities_imported:{cid}', '1')
    from game import energy
    energy.seed(cid)


def city_state(cid, city=0):
    idx=city_index(cid,city)
    if idx is None:
        raise ValueError('invalid city')
    ensure(cid)
    return dict(db.one('SELECT * FROM city_state WHERE cid=? AND city=?',(cid,idx)))


def state_of(cid):
    if cid not in geo.CITIES:
        return {k:100 for k,_,_ in INFRA}
    ensure(cid)
    rows=[dict(r) for r in db.q('SELECT * FROM city_state WHERE cid=?',(cid,))]
    occupied=set(geo.occupied(cid))
    result={}
    for key,_,_ in INFRA:
        relevant=[r for r in rows if key!='port' or geo.is_port(cid,r['city'])]
        from game import energy
        result[key]=round(sum((energy.electricity(cid,r['city'],r['power']) if key=='power' else r[key]) if r['name'] not in occupied else 0 for r in relevant)/len(relevant)) if relevant else 0
    return result


def _save(cid, st):
    """Legacy import/test helper; production attacks always use city-specific damage."""
    ensure(cid)
    with db.transaction():
        for k,_,_ in INFRA:
            if k in st:
                hp=db.integer(st[k],100,0,100)
                if k=='port':
                    for i in geo.PORT_NODES.get(cid,[]):
                        db.ex('UPDATE city_state SET port=? WHERE cid=? AND city=?',(hp,cid,i))
                else:
                    db.ex(f'UPDATE city_state SET {k}=? WHERE cid=?',(hp,cid))


def structure_strength(cid, kind, city=None):
    if cid not in geo.CITIES or kind not in _B:
        return 0.0
    ensure(cid)
    args=[cid,kind,db.now()]
    sql='SELECT s.*,c.power,c.name FROM structures s JOIN city_state c ON c.cid=s.cid AND c.city=s.city WHERE s.cid=? AND s.kind=? AND (s.ready_at<=? OR s.previous_level>0)'
    if city is not None:
        idx=city_index(cid,city)
        if idx is None:
            return 0.0
        sql+=' AND s.city=?';args.append(idx)
    occupied=set(geo.occupied(cid))
    from game import energy
    strengths=[(r['hp']/100)*min(1.0,energy.electricity(cid,r['city'],r['power'])/50)*(1+(energy.level_at(r,db.now())-1)*0.1)
               for r in db.q(sql,tuple(args)) if r['name'] not in occupied and r['hp']>=20]
    return min(1.2, max(strengths, default=0))


def built(cid):
    return {k:structure_strength(cid,k)>0 for k in _B}


def output_mult(cid):
    st=state_of(cid)
    # Landlocked countries are not penalized for not having a seaport.
    keys=['power','airport','industry']+(['port'] if geo.coastal(cid) else [])
    base=max(0.30, sum(st[k] for k in keys)/(100*len(keys)))
    return base*(1+0.08*structure_strength(cid,'housing'))


def power_ok(cid):
    return state_of(cid)['power']>=40


def port_ok(cid):
    # Domestic/overland markets remain available to landlocked countries.
    return state_of(cid)['port']>=40 if geo.coastal(cid) else state_of(cid)['industry']>=40


def airport_mult(cid):
    return max(0.4, min(1.0,state_of(cid)['airport']/70))


def strike_mult(cid):
    return 1+0.08*structure_strength(cid,'base')


def damage_in_mult(cid, city=None):
    return 1-0.10*min(1.0,structure_strength(cid,'bunker',city))


def limit_notes(cid):
    s=state_of(cid);out=[]
    if s['power']<40:out.append('⚡ برق زیر ۴۰٪: خرید تجهیزات سنگین متوقف')
    if s['airport']<70:out.append('🛫 فرودگاه آسیب‌دیده: کاهش اثر عملیات هوایی')
    if geo.coastal(cid) and s['port']<40:out.append('⚓ بندر زیر ۴۰٪: واردات دریایی و عملیات دریایی متوقف')
    if s['industry']<40:out.append('🏭 صنعت ضعیف: تأمین مهمات نیازمند انبار تدارکات سالم')
    return out


@db.atomic
def damage(cid,key,pct,city=0):
    idx=city_index(cid,city)
    if idx is None or key not in TARGETS or type(pct) is not int or not 0<=pct<=100:
        raise ValueError('invalid infrastructure damage')
    s=city_state(cid,idx)
    from game import energy
    energy.before_change(cid)
    if key=='port' and not geo.is_port(cid,idx):
        raise ValueError('city has no port')
    if key in _B:
        db.ex('UPDATE structures SET hp=MAX(0,hp-?) WHERE cid=? AND city=? AND kind=?',(pct,cid,idx,key))
        row=db.one('SELECT hp FROM structures WHERE cid=? AND city=? AND kind=?',(cid,idx,key))
        hp=row['hp'] if row else 0
    else:
        hp=max(0,s[key]-pct)
        db.ex(f'UPDATE city_state SET {key}=? WHERE cid=? AND city=?',(hp,cid,idx))
    energy.on_damage(cid,idx,key,pct)
    return {'key':key,'hp':hp,'city':idx}


def random_damage(cid,rnd):
    choices=[k for k,_,_ in INFRA if k!='port' or geo.is_port(cid,0)]
    return damage(cid,rnd.choice(choices),rnd.randint(6,12))


@db.atomic
def build(uid,key,city=None):
    from game import state, notifications
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];idx=city_index(cid,city)
    if idx is None or key not in _B:return '⛔ شهر یا ساختمان نامعتبر.'
    s=city_state(cid,idx)
    if s['name'] in geo.occupied(cid):return '🚫 در شهر اشغال‌شده نمی‌توان ساخت.'
    if key in ('naval','shipyard') and not geo.is_port(cid,idx):return '🚫 پایگاه دریایی فقط در شهر بندری ساخته می‌شود.'
    if key in ('airbase','naval','radar','sam_base','missile_base','command','refinery','shipyard') and s['power']<40:return '⚡ ابتدا برق همین شهر را به ۴۰٪ برسان.'
    old=db.one('SELECT * FROM structures WHERE cid=? AND city=? AND kind=?',(cid,idx,key))
    if old and old['ready_at']>db.now():return '⏳ ساخت این پایگاه هنوز تمام نشده است.'
    if old and old['hp']<100:return '🔧 ابتدا پایگاه آسیب‌دیده را تعمیر کن.'
    level=(old['level'] if old else 0)+1
    if level>3:return '✅ این ساختمان به سقف سطح ۳ رسیده است.'
    _,name,base,eff=_B[key];cost=base*level
    if not db.debit(uid,cost):return f'💰 پول کافی نیست؛ نیاز: {texts.money(cid,cost)}'
    from game import energy
    energy.before_change(cid)
    previous=old['level'] if old else 0
    ready=db.now()+build_seconds(key,level)
    db.ex('INSERT INTO structures(cid,city,kind,level,hp,ready_at,created,previous_level) VALUES(?,?,?,?,100,?,?,?) ON CONFLICT(cid,city,kind) DO UPDATE SET level=excluded.level,ready_at=excluded.ready_at,hp=100,previous_level=excluded.previous_level',
          (cid,idx,key,level,ready,db.now(),previous))
    db.audit('construction',uid,country=cid,city=idx,kind=key,level=level,cost=cost)
    msg=f"🏗 ساخت {name} سطح {level} در <b>{s['name']}</b> شروع شد.\n⏱ آماده: {db.tehran_date(ready)} تهران\n💰 {texts.money(cid,cost)}\nاثر بعد از تکمیل: {eff}"
    notifications.emit(msg,cids=[cid],uids=[uid])
    return msg


@db.atomic
def repair(uid,key,city=None):
    from game import state, notifications
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];idx=city_index(cid,city)
    if idx is None or key not in TARGETS:return '⛔ شهر یا هدف تعمیر نامعتبر.'
    s=city_state(cid,idx)
    if s['name'] in geo.occupied(cid):return '🚫 شهر اشغال‌شده باید ابتدا آزاد شود.'
    if key=='port' and not geo.is_port(cid,idx):return '🚫 این شهر بندر ندارد.'
    cooldown=f'cityrepair:{cid}:{idx}'
    if db.now()-db.integer(db.kv_get(cooldown))<rules.REPAIR_COOLDOWN:return '⏳ هر شهر هر ۱۰ دقیقه یک عملیات تعمیر دارد.'
    structure=db.one('SELECT * FROM structures WHERE cid=? AND city=? AND kind=?',(cid,idx,key)) if key in _B else None
    if key in _B and not structure:return '⛔ چنین پایگاهی در این شهر ساخته نشده است.'
    if structure and structure['ready_at']>db.now():return '⏳ ساخت هنوز تکمیل نشده است.'
    hp=structure['hp'] if structure else s[key]
    amount=min(rules.REPAIR_POINTS,100-hp)
    if amount<=0:return '✅ سالم است؛ هزینه‌ای کسر نشد.'
    full=_B[key][2] if key in _B else _I[key][2] if key in _I else 2000
    cost=max(10,math.ceil(full*amount/100/10)*10)
    if not db.debit(uid,cost):return f'💰 نیاز: {texts.money(cid,cost)}'
    from game import energy
    energy.before_change(cid)
    if structure:
        db.ex('UPDATE structures SET hp=MIN(100,hp+?) WHERE cid=? AND city=? AND kind=?',(amount,cid,idx,key))
    else:
        db.ex(f'UPDATE city_state SET {key}=MIN(100,{key}+?) WHERE cid=? AND city=?',(amount,cid,idx))
    db.kv_set(cooldown,db.now())
    db.audit('city_repair',uid,country=cid,city=idx,target=key,points=amount,cost=cost)
    msg=f"🔧 {TARGETS[key]} در {s['name']}: {hp}٪ ← {hp+amount}٪\n💰 هزینه: {texts.money(cid,cost)}"
    notifications.emit(msg,cids=[cid],uids=[uid])
    return msg


def view(uid):
    from game import state
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];st=state_of(cid)
    lines=[texts.hdr(f"زیرساخت {countries.COUNTRIES[cid]['name']}",'🏗'),
           f"ضریب درآمد ملی: {int(output_mult(cid)*100)}٪"]
    lines += [f'{name}: {st[key]}٪' for key,name,_ in INFRA if key!='port' or geo.coastal(cid)]
    lines += limit_notes(cid)
    lines += ['', '🏙 از «شهرها و پایگاه‌ها» شهر را انتخاب کن؛ تعمیر حداکثر ۲۰ واحد درصد در هر ۱۰ دقیقه.']
    return '\n'.join(lines)


def city_view(uid,city):
    from game import state
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];idx=city_index(cid,city)
    if idx is None:return '⛔ شهر نامعتبر.'
    s=city_state(cid,idx)
    from game import energy
    energy.settle(cid)
    lines=[texts.hdr(s['name'],'🏙'),f'⚡ برق مؤثر: {energy.electricity(cid,idx)}٪ · ⛽ سوخت ملی: {energy.fuel(cid)/1000:.1f} واحد']
    for key in ('power','airport','port','industry','garrison'):
        if key!='port' or geo.is_port(cid,idx):lines.append(f'{TARGETS[key]}: {s[key]}٪')
    for r in db.q('SELECT * FROM structures WHERE cid=? AND city=? ORDER BY kind',(cid,idx)):
        status=f"⏳ {max(0,(r['ready_at']-db.now()+59)//60)} دقیقه" if r['ready_at']>db.now() else '✅ فعال' if r['hp']>=20 and s['power']>=40 else '❌ ازکارافتاده'
        lines.append(f"{_B.get(r['kind'],('',r['kind']))[1]} · سطح {r['level']} · سلامت {r['hp']}٪ · {status}")
    if s['name'] in geo.occupied(cid):lines.append('🚩 شهر اشغال‌شده: ساخت‌وساز و تولید متوقف است.')
    return '\n'.join(lines)


def buildings_view(uid):
    from game import state
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    lines=['🏗 <b>ساخت‌وساز شهری</b> — هر شهر، پایگاه مستقل؛ ساخت زمان می‌برد.']
    for _,name,cost,eff in BUILDINGS:lines.append(f'{name}: {texts.money(p["country"],cost)} پایه · {eff}')
    return '\n'.join(lines)
