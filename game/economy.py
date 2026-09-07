"""💰 جنگ جهانی — اقتصاد زنده: نفت، دلار، تورم، تنگه‌ها، تحریم.

مدل انتزاعی و متعادل بازی: قیمت‌ها با دلار و تورم بالا می‌روند؛
بستن تنگه نفت را جهانی می‌کند؛ جنگ و شورش تورم می‌آورد.
"""
import json
import random

import countries
import db
import texts
from game import state

# ═══════════ وضعیت جهانی (kv) ═══════════
DEFAULTS = dict(oil=82, dollar=1.0, inflation=0.0, hormuz=1, bab=1, taiwan=1, suez=1)


def world():
    w=dict(DEFAULTS);raw=db.jload(db.kv_get('econ'),{}) or {}
    if not isinstance(raw,dict):raw={}
    for key,lo,hi in (('oil',45,140),('dollar',0.90,1.25),('inflation',0,0.25)):
        try:
            import math
            value=float(raw.get(key,w[key]))
            w[key]=max(lo,min(hi,value)) if math.isfinite(value) else w[key]
        except (ValueError,TypeError):pass
    for key in ('hormuz','bab','taiwan','suez','bosporus','malacca'):
        w[key]=0 if raw.get(key,1) in (0,'0') else 1
    return w


def _save(w: dict):
    import json
    db.kv_set("econ", json.dumps(w, ensure_ascii=False))


def price_factor() -> float:
    """ضریب قیمت: دلار × (۱ + تورم)."""
    w = world()
    return w["dollar"] * (1 + w["inflation"])


def real_price(base: int) -> int:
    """قیمت ثابت و رند — بدون تورم و نرخ ارز؛ دقیقاً همان عدد منو."""
    return base


@db.atomic
def tick():
    """Bounded, mean-reverting ten-minute indicators; opening menus never accelerates inflation."""
    import hashlib
    from game import straits,notifications
    straits.tick()
    for r in db.q("SELECT k,v FROM kv WHERE k LIKE 'sanction_pair:%'"):
        if db.integer(r['v'])<=db.now():
            _,source,target=r['k'].split(':');db.kv_del(r['k'])
            if source in countries.COUNTRIES and target in countries.COUNTRIES:
                notifications.emit(f"✅ تحریم {countries.COUNTRIES[source]['name']} علیه {countries.COUNTRIES[target]['name']} منقضی شد؛ آثار همین تحریم برداشته شد.",cids=[source,target],key=f"sanction_expire:{source}:{target}:{r['v']}")
    bucket=db.now()//MARKET_STEP
    if db.integer(db.kv_get('market_tick'),-1)==bucket:return world()
    rng=random.Random(int(hashlib.sha256(f'{db.GAME.get()}:{bucket}:macro'.encode()).hexdigest(),16))
    w=world();closed=sum(not straits.is_open(k) for k in straits.CONTROLS)
    for k in straits.CONTROLS:w[k]=int(straits.is_open(k))
    wars=min(8,db.one("SELECT COUNT(*) FROM wars WHERE status='active'")[0])
    oil_target=82*(1+0.04*closed+0.008*wars)
    dollar_target=1+0.012*closed+0.008*wars
    inflation_target=0.01+0.004*closed+0.006*wars
    w['oil']=max(45,min(140,w['oil']+0.15*(oil_target-w['oil'])+rng.uniform(-0.4,0.4)))
    w['dollar']=max(.90,min(1.25,w['dollar']+.10*(dollar_target-w['dollar'])+rng.uniform(-.002,.002)))
    w['inflation']=max(0,min(.25,w['inflation']+.08*(inflation_target-w['inflation'])+rng.uniform(-.0003,.0003)))
    _save(w);db.kv_set('market_tick',bucket)
    return w


def sanction_shock(cid):
    return None  # compatibility: removed autonomous NPC sanctions


def fx(cid: str) -> float:
    """💱 نرخ زنده‌ی پول هر کشور — جنگ، تحریم و تورم آن را بالا و پایین می‌برد.

    نرخ بالا = پول ضعیف‌تر (برای هر سکه، پولِ بیشتری می‌شماری).
    """
    import countries
    base = countries.CURRENCIES.get(cid, ("دلار", 1.0))[1]
    mult = 1.0
    w = world()
    mult *= 1 + w["inflation"] * 0.4              # تورم جهانی
    if db.one("SELECT 1 FROM wars WHERE status='active' AND (a=? OR b=?)", (cid, cid)):
        mult *= 1.15                              # جنگ → پول ضعیف
    if sanctioned(cid):
        mult *= 1.20                              # تحریم → پول ضعیف‌تر
    return base * mult


def sanctioned(cid):
    rows=db.q('SELECT v FROM kv WHERE k LIKE ?',(f'sanction_pair:%:{cid}',))
    return any(db.integer(r['v'])>db.now() for r in rows)


@db.atomic
def on_war_start():
    w=world();w['oil']=min(140,w['oil']*1.02);w['dollar']=min(1.25,w['dollar']*1.005);_save(w)


def toggle_strait(uid,name):
    from game import straits
    key=next((k for k,v in straits.CONTROLS.items() if v[0]==name),None)
    if key is None:return '🕊 این گذرگاه کنترل‌کنندهٔ قابل‌انتخاب ندارد.'
    return straits.set_open(uid,key,not straits.is_open(key))


# ═══════════ خزانه‌ی کشورها (از نفت) ═══════════
# هر کشور: bpd = بشکه در روز (صرفاً یادگار توصیفی نسخهٔ قبلی؛ مبنای پاداش نیست)
OIL_BPD = {"ir": 1400, "us": 13200, "ru": 9800, "cn": 4000, "de": 20, "gb": 70,
           "fr": 10, "tr": 70, "il": 0, "kp": 10, "kr": 100, "jp": 30, "in": 700,
           "pk": 90, "sa": 9600, "ae": 2800, "iq": 4200, "sy": 100, "ua": 100, "it": 60}


def oil_share(cid):
    """Bounded per-country resource dividend for balance, not real oil production."""
    from game import catalog
    n=db.one('SELECT COUNT(*) n FROM users WHERE country=?',(cid,))['n']
    if n<1:return 0
    factor=catalog.country_factor(cid)
    penalty=0.85 if sanctioned(cid) else 1.0
    return int(100*factor*penalty/n)


@db.atomic
def sanction(leader_uid,target):
    from game import campaign,notifications
    p,err=campaign._leader(leader_uid)
    if err:return err
    if target not in countries.COUNTRIES or target==p['country']:return '⛔ کشور نامعتبر.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(target,)):return '🕊 کشور خالی تحریم نمی‌شود.'
    key=f"sanction_pair:{p['country']}:{target}"
    if db.integer(db.kv_get(f'un_shield:{target}'))>db.now():return '🕊 رفع تحریمِ مصوب سازمان ملل هنوز معتبر است.'
    if db.integer(db.kv_get(key))>db.now():
        db.kv_del(key);msg='✅ فقط تحریم وضع‌شده توسط کشور شما لغو شد.'
    else:
        cd=f"sanction_cd:{p['country']}"
        if db.now()-db.integer(db.kv_get(cd))<3600:return '⏳ میان وضع تحریم‌ها یک ساعت فاصله لازم است.'
        if not db.debit(leader_uid,300):return '💰 وضع تحریم ۳۰۰ دلار هزینه دارد.'
        db.kv_set(key,db.now()+86400);db.kv_set(cd,db.now())
        msg=f"🚫 تحریم ۲۴ ساعتهٔ {countries.COUNTRIES[target]['name']} ثبت شد؛ اثر اقتصادی محدود و بدون انباشت نامحدود."
    notifications.emit(msg,cids=[p['country'],target],uids=[leader_uid])
    return msg


def market() -> str:
    """گزارش بازار."""
    w = world()
    t = texts
    straits = [("هرمز", w["hormuz"]), ("باب‌المندب", w["bab"]),
               ("تایوان", w["taiwan"]), ("سوئز", w["suez"])]
    return "\n".join([
        t.hdr("بازار جهانی", "📈"),
        t.row("شاخص نفت بازی", f"🛢 ${w['oil']:.0f}"),
        t.row("شاخص دلار", f"💵 ×{w['dollar']:.2f}"),
        t.row("تورم", f"📊 {w['inflation'] * 100:.1f}٪"),
        "", "🌉 <b>تنگه‌ها:</b>",
        *[f"▫️ {n}: {'باز ✅' if v else 'بسته 🚫'}" for n, v in straits],
        t.K,
        "💰 قیمت تجهیزات ثابت است؛ کالاهای تجاری با بازار نوسان می‌کنند. دلارها همه مجازی‌اند."])


# ═══════════ 💼 تجارت: صادرات و واردات ═══════════
def day_index() -> int:
    """📅 روزِ تهران — مرز واحد نیمه‌شب (همان db.day_index)."""
    return db.day_index()


def daily_deals(cid: str) -> list:
    """🔥 پیشنهاد ویژه‌ی امروز — ۲ سلاح با ۲۰٪ تخفیف؛ هر روز تازه، قطعی و بدون تصادف."""
    import hashlib
    import countries
    items = [i for i in countries.COUNTRIES[cid]["items"] if not i.endswith("_e")]
    if not items:
        return []
    h = int(hashlib.sha256(f"{cid}:{day_index()}".encode()).hexdigest(), 16)
    picks = [items[h % len(items)], items[(h // 7) % len(items)]]
    return list(dict.fromkeys(picks))[:2]


def deal_price(base: int) -> int:
    """قیمتِ تخفیف‌دار — رند و قابل محسابه (۲۰٪ کمتر، رند به ۱۰)."""
    return base * 80 // 100 // 10 * 10


GOODS = [
    ("oil", "نفت خام", "🛢", 82),       # قیمت پایه‌ی جهانی (واحد پایه)
    ("gold", "طلا", "🥇", 2400),
    ("wheat", "گندم", "🌾", 250),
    ("steel", "فولاد", "⚙", 480),
    ("copper", "مس", "🟠", 950),
]
GOODS_MAP = {g[0]: g for g in GOODS}
MARKET_STEP = 600          # هر ۱۰ دقیقه بازار حرکت می‌کند
TRADE_CAP = 20             # سقف نگهداری هر کالا
SPREAD = 0.025              # اختلاف خرید/فروش ۵٪ — سود از حرکت بازار می‌آید


@db.atomic
def _mk(gid):
    import hashlib
    if gid not in GOODS_MAP:raise ValueError('unknown good')
    st=db.jload(db.kv_get(f'mk:{gid}'),{}) or {'t':0,'m':1.0,'prev':1.0}
    bucket=db.now()//MARKET_STEP
    if int(st.get('t',0))//MARKET_STEP!=bucket:
        rng=random.Random(int(hashlib.sha256(f'{db.GAME.get()}:{gid}:{bucket}'.encode()).hexdigest(),16))
        prev=max(.85,min(1.15,float(st.get('m',1))))
        st={'t':bucket*MARKET_STEP,'prev':prev,'m':max(.85,min(1.15,prev+.12*(1-prev)+rng.uniform(-.015,.015)))}
        db.kv_set(f'mk:{gid}',json.dumps(st))
    return st


def good_price(gid):
    w=world();base=w['oil'] if gid=='oil' else GOODS_MAP[gid][3]
    return max(1,round(base*_mk(gid)['m']*w['dollar']*(1+w['inflation'])))


def holdings(uid: int) -> dict:
    from game import portfolios
    portfolios.ensure(uid)
    raw=db.jload(db.kv_get(f"trade:{uid}"), {}) or {}
    return {k:db.integer(v,0,0,TRADE_CAP) for k,v in raw.items() if k in GOODS_MAP}


def _save_holdings(uid: int, h: dict):
    db.kv_set(f"trade:{uid}", json.dumps(h, ensure_ascii=False))


def trade_view(uid) -> str:
    """📊 میز تجارت — قیمت‌ها با جهت، موجودی انبار، قواعد شفاف."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    t = texts
    lines = [t.hdr("میز تجارت", "💼"),
             f"💰 خزانه: {t.money(p['country'], p['money'])}", ""]
    h = holdings(uid)
    for gid, nm, em, _ in GOODS:
        mk = _mk(gid)
        pr = good_price(gid)
        arrow = "🟢+" if mk["m"] >= mk["prev"] else "🔴−"
        pct = int(abs(mk["m"] / max(mk["prev"], 0.01) - 1) * 100)
        held = int(h.get(gid, 0))
        mark = f" · 📦 {t.fa(held)}" if held else ""
        lines.append(f"{em} {nm}: {t.money(p['country'], int(pr))} "
                     f"{arrow}{t.fa(pct)}٪{mark}")
    lines += ["",
              "📌 + یعنی واردات (خرید) · − یعنی صادرات (فروش)",
              f"📦 سقف انبار هر کالا: {t.fa(TRADE_CAP)} · اختلاف خرید و فروش ۵٪"]
    if sanctioned(p["country"]):
        lines.append("🚫 تحریمی! خرید ۱۵٪ گران‌تر و فروش ۱۵٪ ارزان‌تر؛ منبع و زمان پایان در منوی تحریم‌ها. اثرها روی هم جمع نمی‌شوند.")
    return "\n".join(lines)


@db.atomic
def trade_buy(uid,gid,qty=1):
    import math
    from game import straits,infra
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if gid not in GOODS_MAP or type(qty) is not int or not 1<=qty<=5:return '⛔ کالا و تعداد صحیح ۱ تا ۵ لازم است.'
    err=straits.trade_check(uid)
    if err:return err
    if not infra.port_ok(p['country']):return '🚢 بندر عملیاتی کافی نیست؛ ابتدا تعمیر کن.'
    h=holdings(uid);held=db.integer(h.get(gid),0,0,TRADE_CAP)
    if held+qty>TRADE_CAP:return '📦 انبار پر است؛ سقف هر کالا ۲۰ واحد.'
    pool=market_pool()
    if pool['stock'].get(gid,0)<qty:return '📦 عرضهٔ این کالا در بازار تمام شده است؛ فروش بازیکنان آن را تأمین می‌کند.'
    cost=math.ceil(good_price(gid)*(1+SPREAD)*(1.15 if sanctioned(p['country']) else 1)*qty)
    if not db.debit(uid,cost):return f'💰 پول کافی نیست؛ لازم: {cost} دلار.'
    h[gid]=held+qty;_save_holdings(uid,h)
    pool['stock'][gid]-=qty;pool['money']+=cost;_save_pool(pool)
    db.audit('market_buy',uid,good=gid,qty=qty,cost=cost)
    return f"📥 واردات {GOODS_MAP[gid][1]} ×{qty}؛ پرداخت {cost} دلار مجازی. انبار: {h[gid]} / {TRADE_CAP}."


@db.atomic
def trade_sell(uid,gid,qty=1):
    import math
    from game import straits,infra
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if gid not in GOODS_MAP or type(qty) is not int or not 1<=qty<=5:return '⛔ کالا و تعداد صحیح ۱ تا ۵ لازم است.'
    err=straits.trade_check(uid)
    if err:return err
    if not infra.port_ok(p['country']):return '🚢 بندر عملیاتی کافی نیست؛ ابتدا تعمیر کن.'
    h=holdings(uid);held=db.integer(h.get(gid),0,0,TRADE_CAP)
    if held<qty:return '📦 موجودی کالا کافی نیست.'
    revenue=math.floor(good_price(gid)*(1-SPREAD)*(.85 if sanctioned(p['country']) else 1)*qty)
    pool=market_pool()
    if revenue>pool['money']:return '🏦 نقدینگی بازار برای این سفارش کافی نیست؛ پول ساخته نمی‌شود.'
    h[gid]=held-qty
    if not h[gid]:h.pop(gid)
    _save_holdings(uid,h)
    pool['stock'][gid]+=qty;pool['money']-=revenue;_save_pool(pool)
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(revenue,uid))
    db.audit('market_sell',uid,good=gid,qty=qty,revenue=revenue)
    return f"📤 صادرات {GOODS_MAP[gid][1]} ×{qty}؛ درآمد {revenue} دلار مجازی. انبار: {h.get(gid,0)} / {TRADE_CAP}."


# ═══════════ 📜 قرارداد تجاری — رهبر ═══════════
CONTRACT_CD = 1200        # ۲۰ دقیقه بین قراردادها (مخصوص هر شخص)


@db.atomic
def contract(uid,target):
    from game import campaign,notifications
    p,err=campaign._leader(uid)
    if err:return err
    if target not in countries.COUNTRIES or target==p['country']:return '⛔ طرف قرارداد نامعتبر.'
    buyer=db.one('SELECT uid FROM users WHERE country=? AND is_leader=1',(target,))
    if not buyer:return '🕊 قرارداد با کشور خالی یا NPC وجود ندارد؛ طرف واقعی لازم است.'
    w=campaign.war_of(p['country'])
    if w and campaign.enemy(p['country'],w)==target:return '⚔️ ابتدا صلح کنید.'
    if db.now()-db.integer(db.kv_get(f'ct:{uid}'))<CONTRACT_CD:return '⏳ بین قراردادهای انجام‌شده ۲۰ دقیقه فاصله لازم است.'
    goods=holdings(uid);gid=next((g for g,n in goods.items() if g in GOODS_MAP and n>0),None)
    if not gid:return '📦 ابتدا یک کالای واقعی در انبارت داشته باش؛ قرارداد پول رایگان ایجاد نمی‌کند.'
    price=max(1,int(good_price(gid)))
    offer={'seller':uid,'buyer':buyer['uid'],'good':gid,'qty':1,'price':price,'expires':db.now()+1800}
    db.kv_set(f"contract:{p['country']}:{target}",json.dumps(offer))
    msg=f"📜 پیشنهاد فروش {GOODS_MAP[gid][1]} ×۱ به {countries.COUNTRIES[target]['name']} ارسال شد؛ قیمت {price} دلار.\nتا پذیرش رهبر خریدار، هیچ پول یا کالایی جابه‌جا نمی‌شود؛ مهلت ۳۰ دقیقه."
    notifications.emit(msg,cids=[p['country'],target],uids=[uid])
    return msg


@db.atomic
def contract_accept(uid,source):
    from game import campaign,notifications
    p,err=campaign._leader(uid)
    if err:return err
    key=f"contract:{source}:{p['country']}"
    offer=db.jload(db.kv_get(key),{}) or {}
    if not offer or offer.get('buyer')!=uid or offer.get('expires',0)<db.now():return '⛔ پیشنهاد معتبر یا مهلت باقی‌مانده‌ای نیست.'
    from game import straits
    route_error=straits.trade_check(uid)
    if route_error:return route_error
    seller=state.active(offer['seller'])
    if not seller or seller['country']!=source or not seller['is_leader']:return '⛔ فروشنده دیگر رهبر این کشور نیست.'
    route_error=straits.trade_check(seller['uid'])
    if route_error:return route_error
    if any(db.integer(db.kv_get(f'sanction_pair:{a}:{b}'))>db.now() for a,b in ((source,p['country']),(p['country'],source))):return '🚫 قرارداد مستقیم بین دو طرف تحریم تا لغو همان تحریم مجاز نیست.'
    w=campaign.war_of(source)
    if w and campaign.enemy(source,w)==p['country']:return '⚔️ در زمان جنگ، پذیرش این قرارداد مجاز نیست.'
    if db.now()-db.integer(db.kv_get(f"ct:{seller['uid']}"))<CONTRACT_CD:return '⏳ فروشنده به‌تازگی قرارداد دیگری انجام داده است.'
    gid=offer['good'];qty=offer['qty'];cost=offer['price']
    a,b=holdings(seller['uid']),holdings(uid)
    if a.get(gid,0)<qty:return '📦 کالای فروشنده دیگر کافی نیست؛ پیشنهاد منقضی شده است.'
    if b.get(gid,0)+qty>TRADE_CAP:return '📦 انبار خریدار جا ندارد.'
    if not db.debit(uid,cost):return '💰 موجودی خریدار کافی نیست.'
    a[gid]-=qty;b[gid]=b.get(gid,0)+qty
    _save_holdings(seller['uid'],a);_save_holdings(uid,b)
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(cost,seller['uid']))
    db.kv_set(f"ct:{seller['uid']}",db.now());db.kv_del(key)
    db.audit('bilateral_trade',uid,seller=seller['uid'],good=gid,qty=qty,price=cost)
    msg=f'📜 قرارداد دوطرفه انجام شد: {qty} واحد {GOODS_MAP[gid][1]} در برابر {cost} دلار مجازی؛ پول از حساب خریدار به فروشنده منتقل شد.'
    notifications.emit(msg,cids=[source,p['country']],uids=[uid,seller['uid']])
    return msg


@db.atomic
def transfer(uid,to,amount):
    from game import notifications
    if type(amount) is not int or not 1<=amount<=10**12:return '⛔ مبلغ باید عدد صحیح مثبت و در محدودهٔ مجاز باشد.'
    a,b=state.active(uid),state.active(to)
    if not a or not b or uid==to:return '⛔ هر دو طرف باید ثبت‌نام‌شده و متفاوت باشند.'
    if not db.debit(uid,amount):return '💰 موجودی کافی نیست.'
    db.ex('UPDATE users SET money=money+? WHERE uid=?',(amount,to))
    db.audit('transfer',uid,to=to,amount=amount)
    msg=f"💸 {texts.mention(uid,a['name'])} → {texts.mention(to,b['name'])}\n{amount:,} دلار مجازی منتقل شد؛ بدون کارمزد."
    notifications.emit(msg,uids=[uid,to])
    return msg


@db.atomic
def market_pool():
    p=db.jload(db.kv_get('market_pool'),None)
    if not p:
        p={'money':500000,'stock':{g:500 for g in GOODS_MAP}}
        _save_pool(p)
        db.audit('market_seed',money=500000,units_per_good=500)
    return p


def _save_pool(p):db.kv_set('market_pool',json.dumps(p,sort_keys=True))


@db.atomic
def apply_sanction(uid,target):
    p=state.active(uid)
    if p and db.integer(db.kv_get(f"sanction_pair:{p['country']}:{target}"))>db.now():
        return '✅ تحریم کشور شما از قبل فعال است؛ این دکمه آن را لغو یا تمدید نمی‌کند.'
    return sanction(uid,target)


@db.atomic
def lift_sanction(uid,target):
    from game import campaign,notifications
    p,err=campaign._leader(uid)
    if err:return err
    if target not in countries.COUNTRIES:return '⛔ کشور نامعتبر.'
    key=f"sanction_pair:{p['country']}:{target}"
    if not db.kv_get(key):return '✅ تحریمی از سوی کشور شما وجود ندارد؛ تحریم تازه‌ای ایجاد نشد.'
    db.kv_del(key)
    remaining=sanctioned(target)
    msg='✅ تحریمِ کشور شما لغو شد؛ '+('تحریم سایر کشورها هنوز برقرار است.' if remaining else 'همهٔ اثرهای تحریم هدف برداشته شد.')
    db.audit('sanction_lift',uid,target=target)
    notifications.emit(msg,cids=[p['country'],target],uids=[uid])
    return msg


def sanctions_view(uid):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    lines=[texts.hdr('تحریم‌ها؛ منبع و مهلت دقیق','🚫')]
    for r in db.q("SELECT k,v FROM kv WHERE k LIKE 'sanction_pair:%' ORDER BY k"):
        _,source,target=r['k'].split(':');until=db.integer(r['v'])
        if until<=db.now() or p['country'] not in (source,target):continue
        leader=db.one('SELECT uid,name FROM users WHERE country=? AND is_leader=1',(source,))
        tag=texts.mention(leader['uid'],leader['name']) if leader else 'بدون رهبر'
        lines.append(f"{countries.COUNTRIES[source]['name']} → {countries.COUNTRIES[target]['name']} · {max(1,(until-db.now())//60)} دقیقه\n{tag}")
    if len(lines)==1:lines.append('تحریم فعالی برای کشور شما ثبت نشده است.')
    lines.append('فقط صادرکننده می‌تواند تحریم خودش را لغو کند؛ انقضای ۲۴ ساعته خودکار است. تحریم‌های هم‌زمان فقط یک اثر ۱۵٪ دارند، نه چند اثر جمع‌شونده.')
    return '\n'.join(lines)
