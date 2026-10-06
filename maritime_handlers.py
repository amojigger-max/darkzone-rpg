"""Energy, physical facilities and tanker controls on the retained DarkZone router."""
from aiogram import F
import countries
import db
import handlers as h
from advanced_handlers import keyboard
from game import state,geo,energy,fleet,campaign

ATTACK_TYPES={'naval':'دریایی','air':'هوایی','multi':'چندمنظوره','drone':'پهپادی','missile':'موشکی'}


def energy_keys(uid,city=None):
    p=state.active(uid);rows=[]
    if p:
        if city is None:
            rows=[[(name,f'en:{idx}')] for idx,name in enumerate(geo.CITIES[p['country']])]
        else:
            rows=[[("⛽ خرید ۵۰ سوخت · ۱۲۵۰ دلار",f'ebuy:{city}:50')],
                  [("⛽ فروش ۵۰ سوخت · ۱۱۵۰ دلار",f'esell:{city}:50')],
                  [("🛢 انتقال ۵ نفت از تجارت به مخزن",f'ecrude:{city}:5')],
                  [('🏗 ساخت و تعمیر تأسیسات این شهر',f'city:{city}')]]
    rows.append([('💰 تجارت','mn:trade'),('🚢 نفت‌کش‌ها','fv:'),('🎛 منو','mn:main')])
    return keyboard(rows)


@h.router.callback_query(F.data.startswith('en:'))
async def cb_energy(c):
    arg=c.data.split(':')[1]
    if not arg:return await h._edit(c,'⚡ شهر را برای مدیریت نیروگاه، نفت خام، پالایشگاه و سوخت انتخاب کن.',energy_keys(c.from_user.id))
    idx=int(arg)
    await h._edit(c,energy.view(c.from_user.id,idx),energy_keys(c.from_user.id,idx))


@h.router.callback_query(F.data.startswith('ebuy:'))
async def cb_energy_buy(c):
    _,idx,amount=c.data.split(':');idx=int(idx)
    await h._edit(c,energy.buy_fuel(c.from_user.id,idx,int(amount))+'\n\n'+energy.view(c.from_user.id,idx),energy_keys(c.from_user.id,idx))


@h.router.callback_query(F.data.startswith('esell:'))
async def cb_energy_sell(c):
    _,idx,amount=c.data.split(':');idx=int(idx)
    await h._edit(c,energy.sell_fuel(c.from_user.id,idx,int(amount)),energy_keys(c.from_user.id,idx))


@h.router.callback_query(F.data.startswith('ecrude:'))
async def cb_energy_crude(c):
    _,idx,amount=c.data.split(':');idx=int(idx)
    await h._edit(c,energy.import_crude(c.from_user.id,idx,int(amount)),energy_keys(c.from_user.id,idx))


def fleet_keys(uid):
    p=state.active(uid);rows=[[('🛠 سفارش نفت‌کش','fbld:'),('📜 پیشنهادهای حمل','finbox:')],[('🎯 نفت‌کش‌های دشمن در جنگ','fet:')]]
    if p:
        for s in db.q("SELECT * FROM tankers WHERE country=? AND status!='sunk' ORDER BY id",(p['country'],)):
            if s['status']=='docked':
                rows.append([(f'📦 بارگیری و پیشنهاد با #{s["id"]}',f'fsend:{s["id"]}')])
                if s['hp']<100:rows.append([(f'🛠 تعمیر #{s["id"]}',f'frp:{s["id"]}')])
            v=fleet.live_voyage(s['id'])
            if v:rows.append([(f'📜 جزئیات سفر #{v["id"]}',f'fvr:{v["id"]}')])
    rows.append([('⛽ انرژی','en:'),('🏙 شهرها','cities:'),('🎛 منو','mn:main')])
    return keyboard(rows)


@h.router.callback_query(F.data=='fv:')
async def cb_fleet(c):
    h._pend_pop(c.from_user.id,c.message.chat.id)
    await h._edit(c,fleet.view(c.from_user.id),fleet_keys(c.from_user.id))


@h.router.callback_query(F.data=='fbld:')
async def cb_fleet_build(c):
    p=state.active(c.from_user.id);rows=[]
    if p:
        rows=[[(geo.CITIES[p['country']][idx],f'ftypes:{idx}')] for idx in geo.PORT_NODES.get(p['country'],[]) if geo.coastal(p['country'])]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'🛠 بندر ساخت را انتخاب کن؛ کارگاه کشتی‌سازی باید تکمیل‌شده باشد. کشورهای محصور در خشکی نفت‌کش اقیانوسی نمی‌سازند.',keyboard(rows))


@h.router.callback_query(F.data.startswith('ftypes:'))
async def cb_fleet_types(c):
    idx=int(c.data.split(':')[1]);rows=[]
    for key,(name,cost,cap,seconds,_) in fleet.CLASSES.items():
        rows.append([(f'{name} · {cost} دلار · {cap} واحد',f'fname:{idx}:{key}')])
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'🚢 نام رده‌ها واقعی/شناخته‌شده است؛ ظرفیت و قیمت فقط واحدهای بازی هستند. ساخت ۲ تا ۶ ساعت پایه، سلامت کارگاه روی سرعت مؤثر است.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fname:'))
async def cb_fleet_name(c):
    _,idx,kind=c.data.split(':')
    h._pend_set(c.from_user.id,c.message.chat.id,f'shipname:{idx}:{kind}')
    await h._edit(c,'✍️ نام نفت‌کش را بنویس؛ ۳ تا ۴۰ حرف. با «لغو» انصراف بده. هزینه فقط در صورت سفارش معتبر کسر می‌شود.',keyboard([[('✋ لغو سفارش','pcancel:'),('↩️ ناوگان','fv:')]]))


@h.router.callback_query(F.data.startswith('fsend:'))
async def cb_fleet_send(c):
    sid=int(c.data.split(':')[1]);_,ship,err=fleet._ship_for(c.from_user.id,sid)
    if err:return await h._edit(c,err,fleet_keys(c.from_user.id))
    rows=[[(fleet.CARGO_LABELS[car],f'fcar:{sid}:{car}')] for car in sorted(fleet.CLASSES[ship['class']][4])]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'📦 نوع بار را انتخاب کن؛ بار باید واقعاً در مخزن همان بندر موجود باشد.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fcar:'))
async def cb_fleet_cargo(c):
    _,sid,cargo=c.data.split(':');p=state.active(c.from_user.id);rows=[]
    if p:
        for r in db.q('SELECT country FROM users WHERE is_leader=1 AND country!=? ORDER BY country',(p['country'],)):
            if r['country'] in countries.COUNTRIES and geo.coastal(r['country']):rows.append([(countries.COUNTRIES[r['country']]['name'],f'fdest:{sid}:{cargo}:{r["country"]}')])
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'🌍 خریدار واقعی را انتخاب کن. حرکت فقط با پذیرش خریدار و امانت‌گذاری پول انجام می‌شود.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fdest:'))
async def cb_fleet_dest(c):
    _,sid,cargo,dest=c.data.split(':')
    rows=[[(geo.CITIES[dest][idx],f'fport:{sid}:{cargo}:{dest}:{idx}')] for idx in geo.PORT_NODES.get(dest,[]) if geo.coastal(dest)]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'⚓ بندر مقصد را انتخاب کن؛ انبار و بندر در زمان پذیرش و تحویل دوباره بررسی می‌شوند.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fport:'))
async def cb_fleet_port(c):
    _,sid,cargo,dest,idx=c.data.split(':');_,ship,err=fleet._ship_for(c.from_user.id,int(sid))
    if err:return await h._edit(c,err,fleet_keys(c.from_user.id))
    cap=fleet.CLASSES[ship['class']][2]
    rows=[[(f'{n} واحد · نرخ مرجع فعلی {energy.reference_price(cargo)*n} دلار',f'foqty:{sid}:{cargo}:{dest}:{idx}:{n}')] for n in sorted({min(20,cap),min(40,cap),cap})]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'📦 مقدار بار؟ قیمت نهایی در پیشنهاد ۳۰دقیقه‌ای ثابت می‌شود؛ پول تا تحویل امانی می‌ماند.',keyboard(rows))


@h.router.callback_query(F.data.startswith('foqty:'))
async def cb_fleet_escort(c):
    fields=c.data.split(':')[1:]
    rows=[[(f'اسکورت: {n} شناور واقعی',f'foesc:{":".join(fields)}:{n}')] for n in (0,1,3)]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'🛡 اسکورت از موجودی آزاد رزرو می‌شود و تا بازگشت در حمله/تعمیر/ارتقا قابل استفاده نیست. صفر یعنی بدون اسکورت.',keyboard(rows))


@h.router.callback_query(F.data.startswith('foesc:'))
async def cb_fleet_offer(c):
    _,sid,cargo,dest,idx,amount,esc=c.data.split(':')
    await h._edit(c,fleet.offer(c.from_user.id,int(sid),dest,int(idx),cargo,int(amount),int(esc)),fleet_keys(c.from_user.id))


@h.router.callback_query(F.data=='finbox:')
@h.router.callback_query(F.data.startswith('fipage:'))
async def cb_fleet_inbox(c):
    uid=c.from_user.id
    count=db.one("SELECT COUNT(*) FROM voyages WHERE status='offered' AND expires>? AND (buyer=? OR seller=?)",(db.now(),uid,uid))[0]
    page=0 if c.data=='finbox:' else int(c.data.split(':')[1])
    page=min(page,max(0,(count-1)//20))
    rows=[[(f'پیشنهاد #{r["id"]} · {r["amount"]} {fleet.CARGO_LABELS[r["cargo"]]} · {r["price"]} دلار',f'fvr:{r["id"]}')] for r in db.q("SELECT * FROM voyages WHERE status='offered' AND expires>? AND (buyer=? OR seller=?) ORDER BY id LIMIT 20 OFFSET ?",(db.now(),uid,uid,page*20))]
    nav=[]
    if page:nav.append(("◀️ قبلی",f"fipage:{page-1}"))
    if (page+1)*20<count:nav.append(("بعدی ▶️",f"fipage:{page+1}"))
    if nav:rows.append(nav)
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'📜 پیشنهادهای حمل منتظر پاسخ؛ هیچ پرداختی با مشاهدهٔ این صفحه انجام نمی‌شود.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fvr:'))
async def cb_fleet_voyage(c):
    vid=int(c.data.split(':')[1]);v=db.one('SELECT * FROM voyages WHERE id=?',(vid,));rows=[]
    if v and v['status']=='offered':
        if v['buyer']==c.from_user.id:rows.append([('✅ پذیرش و امانت‌گذاری مبلغ',f'facc:{vid}')])
        if c.from_user.id in (v['buyer'],v['seller']):rows.append([('❌ رد / لغو پیشنهاد',f'fcancel:{vid}')])
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,fleet.voyage_view(vid),keyboard(rows))


@h.router.callback_query(F.data.startswith('facc:'))
async def cb_fleet_accept(c):await h._edit(c,fleet.accept(c.from_user.id,int(c.data.split(':')[1])),fleet_keys(c.from_user.id))


@h.router.callback_query(F.data.startswith('fcancel:'))
async def cb_fleet_cancel(c):await h._edit(c,fleet.cancel_offer(c.from_user.id,int(c.data.split(':')[1])),fleet_keys(c.from_user.id))


@h.router.callback_query(F.data.startswith('frp:'))
async def cb_fleet_repair(c):await h._edit(c,fleet.repair(c.from_user.id,int(c.data.split(':')[1])),fleet_keys(c.from_user.id))


@h.router.callback_query(F.data=='fet:')
async def cb_fleet_targets(c):
    p=state.active(c.from_user.id);w=campaign.war_of(p['country']) if p else None;rows=[]
    if w:
        enemy=campaign.enemy(p['country'],w)
        rows=[[(f'#{r["id"]} {r["name"]} · {r["hp"]}٪',f'fatk:{r["id"]}')] for r in db.q("SELECT id,name,hp FROM tankers WHERE country=? AND status IN ('docked','reserved','sailing','returning') ORDER BY id",(enemy,))]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'🎯 تنها نفت‌کش دشمنِ جنگ فعال قابل حمله است. بندر کشور ثالث محافظت دارد؛ برد، استقرار، مهمات و سوخت بررسی می‌شود.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fatk:'))
async def cb_fleet_attack_types(c):
    sid=c.data.split(':')[1]
    rows=[[(f'{label} ×{n}',f'fat:{sid}:{key}:{n}') for n in (1,3)] for key,label in ATTACK_TYPES.items()]
    rows.append([('↩️ ناوگان','fv:')])
    await h._edit(c,'⚔️ موج دریایی یا پروازی؟ اولین موج کشتی سالم را غرق نمی‌کند. موشک همچنان سهمیهٔ ۳/۶/۲۰ و زمان پرواز دارد.',keyboard(rows))


@h.router.callback_query(F.data.startswith('fat:'))
async def cb_fleet_attack(c):
    _,sid,kind,count=c.data.split(':')
    await h._edit(c,fleet.attack(c.from_user.id,int(sid),ATTACK_TYPES[kind],int(count)),fleet_keys(c.from_user.id))


h.WORD_VIEWS.update({'ناوگان':lambda uid:(fleet.view(uid),fleet_keys(uid)),
                    'انرژی':lambda uid:('⚡ شهر انرژی را انتخاب کن.',energy_keys(uid))})
