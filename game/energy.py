"""City depots and refineries; shared national fuel, physical generation and conserved trade.

Units and rates are game abstractions. No NPC decisions or real-world energy data.
"""
import countries
import db
import texts
from game import geo

def _must(ok):
    if not ok:raise RuntimeError('transaction precondition changed')


MILLI=1000
INITIAL_FUEL=120
BASE_CAPACITY=200
DEPOT_CAPACITY=250
REFINE_PER_HOUR=3
FUEL_PER_CRUDE=4
PLANT_BURN_PER_HOUR=2
FUEL_BUY=25
FUEL_SELL=23


def level_at(row,at):
    if not row:return 0
    return row['level'] if row['ready_at']<=at else row['previous_level']


def _raw(cid,city,kind,at=None):
    row=db.one('SELECT * FROM structures WHERE cid=? AND city=? AND kind=?',(cid,city,kind))
    lvl=level_at(row,db.now() if at is None else at)
    return (lvl,row['hp']) if row and lvl and row['hp']>=20 else (0,0)


@db.atomic
def seed(cid):
    """Each pre-existing civil city keeps its original working power supply on upgrade."""
    for row in db.q('SELECT city FROM city_state WHERE cid=?',(cid,)):
        idx=row['city']
        cur=db.ex('INSERT OR IGNORE INTO city_energy(cid,city,last_ts,fuel_milli) VALUES(?,?,?,?)',(cid,idx,db.now(),INITIAL_FUEL*MILLI))
        if cur.rowcount:
            db.ex("INSERT OR IGNORE INTO structures(cid,city,kind,level,hp,ready_at,created,previous_level) VALUES(?,?,'power_plant',1,100,?,?,0)",(cid,idx,db.now(),db.now()))
    # Existing structure records are never healed or reconstructed by repeated seeding.


def capacity(cid,city,at=None):
    lvl,hp=_raw(cid,city,'fuel_depot',at)
    return (BASE_CAPACITY+DEPOT_CAPACITY*lvl*hp//100)*MILLI


def available_cities(cid):
    occupied=set(geo.occupied(cid))
    return [r['city'] for r in db.q('SELECT city,name FROM city_state WHERE cid=? ORDER BY city',(cid,)) if r['name'] not in occupied]


def fuel(cid):
    cities=available_cities(cid)
    return sum(r['fuel_milli'] for r in db.q('SELECT city,fuel_milli FROM city_energy WHERE cid=?',(cid,)) if r['city'] in cities)


def electricity(cid,city,grid=None,at=None,physical=False):
    """Network integrity × generation. 25% emergency power is not normal generation."""
    if grid is None:
        r=db.one('SELECT power FROM city_state WHERE cid=? AND city=?',(cid,city))
        if not r:return 0
        grid=r['power']
    lvl,hp=_raw(cid,city,'power_plant',at)
    reserve=db.one('SELECT COALESCE(SUM(fuel_milli),0) FROM city_energy WHERE cid=?',(cid,))[0] if physical else fuel(cid)
    generation=min(1.0,hp/100*(1+0.10*max(0,lvl-1))) if lvl and reserve>0 else 0.0
    return round(grid*(0.25+0.75*generation))


def _take_fuel(cid,milli):
    """Must be inside a transaction. No partial spend on insufficient fuel."""
    if milli<0 or fuel(cid)<milli:return False
    cities=available_cities(cid)
    for row in db.q('SELECT * FROM city_energy WHERE cid=? ORDER BY fuel_milli DESC,city',(cid,)):
        if row['city'] not in cities:continue
        take=min(milli,row['fuel_milli'])
        if take:db.ex('UPDATE city_energy SET fuel_milli=fuel_milli-? WHERE cid=? AND city=?',(take,cid,row['city']))
        milli-=take
        if not milli:break
    return True


@db.atomic
def settle(cid,until=None,exact=False):
    """Deterministic minute-step catch-up, with exact boundaries for physical changes.

    Rows are loaded once and evolved in memory. A week of downtime is not treated
    as 'fill tanks once, then burn a whole week', which would destroy viable supply.
    """
    clock=db.now() if until is None else min(db.now(),int(until))
    end=clock if exact or until is not None else clock//60*60
    rows=[dict(r) for r in db.q('SELECT e.*,c.power,c.name FROM city_energy e JOIN city_state c USING(cid,city) WHERE e.cid=?',(cid,))]
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(cid,)):
        db.ex('UPDATE city_energy SET last_ts=MAX(last_ts,?) WHERE cid=?',(end,cid))
        return
    claimed=db.integer(db.kv_get(f'claimed:{cid}'))
    for row in rows:row['last_ts']=max(row['last_ts'],claimed)
    active=[r for r in rows if r['last_ts']<end]
    if not active:return
    occupied=set(geo.occupied(cid))
    stores={r['city']:{s['kind']:dict(s) for s in db.q('SELECT * FROM structures WHERE cid=? AND city=?',(cid,r['city']))} for r in rows}
    start=max(min(r['last_ts'] for r in active),end-7*86400)
    cuts={start,end,*range((start//60+1)*60,end,60)}
    for kinds in stores.values():
        cuts.update(s['ready_at'] for s in kinds.values() if start<s['ready_at']<end)
    cuts=sorted(cuts)
    remainder=db.integer(db.kv_get(f'fuel_burn_remainder:{cid}'))
    for left,right in zip(cuts,cuts[1:]):
        burn=0
        for r in active:
            seconds=max(0,right-max(left,r['last_ts']))
            if not seconds or r['name'] in occupied:continue
            kinds=stores[r['city']]
            ref=kinds.get('refinery');lvl=level_at(ref,left)
            if ref and lvl and ref['hp']>=20:
                numerator=seconds*REFINE_PER_HOUR*MILLI*lvl*ref['hp']*r['power']+r['process_remainder']
                throughput,r['process_remainder']=divmod(numerator,3600*10000)
                depot=kinds.get('fuel_depot');dlvl=level_at(depot,left)
                extra=DEPOT_CAPACITY*dlvl*depot['hp']//100 if depot and dlvl and depot['hp']>=20 else 0
                cap=(BASE_CAPACITY+extra)*MILLI
                used=min(r['crude_milli'],throughput,max(0,cap-r['fuel_milli'])//FUEL_PER_CRUDE)
                r['crude_milli']-=used;r['fuel_milli']+=used*FUEL_PER_CRUDE
            plant=kinds.get('power_plant');plvl=level_at(plant,left)
            if plant and plvl and plant['hp']>=20:
                numerator=seconds*PLANT_BURN_PER_HOUR*MILLI*plant['hp']+remainder
                used,remainder=divmod(numerator,3600*100)
                burn+=used
        for r in sorted(rows,key=lambda x:(-x['fuel_milli'],x['city'])):
            if r['name'] in occupied:continue
            amount=min(burn,r['fuel_milli']);r['fuel_milli']-=amount;burn-=amount
            if not burn:break
    for r in active:
        db.ex('UPDATE city_energy SET crude_milli=?,fuel_milli=?,last_ts=?,process_remainder=? WHERE cid=? AND city=?',(r['crude_milli'],r['fuel_milli'],end,r['process_remainder'],cid,r['city']))
    db.kv_set(f'fuel_burn_remainder:{cid}',remainder)
    empty=fuel(cid)==0
    if empty and not db.kv_get(f'fuel_empty:{cid}'):
        from game import notifications
        notifications.emit(f'⚠️ ذخیرهٔ سوخت {countries.COUNTRIES[cid]["name"]} تمام شد؛ برق اضطراری ۲۵٪ است. سوخت وارد کن یا پالایشگاه را تغذیه کن؛ کشور خودکار واگذار نمی‌شود.',cids=[cid])
        db.kv_set(f'fuel_empty:{cid}',1)
    elif not empty:db.kv_del(f'fuel_empty:{cid}')


@db.atomic
def before_change(cid):
    settle(cid,exact=True)
    # Imported lazily to avoid a circular import during initial city setup.
    from game import fleet
    fleet.progress_builds(cid)


@db.atomic
def on_damage(cid,city,key,damage):
    if key!='fuel_depot' or damage<=0:return
    r=db.one('SELECT * FROM city_energy WHERE cid=? AND city=?',(cid,city))
    if not r:return
    cap=capacity(cid,city)
    # Damage causes bounded losses in THAT city only, not a countrywide explosion.
    new_fuel=min(cap,r['fuel_milli']*(100-damage)//100)
    new_crude=min(cap,r['crude_milli']*(100-damage)//100)
    db.ex('UPDATE city_energy SET fuel_milli=?,crude_milli=? WHERE cid=? AND city=?',(new_fuel,new_crude,cid,city))
    db.audit('depot_loss',country=cid,city=city,fuel_milli=r['fuel_milli']-new_fuel,crude_milli=r['crude_milli']-new_crude)


def _actor(uid,city):
    from game import state,infra
    p=state.active(uid)
    if not p or not p['is_leader']:return None,None,'👑 مدیریت ذخایر فقط برای رهبر کشور است.'
    idx=infra.city_index(p['country'],city)
    if idx is None:return None,None,'⛔ شهر نامعتبر.'
    infra.ensure(p['country'])
    if idx not in available_cities(p['country']):return None,None,'🚩 انبار شهر اشغال‌شده در اختیار کشور شما نیست.'
    return p,idx,''


def stock(cid,city,cargo):
    if cargo not in ('crude','fuel'):return 0
    r=db.one(f'SELECT {cargo}_milli FROM city_energy WHERE cid=? AND city=?',(cid,city))
    return r[0] if r else 0


def room(cid,city,cargo):return max(0,capacity(cid,city)-stock(cid,city,cargo))


def take_cargo(cid,city,cargo,milli):
    if cargo not in ('crude','fuel') or milli<0 or stock(cid,city,cargo)<milli:return False
    db.ex(f'UPDATE city_energy SET {cargo}_milli={cargo}_milli-? WHERE cid=? AND city=?',(milli,cid,city));return True


def deposit(cid,city,cargo,milli):
    if cargo not in ('crude','fuel') or milli<0 or city not in available_cities(cid) or room(cid,city,cargo)<milli:return False
    db.ex(f'UPDATE city_energy SET {cargo}_milli={cargo}_milli+? WHERE cid=? AND city=?',(milli,cid,city));return True


def _market_fuel():
    from game import economy
    pool=economy.market_pool()
    if 'fuel' not in pool['stock']:
        pool['stock']['fuel']=5000;economy._save_pool(pool)
    return pool


def reference_price(cargo):
    from game import economy
    return FUEL_BUY if cargo=='fuel' else economy.good_price('oil')


@db.atomic
def buy_fuel(uid,city,amount=50):
    from game import economy
    p,idx,err=_actor(uid,city)
    if err:return err
    if type(amount) is not int or not 1<=amount<=200:return '⛔ خرید سوخت: عدد صحیح ۱ تا ۲۰۰.'
    cid=p['country'];settle(cid,exact=True);milli=amount*MILLI
    if room(cid,idx,'fuel')<milli:return '📦 مخزن همین شهر جا ندارد؛ انبار سوخت بساز یا شهر دیگری انتخاب کن.'
    pool=_market_fuel();cost=amount*FUEL_BUY
    if pool['stock']['fuel']<amount:return '🏦 عرضهٔ سوخت بازار کافی نیست.'
    if not db.debit(uid,cost):return f'💰 نیاز: {cost} دلار برای {amount} واحد سوخت.'
    _must(deposit(cid,idx,'fuel',milli))
    pool['stock']['fuel']-=amount;pool['money']+=cost;economy._save_pool(pool)
    db.audit('fuel_purchase',uid,city=idx,units=amount,cost=cost)
    return f'⛽ {amount} واحد سوخت در {geo.CITIES[cid][idx]} ذخیره شد؛ {cost} دلار پرداخت شد.'


@db.atomic
def sell_fuel(uid,city,amount=50):
    from game import economy
    p,idx,err=_actor(uid,city)
    if err:return err
    if type(amount) is not int or not 1<=amount<=200:return '⛔ فروش سوخت: عدد صحیح ۱ تا ۲۰۰.'
    cid=p['country'];settle(cid,exact=True);milli=amount*MILLI;pool=_market_fuel();value=amount*FUEL_SELL
    if stock(cid,idx,'fuel')<milli:return '📦 سوخت همین شهر کافی نیست.'
    if pool['money']<value:return '🏦 نقدینگی بازار کافی نیست؛ پول ساخته نشد.'
    _must(take_cargo(cid,idx,'fuel',milli))
    pool['stock']['fuel']+=amount;pool['money']-=value;economy._save_pool(pool)
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(value,uid));db.audit('fuel_sale',uid,city=idx,units=amount,amount=value)
    return f'⛽ {amount} واحد سوخت فروخته شد؛ {value} دلار از ذخیرهٔ بازار منتقل شد.'


@db.atomic
def import_crude(uid,city,amount=5):
    from game import economy
    p,idx,err=_actor(uid,city)
    if err:return err
    if type(amount) is not int or not 1<=amount<=20:return '⛔ نفت خام: عدد صحیح ۱ تا ۲۰.'
    cid=p['country'];settle(cid,exact=True);bag=economy.holdings(uid)
    if bag.get('oil',0)<amount:return '📦 ابتدا نفت خام را از تجارت بخر.'
    if room(cid,idx,'crude')<amount*MILLI:return '📦 مخزن نفت خام جا ندارد.'
    bag['oil']-=amount;economy._save_holdings(uid,bag)
    _must(deposit(cid,idx,'crude',amount*MILLI))
    db.audit('crude_to_refinery',uid,city=idx,units=amount)
    return f'🛢 {amount} واحد نفت خام از انبار تجارت به مخزن شهری منتقل شد؛ با پالایشگاه آماده به سوخت تبدیل می‌شود.'


def view(uid,city=0):
    p,idx,err=_actor(uid,city)
    if err:return err
    cid=p['country'];settle(cid)
    return '\n'.join([texts.hdr(f'انرژی {geo.CITIES[cid][idx]}','⚡'),
        f'برق مؤثر شهر: {electricity(cid,idx)}٪',f'سوخت در دسترس کشور: {fuel(cid)/MILLI:.1f} واحد',
        f'سوخت همین شهر: {stock(cid,idx,"fuel")/MILLI:.1f} / {capacity(cid,idx)//MILLI}',
        f'نفت خام همین شهر: {stock(cid,idx,"crude")/MILLI:.1f} / {capacity(cid,idx)//MILLI}',
        'نیروگاه سالم: ۲ واحد سوخت/ساعت؛ پالایشگاه سطح یک: حداکثر ۳ نفت خام → ۱۲ سوخت/ساعت.',
        'خرید سوخت ۲۵ و فروش ۲۳ دلار/واحد؛ نفت تجاری و دکل سرمایه‌گذاری همچنان جدا هستند.',
        'مدل بازی: ذخایر شهرهای آزاد، شبکهٔ سوخت ملی مشترک دارند؛ انبار اشغال‌شده قابل برداشت نیست.'])
