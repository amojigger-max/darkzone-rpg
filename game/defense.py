"""Six defensive layers: technology, condition, electricity and installed equipment."""
import countries
import db
import texts
from game import catalog, infra

LAYERS={"ضد موشک":"🚀","ضد هوایی":"✈️","ضد پهپاد":"🛩","ضد دریایی":"🚢","دفاع زمینی":"🚜","جنگ الکترونیک":"⚡"}
KIND_LAYER={"موشکی":"ضد موشک","هوایی":"ضد هوایی","چندمنظوره":"ضد هوایی","پهپادی":"ضد پهپاد",
            "دریایی":"ضد دریایی","آبی‌خاکی":"دفاع زمینی","زمینی":"دفاع زمینی","توپخانه":"دفاع زمینی"}


@db.atomic
def ensure(cid):
    if cid not in countries.COUNTRIES:return
    base=round(50*catalog.country_factor(cid))
    for layer in LAYERS:
        lv=base-(4 if layer=='جنگ الکترونیک' else 0)
        db.ex('INSERT OR IGNORE INTO defense(cid,layer,level,hp) VALUES(?,?,?,100)',(cid,layer,lv))


def level(cid,layer):
    ensure(cid)
    r=db.one('SELECT level FROM defense WHERE cid=? AND layer=?',(cid,layer))
    return r['level'] if r else 0


def equipment_bonus(cid):
    rows=db.q('SELECT n.iid,n.qty,n.dur FROM inventory n JOIN users u ON u.uid=n.uid WHERE u.country=? AND n.qty>0 AND n.dur>0',(cid,))
    points=0
    for r in rows:
        if catalog.primary(r['iid'])=='پدافندی':
            item=countries.ITEMS[r['iid']]
            points+=item[4]*r['dur']/100*min(r['qty'],3)/25
    return min(10.0,points)


def effective(cid,layer,city=None):
    ensure(cid)
    r=db.one('SELECT level,hp FROM defense WHERE cid=? AND layer=?',(cid,layer))
    if not r:return 0
    from game import energy
    power=energy.electricity(cid,infra.city_index(cid,city)) if city is not None else infra.state_of(cid)['power']
    value=r['level']*r['hp']/100*max(0.2,min(1.0,power/60))
    if layer in ('ضد موشک','ضد هوایی','ضد پهپاد'):
        value+=equipment_bonus(cid)
        value+=8*infra.structure_strength(cid,'radar',city)
        value+=6*infra.structure_strength(cid,'sam_base',city)
    return min(90,value)


@db.atomic
def absorb(cid,kind,shots,city=None):
    if kind not in KIND_LAYER or type(shots) is not int or not 1<=shots<=5:
        raise ValueError('invalid defensive wave')
    layer=KIND_LAYER[kind]
    eff=effective(cid,layer,city)
    ew=effective(cid,'جنگ الکترونیک',city)
    chance=min(0.72,max(0.03,eff/130))
    reduction=1-min(0.30,ew/300)
    # Condition wears; purchased technology is not silently erased.
    db.ex('UPDATE defense SET hp=MAX(0,hp-?) WHERE cid=? AND layer=?',(shots*2,cid,layer))
    db.ex("UPDATE defense SET hp=MAX(0,hp-1) WHERE cid=? AND layer='جنگ الکترونیک'",(cid,))
    return chance,reduction,layer,round(eff)


@db.atomic
def restore(cid,layer,amount=2):
    if layer not in LAYERS or type(amount) is not int or amount<0:
        raise ValueError('invalid defense restoration')
    ensure(cid)
    db.ex('UPDATE defense SET level=MIN(95,level+?), hp=MIN(100,hp+?) WHERE cid=? AND layer=?',(amount,20,cid,layer))


@db.atomic
def strengthen(uid,layer):
    from game import state,quests,notifications
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if layer not in LAYERS:return '⛔ لایه نامعتبر.'
    cid=p['country'];ensure(cid)
    r=db.one('SELECT * FROM defense WHERE cid=? AND layer=?',(cid,layer))
    if r['level']>=95 and r['hp']>=100:return '✅ این لایه در اوج و سالم است.'
    key=f'defcool:{cid}:{layer}'
    if db.now()-db.integer(db.kv_get(key))<120:return '⏳ بین تقویت همین لایه ۲ دقیقه فاصله لازم است.'
    cost=150+r['level']*4
    if not db.debit(uid,cost):return f'💰 پول کافی نیست — نیاز: {texts.money(cid,cost)}'
    restore(cid,layer,3 if r['level']<95 else 0)
    db.kv_set(key,db.now())
    quests.on_event(uid,'پدافند')
    new=db.one('SELECT * FROM defense WHERE cid=? AND layer=?',(cid,layer))
    msg=f"🛡 لایهٔ {layer}: سطح {new['level']} · سلامت {new['hp']}٪\n💰 هزینه: {texts.money(cid,cost)}\n⚡ رهگیری به برق، سلامت و تجهیزات نصب‌شده هم وابسته است."
    notifications.emit(msg,cids=[cid],uids=[uid])
    return msg


def status(cid):
    if cid not in countries.COUNTRIES:return '⛔ کشور نامعتبر.'
    ensure(cid)
    lines=[texts.hdr(f"سپر ملی {countries.COUNTRIES[cid]['name']}",'🛡')]
    for r in db.q('SELECT * FROM defense WHERE cid=?',(cid,)):
        lines.append(f"{LAYERS.get(r['layer'],'▫️')} {r['layer']}: فناوری {r['level']} · سلامت {r['hp']}٪ · توان مؤثر {round(effective(cid,r['layer']))}")
    lines+=['','سامانه‌های پدافندی داخل تجهیزات واقعاً در رهگیری اثر دارند؛ سقف احتمال دفع ۷۲٪ است.']
    return '\n'.join(lines)
