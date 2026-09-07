"""A player-only UN: one country/one vote, finite donation fund, no NPC votes or veto."""
import json
import math
import countries
import db
import texts
from game import state,campaign,notifications

KINDS={'ceasefire':'آتش‌بس با رضایت دو طرف','sanctions':'بازبینی و تعلیق تحریم','aid':'کمک از صندوق واقعی'}
VOTE_TIME=24*3600
MIN_DEBATE=600
COST=150
AID=2000


def members():return [r['country'] for r in db.q('SELECT DISTINCT country FROM users WHERE is_leader=1 AND country IS NOT NULL ORDER BY country') if r['country'] in countries.COUNTRIES]


def fund():return db.integer(db.kv_get('un_fund'),0,0,10**15)


@db.atomic
def donate(uid,amount):
    p=state.active(uid)
    if not p or type(amount) is not int or not 1<=amount<=5000:return '⛔ حساب فعال و مبلغ صحیح ۱ تا ۵۰۰۰ لازم است.'
    if not db.debit(uid,amount):return '💰 موجودی کافی نیست.'
    db.kv_set('un_fund',fund()+amount);db.audit('un_donation',uid,amount=amount)
    return f'🇺🇳 {amount} دلار به صندوق کمک منتقل شد؛ موجودی صندوق {fund()} دلار.'


@db.atomic
def propose(uid,kind,target):
    p,err=campaign._leader(uid)
    if err:return err
    eligible=members()
    if len(eligible)<2:return '🇺🇳 دست‌کم دو کشور با رهبر واقعی لازم است.'
    if kind not in KINDS or target not in eligible:return '⛔ نوع قطعنامه یا کشور هدف معتبر نیست.'
    if db.now()-db.integer(db.kv_get(f'un_propose:{uid}'))<3600:return '⏳ هر رهبر در هر ساعت یک پیشنهاد.'
    if db.one("SELECT 1 FROM un_resolutions WHERE kind=? AND target=? AND status='voting' AND expires>?",(kind,target,db.now())):return '⏳ پیشنهاد هم‌موضوع در حال رأی‌گیری است.'
    data={}
    if kind=='ceasefire':
        w=campaign.war_of(target)
        if not w:return '🕊 کشور هدف در جنگ نیست.'
        data={'war_id':w['id'],'a':w['a'],'b':w['b']}
    if kind=='aid' and fund()<AID:return '🏦 صندوق برای کمک ۲۰۰۰ دلاری موجودی ندارد؛ ابتدا اهدای داوطلبانه.'
    if not db.debit(uid,COST):return '💰 هزینهٔ برگزاری جلسه ۱۵۰ دلار است.'
    db.kv_set('un_fund',fund()+COST)
    cur=db.ex('INSERT INTO un_resolutions(uid,kind,target,eligible,data,created,expires) VALUES(?,?,?,?,?,?,?)',
             (uid,kind,target,json.dumps(eligible),json.dumps(data),db.now(),db.now()+VOTE_TIME))
    rid=cur.lastrowid;db.kv_set(f'un_propose:{uid}',db.now())
    db.ex('INSERT INTO un_votes(resolution_id,country,uid,vote,ts) VALUES(?,?,?,?,?)',(rid,p['country'],uid,'yes',db.now()))
    msg=f'🇺🇳 قطعنامهٔ #{rid}: {KINDS[kind]} دربارهٔ {countries.COUNTRIES[target]["name"]}.\nهر کشور یک رأی؛ تصویب با دوسوم کل اعضای جلسه، حداقل ۱۰ دقیقه بررسی و مهلت ۲۴ ساعت. رأی‌گیری: /un'
    notifications.emit(msg,all_players=True,key=f'un:{rid}:proposal')
    return msg


@db.atomic
def vote(uid,rid,choice):
    p,err=campaign._leader(uid)
    if err:return err
    r=db.one('SELECT * FROM un_resolutions WHERE id=?',(rid,))
    if not r or choice not in ('yes','no','abstain'):return '⛔ رأی یا قطعنامه معتبر نیست.'
    if r['status']!='voting' or db.now()>=r['expires']:return '⛔ رأی‌گیری پایان یافته است.'
    if p['country'] not in json.loads(r['eligible']):return '⛔ کشور تو عضو این جلسه در زمان تشکیل نبوده است.'
    db.ex('INSERT INTO un_votes(resolution_id,country,uid,vote,ts) VALUES(?,?,?,?,?) ON CONFLICT(resolution_id,country) DO UPDATE SET uid=excluded.uid,vote=excluded.vote,ts=excluded.ts',
          (rid,p['country'],uid,choice,db.now()))
    tick()
    return '🗳 رأی کشور ثبت/اصلاح شد؛ تکرار دکمه رأی اضافه نمی‌کند.\n'+resolution_view(rid)


@db.atomic
def tick():
    for row in db.q("SELECT * FROM un_resolutions WHERE status='voting' ORDER BY id"):
        r=dict(row);eligible=json.loads(r['eligible']);needed=max(2,math.ceil(len(eligible)*2/3))
        votes={v['country']:v['vote'] for v in db.q('SELECT country,vote FROM un_votes WHERE resolution_id=?',(r['id'],))}
        yes=sum(v=='yes' for v in votes.values())
        if yes>=needed and db.now()>=r['created']+MIN_DEBATE:
            result=_apply(r,votes)
            db.ex("UPDATE un_resolutions SET status='passed',result=? WHERE id=?",(result,r['id']))
            notifications.emit(f"🇺🇳 قطعنامهٔ #{r['id']} تصویب شد.\n{result}",all_players=True,key=f"un:{r['id']}:result")
        elif db.now()>=r['expires']:
            db.ex("UPDATE un_resolutions SET status='expired',result='آرای لازم جمع نشد' WHERE id=?",(r['id'],))
            notifications.emit(f"🇺🇳 قطعنامهٔ #{r['id']} بدون آرای لازم بسته شد؛ هیچ اثر پنهانی اعمال نشد.",all_players=True,key=f"un:{r['id']}:result")


def _apply(r,votes):
    target=r['target'];kind=r['kind'];data=json.loads(r['data'])
    if kind=='sanctions':
        db.ex('DELETE FROM kv WHERE k LIKE ?',(f'sanction_pair:%:{target}',))
        db.kv_set(f'un_shield:{target}',db.now()+6*3600)
        return '✅ تحریم‌های موجود هدف با رأی جمعی لغو و برای ۶ ساعت از وضع مجدد محافظت شد.'
    if kind=='ceasefire':
        w=db.one("SELECT * FROM wars WHERE id=? AND status='active'",(data['war_id'],))
        if not w:return '🕊 جنگ مربوطه قبلاً پایان یافته؛ جنگ تازه‌ای دست‌کاری نشد.'
        if votes.get(w['a'])=='yes' and votes.get(w['b'])=='yes':return campaign.finish(w,'peace')
        return '🕊 توصیهٔ آتش‌بس تصویب شد؛ چون هر دو طرف جنگ موافق نیستند، جنگ به‌زور یا خودکار متوقف نشد.'
    if kind=='aid':
        rows=db.q('SELECT uid FROM users WHERE country=? ORDER BY uid',(target,))
        if not rows or fund()<AID:return '🏦 هنگام اجرا، گیرنده یا موجودی کافی نبود؛ هیچ پولی ساخته نشد.'
        db.kv_set('un_fund',fund()-AID)
        share,extra=divmod(AID,len(rows))
        for i,p in enumerate(rows):db.ex('UPDATE users SET money=money+? WHERE uid=?',(share+(i<extra),p['uid']))
        db.audit('un_aid',resolution=r['id'],target=target,amount=AID)
        return '💰 ۲۰۰۰ دلار از موجودی صندوق به اعضای واقعی کشور منتقل شد؛ پرداخت یک‌باره.'
    raise ValueError('unknown resolution type')


def resolution_view(rid):
    r=db.one('SELECT * FROM un_resolutions WHERE id=?',(rid,))
    if not r:return '⛔ قطعنامه پیدا نشد.'
    voters=db.q('SELECT * FROM un_votes WHERE resolution_id=? ORDER BY country',(rid,))
    label={'voting':'رأی‌گیری','passed':'تصویب‌شده','rejected':'ردشده','expired':'مهلت پایان‌یافته'}[r['status']]
    lines=[f"🇺🇳 #{rid} — {KINDS[r['kind']]} / {countries.COUNTRIES[r['target']]['name']}",
           f"وضعیت: {label} · لازم: {max(2,math.ceil(len(json.loads(r['eligible']))*2/3))} رأی موافق"]
    for v in voters:
        p=state.get(v['uid']) or {}
        lines.append(f"{countries.COUNTRIES[v['country']]['flag']} {texts.mention(v['uid'],p.get('name'))}: "+{'yes':'موافق','no':'مخالف','abstain':'ممتنع'}[v['vote']])
    if r['result']:lines.append(r['result'])
    return '\n'.join(lines)


def view(uid=None):
    lines=[texts.hdr('سازمان ملل بازیکنان','🇺🇳'),f'اعضا: {len(members())} کشور · صندوق واقعی: {fund()} دلار',
           'کشور قدرتمند رأی بیشتر یا حق وتوی خودکار ندارد. بدون رهبر NPC، بدون رأی ساختگی.',
           'جلسه: ۱۵۰ دلار به صندوق؛ اهدای داوطلبانه ۱ تا ۵۰۰۰؛ کمک مصوب ۲۰۰۰ دلار از صندوق.']
    for r in db.q("SELECT id FROM un_resolutions WHERE status='voting' ORDER BY id"):
        lines.append(f"\nقطعنامهٔ #{r['id']} در رأی‌گیری؛ جزئیات و رأی‌ها از دکمهٔ خودش.")
    return '\n'.join(lines)
