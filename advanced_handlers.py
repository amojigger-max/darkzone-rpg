"""v41 menus extending the original router, not replacing the original bot."""
from aiogram import F
from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
import countries
import db
import handlers as h
from game import economy,straits,operations,un,state


def keyboard(rows):return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) for t,d in row] for row in rows])


def strait_keys(uid,key=None):
    p=state.active(uid);rows=[]
    if key in straits.CONTROLS:
        if p and p['country']==straits.CONTROLS[key][1] and p['is_leader']:
            rows.append([('🔓 باز کن',f'sgact:{key}:open'),('🔒 بستن ۶ساعته · $۱۵۰',f'sgact:{key}:close')])
            rows.append([('🏦 برداشت صندوق همین گذرگاه',f'sgget:{key}')])
            rows.extend([[('🛃 تعرفه '+str(n)+' دلار',f'sgfee:{key}:{n}')] for n in straits.FEES])
        if straits.relevant(uid,key):rows.append([('💵 پرداخت مجوز روزانه',f'sgpay:{key}')])
    else:
        for k,v in straits.CONTROLS.items():rows.append([(v[0]+' · '+countries.COUNTRIES[v[1]]['name'],f'sg:{k}')])
    rows.append([('🌉 همهٔ گذرگاه‌ها','sg:'),('🎛 منو','mn:main')])
    return keyboard(rows)


@h.router.callback_query(F.data.startswith('sg:'))
async def cb_strait_view(c):
    key=c.data.split(':')[1] or None
    await h._edit(c,straits.view(c.from_user.id,key),strait_keys(c.from_user.id,key))


@h.router.callback_query(F.data.startswith('sgact:'))
async def cb_strait_action(c):
    _,key,action=c.data.split(':')
    await h._edit(c,straits.set_open(c.from_user.id,key,action=='open')+'\n\n'+straits.view(c.from_user.id,key),strait_keys(c.from_user.id,key))


@h.router.callback_query(F.data.startswith('sgfee:'))
async def cb_strait_fee(c):
    _,key,amount=c.data.split(':')
    await h._edit(c,straits.set_fee(c.from_user.id,key,int(amount)),strait_keys(c.from_user.id,key))


@h.router.callback_query(F.data.startswith('sgget:'))
async def cb_strait_collect(c):
    key=c.data.split(':')[1]
    await h._edit(c,straits.collect(c.from_user.id,key),strait_keys(c.from_user.id,key))


@h.router.callback_query(F.data.startswith('sgpay:'))
async def cb_strait_pay(c):
    key=c.data.split(':')[1]
    await h._edit(c,straits.pay(c.from_user.id,key),strait_keys(c.from_user.id,key))


@h.router.callback_query(F.data.startswith('sapply:'))
async def cb_sanction_apply(c):
    await h._edit(c,economy.apply_sanction(c.from_user.id,c.data.split(':')[1]),h.kb_market())


@h.router.callback_query(F.data.startswith('slift:'))
async def cb_sanction_lift(c):
    await h._edit(c,economy.lift_sanction(c.from_user.id,c.data.split(':')[1]),h.kb_market())


def operation_keys(uid):
    rows=[[('🧭 عملیات جدید با نام دلخواه','opnew:')]]
    p=state.active(uid)
    if p:
        for r in db.q("SELECT id,name,status FROM operation_plans WHERE country=? AND status IN ('planned','active')",(p['country'],)):
            if r['status']=='planned':rows.append([(f"▶️ اجرای #{r['id']}",f"opgo:{r['id']}")])
            rows.append([(f"🛑 لغو #{r['id']}",f"opcancel:{r['id']}")])
    rows.append([('⚔️ جبهه','mn:front'),('🎛 منو','mn:main')])
    return keyboard(rows)


@h.router.callback_query(F.data=='ops:')
async def cb_operations(c):await h._edit(c,operations.view(c.from_user.id),operation_keys(c.from_user.id))


@h.router.callback_query(F.data=='opnew:')
async def cb_operations_new(c):await h._edit(c,'🧭 کشور هدف عملیات را انتخاب کن؛ فقط رهبر بازیکن‌دار.',h.kb_targets(c.from_user.id,'opt'))


@h.router.callback_query(F.data.startswith('opt:'))
async def cb_operation_target(c):
    target=c.data.split(':')[1]
    await h._edit(c,'🧭 دکترین عملیات؟ هر نوع فقط برای موج‌های مناسب خودش ۱۰٪ مزیت دارد.',keyboard([[(v[0],f'opkind:{target}:{k}')] for k,v in operations.DOCTRINES.items()]))


@h.router.callback_query(F.data.startswith('opkind:'))
async def cb_operation_kind(c):
    from game import rules
    _,target,kind=c.data.split(':')
    await h._edit(c,'⚔️ شیوهٔ جنگ را انتخاب کن؛ در جنگ جاری باید همان شیوه باشد.',keyboard([[(v.label,f'opmode:{target}:{kind}:{k}')] for k,v in rules.MODES.items()]))


@h.router.callback_query(F.data.startswith('opmode:'))
async def cb_operation_name(c):
    _,target,kind,mode=c.data.split(':')
    h._pend_set(c.from_user.id,c.message.chat.id,f'opname:{target}:{kind}:{mode}')
    await h._edit(c,'✍️ نام دلخواه عملیات را همین‌جا بنویس: ۳ تا ۴۰ حرف.\nهزینهٔ ثبت برنامه ۵۰۰ دلار؛ آماده‌سازی یک ساعت. برای انصراف «لغو».',h.kb_cancel_pol())


@h.router.callback_query(F.data.startswith('opgo:'))
async def cb_operation_start(c):
    await h._edit(c,operations.activate(c.from_user.id,int(c.data.split(':')[1])),operation_keys(c.from_user.id))


@h.router.callback_query(F.data.startswith('opcancel:'))
async def cb_operation_cancel(c):
    await h._edit(c,operations.cancel(c.from_user.id,int(c.data.split(':')[1])),operation_keys(c.from_user.id))


def un_keys(page=0):
    page=max(0,page);rows=[[('📝 پیشنهاد قطعنامه','unnew:'),('💝 اهدای ۵۰۰ دلار','undonate:500')]]
    n=db.one("SELECT COUNT(*) FROM un_resolutions WHERE status='voting'")[0]
    page=min(page,max(0,(n-1)//10))
    for r in db.q("SELECT id,kind,target FROM un_resolutions WHERE status='voting' ORDER BY id LIMIT 10 OFFSET ?",(page*10,)):
        rows.append([(f"#{r['id']} {un.KINDS[r['kind']]} · {countries.COUNTRIES[r['target']]['name']}",f"unr:{r['id']}")])
    nav=[]
    if page:nav.append(('◀️ قبلی',f'unpage:{page-1}'))
    if (page+1)*10<n:nav.append(('بعدی ▶️',f'unpage:{page+1}'))
    if nav:rows.append(nav)
    rows.append([('🎛 منو','mn:main')])
    return keyboard(rows)


@h.router.callback_query(F.data=='un:')
async def cb_un(c):await h._edit(c,un.view(c.from_user.id),un_keys())


@h.router.callback_query(F.data.startswith('unpage:'))
async def cb_un_page(c):await h._edit(c,un.view(c.from_user.id),un_keys(int(c.data.split(':')[1])))


@h.router.callback_query(F.data=='unnew:')
async def cb_un_new(c):
    # Country target, including own country, is intentional: aid can be proposed for self, voted by all.
    rows=[[(v['name'],f'unt:{k}')] for k,v in countries.COUNTRIES.items() if k in un.members()]
    rows.append([('↩️ سازمان ملل','un:')])
    await h._edit(c,'🇺🇳 کشور موضوع قطعنامه؟ جلسه ۱۵۰ دلار به صندوق سازمان ملل واریز می‌کند.',keyboard(rows))


@h.router.callback_query(F.data.startswith('unt:'))
async def cb_un_target(c):
    target=c.data.split(':')[1]
    await h._edit(c,'🇺🇳 موضوع جلسه؟',keyboard([[(v,f'unprop:{k}:{target}')] for k,v in un.KINDS.items()]))


@h.router.callback_query(F.data.startswith('unprop:'))
async def cb_un_propose(c):
    _,kind,target=c.data.split(':')
    await h._edit(c,un.propose(c.from_user.id,kind,target),un_keys())


@h.router.callback_query(F.data.startswith('unr:'))
async def cb_un_resolution(c):
    rid=int(c.data.split(':')[1])
    rows=[[('✅ موافق',f'unvote:{rid}:yes'),('❌ مخالف',f'unvote:{rid}:no'),('➖ ممتنع',f'unvote:{rid}:abstain')],[('↩️ سازمان ملل','un:')]]
    await h._edit(c,un.resolution_view(rid),keyboard(rows))


@h.router.callback_query(F.data.startswith('unvote:'))
async def cb_un_vote(c):
    _,rid,vote=c.data.split(':')
    await h._edit(c,un.vote(c.from_user.id,int(rid),vote),un_keys())


@h.router.callback_query(F.data.startswith('undonate:'))
async def cb_un_donate(c):await h._edit(c,un.donate(c.from_user.id,int(c.data.split(':')[1])),un_keys())


h.WORD_VIEWS.update({'عملیات':lambda uid:(operations.view(uid),operation_keys(uid)),
                    'سازمان‌ملل':lambda uid:(un.view(uid),un_keys()),
                    'تنگه‌ها':lambda uid:(straits.view(uid),strait_keys(uid))})


@h.router.callback_query(F.data.startswith('dpage:'))
async def cb_duel_page(c):await h._edit(c,'⚔️ انتخاب حریف واقعی؛ بدون حذف بازیکنان از فهرست.',h.kb_duel(c.from_user.id,int(c.data.split(':')[1])))


def upgrade_view(uid,page=0):
    from game import military
    rows=db.q('SELECT iid FROM inventory WHERE uid=? AND qty>0 ORDER BY iid',(uid,))
    rows=[r for r in rows if r['iid'] in countries.ITEMS]
    page=max(0,min(page,max(0,(len(rows)-1)//10)))
    keys=[]
    for r in rows[page*10:(page+1)*10]:
        iid=r['iid'];it=countries.ITEMS[iid]
        keys.append([(f'{it[1]} {it[0]} · سطح {military.item_level(uid,iid)}',f'up:{iid}')])
    nav=[]
    if page:nav.append(('◀️ قبلی',f'upage:{page-1}'))
    if (page+1)*10<len(rows):nav.append(('بعدی ▶️',f'upage:{page+1}'))
    if nav:keys.append(nav)
    keys.append([('🎛 منو','mn:main')])
    return '⬆️ پژوهش و ارتقای نوع تجهیز؛ تمام اقلام انبار با صفحه‌بندی در دسترس‌اند.',keyboard(keys)


@h.router.callback_query(F.data.startswith('upage:'))
async def cb_upgrade_page(c):
    body,kb=upgrade_view(c.from_user.id,int(c.data.split(':')[1]))
    await h._edit(c,body,kb)


@h.router.callback_query(F.data=='allymanage:')
async def cb_alliance_management(c):
    from game import war
    p=state.active(c.from_user.id);allies=war.allies_of(p['country']) if p else []
    rows=[[(f"پایان اتحاد {countries.COUNTRIES[cid]['name']} · آتش‌بس ۱۲ساعته",f'aquit:{cid}')] for cid in allies]
    rows.append([('↩️ دیپلماسی','mn:pol')])
    body='🤝 پایان اتحاد، اجازهٔ پایگاه را هم لغو می‌کند و تا ۱۲ ساعت حملهٔ مستقیم ممنوع می‌ماند.'
    if not allies:body+='\nاتحاد فعالی نداری.'
    await h._edit(c,body,keyboard(rows))


@h.router.callback_query(F.data.startswith('aquit:'))
async def cb_end_alliance(c):
    from game import war
    await h._edit(c,war.end_alliance(c.from_user.id,c.data.split(':')[1]),h.kb_pol())
