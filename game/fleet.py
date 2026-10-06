"""Player-owned tankers, cargo escrow, chokepoint travel, escorts and wartime targets.

Physical classes use familiar names; prices, capacity and timings are explicitly game stats.
"""
import json
import math
import random
import countries
import db
import texts
from game import state,geo,infra,energy,straits,sea_routes,notifications,catalog

def _must(ok):
    if not ok:raise RuntimeError('transaction precondition changed')


CLASSES={
 'coastal':('نفت‌کش ساحلی',4500,40,7200,{'crude','fuel'}),
 'product':('نفت‌کش فرآورده‌بر MR',8500,80,10800,{'fuel'}),
 'aframax':('نفت‌کش افرامکس',10000,100,14400,{'crude'}),
 'vlcc':('نفت‌کش VLCC',16000,180,21600,{'crude'}),
}
LIVE=('offered','outbound','held','unloading','returning','return_held')
MAX_SHIPS=5
VOYAGE_DEADLINE=72*3600
CARGO_LABELS={'crude':'نفت خام','fuel':'سوخت پالایش‌شده'}
STATUS={'building':'در حال ساخت','docked':'در بندر','reserved':'منتظر پذیرش قرارداد','sailing':'در مسیر',
 'returning':'در بازگشت','seized':'توقیف در بندر اشغالی','sunk':'غرق‌شده'}
VSTATUS={'offered':'پیشنهاد','outbound':'در مسیر رفت','held':'پشت گذرگاه بسته','unloading':'منتظر تخلیه',
 'returning':'بازگشت','return_held':'بازگشت متوقف','returned':'پایان سفر','cancelled':'لغوشده','sunk':'غرق‌شده'}


def _leader(uid):
    p=state.active(uid)
    return (p,'') if p and p['is_leader'] else (None,'👑 فقط رهبر کشور می‌تواند ناوگان را مدیریت کند.')


def _port(cid,city):
    return sea_routes.port_sea(cid,city) and city in energy.available_cities(cid) and infra.city_state(cid,city)['port']>=40


def _ship_for(uid,sid):
    p,err=_leader(uid)
    if err:return None,None,err
    if type(sid) is not int or sid<1:return None,None,'⛔ شناسهٔ کشتی نامعتبر.'
    ship=db.one('SELECT * FROM tankers WHERE id=?',(sid,))
    if not ship or ship['country']!=p['country']:return None,None,'⛔ این نفت‌کش متعلق به کشور شما نیست.'
    return p,dict(ship),''


def live_voyage(sid):
    return db.one("SELECT * FROM voyages WHERE ship_id=? AND status IN ('offered','outbound','held','unloading','returning','return_held')",(sid,))


@db.atomic
def progress_builds(cid):
    now=db.now();occupied=set(geo.occupied(cid))
    for row in db.q("SELECT * FROM tankers WHERE country=? AND status IN ('building','docked','reserved','seized')",(cid,)):
        s=dict(row);idx=s['home_city'];city=db.one('SELECT * FROM city_state WHERE cid=? AND city=?',(cid,idx))
        if not city:continue
        if city['name'] in occupied:
            if s['status'] in ('docked','reserved'):db.ex("UPDATE tankers SET status='seized' WHERE id=?",(s['id'],))
            db.ex('UPDATE tankers SET last_build=? WHERE id=?',(now,s['id']))
            continue
        if s['status']=='seized':
            db.ex("UPDATE tankers SET status='docked' WHERE id=?",(s['id'],));continue
        if s['status']!='building' or now<=s['last_build']:continue
        yard=db.one("SELECT * FROM structures WHERE cid=? AND city=? AND kind='shipyard'",(cid,idx))
        left=s['last_build'];remaining=s['build_work']
        cuts=sorted({left,now,*([yard['ready_at']] if yard and left<yard['ready_at']<now else [])})
        for a,b in zip(cuts,cuts[1:]):
            lvl=energy.level_at(yard,a)
            if yard and lvl and yard['hp']>=20 and city['port']>=40 and city['power']>=40:
                rate=yard['hp']*(100+10*(lvl-1))//10
                remaining=max(0,remaining-(b-a)*rate)
        status='docked' if remaining==0 and s['hp']>=20 else 'building'
        db.ex('UPDATE tankers SET build_work=?,last_build=?,status=? WHERE id=?',(remaining,now,status,s['id']))
        if status=='docked':notifications.emit(f"🚢 ساخت «{texts.esc(s['name'])}» در {city['name']} کامل شد؛ اکنون قابل بارگیری است.",cids=[cid],key=f"tanker:{s['id']}:built")


@db.atomic
def build(uid,city,kind='coastal',name=None):
    p,err=_leader(uid)
    if err:return err
    if kind not in CLASSES:return '⛔ ردهٔ نفت‌کش نامعتبر.'
    cid=p['country'];idx=infra.city_index(cid,city);infra.ensure(cid)
    if idx is None or not _port(cid,idx):return '⚓ بندر سالم و آزاد با دسترسی به آب آزاد لازم است.'
    if infra.structure_strength(cid,'shipyard',idx)<=0:return '🛠 ابتدا کارخانهٔ کشتی‌سازی همین بندر را تکمیل کن.'
    if db.one("SELECT COUNT(*) FROM tankers WHERE country=? AND status!='sunk'",(cid,))[0]>=MAX_SHIPS:return '⚓ سقف ناوگان هر کشور پنج نفت‌کش فعال/در حال ساخت است.'
    label,cost,capacity,seconds,_=CLASSES[kind]
    if name is not None and not isinstance(name,str):return '⛔ نام باید متن باشد.'
    name=' '.join((name or label).split())
    if not 3<=len(name)<=40:return '⛔ نام کشتی باید ۳ تا ۴۰ حرف باشد.'
    if not db.debit(uid,cost):return f'💰 هزینهٔ ساخت: {cost} دلار.'
    cur=db.ex('INSERT INTO tankers(country,creator,name,class,home_city,build_work,last_build,created) VALUES(?,?,?,?,?,?,?,?)',(cid,uid,name,kind,idx,seconds*1000,db.now(),db.now()))
    db.audit('tanker_order',uid,ship=cur.lastrowid,class_id=kind,cost=cost,city=idx)
    msg=f'🚢 سفارش «{texts.esc(name)}» ثبت شد: {label} · ظرفیت بازی {capacity} واحد · زمان پایه {seconds//3600} ساعت.\nتعطیلی یا آسیب کشتی‌سازی پیشرفت را متوقف/کند می‌کند؛ کشتی فوری آماده نمی‌شود.'
    notifications.emit(msg,cids=[cid],uids=[uid],key=f'tanker:{cur.lastrowid}:order')
    return msg


def escort_locked(uid,iid):
    return db.one("SELECT COALESCE(SUM(e.units),0) FROM naval_escorts e JOIN voyages v ON v.id=e.voyage_id WHERE e.uid=? AND e.iid=? AND v.status IN ('outbound','held','unloading','returning','return_held')",(uid,iid))[0]


def _escorts(uid,n):
    rows=[]
    for r in db.q('SELECT * FROM inventory WHERE uid=? AND qty>0 AND dur>=20',(uid,)):
        if catalog.primary(r['iid'])!='دریایی':continue
        free=r['qty']-escort_locked(uid,r['iid'])
        if free>0:rows.append((r['iid'],free,r['dur'],countries.ITEMS[r['iid']][4]*r['dur']/100))
    rows.sort(key=lambda r:r[3],reverse=True);out=[]
    for iid,free,dur,guard in rows:
        take=min(n,free)
        if take:out.append((iid,take,guard));n-=take
        if not n:break
    return None if n else out


@db.atomic
def offer(uid,sid,dest,dest_city,cargo,amount,escort_count=0):
    p,s,err=_ship_for(uid,sid)
    if err:return err
    progress_builds(p['country']);s=dict(db.one('SELECT * FROM tankers WHERE id=?',(sid,)))
    if db.now()-db.integer(db.kv_get(f'voyage_offer:{uid}'))<60:return '⏳ بین پیشنهادهای حمل همین فرمانده یک دقیقه فاصله لازم است.'
    if s['status']!='docked' or s['hp']<40 or live_voyage(sid):return '⛔ کشتی باید در بندر، بدون سفر/پیشنهاد دیگر و با سلامت حداقل ۴۰٪ باشد.'
    if type(amount) is not int or not 1<=amount<=CLASSES[s['class']][2] or cargo not in CLASSES[s['class']][4]:return '⛔ نوع بار یا مقدار با ظرفیت این رده سازگار نیست.'
    if type(escort_count) is not int or not 0<=escort_count<=3:return '⛔ اسکورت: صفر تا سه شناور واقعی.'
    if dest not in countries.COUNTRIES or dest==p['country']:return '⛔ کشور دریافت‌کننده باید یک کشور دیگر با رهبر واقعی باشد.'
    buyer=db.one('SELECT uid FROM users WHERE country=? AND is_leader=1',(dest,))
    if not buyer:return '🕊 خریداری با رهبر واقعی وجود ندارد؛ قرارداد NPC نداریم.'
    infra.ensure(dest);idx=infra.city_index(dest,dest_city)
    if idx is None or not _port(dest,idx) or not _port(s['country'],s['home_city']):return '⚓ بندر مبدأ و مقصد باید سالم و آزاد باشند.'
    from game import campaign
    w=campaign.war_of(s['country'])
    if w and campaign.enemy(s['country'],w)==dest:return '⚔️ فروش مستقیم به دشمن فعال مجاز نیست.'
    if any(db.integer(db.kv_get(f'sanction_pair:{a}:{b}'))>db.now() for a,b in ((s['country'],dest),(dest,s['country']))):return '🚫 تحریم دوجانبهٔ همین طرف‌ها باید رفع شود.'
    energy.settle(s['country']);energy.settle(dest)
    if energy.stock(s['country'],s['home_city'],cargo)<amount*1000:return '📦 بار کافی در مخزن بندر مبدأ نیست.'
    if energy.room(dest,idx,cargo)<amount*1000:return '📦 انبار مقصد برای این پیشنهاد جا ندارد.'
    path=sea_routes.route(sea_routes.port_sea(s['country'],s['home_city']),sea_routes.port_sea(dest,idx))
    if path is None:return '🌉 مسیر بازی به‌علت گذرگاه بسته قابل عبور نیست؛ فعلاً پیشنهاد صادر نشد.'
    if escort_count and (infra.structure_strength(s['country'],'naval',s['home_city'])<=0 or _escorts(uid,escort_count) is None):return '🛡 برای اسکورت، پایگاه دریایی همین بندر و شناور آزاد واقعی لازم است.'
    quoted_fees=straits.transit_quote(uid,[leg['gate'] for leg in path])
    if quoted_fees is None:return '🌉 مسیر در زمان قیمت‌گذاری بسته شد؛ پیشنهادی صادر نشد.'
    price=energy.reference_price(cargo)*amount
    cur=db.ex('INSERT INTO voyages(ship_id,seller,buyer,source,source_city,dest,dest_city,cargo,amount,price,offered,expires,escort_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,uid,buyer['uid'],s['country'],s['home_city'],dest,idx,cargo,amount,price,db.now(),db.now()+1800,escort_count))
    db.ex('UPDATE voyages SET fees=? WHERE id=?',(json.dumps(quoted_fees),cur.lastrowid))
    db.kv_set(f'voyage_offer:{uid}',db.now())
    db.ex("UPDATE tankers SET status='reserved' WHERE id=?",(sid,))
    msg=f'📜 پیشنهاد حمل #{cur.lastrowid}: «{texts.esc(s["name"])}» · {amount} واحد {CARGO_LABELS[cargo]} به {geo.CITIES[dest][idx]} · {price} دلار.\nسقف عوارض تأییدشدهٔ فروشنده: {sum(quoted_fees.values())} دلار؛ افزایش تعرفه نیاز به پیشنهاد تازه دارد.\nخریدار ۳۰ دقیقه برای پذیرش فرصت دارد. تا پذیرش نه پولی کسر می‌شود نه باری خارج می‌شود. پذیرش: منوی ناوگان → پیشنهادها.'
    notifications.emit(msg,cids=[s['country'],dest],uids=[uid,buyer['uid']],key=f'voyage:{cur.lastrowid}:offer')
    return msg


def _voyage_fuel(s,path):return max(2,2*math.ceil(sum(p['seconds'] for p in path)/3600)*(2 if s['class'] in ('aframax','vlcc') else 1))


@db.atomic
def accept(uid,vid):
    p,err=_leader(uid)
    if err:return err
    v=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
    if not v or v['buyer']!=uid or p['country']!=v['dest']:return '⛔ این پیشنهاد برای کشور/حساب شما نیست.'
    if v['status']!='offered' or v['expires']<=db.now():return '⛔ پیشنهاد پاسخ داده شده یا منقضی است.'
    s=dict(db.one('SELECT * FROM tankers WHERE id=?',(v['ship_id'],)))
    seller=state.active(v['seller'])
    if not seller or not seller['is_leader'] or seller['country']!=v['source']:return '⛔ فروشنده دیگر رهبر این کشور نیست؛ پیشنهاد تازه لازم است.'
    if s['status']!='reserved' or s['country']!=v['source'] or s['hp']<40:return '⛔ نفت‌کش دیگر آمادهٔ این سفر نیست.'
    from game import campaign
    w=campaign.war_of(v['source'])
    if w and campaign.enemy(v['source'],w)==v['dest']:return '⚔️ در زمان جنگ دوجانبه، این پیشنهاد پذیرفته نمی‌شود.'
    if any(db.integer(db.kv_get(f'sanction_pair:{a}:{b}'))>db.now() for a,b in ((v['source'],v['dest']),(v['dest'],v['source']))):return '🚫 تحریم دوجانبه برقرار است.'
    if not _port(v['source'],v['source_city']) or not _port(v['dest'],v['dest_city']):return '⚓ بندر مبدأ/مقصد از دسترس خارج شده است.'
    energy.settle(v['source']);energy.settle(v['dest'])
    cargo=v['amount']*1000
    if energy.stock(v['source'],v['source_city'],v['cargo'])<cargo:return '📦 بار کافی دیگر در مخزن مبدأ نیست.'
    if energy.room(v['dest'],v['dest_city'],v['cargo'])<cargo:return '📦 مقصد جا ندارد؛ پذیرش بدون برداشت پول رد شد.'
    path=sea_routes.route(sea_routes.port_sea(v['source'],v['source_city']),sea_routes.port_sea(v['dest'],v['dest_city']))
    if path is None:return '🌉 مسیر قانونی فعلاً بسته است؛ پولی کسر نشد.'
    fees=straits.transit_quote(v['seller'],[leg['gate'] for leg in path])
    if fees is None:return '🌉 گذرگاه مسیر بسته شده است.'
    budget=sum(db.jload(v['fees'],{}).values())
    if sum(fees.values())>budget:return '🛃 تعرفه از سقف پیشنهاد بیشتر شده؛ بدون برداشت پول، پیشنهاد تازه لازم است.'
    escort=_escorts(v['seller'],v['escort_count'])
    if escort is None or (v['escort_count'] and infra.structure_strength(v['source'],'naval',v['source_city'])<=0):return '🛡 اسکورت تعهدشده آزاد/عملیاتی نیست.'
    fuel_cost=_voyage_fuel(s,path)*1000
    if energy.fuel(v['source'])<fuel_cost+(cargo if v['cargo']=='fuel' else 0):return '⛽ سوخت بار و سوخت حرکت باید جداگانه موجود باشد.'
    if seller['money']<sum(fees.values()):return '💰 موجودی فروشنده برای عوارض مسیر کافی نیست.'
    if p['money']<v['price']:return '💰 موجودی خریدار کافی نیست.'
    _must(db.debit(uid,v['price']))
    _must(straits.pay_transit(v['seller'],fees))
    _must(energy.take_cargo(v['source'],v['source_city'],v['cargo'],cargo))
    _must(energy._take_fuel(v['source'],fuel_cost))
    for iid,units,guard in escort:
        db.ex('INSERT INTO naval_escorts(voyage_id,uid,iid,units,guard) VALUES(?,?,?,?,?)',(vid,v['seller'],iid,units,guard))
    now=db.now()
    db.ex("UPDATE voyages SET status='outbound',remaining_milli=?,escrow=price,started=?,deadline=?,route=?,leg=0,leg_due=?,region=?,fees=? WHERE id=?",(cargo,now,now+VOYAGE_DEADLINE,json.dumps(path),now+path[0]['seconds'],path[0]['a'],json.dumps(fees),vid))
    db.ex("UPDATE tankers SET status='sailing' WHERE id=?",(s['id'],))
    db.audit('voyage_departure',uid,voyage=vid,escrow=v['price'],cargo_milli=cargo,fees=fees,fuel_milli=fuel_cost,route=path)
    msg=f'🚢 سفر #{vid} آغاز شد؛ پول خریدار امانی است و پس از تحویل واقعی آزاد می‌شود.\nمسیر: '+ ' ← '.join([sea_routes.SEAS[path[0]['a']],*[sea_routes.SEAS[leg['b']] for leg in path]])+f'\nزمان پایه: {sum(leg["seconds"] for leg in path)//60} دقیقه · سوخت حرکت {fuel_cost//1000} · عوارض {sum(fees.values())} دلار.\nغرق شدن: بازپرداخت امانت؛ خسارت جزئی: پرداخت فقط برای بار رسیده. اسکورت از موجودی آزاد همان کشور رزرو شد.'
    notifications.emit(msg,cids=[v['source'],v['dest']],uids=[v['seller'],uid],key=f'voyage:{vid}:departure')
    return msg


@db.atomic
def cancel_offer(uid,vid):
    v=db.one('SELECT * FROM voyages WHERE id=?',(vid,));p=state.active(uid)
    if not v or not p or not p['is_leader'] or not ((uid==v['seller'] and p['country']==v['source']) or (uid==v['buyer'] and p['country']==v['dest'])):return '⛔ پیشنهاد متعلق به شما نیست.'
    if v['status']!='offered':return '⛔ فقط پیشنهادِ حرکت‌نکرده قابل لغو است؛ امانت سفر در حال حرکت را نمی‌توان دو بار خرج کرد.'
    db.ex("UPDATE voyages SET status='cancelled',outcome='لغو پیش از حرکت',completed_at=? WHERE id=?",(db.now(),vid))
    db.ex("UPDATE tankers SET status='docked' WHERE id=? AND status='reserved'",(v['ship_id'],))
    return '🛑 پیشنهاد لغو شد؛ هیچ پول یا باری منتقل نشده بود.'


def _refund(v,reason):
    if v['escrow']:
        db.ex('UPDATE users SET money=money+? WHERE uid=?',(v['escrow'],v['buyer']))
    db.ex('UPDATE voyages SET escrow=0,outcome=? WHERE id=?',(reason,v['id']))
    v['escrow']=0


def _release_escorts(v,extra_wear=0):
    for e in db.q('SELECT * FROM naval_escorts WHERE voyage_id=?',(v['id'],)):
        inv=db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(e['uid'],e['iid']))
        if inv and inv['qty']:
            wear=math.ceil(min(100,e['wear']+extra_wear)*e['units']/inv['qty'])
            db.ex('UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?',(wear,e['uid'],e['iid']))
    db.ex('DELETE FROM naval_escorts WHERE voyage_id=?',(v['id'],))


def _start_return(v,at,reason,completed_path=None):
    path=json.loads(v['route'])
    if completed_path is None:completed_path=path[:v['leg']]
    back=sea_routes.reverse(completed_path)
    if not back:back=[{'a':v['region'],'b':sea_routes.port_sea(v['source'],v['source_city']),'gate':None,'seconds':3600}]
    db.ex("UPDATE voyages SET status='returning',route=?,leg=0,leg_due=?,region=?,outcome=? WHERE id=?",(json.dumps(back),at+back[0]['seconds'],back[0]['a'],reason,v['id']))
    db.ex("UPDATE tankers SET status='returning' WHERE id=?",(v['ship_id'],))
    db.audit('voyage_return',v['seller'],voyage=v['id'],reason=reason,route=back)


def _try_unload(v,at):
    p=state.active(v['buyer'])
    if not p or p['country']!=v['dest'] or not p['is_leader']:
        _refund(v,'گیرنده تغییر کرد؛ امانت برگشت')
        _start_return(v,at,'گیرنده تغییر کرد؛ بار در بازگشت',json.loads(v['route']))
        notifications.emit(f'↩️ گیرندهٔ سفر #{v["id"]} تغییر کرد؛ امانت به همان حساب خریدار بازپرداخت شد و بار در مسیر بازگشت است.',cids=[v['source'],v['dest']],uids=[v['seller'],v['buyer']],key=f'voyage:{v["id"]}:buyer_changed')
        return
    if not _port(v['dest'],v['dest_city']):return
    energy.settle(v['dest'],until=at)
    if energy.room(v['dest'],v['dest_city'],v['cargo'])<v['remaining_milli']:return
    delivered=v['remaining_milli']
    _must(energy.deposit(v['dest'],v['dest_city'],v['cargo'],delivered))
    payout=v['price']*delivered//(v['amount']*1000)
    payout=min(payout,v['escrow']);refund=v['escrow']-payout
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(payout,v['seller']))
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(refund,v['buyer']))
    db.ex('UPDATE voyages SET escrow=0,remaining_milli=0,delivered_at=? WHERE id=?',(at,v['id']))
    msg=f'✅ تحویل سفر #{v["id"]}: {delivered/1000:.1f} واحد {CARGO_LABELS[v["cargo"]]}؛ {payout} دلار به فروشنده و {refund} دلار ماندهٔ امانت به خریدار برگشت.\nکشتی خالی در مسیر بازگشت است؛ نه بار و نه پول دوباره تحویل نمی‌شود.'
    db.audit('voyage_delivery',v['buyer'],voyage=v['id'],cargo_milli=delivered,payout=payout,refund=refund)
    notifications.emit(msg,cids=[v['source'],v['dest']],uids=[v['seller'],v['buyer']],key=f'voyage:{v["id"]}:delivery')
    _start_return(v,at,'تحویل کامل' if delivered==v['amount']*1000 else 'تحویل جزئی',json.loads(v['route']))


def _timeout(v,at):
    _refund(v,'مهلت ۷۲ساعته تمام شد؛ امانت برگشت')
    _start_return(v,at,'عدم تحویل در مهلت؛ بازگشت بار')
    notifications.emit(f'↩️ سفر #{v["id"]} در ۷۲ ساعت تحویل نشد؛ امانت خریدار بازپرداخت و کشتی با بار باقی‌مانده وارد مسیر بازگشت شد.',cids=[v['source'],v['dest']],uids=[v['seller'],v['buyer']],key=f'voyage:{v["id"]}:timeout')


@db.atomic
def tick_one(vid):
    row=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
    if not row or row['status'] not in LIVE:return
    v=dict(row);now=db.now()
    if v['status']=='offered':
        if v['expires']<=now:
            db.ex("UPDATE voyages SET status='cancelled',outcome='انقضای پیشنهاد',completed_at=? WHERE id=?",(now,vid))
            db.ex("UPDATE tankers SET status='docked' WHERE id=? AND status='reserved'",(v['ship_id'],))
        return
    if v['status']=='unloading':
        _try_unload(v,min(now,v['deadline']))
        current=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
        if current['status']=='unloading' and now>=v['deadline']:_timeout(dict(current),now)
        return
    returning=v['status'] in ('returning','return_held');path=json.loads(v['route'])
    horizon=now if returning else min(now,v['deadline'])
    while v['leg']<len(path) and v['leg_due']<=horizon:
        leg=path[v['leg']];cross=straits.pass_time(leg['gate'],v['leg_due'])
        if cross>horizon:
            if not returning and now>=v['deadline']:
                _timeout(v,now);return
            db.ex('UPDATE voyages SET status=? WHERE id=?',('return_held' if returning else 'held',vid))
            return  # keep original gate arrival; early reopening can shorten the wait
        v['region']=leg['b'];v['leg']+=1
        if v['leg']<len(path):v['leg_due']=cross+path[v['leg']]['seconds']
        else:v['leg_due']=cross
        db.ex('UPDATE voyages SET leg=?,leg_due=?,region=?,status=? WHERE id=?',(v['leg'],v['leg_due'],v['region'],'returning' if returning else 'outbound',vid))
    if v['leg']<len(path):
        if not returning and now>=v['deadline']:_timeout(v,now)
        return
    if returning:
        if not _port(v['source'],v['source_city']):
            db.ex("UPDATE voyages SET status='return_held' WHERE id=?",(vid,));return
        energy.settle(v['source'])
        if v['remaining_milli'] and energy.room(v['source'],v['source_city'],v['cargo'])<v['remaining_milli']:
            db.ex("UPDATE voyages SET status='return_held' WHERE id=?",(vid,));return
        if v['remaining_milli']:_must(energy.deposit(v['source'],v['source_city'],v['cargo'],v['remaining_milli']))
        _release_escorts(v,3)
        db.ex("UPDATE voyages SET status='returned',remaining_milli=0,completed_at=? WHERE id=?",(now,vid))
        db.ex("UPDATE tankers SET status='docked',hp=MAX(1,hp-2) WHERE id=?",(v['ship_id'],))
        notifications.emit(f'⚓ نفت‌کش سفر #{vid} به بندر مبدأ برگشت؛ اسکورت آزاد شد.',cids=[v['source']],uids=[v['seller']],key=f'voyage:{vid}:returned')
    else:
        db.ex("UPDATE voyages SET status='unloading' WHERE id=?",(vid,))
        v['status']='unloading';_try_unload(v,v['leg_due'])
        current=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
        if current['status']=='unloading' and now>=v['deadline']:_timeout(dict(current),now)


def tick():
    straits.tick()
    for r in db.q('SELECT DISTINCT country FROM tankers'):
        progress_builds(r['country'])
    for r in db.q("SELECT id FROM voyages WHERE status IN ('offered','outbound','held','unloading','returning','return_held') ORDER BY id"):
        try:tick_one(r['id'])
        except Exception as exc:db.log('error',f'voyage {r["id"]}: {type(exc).__name__}')


@db.atomic
def repair(uid,sid):
    p,s,err=_ship_for(uid,sid)
    if err:return err
    if s['status']!='docked' or live_voyage(sid):return '⚓ تعمیر فقط در بندر، خارج از سفر یا پیشنهاد ممکن است.'
    if not _port(s['country'],s['home_city']) or infra.structure_strength(s['country'],'shipyard',s['home_city'])<=0:return '🛠 کشتی‌سازی سالمِ همین بندر لازم است.'
    if db.now()-s['repair_at']<1800:return '⏳ هر نفت‌کش هر ۳۰ دقیقه یک تعمیر.'
    points=min(20,100-s['hp'])
    if not points:return '✅ نفت‌کش سالم است؛ هزینه‌ای کسر نشد.'
    cost=math.ceil(CLASSES[s['class']][1]*points/100)
    if not db.debit(uid,cost):return f'💰 هزینه: {cost} دلار.'
    db.ex('UPDATE tankers SET hp=hp+?,repair_at=? WHERE id=?',(points,db.now(),sid))
    return f'🛠 {points} واحد درصد از سلامت نفت‌کش تعمیر شد؛ {cost} دلار.'


def _naval_origins(cid):
    from game import war
    hosts=[cid]+[h for h in war.allies_of(cid) if db.integer(db.kv_get(f'staging:{h}:{cid}'))>db.now()]
    return {sea_routes.port_sea(h,i) for h in hosts for i in geo.PORT_NODES.get(h,[]) if infra.structure_strength(h,'naval',i)>0 and _port(h,i)}-{None}


def target_context(s):
    v=live_voyage(s['id'])
    if s['status'] in ('sunk','seized','building'):return None,'⛔ این کشتی غرق، توقیف یا هنوز در حال ساخت است؛ کشتی‌سازی را هدف بگیر.'
    if v and v['status']=='unloading':return None,'🕊 کشتی در بندر کشور ثالث برای تخلیه است؛ بدون جنگ با میزبان، حمله در آن بندر مجاز نیست.'
    if s['status'] in ('sailing','returning') and v:
        return {'sea':v['region'],'sea_target':True,'port_city':s['home_city']},''
    if not _port(s['country'],s['home_city']):return None,'⚓ نفت‌کش در بندر قابل هدف‌گیری نیست یا بندر اشغال شده است.'
    return {'sea':sea_routes.port_sea(s['country'],s['home_city']),'sea_target':False,'port_city':s['home_city']},''


@db.atomic
def attack(uid,sid,kind,count=1):
    from game import campaign
    p,err=_leader(uid)
    if err:return err
    if kind not in ('دریایی','هوایی','چندمنظوره','پهپادی','موشکی'):return '⛔ نفت‌کش هدف عملیات زمینی یا توپخانهٔ سراسری نیست.'
    s=db.one('SELECT * FROM tankers WHERE id=?',(sid,))
    w=campaign.war_of(p['country'])
    if not s or not w or s['country']!=campaign.enemy(p['country'],w):return '⛔ فقط نفت‌کش کشور دشمنِ همین جنگ، نه خودی یا کشور بی‌طرف.'
    v=live_voyage(sid)
    if v:tick_one(v['id'])
    s=dict(db.one('SELECT * FROM tankers WHERE id=?',(sid,)))
    loc,err=target_context(s)
    if err:return err
    if kind=='دریایی' and not any(sea_routes.coastal_reach(origin,loc['sea']) for origin in _naval_origins(p['country'])):
        return '🗺 در این پهنه نیروی دریایی مستقر نداری؛ پایگاه خودی یا متحد با اجازه لازم است، نه شلیک از آن‌سوی جهان.'
    required=sea_routes.air_band(p['country'],loc['sea'])
    if kind!='موشکی':
        from game import war
        if any(db.integer(db.kv_get(f'staging:{h}:{p["country"]}'))>db.now() and infra.structure_strength(h,'airbase')>0 and sea_routes.air_band(h,loc['sea'])==2 for h in war.allies_of(p['country'])):required=2
    maritime={'ship_id':sid,'required_range':required,'at_sea':loc['sea_target']}
    ctx,err=campaign._prepare(uid,kind,count,'port',s['home_city'],maritime=maritime)
    if err:return err
    if kind=='موشکی':return campaign.store_missile(ctx,asset={'type':'tanker','id':sid})
    return resolve_attack(ctx,sid)


def resolve_attack(ctx,sid):
    from game import campaign,military,defense
    s=db.one('SELECT * FROM tankers WHERE id=?',(sid,))
    if not s or s['hp']<=0:return '🕊 هدف پیش از برخورد از بین رفته است؛ امتیاز اضافه نشد.'
    s=dict(s);loc,err=target_context(s)
    if err:return err+' مهمات شلیک‌شده بازنمی‌گردد.'
    v=live_voyage(sid);escorts=db.q('SELECT * FROM naval_escorts WHERE voyage_id=?',(v['id'],)) if v else []
    chance=min(.65,.05+sum(e['guard']*e['units']*(100-e['wear'])/100 for e in escorts)/300)
    if not loc['sea_target']:
        chance=max(chance,defense.absorb(s['country'],ctx['kind'],ctx['count'],s['home_city'])[0])
    chance=min(.72,chance)
    cid=ctx['p']['country'];role,_=military.atk_mult(ctx['p'],'هوایی' if ctx['kind']=='چندمنظوره' else ctx['kind'])
    mult=catalog.country_factor(cid)*role*infra.strike_mult(cid)*ctx.get('operation_mult',1)*ctx.get('facility_mult',1)
    total=0;hits=0
    for item in ctx['equipment']:
        for _ in range(item['units']):
            if random.random()>=chance:hits+=1;total+=item['power']*mult*random.uniform(.90,1.10)
    damage=min(s['hp'],20,max(1,int(total/8))) if hits else 0
    hp=s['hp']-damage;db.ex('UPDATE tankers SET hp=? WHERE id=?',(hp,sid))
    cargo_lost=0
    if v:
        cargo_lost=v['remaining_milli']*damage//100
        db.ex('UPDATE voyages SET remaining_milli=MAX(0,remaining_milli-?) WHERE id=?',(cargo_lost,v['id']))
        db.ex('UPDATE naval_escorts SET wear=MIN(100,wear+?) WHERE voyage_id=?',(ctx['count']*2,v['id']))
    side=campaign._side(ctx['w'],cid)
    db.ex(f'UPDATE wars SET score_{side}=score_{side}+? WHERE id=?',(damage,ctx['w']['id']))
    db.ex(f'UPDATE campaigns SET rounds_{side}=rounds_{side}+1 WHERE war_id=?',(ctx['w']['id'],))
    # Merchant attacks do NOT farm the four naval-dominance waves required for landing.
    msg=f'🎯 موج علیه نفت‌کش «{texts.esc(s["name"])}»: برخورد {hits}/{ctx["count"]} · سلامت {s["hp"]}٪ ← {hp}٪ · آسیب بار {cargo_lost/1000:.1f} واحد.\nاین حمله شهر یا کشور را تصرف نمی‌کند؛ نخستین موج حداکثر ۲۰٪ آسیب می‌زند.'
    if hp==0:
        db.ex("UPDATE tankers SET status='sunk' WHERE id=?",(sid,))
        if v:
            vv=dict(db.one('SELECT * FROM voyages WHERE id=?',(v['id'],)))
            _refund(vv,'غرق شدن؛ امانت بازپرداخت شد');_release_escorts(vv,10)
            db.ex("UPDATE voyages SET status='sunk',remaining_milli=0,completed_at=? WHERE id=?",(db.now(),v['id']))
        msg+='\n🌊 نفت‌کش غرق شد؛ بار از بین رفت و امانت پرداخت‌نشده به خریدار برگشت، نه به مهاجم.'
    db.audit('tanker_hit',ctx['p']['uid'],ship=sid,damage=damage,cargo_lost=cargo_lost)
    notifications.emit(msg,cids=[cid,s['country']]+([v['dest']] if v else []),uids=[ctx['p']['uid']]+([v['seller'],v['buyer']] if v else []),key=None)
    return msg


def view(uid):
    p,err=_leader(uid)
    if err:return err
    progress_builds(p['country'])
    lines=[texts.hdr('ناوگان نفت‌کش و قراردادهای حمل','🚢'),'نام رده‌ها شناخته‌شده است؛ ظرفیت، قیمت، سلامت و زمان‌ها مخصوص بازی‌اند.']
    for s in db.q('SELECT * FROM tankers WHERE country=? ORDER BY id',(p['country'],)):
        if s['status']=='sunk':continue
        lines.append(f'\n#{s["id"]} «{texts.esc(s["name"])}» · {CLASSES[s["class"]][0]}\n{STATUS[s["status"]]} · سلامت {s["hp"]}٪ · ظرفیت {CLASSES[s["class"]][2]}')
        if s['status']=='building':lines.append(f'کار ساخت باقی‌مانده با کارگاه سالم: {math.ceil(s["build_work"]/60000)} دقیقه')
        v=live_voyage(s['id'])
        if v:lines.append(voyage_view(v['id']))
    return '\n'.join(lines)


def voyage_view(vid):
    v=db.one('SELECT * FROM voyages WHERE id=?',(vid,))
    if not v:return '⛔ سفر پیدا نشد.'
    path=json.loads(v['route']);eta=v['leg_due']+sum(p['seconds'] for p in path[v['leg']+1:]) if path else 0
    return f'📜 سفر #{vid}: {VSTATUS[v["status"]]} · {CARGO_LABELS[v["cargo"]]} {v["remaining_milli"]/1000:.1f} / {v["amount"]} واحد\nامانت: {v["escrow"]} دلار · پهنه: {sea_routes.SEAS.get(v["region"],"پیش از حرکت")}'+(f'\nبرآورد پایان مرحلهٔ فعلی: {db.tehran_date(eta)} (بسته‌شدن مسیر/بندر می‌تواند تأخیر دهد)' if eta else '')
