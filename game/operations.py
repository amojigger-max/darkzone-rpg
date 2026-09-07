"""Named, prepared offensives: modest, finite bonuses; no override of geography or war phases."""
import html
import countries
import db
import texts
from game import state,campaign,rules,notifications

DOCTRINES={
 'ground':('پیشروی زمینی',{'زمینی','توپخانه'}),
 'air':('برتری هوایی',{'هوایی','چندمنظوره'}),
 'naval':('گشایش دریایی',{'دریایی','آبی‌خاکی'}),
 'precision':('ضربت دقیق',{'موشکی','پهپادی'}),
}
PLAN_COST=500
PLAN_TIME=3600
PLAN_TTL=24*3600
BONUS=.10
WAVES=6


@db.atomic
def tick():
    db.ex("UPDATE operation_plans SET status='completed' WHERE status IN ('planned','active') AND expires<=?",(db.now(),))
    db.ex("UPDATE operation_plans SET status='completed' WHERE status='active' AND (uses>=? OR war_id NOT IN (SELECT id FROM wars WHERE status='active'))",(WAVES,))


@db.atomic
def create(uid,target,name,doctrine='ground',mode='total'):
    p,err=campaign._leader(uid)
    if err:return err
    if target not in countries.COUNTRIES or target==p['country'] or doctrine not in DOCTRINES or mode not in rules.MODES:return '⛔ نوع عملیات، هدف یا شیوهٔ جنگ معتبر نیست.'
    if not isinstance(name,str):return '⛔ نام باید متن باشد.'
    clean=' '.join(html.unescape(name).split())
    if not 3<=len(clean)<=40:return '⛔ نام عملیات باید بین ۳ تا ۴۰ حرف باشد.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(target,)):return '🕊 کشور خالی هدف عملیات نیست.'
    tick()
    if db.one("SELECT 1 FROM operation_plans WHERE country=? AND status IN ('planned','active')",(p['country'],)):return '⏳ کشور تو یک عملیات آماده یا فعال دارد؛ ابتدا آن را تمام یا لغو کن.'
    w=campaign.war_of(p['country'])
    if w and (campaign.enemy(p['country'],w)!=target or campaign.ensure_campaign(w)['mode']!=mode):return '⚔️ در زمان جنگ، برنامه باید برای همان دشمن و همان نوع جنگ باشد.'
    if doctrine in ('ground','naval'):
        kind='زمینی' if doctrine=='ground' else 'دریایی'
        ok,why=campaign.can_strike_kind(p['country'],target,kind)
        if not ok:return why
    if not db.debit(uid,PLAN_COST):return f'💰 طراحی ستاد {PLAN_COST} دلار هزینه دارد.'
    cur=db.ex('INSERT INTO operation_plans(uid,country,target,name,doctrine,mode,created,ready_at,expires) VALUES(?,?,?,?,?,?,?,?,?)',
        (uid,p['country'],target,clean,doctrine,mode,db.now(),db.now()+PLAN_TIME,db.now()+PLAN_TTL))
    db.audit('operation_plan',uid,id=cur.lastrowid,target=target,mode=mode,doctrine=doctrine,cost=PLAN_COST)
    return f'🧭 عملیات «{texts.esc(clean)}» ثبت شد؛ آماده‌سازی یک ساعت، فرصت اجرا ۲۴ ساعت.\nمزیت: ۱۰٪ هماهنگی برای ۶ موج هم‌نوع؛ سقف خسارت، موجودی موشک، مرز و زمان فتح حذف نمی‌شوند.'


@db.atomic
def activate(uid,operation_id):
    p,err=campaign._leader(uid)
    if err:return err
    tick()
    op=db.one('SELECT * FROM operation_plans WHERE id=?',(operation_id,))
    if not op or op['uid']!=uid or op['country']!=p['country']:return '⛔ عملیات متعلق به این رهبر/کشور نیست.'
    if op['status']!='planned':return '⛔ عملیات دیگر در مرحلهٔ آماده‌سازی نیست.'
    if db.now()<op['ready_at']:return '⏳ آماده‌سازی یک‌ساعته کامل نشده است.'
    w=campaign.war_of(p['country'])
    msg=''
    if not w:
        msg=campaign.declare(uid,op['target'],op['mode'])
        w=campaign.war_of(p['country'])
        if not w:return msg
    if campaign.enemy(p['country'],w)!=op['target'] or campaign.ensure_campaign(w)['mode']!=op['mode']:
        return '⛔ دشمن یا نوع جنگ نسبت به برنامه تغییر کرده است.'
    db.ex("UPDATE operation_plans SET status='active',war_id=?,expires=? WHERE id=?",(w['id'],db.now()+PLAN_TTL,operation_id))
    notice=f"🧭 عملیات «{texts.esc(op['name'])}» فعال شد: {DOCTRINES[op['doctrine']][0]} علیه {countries.COUNTRIES[op['target']]['name']}.\nدورهٔ اخطار جنگ جداست؛ اولین ضربه کشور را تسلیم نمی‌کند."
    notifications.emit(notice,cids=[op['country'],op['target']],uids=[uid],key=f'operation:{operation_id}:active')
    return msg+'\n'+notice


@db.atomic
def cancel(uid,operation_id):
    p=state.active(uid);op=db.one('SELECT * FROM operation_plans WHERE id=?',(operation_id,))
    if not p or not p['is_leader'] or not op or op['uid']!=uid or op['country']!=p['country']:return '⛔ عملیات متعلق به شما نیست.'
    if op['status'] not in ('planned','active'):return '✅ عملیات قبلاً پایان یافته است.'
    db.ex("UPDATE operation_plans SET status='cancelled' WHERE id=?",(operation_id,))
    return '🛑 عملیات لغو شد؛ هزینهٔ طراحی مصرف‌شده و مهمات شلیک‌شده بازنمی‌گردد.'


def reserve(uid,war_id,target,kind):
    """Called inside the wave launch transaction; failure rolls back the use, too."""
    tick()
    op=db.one("SELECT * FROM operation_plans WHERE uid=? AND war_id=? AND target=? AND status='active' AND uses<?",(uid,war_id,target,WAVES))
    if not op or kind not in DOCTRINES[op['doctrine']][1]:return 1.0,''
    db.ex('UPDATE operation_plans SET uses=uses+1 WHERE id=?',(op['id'],))
    return 1+BONUS,op['name']


def view(uid):
    tick();p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    lines=[texts.hdr('ستاد عملیات نام‌گذاری‌شده','🧭'),
      'طراحی ۵۰۰ دلار · آماده‌سازی ۱ ساعت · ۱۰٪ هماهنگی برای ۶ موج مناسب · فقط یک برنامهٔ هم‌زمان برای هر کشور.']
    rows=db.q("SELECT * FROM operation_plans WHERE country=? ORDER BY id DESC LIMIT 20",(p['country'],))
    for r in rows:
        label={'planned':'در آماده‌سازی' if db.now()<r['ready_at'] else 'آمادهٔ اجرا','active':'فعال','completed':'پایان‌یافته','cancelled':'لغوشده'}[r['status']]
        lines.append(f"\n#{r['id']} «{texts.esc(r['name'])}» → {countries.COUNTRIES[r['target']]['name']}\n{DOCTRINES[r['doctrine']][0]} · {label} · موج مصرف‌شده {r['uses']}/{WAVES}")
    if not rows:lines.append('برنامه‌ای نیست؛ از دکمهٔ «عملیات جدید» آغاز کن.')
    return '\n'.join(lines)
