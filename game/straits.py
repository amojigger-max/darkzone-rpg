"""Geographic chokepoints in the GAME map. Not a claim about real-world sovereignty."""
import json
import countries
import db
import texts
from game import state,infra,notifications

# One designated controller per playable chokepoint; no globally editable switch.
CONTROLS={
 'hormuz':('هرمز','ir',{'sa','ae','iq','qa','kw'}),
 'suez':('سوئز','eg',{'il','sa'}),
 'bosporus':('بسفر','tr',{'ua','ru'}),
 'malacca':('مالاکا','my',{'id','th'}),
 'taiwan':('تایوان','cn',{'kr','jp'}),
}
FEES=(0,25,50,75,100)
CLOSE_MAX=6*3600
CHANGE_CD=3600


@db.atomic
def ensure():
    if db.kv_get('straits_v41'):return
    econ=db.jload(db.kv_get('econ'),{}) or {}
    for key in CONTROLS:
        closed=econ.get(key,1)==0
        db.kv_set(f'strait:{key}',json.dumps({'closed_until':db.now()+CLOSE_MAX if closed else 0,
            'fee':50 if key=='hormuz' and db.kv_get('toll_on')=='1' else 0,
            'pot':max(0,db.integer(db.kv_get('toll_pot'))) if key=='hormuz' else 0,'changed':0}))
    db.kv_set('straits_v41','1')
    db.kv_del('toll_on');db.kv_del('toll_pot')


def get(key):
    if key not in CONTROLS:return None
    ensure()
    r=db.jload(db.kv_get(f'strait:{key}'),{}) or {}
    return {'closed_until':db.integer(r.get('closed_until')), 'fee':db.integer(r.get('fee'),0,0,100),
            'pot':db.integer(r.get('pot'),0,0,10**15),'changed':db.integer(r.get('changed'))}


def _save(key,r):db.kv_set(f'strait:{key}',json.dumps(r))


def _authority(uid,key,base=True):
    p=state.active(uid)
    if key not in CONTROLS:return None,'⛔ گذرگاه نامعتبر.'
    if not p or not p['is_leader'] or p['country']!=CONTROLS[key][1]:
        return None,'⛔ فقط رهبر کشور کنترل‌کنندهٔ همین گذرگاه مجاز است؛ نه رهبر کشور دیگر.'
    if base and infra.structure_strength(p['country'],'naval')<=0:
        return None,'⚓ پایگاه دریایی تکمیل‌شده و خارج از اشغال لازم است.'
    return p,''


def operational(key):
    cid=CONTROLS[key][1]
    return bool(db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(cid,))) and infra.structure_strength(cid,'naval')>0


def is_open(key):
    r=get(key)
    return bool(r and (r['closed_until']<=db.now() or not operational(key)))


@db.atomic
def set_open(uid,key,opened):
    p,err=_authority(uid,key)
    if err:return err
    if type(opened) is not bool:return '⛔ وضعیت نامعتبر.'
    r=get(key)
    if opened==is_open(key):return '✅ گذرگاه از قبل در همین وضعیت است؛ هزینه‌ای کسر نشد.'
    # Reopening must never be blocked by the close cooldown.
    if not opened:
        if db.now()-r['changed']<CHANGE_CD:return '⏳ برای بستن دوباره یک ساعت فاصله لازم است.'
        if not db.debit(uid,150):return '💰 بستن گذرگاه ۱۵۰ دلار هزینه دارد.'
        r['changed']=db.now()
    if opened:
        db.ex('UPDATE strait_closures SET ended=MIN(ended,?) WHERE gate=? AND started<=? AND ended>?',(db.now(),key,db.now(),db.now()))
    else:
        db.ex('INSERT INTO strait_closures(gate,started,ended) VALUES(?,?,?)',(key,db.now(),db.now()+CLOSE_MAX))
    r['closed_until']=0 if opened else db.now()+CLOSE_MAX
    _save(key,r)
    w=db.jload(db.kv_get('econ'),{}) or {};w[key]=int(opened);db.kv_set('econ',json.dumps(w))
    msg=f"🌉 {CONTROLS[key][0]} در قواعد بازی "+('باز شد.' if opened else 'حداکثر ۶ ساعت بسته شد؛ سپس خودکار باز می‌شود.')
    notifications.emit(msg,all_players=True,uids=[uid])
    db.audit('strait_status',uid,key=key,opened=opened)
    return msg


@db.atomic
def set_fee(uid,key,fee):
    p,err=_authority(uid,key)
    if err:return err
    if type(fee) is not int or fee not in FEES:return '⛔ تعرفهٔ مجاز: ۰، ۲۵، ۵۰، ۷۵ یا ۱۰۰ دلار.'
    r=get(key)
    if r['fee']==fee:return '✅ تعرفه تغییری نکرد.'
    cd=f'strait_fee_cd:{key}'
    if fee and db.now()-db.integer(db.kv_get(cd))<CHANGE_CD:return '⏳ تغییر تعرفه هر ساعت یک بار.'
    r['fee']=fee;_save(key,r);db.kv_set(cd,db.now())
    msg=f"🛃 تعرفهٔ مسیر {CONTROLS[key][0]}: {fee} دلار مجازی برای مجوز روزانه؛ مجوز پرداخت‌شدهٔ امروز همچنان معتبر است."
    notifications.emit(msg,all_players=True,uids=[uid])
    db.audit('strait_fee',uid,key=key,fee=fee)
    return msg


def relevant(uid,key):
    p=state.active(uid)
    return bool(p and key in CONTROLS and p['country'] in CONTROLS[key][2])


def paid(uid,key):return db.kv_get(f'passage:{key}:{uid}')==str(db.day_index())


@db.atomic
def pay(uid,key):
    p=state.active(uid);r=get(key)
    if not r or not p:return '⛔ کشور یا گذرگاه معتبر نیست.'
    if not relevant(uid,key):return '✅ کشور تو خارج از این مسیر یا کنترل‌کنندهٔ آن است؛ عوارض لازم نیست.'
    if not operational(key) or r['fee']==0:return '✅ این مسیر عوارض فعال ندارد.'
    if not is_open(key):return '🚫 مسیر بسته است؛ هزینه‌ای کسر نشد و مجوز فروخته نمی‌شود.'
    if paid(uid,key):return '✅ مجوز امروز قبلاً پرداخت شده است.'
    if not db.debit(uid,r['fee']):return '💰 موجودی مجوز کافی نیست.'
    r['pot']+=r['fee'];_save(key,r);db.kv_set(f'passage:{key}:{uid}',db.day_index())
    db.audit('passage_fee',uid,key=key,amount=r['fee'])
    return f"🛃 {r['fee']} دلار به صندوق {CONTROLS[key][0]} واریز شد؛ تا نیمه‌شب تهران معتبر است."


@db.atomic
def collect(uid,key):
    p,err=_authority(uid,key,base=False)
    if err:return err
    r=get(key);amount=r['pot']
    if not amount:return '🏦 صندوق این گذرگاه خالی است.'
    r['pot']=0;_save(key,r)
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(amount,uid))
    db.audit('passage_withdrawal',uid,key=key,amount=amount)
    msg=f"🏦 {amount} دلار پرداخت‌شدهٔ بازیکنان از صندوق {CONTROLS[key][0]} به خزانهٔ {countries.COUNTRIES[p['country']]['name']} منتقل شد."
    notifications.emit(msg,cids=[p['country']],uids=[uid])
    return msg


def trade_check(uid):
    for key in CONTROLS:
        if not relevant(uid,key) or not operational(key):continue
        if not is_open(key):return f'🚫 مسیر {CONTROLS[key][0]} بسته است؛ تجارت این مسیر تا بازگشایی متوقف است.'
        if get(key)['fee'] and not paid(uid,key):return f'🛃 ابتدا مجوز روزانهٔ {CONTROLS[key][0]} را از منوی گذرگاه‌ها بگیر؛ جریمه یا برداشت خودکار نداریم.'
    return ''


@db.atomic
def tick():
    for key in CONTROLS:
        r=get(key)
        if r['closed_until'] and (r['closed_until']<=db.now() or not operational(key)):
            db.ex('UPDATE strait_closures SET ended=MIN(ended,?) WHERE gate=? AND started<=? AND ended>?',(db.now(),key,db.now(),db.now()))
            r['closed_until']=0;_save(key,r)
            w=db.jload(db.kv_get('econ'),{}) or {};w[key]=1;db.kv_set('econ',json.dumps(w))
            notifications.emit(f'🌉 گذرگاه {CONTROLS[key][0]} با پایان مهلت یا از دست رفتن کنترل عملیاتی باز شد.',all_players=True)


def view(uid=None,key=None):
    lines=[texts.hdr('گذرگاه‌ها و صندوق‌های مستقل','🌉'),'مالکیت‌ها انتزاعی و مخصوص نقشهٔ بازی‌اند، نه ادعای حقوقی دربارهٔ جهان واقعی.']
    for k in ([key] if key in CONTROLS else CONTROLS):
        name,cid,_=CONTROLS[k];r=get(k)
        leader=db.one('SELECT uid,name FROM users WHERE country=? AND is_leader=1',(cid,))
        who=texts.mention(leader['uid'],leader['name']) if leader else 'بدون رهبر؛ بدون کنترل خودکار'
        lines.append(f"\n{name} · {countries.COUNTRIES[cid]['name']} · {'باز' if is_open(k) else 'بسته'}\n{who}\nتعرفه: {r['fee'] if operational(k) else 0} دلار · صندوق: {r['pot']} دلار")
        if uid and relevant(uid,k):lines.append('✅ مجوز امروز معتبر است.' if paid(uid,k) else 'مجوز روزانه از همین منو؛ فقط در صورت تعرفهٔ فعال.')
    lines.append('\nباب‌المندب: کنترل‌کنندهٔ قابل‌انتخاب در این نسخه ندارد؛ هیچ کشور دیگری نمی‌تواند آن را ببندد یا عوارضش را بردارد.')
    return '\n'.join(lines)


def pass_time(key,at):
    """Earliest historical crossing time, including early reopenings and server downtime."""
    if not key:return at
    cursor=at
    for r in db.q('SELECT started,ended FROM strait_closures WHERE gate=? AND ended>? ORDER BY started,id',(key,at)):
        if r['started']<=cursor<r['ended']:cursor=r['ended']
    current=get(key)
    if current and operational(key) and current['changed']<=cursor<current['closed_until']:
        cursor=current['closed_until']
    return cursor


def transit_quote(uid,keys):
    """A real voyage may use a gate even if its owner's country is outside the retail route."""
    p=state.active(uid)
    if not p:return None
    quote={}
    for key in dict.fromkeys(k for k in keys if k):
        if key not in CONTROLS or not is_open(key):return None
        if p['country']==CONTROLS[key][1] or not operational(key) or paid(uid,key):continue
        quote[key]=get(key)['fee']
    return quote


def pay_transit(uid,quote):
    # Internal: caller has checked the route and holds a database transaction.
    total=sum(quote.values())
    if total and not db.debit(uid,total):return False
    for key,amount in quote.items():
        r=get(key);r['pot']+=amount;_save(key,r)
        db.kv_set(f'passage:{key}:{uid}',db.day_index())
    db.audit('voyage_passages',uid,fees=quote,total=total)
    return True
