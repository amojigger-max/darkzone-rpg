"""War public API, retained menus and player-to-player diplomacy; v41 campaign engine."""
import json
import random

import db
import countries
import texts
from game import defense, geo, infra, military, state, campaign, catalog, notifications, rules

# 📡 خبر فوری بی‌بی‌سی — بعد از هر موج، فرستنده می‌خواند و پاک می‌کند
PENDING_BBC = notifications.NewsQueue()


def bbc_pop() -> str:
    """📰 آخرین خبر فوری — برای ارسال جداگانه در گروه."""
    return PENDING_BBC.pop(0) if PENDING_BBC else ""


FA_D = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

WAR_HOURS = rules.MODES["total"].maximum // 3600

EMOJI_KIND = {"🚀": "موشکی", "🛩": "پهپادی", "🚢": "دریایی", "🤿": "دریایی",
              "🚜": "زمینی", "🛻": "زمینی", "💥": "توپخانه", "🛡": "پدافندی", "✈️": "هوایی"}


def kind_of(iid: str):
    return catalog.primary(iid)


# ═══════════ اتحادها ═══════════

@db.atomic
def alliance_request(leader_uid: int, target: str) -> str:
    p,err=campaign._leader(leader_uid)
    if err:return err
    if target not in countries.COUNTRIES or target==p['country']:return '⛔ کشور هدف نامعتبر.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(target,)):return '🕊 کشور خالی طرف قرارداد نیست؛ رهبر بازیکن لازم است.'
    if target in allies_of(p['country']):return '🤝 از قبل متحد هستید.'
    w=war_of(p['country'])
    if w and _enemy(p['country'],w)==target:return '⚔️ ابتدا صلح کنید.'
    key=f"alliance_req:{p['country']}:{target}"
    db.kv_set(key,db.now())
    msg=f"🤝 پیشنهاد اتحاد {countries.COUNTRIES[p['country']]['name']} → {countries.COUNTRIES[target]['name']} ارسال شد؛ ۲۴ ساعت فرصت پذیرش.\nاتحاد خودکار امتیاز یا نیروی NPC تولید نمی‌کند."
    notifications.emit(msg,cids=[p['country'],target],uids=[leader_uid])
    return msg


def side_tags(*cids: str) -> str:
    ids=notifications.player_ids(cids)
    return " ".join(texts.mention(uid, (state.get(uid) or {}).get('name','بازیکن')) for uid in ids)


@db.atomic
def alliance_accept(leader_uid: int, cid: str) -> str:
    p,err=campaign._leader(leader_uid)
    if err:return err
    if cid not in countries.COUNTRIES or cid==p['country']:return '⛔ درخواست نامعتبر.'
    key=f"alliance_req:{cid}:{p['country']}";ts=db.integer(db.kv_get(key))
    if not ts or db.now()-ts>86400:return '⛔ درخواست معتبر یا مهلت باقی‌مانده‌ای نیست.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(cid,)):return '⛔ کشور درخواست‌کننده دیگر رهبر ندارد.'
    w=war_of(p['country'])
    if w and _enemy(p['country'],w)==cid:return '⚔️ ابتدا صلح کنید.'
    a,b=sorted((cid,p['country']))
    if db.one('SELECT 1 FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)',(a,b,b,a)):
        db.kv_del(key);return '🤝 از قبل متحد هستید.'
    db.ex('INSERT INTO alliances(a,b,created) VALUES(?,?,?)',(a,b,db.now()))
    db.kv_del(key)
    msg=f"🤝 اتحاد رسمی {countries.COUNTRIES[a]['name']} و {countries.COUNTRIES[b]['name']} ثبت شد.\nکمک باید با اقدام واقعی بازیکن باشد؛ استفاده از پایگاه نیازمند اجازهٔ جداست."
    notifications.emit(msg,cids=[a,b],uids=[leader_uid])
    return msg


def allies_of(cid: str):
    rows = db.q("SELECT a, b FROM alliances WHERE a=? OR b=?", (cid, cid))
    return list({r["a"] if r["b"] == cid else r["b"] for r in rows})


@db.atomic
def call_help(leader_uid: int) -> str:
    p,err=campaign._leader(leader_uid)
    if err:return err
    w=war_of(p['country'])
    if not w:return '🕊 کشورت در جنگ نیست.'
    allies=allies_of(p['country'])
    if not allies:return '🤝 اتحادی نداری.'
    key=f"help:{w['id']}:{p['country']}"
    if db.now()-db.integer(db.kv_get(key))<1800:return '⏳ فراخوان کمک هر ۳۰ دقیقه یک بار.'
    db.kv_set(key,db.now())
    msg='🆘 درخواست کمک به متحدان ارسال شد؛ انتقال پول یا اجازهٔ پایگاه با تصمیم خودشان است. هیچ امتیازی اضافه نشد.'
    notifications.emit(msg,cids=[p['country'],*allies],uids=[leader_uid])
    return msg


# ═══════════ صلح ═══════════

@db.atomic
def peace_request(uid) -> str:
    p,err=campaign._leader(uid)
    if err:return err
    w=war_of(p['country'])
    if not w:return '🕊 جنگی نیست.'
    db.kv_set(f"peace:{w['id']}",p['country'])
    db.kv_set(f"peace_ts:{w['id']}",db.now())
    msg='🕊 درخواست صلح ارسال شد؛ رهبر طرف مقابل ظرف ۶ ساعت از منوی جنگ «قبول صلح» را بزند.\nکنترل شهرها در خط آتش‌بس می‌ماند؛ هیچ کشوری خودکار تابع نمی‌شود.'
    notifications.emit(msg,cids=[w['a'],w['b']],uids=[uid])
    return msg


@db.atomic
def peace_accept(uid) -> str:
    p,err=campaign._leader(uid)
    if err:return err
    w=war_of(p['country'])
    if not w:return '🕊 جنگی نیست.'
    if db.kv_get(f"peace:{w['id']}")!=_enemy(p['country'],w):return '⛔ درخواست صلحی از طرف مقابل نیست.'
    if db.now()-db.integer(db.kv_get(f"peace_ts:{w['id']}"))>21600:return '⏳ مهلت درخواست صلح تمام شد.'
    return campaign.finish(w,'peace')


def surrender(uid):
    return campaign.surrender(uid)


# ═══════════ نبرد تن‌به‌تن (PvP) ═══════════

@db.atomic
def duel_request(uid,target_name,target_uid=None):
    a,b=state.active(uid),state.active(target_uid) if target_uid else None
    if not a or not b or uid==target_uid:return '⛔ چالش فقط با یک بازیکن واقعی و متفاوت ممکن است.'
    if db.now()-db.integer(db.kv_get(f'duel_cd:{uid}'))<300:return '⏳ میان نبردها ۵ دقیقه فاصله لازم است.'
    key=f'duel_to:{target_uid}'
    existing=db.jload(db.kv_get(key),{}) or {}
    if existing and existing.get('expires',0)>db.now():return '⏳ این بازیکن یک چالش پاسخ‌داده‌نشده دارد.'
    db.kv_set(key,json.dumps({'a':uid,'b':target_uid,'expires':db.now()+300}))
    msg=f"⚔️ {texts.mention(uid,a['name'])} از {texts.mention(target_uid,b['name'])} برای نبرد دعوت کرد؛ ۵ دقیقه فرصت پذیرش.\nنبرد پول رایگان یا شهر تولید نمی‌کند."
    notifications.emit(msg,uids=[uid,target_uid])
    return msg


@db.atomic
def duel_accept(uid):
    key=f'duel_to:{uid}';d=db.jload(db.kv_get(key),{}) or {}
    if not d or d.get('b')!=uid or d.get('expires',0)<db.now():return '⛔ چالش معتبر نیست یا مهلتش گذشته است.'
    a,b=state.active(d['a']),state.active(uid)
    if not a or not b:return '⛔ یکی از دو حساب دیگر کشور ندارد.'
    if a['branch'] in (None,'') or b['branch'] in (None,''):return '🪖 هر دو باید شاخهٔ نظامی انتخاب کرده باشند.'
    if min(a['hp'],b['hp'])<20:return '🏥 هر دو فرمانده باید دست‌کم ۲۰ جان داشته باشند.'
    if any(db.now()-db.integer(db.kv_get(f"duel_cd:{p['uid']}"))<300 for p in (a,b)):return '⏳ یکی از طرف‌ها به‌تازگی نبرد کرده است.'
    ap=military.loadout(a['uid']);bp=military.loadout(b['uid'])
    scores=[(ap[2]+ap[3])*random.uniform(0.95,1.05),(bp[2]+bp[3])*random.uniform(0.95,1.05)]
    winner=a if scores[0]>=scores[1] else b
    for p,kit in ((a,ap),(b,bp)):
        db.ex('UPDATE users SET hp=MAX(10,hp-10) WHERE uid=?',(p['uid'],))
        db.kv_set(f"duel_cd:{p['uid']}",db.now())
        for iid in set(i for i in kit[4:] if i):db.ex('UPDATE inventory SET dur=MAX(0,dur-3) WHERE uid=? AND iid=?',(p['uid'],iid))
    daykey=f"duel_xp:{winner['uid']}:{db.day_index()}"
    if db.integer(db.kv_get(daykey))<3:
        state.gain_xp(winner['uid'],20);db.kv_set(daykey,db.integer(db.kv_get(daykey))+1)
    db.kv_del(key)
    msg=f"🏆 برندهٔ نبرد: {texts.mention(winner['uid'],winner['name'])}.\nهیچ پول یا شهری ساخته نشد؛ تجربهٔ جایزه حداکثر سه بار در روز است."
    notifications.emit(msg,uids=[a['uid'],b['uid']])
    return msg


# ═══════════ جنگ ═══════════

def declare(leader_uid: int, target: str, mode: str = "total") -> str:
    return campaign.declare(leader_uid, target, mode)


def war_of(cid: str):
    return campaign.war_of(cid)


# ═══════════ مهمات — محدودیت مستقل هر کشور در هر جنگ ═══════════

def _ammo_key(w, cid: str) -> str:
    return f"ammo:{w['id']}:{cid}"


def _ammo_total(cid: str) -> int:
    return rules.AMMO_CAP


def _init_ammo(w):
    campaign.ensure_campaign(w)


def front(uid) -> str:
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    w=war_of(p['country'])
    if not w:return texts.hdr('جبهه','🗺')+'\n🕊 کشورت در جنگ نیست.'
    cp=campaign.ensure_campaign(w);mode=rules.MODES[cp['mode']];cid=p['country'];ecid=_enemy(cid,w)
    lines=[texts.hdr('جبههٔ جنگ','🗺'),
           f"{countries.COUNTRIES[cid]['name']} ↔ {countries.COUNTRIES[ecid]['name']} · {mode.label}",
           f"امتیاز: {w['score_a']} : {w['score_b']} · موج‌ها: {cp['rounds_a']} : {cp['rounds_b']}",
           f"آماده‌سازی: {max(0,(cp['ready_at']-db.now()+59)//60)} دقیقه باقی",
           f"حداقل نتیجه: {db.tehran_date(cp['min_end'])} · پایان مهلت: {db.tehran_date(w['ends'])} تهران",
           f"مهمات: {db.kv_get(_ammo_key(w,cid))}/{rules.AMMO_CAP}",
           '']
    for row in db.q('SELECT * FROM sieges WHERE war_id=? ORDER BY defender,city',(w['id'],)):
        name=geo.CITIES[row['defender']][row['city']]
        lines.append(f"🏙 {name}: فشار {row['pressure']}٪ · {row['rounds']} موج · "+('کنترل تثبیت‌شده' if row['captured_at'] else 'محاصره'))
    for c in (cid,ecid):
        st=infra.state_of(c)
        lines.append(f"{countries.COUNTRIES[c]['flag']} برق {st['power']}٪ · صنعت {st['industry']}٪ · فرودگاه {st['airport']}٪")
    ok,why=campaign.can_capitulate(ecid,cid)
    lines+=['',('🏳 '+why), 'تصرف: ۸ موج زمینی موفق + ۶ ساعت محاصره + برق ≤۵۵٪ + پادگان ≤۲۵٪ + پایگاه دشمن ≤۳۰٪.',
            'پایتخت اولین شهر زمینی نیست. بمباران به‌تنهایی شهر نمی‌گیرد.']
    return '\n'.join(lines)


def army(uid) -> str:
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];atk=guard=0
    for r in db.q('SELECT n.iid,n.qty,n.dur FROM inventory n JOIN users u ON u.uid=n.uid WHERE u.country=? AND n.qty>0',(cid,)):
        it=countries.ITEMS.get(r['iid'])
        if it:
            atk+=int(it[3]*r['qty']*r['dur']/100)
            guard+=int(it[4]*r['qty']*r['dur']/100)
    return '\n'.join([texts.hdr(f"ارتش {countries.COUNTRIES[cid]['name']}",'🪖'),
        f'توان کل تجهیزات: حمله {atk} · دفاع {guard}',
        f'ضریب پایهٔ کشور: {catalog.country_factor(cid):.3f}؛ تفاوت پایه محدود است.',
        f'پدافند تجهیزاتی: +{defense.equipment_bonus(cid):.1f} توان مؤثر',
        'محدودیت: یک جنگ هم‌زمان، حداکثر ۵ واحد هر موج، ۵ دقیقه فاصلهٔ فرمانده.',
        'هر موج به تعداد واقعی تجهیزات سالم نیاز دارد. تعمیر و تدارکات از منو.',
        'NPC وجود ندارد؛ تجهیزات پدافندی خودکار فقط ضربه را رهگیری می‌کنند.'])


def _enemy(cid: str, w) -> str:
    return w["b"] if w["a"] == cid else w["a"]


MISSILE_FLIGHT = 30  # ⏱ ثانیه — زمان پرواز موشک تا برخورد


def can_strike_kind(a: str, b: str, kind: str):
    return campaign.can_strike_kind(a,b,kind)


def _strike_precheck(uid, kind, count, target=None):
    # Compatibility only; production uses the atomic strike/launch entry points.
    raise RuntimeError("Use strike or launch_missile; do not split an atomic operation")


def _resolve_wave(uid, kind, ctx, title=None):
    raise RuntimeError("Use the persisted campaign resolver")


def strike(uid, kind, count=1, target=None, city=None):
    return campaign.strike(uid,kind,count,target,city)


def launch_missile(uid, count=1, target=None, city=None):
    return campaign.launch_missile(uid,count,target,city)


def resolve_missile(uid):
    return campaign.resolve_missile(uid)


def settle():
    return campaign.settle()


def world_status() -> str:
    lines=[texts.hdr('وضعیت جهان','🌍'),'کشور خالی منتظر انتخاب بازیکن است؛ حمله یا قرارداد با کشور خالی ممنوع.','']
    for cid,c in countries.COUNTRIES.items():
        players=db.q('SELECT uid,name,is_leader FROM users WHERE country=? ORDER BY uid',(cid,))
        who=' · '.join(texts.mention(r['uid'],r['name'])+(' 👑' if r['is_leader'] else '') for r in players) or '🕊 خالی'
        colonizer=geo.colony_of(cid)
        status=f" · تابع {countries.COUNTRIES[colonizer]['name']}" if colonizer in countries.COUNTRIES else ''
        lines.append(f"{c['flag']} {c['name']}: {who}{status}")
    lines+=['','⚔️ جنگ‌های فعال:']
    for w in db.q("SELECT * FROM wars WHERE status='active' ORDER BY id"):
        lines.append(f"{countries.COUNTRIES[w['a']]['name']} ↔ {countries.COUNTRIES[w['b']]['name']} · {w['score_a']}:{w['score_b']}")
    return '\n'.join(lines)


def colonies() -> str:
    """⛓ نقشه‌ی مستعمره‌های جهان."""
    import countries as _c
    t = texts
    rows = db.q("SELECT k, v FROM kv WHERE k LIKE 'colony:%' AND v != ''")
    if not rows:
        return t.hdr("مستعمره‌های جهان", "⛓") + "\n🕊 مستعمره‌ای نیست — " \
               "جنگ بگیر، همه‌ی شهرهای دشمن را تصرف کن!"
    groups = {}
    for r in rows:
        groups.setdefault(r["v"], []).append(r["k"].split(":")[1])
    lines = [t.hdr("مستعمره‌های جهان", "⛓"), ""]
    for by, cids in sorted(groups.items(), key=lambda x: -len(x[1])):
        b = _c.COUNTRIES.get(by)
        if not b:
            continue
        names = " · ".join(f"{_c.COUNTRIES[c]['flag']} {_c.COUNTRIES[c]['name']}"
                           for c in cids if c in _c.COUNTRIES)
        lines.append(f"👑 {b['flag']} {b['name']} ({t.fa(len(cids))}):\n   {names}")
    lines += ["", "💡 مستعمره: ۳۰٪ مالیات جیره‌ی مردمش · خراج برای اشغال‌گر",
              "🕊 آزادی: مستعمره در جنگ بعدی بر ضد اشغال‌گرش پیروز شود"]
    return "\n".join(lines)


def power_rank(top: int = 10) -> str:
    top=db.integer(top,10,1,50);rank=[]
    for r in db.q("SELECT DISTINCT country FROM users WHERE country IS NOT NULL AND country<>''"):
        cid=r['country']
        if cid not in countries.COUNTRIES:continue
        power=100*catalog.country_factor(cid)
        for eq in db.q('SELECT n.* FROM inventory n JOIN users u ON u.uid=n.uid WHERE u.country=? AND n.qty>0',(cid,)):
            it=countries.ITEMS.get(eq['iid'])
            if it:power+=(it[3]+it[4])*eq['qty']*eq['dur']/100/8
        power+=sum(defense.effective(cid,l) for l in defense.LAYERS)/6
        power*=max(0.5,infra.output_mult(cid))
        rank.append((round(power),cid))
    rank.sort(key=lambda r:(-r[0],r[1]))
    lines=[texts.hdr('قدرت کشورهای بازیکن‌دار','🥇')]
    for i,(power,cid) in enumerate(rank[:top],1):
        lines.append(f"{i}. {countries.COUNTRIES[cid]['flag']} {countries.COUNTRIES[cid]['name']}: {power} · {side_tags(cid)}")
    if not rank:lines.append('هنوز هیچ کشوری انتخاب نشده است.')
    return '\n'.join(lines)


def leaderboard() -> str:
    rows = db.q("SELECT * FROM users ORDER BY level DESC, kills DESC,uid")
    t = texts
    lines = [t.hdr("برترین فرماندهان", "🏆"), ""]
    for i, r in enumerate(rows, 1):
        c = countries.COUNTRIES.get(r["country"], {})
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{t.fa(i)}.")
        lines.append(f"{medal} {t.mention(r['uid'], r['name'] or 'سرباز')} — "
                     f"{c.get('flag', '')} سطح {t.fa(r['level'])} · ⚔️ {t.fa(r['kills'])}")
    return "\n".join(lines)


@db.atomic
def end_alliance(uid,target):
    p,err=campaign._leader(uid)
    if err:return err
    if target not in countries.COUNTRIES:return '⛔ کشور نامعتبر.'
    cid=p['country']
    if target not in allies_of(cid):return '✅ پیمانی وجود ندارد؛ زمان آتش‌بس تازه‌ای ایجاد نشد.'
    db.ex('DELETE FROM alliances WHERE (a=? AND b=?) OR (a=? AND b=?)',(cid,target,target,cid))
    db.kv_del(f'staging:{cid}:{target}');db.kv_del(f'staging:{target}:{cid}')
    pair=':'.join(sorted((cid,target)))
    db.kv_set(f'truce:{pair}',max(db.integer(db.kv_get(f'truce:{pair}')),db.now()+rules.TRUCE_TIME))
    msg=f"🤝 پیمان {countries.COUNTRIES[cid]['name']} و {countries.COUNTRIES[target]['name']} پایان یافت؛ مجوز پایگاه متقابل لغو و ۱۲ ساعت آتش‌بس برای جلوگیری از حملهٔ غافلگیرانه برقرار شد."
    notifications.emit(msg,cids=[cid,target],uids=[uid]);db.audit('alliance_ended',uid,target=target)
    return msg
