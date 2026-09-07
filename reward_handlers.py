"""Gift overflow storage and explicit, single-use personal inventory disposal."""
from aiogram import F
import countries
import db
import handlers as h
from advanced_handlers import keyboard
from game import rewards,military,state


def gift_keys(uid):
    rows=[]
    if state.active(uid):
        if db.one('SELECT 1 FROM reward_stock WHERE uid=? AND qty>0',(uid,)):
            rows.append([('📦 انتقال ذخیرهٔ هدایا به زرادخانه','grstock:')])
        rows.append([('🗑 آزادکردن جا با تأیید جداگانه','scraps:')])
    rows.append([('🎛 منو','mn:main')])
    return keyboard(rows)


def gift_view(uid):
    paid=rewards.award_pending(uid)
    return ('\n\n'.join(paid)+'\n\n' if paid else '')+rewards.pending_view(uid)


@h.router.callback_query(F.data=='grstock:')
async def cb_claim_gift_stock(c):
    await h._edit(c,rewards.claim_stock(c.from_user.id)+'\n\n'+rewards.pending_view(c.from_user.id),gift_keys(c.from_user.id))


@h.router.callback_query(F.data=='scraps:')
@h.router.callback_query(F.data.startswith('scpage:'))
async def cb_disposal_list(c):
    uid=c.from_user.id;page=0 if c.data=='scraps:' else int(c.data.split(':')[1])
    count=db.one('SELECT COUNT(*) FROM inventory WHERE uid=? AND qty>0',(uid,))[0]
    page=min(page,max(0,(count-1)//10));rows=[]
    for r in db.q('SELECT iid,qty,dur FROM inventory WHERE uid=? AND qty>0 ORDER BY iid LIMIT 10 OFFSET ?',(uid,page*10)):
        if r['iid'] in countries.ITEMS:rows.append([(f"{countries.ITEMS[r['iid']][0]} · {r['qty']} عدد · {r['dur']}٪",f"scprep:{r['iid']}")])
    nav=[]
    if page:nav.append(('◀️ قبلی',f'scpage:{page-1}'))
    if (page+1)*10<count:nav.append(('بعدی ▶️',f'scpage:{page+1}'))
    if nav:rows.append(nav)
    rows.append([('↩️ هدایا','srcancel:')])
    await h._edit(c,'🗑 این فهرست چیزی حذف نمی‌کند. انتخاب هر تجهیز فقط صفحهٔ تأیید حذف یک عدد را باز می‌کند؛ پولی در ازای حذف داده نمی‌شود.',keyboard(rows))


@h.router.callback_query(F.data.startswith('scprep:'))
async def cb_disposal_prepare(c):
    body,nonce=military.retire_offer(c.from_user.id,c.data.split(':')[1],1)
    rows=[]
    if nonce:rows.append([('⚠️ تأیید حذف دقیقاً یک عدد',f'scrok:{nonce}')])
    rows.append([('✋ لغو بدون حذف','srcancel:')])
    await h._edit(c,body,keyboard(rows))


@h.router.callback_query(F.data.startswith('scrok:'))
async def cb_disposal_confirm(c):
    await h._edit(c,military.retire_confirm(c.from_user.id,c.data.split(':')[1]),gift_keys(c.from_user.id))


@h.router.callback_query(F.data=='srcancel:')
async def cb_disposal_cancel(c):
    db.kv_del(f'retire:{c.from_user.id}')
    await h._edit(c,'✋ حذف لغو شد؛ چیزی از انبار کم نشد.\n\n'+rewards.pending_view(c.from_user.id),gift_keys(c.from_user.id))


h.WORD_VIEWS['هدایا']=lambda uid:(gift_view(uid),gift_keys(uid))
