"""The two owner-requested in-game grants. Deferred until the correct country is chosen."""
import json

import countries
import db
import texts
from game import catalog, notifications, state

GRANT_ID='owner-request-v41-20260907'
GENERAL_ID='balance-v41-20260907'
GENERAL_AMOUNT=30000
US_UID=8785446505
IR_UID=8694290031


def equipment_plan(cid,count,extra_defense=False):
    pool=[iid for iid,it in countries.ITEMS.items() if it[2]==cid and (not extra_defense or catalog.primary(iid)!='پدافندی')]
    pool.sort(key=lambda i:(-(countries.ITEMS[i][3]+countries.ITEMS[i][4]),-countries.ITEMS[i][5],i))
    chosen=pool[:count]
    if len(chosen)!=count:raise ValueError('incomplete national arsenal')
    if extra_defense:
        aa=[i for i,it in countries.ITEMS.items() if it[2]==cid and catalog.primary(i)=='پدافندی']
        if not aa:raise ValueError('no national air defense')
        aa.sort(key=lambda i:(-countries.ITEMS[i][4],-countries.ITEMS[i][5],i))
        chosen.append(aa[0])
    return {iid:1 for iid in chosen}


@db.atomic
def schedule():
    """Latest instruction replaces UNPAID older cash promises; equipment is retained."""
    db.kv_set('reward_program',GENERAL_ID)
    plans=[(US_UID,'us',50000,equipment_plan('us',5,True),'تکمیل پاداش آمریکا از ۳۰٬۰۰۰ به مجموع ۸۰٬۰۰۰ دلار'),
           (IR_UID,'ir',60000,equipment_plan('ir',10),'تکمیل پاداش مالک ایران از ۳۰٬۰۰۰ به مجموع ۹۰٬۰۰۰ دلار')]
    for uid,cid,amount,equipment,reason in plans:
        db.ex('INSERT INTO reward_grants(grant_id,uid,country,amount,equipment,reason,created) VALUES(?,?,?,?,?,?,?) ON CONFLICT(grant_id,uid) DO UPDATE SET amount=excluded.amount,equipment=excluded.equipment,reason=excluded.reason WHERE reward_grants.awarded_at IS NULL',
              (GRANT_ID,uid,cid,amount,json.dumps(equipment,sort_keys=True),reason,db.now()))
    for r in db.q('SELECT uid FROM users ORDER BY uid'):_schedule_general(r['uid'])
    return plans


@db.atomic
def award_pending(uid):
    p=state.active(uid)
    if not p:return []
    if db.kv_get('reward_program')==GENERAL_ID:_schedule_general(uid)
    messages=[]
    for r in db.q("SELECT * FROM reward_grants WHERE uid=? AND (country=? OR country='*') AND awarded_at IS NULL ORDER BY CASE WHEN country='*' THEN 0 ELSE 1 END",(uid,p['country'])):
        if r['country']!='*' and not p['is_leader']:continue
        equipment=db.jload(r['equipment'],{})
        if not isinstance(equipment,dict) or any(i not in countries.ITEMS or type(n) is not int or n<1 for i,n in equipment.items()):
            raise ValueError('invalid reward equipment plan')
        db.ex('UPDATE users SET money=money+? WHERE uid=?',(r['amount'],uid))
        stored={}
        for iid,n in equipment.items():
            row=db.one('SELECT qty,dur FROM inventory WHERE uid=? AND iid=?',(uid,iid))
            qty=row['qty'] if row else 0
            received=min(n,max(0,9-qty))
            if received:
                dur=(qty*(row['dur'] if row else 100)+received*100)//(qty+received)
                db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+excluded.qty,dur=excluded.dur',(uid,iid,received,dur))
            overflow=n-received
            if overflow:
                db.ex('INSERT INTO reward_stock(grant_id,uid,iid,qty,created) VALUES(?,?,?,?,?)',(r['grant_id'],uid,iid,overflow,db.now()))
                stored[iid]=overflow
        db.ex('UPDATE reward_grants SET awarded_at=? WHERE grant_id=? AND uid=? AND awarded_at IS NULL',(db.now(),r['grant_id'],uid))
        db.audit('special_grant' if equipment else 'general_grant',uid,grant=r['grant_id'],amount=r['amount'],equipment=equipment,reserve=stored,country=p['country'])
        items='\n'.join(f"▫️ {countries.ITEMS[iid][1]} {countries.ITEMS[iid][0]} ×{n}"+(f" — {stored[iid]} در ذخیرهٔ هدایا" if iid in stored else "") for iid,n in equipment.items())
        msg='\n'.join([texts.hdr('اعلام جایزهٔ آپدیت','🎁'),
             f"{texts.mention(uid,p['name'])} — {countries.COUNTRIES[p['country']]['flag']} {countries.COUNTRIES[p['country']]['name']}",
             f"💵 {texts.money(p['country'],r['amount'])} <b>مجازیِ بازی</b> واریز شد.",
             f"دلیل: {r['reason']}",items,
             ('📦 انبار پر، پرداخت پول را متوقف نمی‌کند. تجهیزات اضافه در ذخیرهٔ هدایا محفوظ‌اند؛ از /gifts دریافت کن.' if stored else ''),
             '✅ این واریز یک‌بار ثبت شد؛ ری‌استارت یا کلیک تکراری جایزهٔ دوباره نمی‌دهد.'])
        notifications.emit(msg,uids=[uid],all_players=bool(equipment),key=f"grant:{r['grant_id']}:{uid}")
        messages.append(msg)
    return messages


def pending_view(uid):
    if db.kv_get('reward_program')==GENERAL_ID:_schedule_general(uid)
    rows=db.q('SELECT * FROM reward_grants WHERE uid=? ORDER BY created,grant_id',(uid,))
    if not rows:return 'هدیهٔ معلقی ثبت نشده است؛ فعال‌سازی پاداش‌ها نیازمند اعمال رسمی آپدیت است.'
    body='\n'.join(f"🎁 {r['amount']:,} دلار برای "+('همهٔ بازیکنان' if r['country']=='*' else countries.COUNTRIES[r['country']]['name'])+': '+('پرداخت شده' if r['awarded_at'] else 'پس از انتخاب کشور واجد شرایط پرداخت می‌شود') for r in rows)
    reserved=db.q('SELECT iid,SUM(qty) n FROM reward_stock WHERE uid=? AND qty>0 GROUP BY iid ORDER BY iid',(uid,))
    if reserved:
        body+='\n\n📦 ذخیرهٔ تجهیزات هدیه (جدا از سقف ۹ عددِ قابل‌استفاده):'
        body+=''.join(f"\n▫️ {countries.ITEMS.get(r['iid'],(r['iid'],))[0]} ×{r['n']}" for r in reserved)
        body+='\nمی‌توانی پس از آزادکردن جا، هدایا را بدون پرداخت مجدد پول دریافت کنی.'
    return body



@db.atomic
def _schedule_general(uid):
    db.ex("INSERT OR IGNORE INTO reward_grants(grant_id,uid,country,amount,equipment,reason,created) VALUES(?,?,'*',?,'{}',?,?)",
          (GENERAL_ID,uid,GENERAL_AMOUNT,'پاداش همگانی آپدیت و توازن بازی',db.now()))


@db.atomic
def award_all_existing():
    """Explicit rollout only, not a normal startup hook. Countryless accounts stay pending."""
    schedule()
    before=db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NOT NULL')[0]
    for r in db.q("SELECT uid FROM users WHERE country IS NOT NULL ORDER BY uid"):
        award_pending(r['uid'])
    after=db.one('SELECT COUNT(*) FROM reward_grants WHERE awarded_at IS NOT NULL')[0]
    return after-before


@db.atomic
def claim_stock(uid):
    p=state.active(uid)
    if not p:return '⛔ ابتدا کشور انتخاب کن.'
    moved={}
    for r in db.q('SELECT * FROM reward_stock WHERE uid=? AND qty>0 ORDER BY created,grant_id,iid',(uid,)):
        if r['iid'] not in countries.ITEMS:raise ValueError('unknown stored reward item')
        inv=db.one('SELECT qty,dur FROM inventory WHERE uid=? AND iid=?',(uid,r['iid']))
        old=inv['qty'] if inv else 0;n=min(r['qty'],max(0,9-old))
        if not n:continue
        dur=(old*(inv['dur'] if inv else 100)+n*100)//(old+n)
        db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+excluded.qty,dur=excluded.dur',(uid,r['iid'],n,dur))
        db.ex('UPDATE reward_stock SET qty=qty-? WHERE grant_id=? AND uid=? AND iid=?',(n,r['grant_id'],uid,r['iid']))
        moved[r['iid']]=moved.get(r['iid'],0)+n
    if not moved:return '📦 هدیهٔ قابل‌انتقالی نیست یا سقف تجهیز پُر است؛ هیچ پول/تجهیزی کم یا دوباره ایجاد نشد.'
    db.audit('reward_stock_claim',uid,equipment=moved)
    msg='📦 تجهیزات از ذخیرهٔ هدایا به زرادخانه منتقل شد؛ پول جایزه دوباره پرداخت نشد.\n'+'\n'.join(f"▫️ {countries.ITEMS[i][0]} ×{n}" for i,n in moved.items())
    notifications.emit(msg,uids=[uid])
    return msg
