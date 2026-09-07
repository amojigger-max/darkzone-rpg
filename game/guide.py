"""Practical Persian guide using the same rule constants as the campaign engine."""
import json
import countries
import db
import texts
from game import catalog, rules, state


def guide(cid):
    c=countries.COUNTRIES.get(cid)
    if not c:return '⛔ کشور نامعتبر.'
    spec,pct,name=countries.spec_of(cid)
    lines=[texts.hdr(f"راهنمای {c['name']}",'📖'),
           f'تخصص: {name} · +{pct}٪ در {spec}',
           f'ضریب پایهٔ کشور: {catalog.country_factor(cid):.3f}؛ تجهیزات و تصمیم‌های بازیکن تعیین‌کننده‌اند.',
           'اعداد و ویژگی‌های تجهیزات، انتزاعی و مخصوص بازی هستند.','', '🪖 شاخه‌ها:']
    lines+=c['branches']
    lines+=['','🛒 تجهیزات همان نسخهٔ قبلی، با نقش و توازن اصلاح‌شده:']
    for iid in c['items']:
        it=countries.ITEMS[iid]
        lines.append(f"{it[1]} {it[0]} · {catalog.primary(iid)} · ⚔️{it[3]} / 🛡{it[4]} · {it[5]} دلار")
    lines+=['','جنگ را از نوع مناسب آغاز کن؛ در دورهٔ آماده‌سازی مهمات مصرف نمی‌شود.',
            f'گرفتن هر شهر: دست‌کم {rules.CITY_MIN_ROUNDS} موج زمینی موفق و {rules.CITY_MIN_SIEGE//3600} ساعت محاصره.',
            'خاموش‌کردن برق یا زدن پایگاه، شهر یا کشور را یک‌باره تسلیم نمی‌کند.',
            'برای هدف شهری: جبهه → حملهٔ هدفمند → شهر → بخش → تجهیزات.',
            'برای پایگاه: منو → شهرها → شهر دلخواه → نوع پایگاه؛ زمان ساخت را صبر کن.']
    return '\n'.join(lines)


@db.atomic
def mark_read(uid,page,total):
    if not state.active(uid) or not 1<=page<=total:return ''
    visited=set(db.jload(db.kv_get(f'read_pages:{uid}'),[]) or [])
    visited.add(page)
    db.kv_set(f'read_pages:{uid}',json.dumps(sorted(visited)))
    if set(range(1,total+1))<=visited and not db.kv_get(f'guide_done:{uid}'):
        db.ex('UPDATE users SET money=money+300 WHERE uid=?',(uid,))
        db.kv_set(f'guide_done:{uid}',1)
        return '\n\n🎓 همهٔ صفحات باز شدند؛ ۳۰۰ دلار مجازی و نشان دانش‌آموخته، فقط یک بار.'
    return ''
