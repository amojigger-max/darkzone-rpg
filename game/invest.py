"""Investments accrue by seconds; a new asset never earns income retroactively."""
import json
import db
import texts
from game import state

ASSETS=[('mine','⛏ معدن طلا',2500,110),('oil','🛢 دکل نفت',6000,250),
        ('ref','🏭 پالایشگاه',15000,620),('fac','🏗 کارخانهٔ تسلیحات',40000,1600),
        ('bank','🏦 بانک سرمایه',100000,3900)]
_A={a[0]:a for a in ASSETS}
MICRO=1_000_000


def _bag(uid):
    from game import portfolios
    portfolios.ensure(uid)
    raw=db.jload(db.kv_get(f'investment:{uid}'),{}) or {}
    return {k:db.integer(v,0,0,50) for k,v in raw.items() if k in _A}


def _last(uid):
    row=db.one('SELECT last_ts FROM invest_accrual WHERE uid=?',(uid,))
    return row['last_ts'] if row else db.integer(db.kv_get(f'invt:{uid}'))


def rate(uid):
    return sum(_A[k][3]*v for k,v in _bag(uid).items())


@db.atomic
def accrue(uid):
    p=state.active(uid)
    if not p:return 0
    from game import infra,welfare
    row=db.one('SELECT * FROM invest_accrual WHERE uid=?',(uid,))
    if row is None:
        last=_last(uid) or db.now()
        db.ex('INSERT INTO invest_accrual(uid,last_ts,micro_dollars) VALUES(?,?,0)',(uid,last))
        row=db.one('SELECT * FROM invest_accrual WHERE uid=?',(uid,))
    if db.now()<=row['last_ts']:return row['micro_dollars']
    elapsed=min(7*86400,db.now()-row['last_ts'])
    multiplier=infra.output_mult(p['country'])*welfare.welfare_mult(p['country'])
    income=int(rate(uid)*elapsed*MICRO/3600*multiplier)
    amount=row['micro_dollars']+income
    db.ex('UPDATE invest_accrual SET last_ts=?,micro_dollars=? WHERE uid=?',(db.now(),amount,uid))
    db.kv_set(f'invt:{uid}',db.now())
    return amount


def view(uid):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    pending=accrue(uid)//MICRO;bag=_bag(uid)
    lines=[texts.hdr('سرمایه‌گذاری','🏭'),f"خزانه: {texts.money(p['country'],p['money'])}",
           f"درآمد پایهٔ ساعتی: {texts.money(p['country'],rate(uid))}",f'قابل برداشت: {pending} دلار']
    lines += [f'{name}: {bag.get(key,0)} عدد · قیمت {price} · درآمد {income}/ساعت' for key,name,price,income in ASSETS]
    lines += ['','درآمد تا ثانیه محاسبه می‌شود؛ خرید تازه برای زمان قبل از خرید درآمد ندارد.',
              'ضریب زیرساخت و رفاه هنگام تسویه اعمال می‌شود؛ سقف ذخیرهٔ آفلاین ۷ روز.']
    return '\n'.join(lines)


@db.atomic
def buy(uid,key):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if key not in _A:return '⛔ دارایی نامعتبر.'
    bag=_bag(uid)
    if bag.get(key,0)>=50:return '📦 سقف این دارایی ۵۰ عدد است.'
    _,name,price,_=_A[key]
    if p['money']<price:return f'💰 پول کافی نیست؛ {texts.money(p["country"],price)} لازم است.'
    accrue(uid)  # settle the OLD rate BEFORE increasing the asset count
    if not db.debit(uid,price):return '💰 موجودی تغییر کرده است؛ دوباره بررسی کن.'
    bag[key]=bag.get(key,0)+1
    db.kv_set(f'investment:{uid}',json.dumps(bag))
    db.audit('investment_purchase',uid,asset=key,cost=price)
    return f'🏭 {name} خریده شد؛ درآمد جدید از همین لحظه شروع می‌شود.'


@db.atomic
def collect(uid):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if not rate(uid):return '🏭 ابتدا دارایی بخر.'
    amount=accrue(uid);pay,remainder=divmod(amount,MICRO)
    if pay<=0:return '⏳ هنوز یک دلار کامل انباشته نشده؛ سهم کسری محفوظ است.'
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(pay,uid))
    db.ex('UPDATE invest_accrual SET micro_dollars=? WHERE uid=?',(remainder,uid))
    db.audit('investment_income',uid,amount=pay)
    return f'💰 {texts.money(p["country"],pay)} واریز شد؛ کسری ثانیه/دلار حفظ شد.'
