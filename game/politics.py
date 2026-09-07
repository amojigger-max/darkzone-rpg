"""🏛 جنگ جهانی — سیاست: حزب، بیانیه، شورش، رهبری، جاسوسی."""
import random

import db
import countries
import texts
from game import state

PARTY_COST = 1200           # متناسب اقتصاد ۱۰۰۰ (~۵ جیره)
REBEL_POWER = 150           # قدرت لازم برای شورش (بیانیه +۱۰ · عضو +۵)
SPY_COOLDOWN = 300


def my_party(uid) -> dict | None:
    p = db.one("SELECT party_id FROM users WHERE uid=?", (uid,))
    if not p or not p["party_id"]:
        return None
    r = db.one("SELECT * FROM parties WHERE id=?", (p["party_id"],))
    return dict(r) if r else None


@db.atomic
def found(uid, name: str, ideology: str) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if p["branch"] in (None, ""):
        return "🪖 ساخت حزب نیازمند عضویت نظامی است — «ارتشی»"
    if my_party(uid):
        return "🔒 قبلاً در حزبی هستی."
    if len(name) < 3 or len(name) > 28:
        return "⛔ نام حزب: ۳ تا ۲۸ حرف."
    if p["money"] < PARTY_COST:
        return (f"💰 تأسیس حزب {texts.money(p['country'], PARTY_COST)} می‌ارزد — "
                f"داری: {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (PARTY_COST, uid))
    db.ex("INSERT INTO parties(name,country,ideology,leader_uid,members,power,created) "
          "VALUES(?,?,?,?,1,10,?)", (texts.esc(name), p["country"],
                                     texts.esc(ideology or "ملی")[:24], uid, db.now()))
    pid = db.one("SELECT last_insert_rowid() id")["id"]
    db.ex("UPDATE users SET party_id=? WHERE uid=?", (pid, uid))
    return (f"🏛 حزب <b>{texts.esc(name)}</b> رسماً تأسیس شد!\n"
            f"ایدئولوژی: {texts.esc(ideology or 'ملی')}\n"
            f"عضوگیری: فهرست احزاب — مواضع: دکمه‌ی 📰 بیانیه (منو)")


def list_parties(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    rows = db.q("SELECT * FROM parties WHERE country=? ORDER BY power DESC LIMIT 10",
                (p["country"],))
    c = countries.COUNTRIES[p["country"]]
    lines = [texts.hdr(f"احزاب {c['name']}", "🏛"), ""]
    if not rows:
        lines.append("هنوز حزبی نیست — اولین حزب را تو بساز! ⬇️")
    for r in rows:
        lead = db.one("SELECT name FROM users WHERE uid=?", (r["leader_uid"],))
        tag = " 🔴 شورشی" if r["rebel"] else ""
        lines.append(f"▫️ <b>{r['name']}</b>{tag} — {r['ideology']}")
        lines.append(f"   👥 {r['members']} عضو · ⚡ قدرت {r['power']} · رهبر: {lead['name'] if lead else '—'}")
    lines.append("")
    lines.append("👥 عضویت با دکمه‌های زیر · ➕ حزب جدید هم همان‌جا")
    return "\n".join(lines)


@db.atomic
def join(uid,name):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    party=db.one('SELECT * FROM parties WHERE name=? AND country=?',(name,p['country']))
    if not party:return '⛔ حزب در همین کشور پیدا نشد.'
    if p['party_id']==party['id']:return '✅ از قبل عضو هستی.'
    old=my_party(uid)
    if old and old['leader_uid']==uid:return '👑 رهبر حزب نمی‌تواند با جابه‌جایی، اعضا یا قدرت ساختگی تولید کند.'
    if old:db.ex('UPDATE parties SET members=MAX(0,members-1),power=MAX(0,power-5) WHERE id=?',(old['id'],))
    db.ex('UPDATE users SET party_id=? WHERE uid=?',(party['id'],uid))
    db.ex('UPDATE parties SET members=members+1,power=power+5 WHERE id=?',(party['id'],))
    return f"🏛 به حزب {party['name']} پیوستی؛ شمارش اعضای حزب قبلی هم اصلاح شد."


@db.atomic
def statement(uid, body: str) -> str:
    """بیانیه‌ی رسمی حزب — ثبت دائمی + قدرت می‌دهد."""
    p = state.active(uid)
    party = my_party(uid)
    if not p or not party:
        return "⛔ بیانیه فقط برای اعضای حزب — اول حزب بساز یا عضو شو (منو → احزاب)."
    if not isinstance(body,str) or not 10<=len(body)<=800:
        return "⛔ متن بیانیه کوتاه است — حداقل ۱۰ حرف."
    if db.now()-db.integer(db.kv_get(f"statement:{uid}"))<600:return "⏳ هر ۱۰ دقیقه یک بیانیه."
    db.kv_set(f"statement:{uid}",db.now())
    t = texts
    db.ex("INSERT INTO statements(party_id,uid,body,ts) VALUES(?,?,?,?)",
          (party["id"], uid, texts.esc(body[:800]), db.now()))
    db.ex("UPDATE parties SET power=MIN(150,power+10) WHERE id=?", (party["id"],))
    return "\n".join([
        t.hdr("بیانیه‌ی رسمی", "📰"),
        f"🏛 حزب: <b>{party['name']}</b>",
        f"🗺 کشور: {countries.COUNTRIES[party['country']]['flag']} "
        f"{countries.COUNTRIES[party['country']]['name']}",
        t.K, f"«{texts.esc(body[:800])}»", t.K,
        "⚡ قدرت حزب +۱۰ — بیانیه‌ها در آرشیو کشور می‌مانند."])


def rebel(uid):
    return revolt_start(uid)


# ═══════════ جاسوسی ═══════════

@db.atomic
def spy(uid,target):
    from game import campaign,infra,notifications,quests
    p,err=campaign._leader(uid)
    if err:return err
    if target not in countries.COUNTRIES or target==p['country']:return '⛔ کشور هدف نامعتبر.'
    if not db.one('SELECT 1 FROM users WHERE country=? AND is_leader=1',(target,)):return '🕊 کشور خالی اطلاعات نظامی بازیکنی ندارد.'
    if db.now()-db.integer(db.kv_get(f'spy:{uid}'))<SPY_COOLDOWN:return '⏳ فاصلهٔ عملیات جاسوسی ۵ دقیقه است.'
    if not db.debit(uid,100):return '💰 هزینهٔ عملیات اطلاعاتی ۱۰۰ دلار است.'
    db.kv_set(f'spy:{uid}',db.now())
    db.ex('UPDATE users SET spy_ops=spy_ops+1 WHERE uid=?',(uid,))
    quests.on_event(uid,'جاسوسی')
    success=random.random()<0.55
    if success:
        st=infra.state_of(target)
        pending=db.one("SELECT COUNT(*) n FROM missions WHERE attacker=? AND status='pending'",(target,))['n']
        info=f"برق {st['power']}٪ · صنعت {st['industry']}٪ · مأموریت واقعاً در راه: {pending}"
        state.gain_xp(uid,30)
    else:
        info='گزارش قابل اتکایی به دست نیامد؛ هیچ برنامهٔ ساختگی برای دشمن تولید نشد.'
    db.ex('INSERT INTO spyops(uid,target,success,info,ts) VALUES(?,?,?,?,?)',(uid,target,int(success),info,db.now()))
    # Intel itself stays with the acting player; counterpart is notified of the operation only.
    notifications.emit(f"🕵 عملیات اطلاعاتی {countries.COUNTRIES[p['country']]['name']} دربارهٔ {countries.COUNTRIES[target]['name']} ثبت شد.",cids=[p['country'],target],uids=[uid])
    return ('🕵 گزارش معتبر بازی: ' if success else '🕵 عملیات ناموفق: ')+info


# ═══ 🔥 شورش — تغییر رژیم، آزادی از دست‌نشانده ═══

REVOLT_COST = 400
REVOLT_WINDOW = 48 * 3600

# رژیم‌های ممکن — اولی وضع موجود (خالی)؛ بعدی‌ها با شورش
REGIMES = {
    "ir": ["", "پهلوی", "جمهوری خلق"],
}
_GENERIC = ["", "حکومت مردمی", "دولت نظامی"]


def regime_of(cid) -> str:
    """🏷 رژیم فعلی کشور — خالی یعنی وضع موجود."""
    import db
    i = int(db.kv_get(f"regime_i:{cid}", "0") or 0)
    lst = REGIMES.get(cid, _GENERIC)
    return lst[i % len(lst)] if i else ""


def _revolt(cid) -> dict:
    import db
    d = db.jload(db.kv_get(f"revolt:{cid}"), None) or {}
    if d and db.now() - int(d.get("ts", 0)) > REVOLT_WINDOW:
        db.kv_del(f"revolt:{cid}")
        return {}
    return d


def revolt_view(uid) -> str:
    """🔥 وضعیت شورش کشور."""
    import db
    import texts
    from game import state, geo
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    c = __import__("countries").COUNTRIES[cid]
    t = texts
    rv = _revolt(cid)
    members = db.q("SELECT uid FROM users WHERE country=?", (cid,))
    need = max(1, (len(members) + 1) // 2)
    col = geo.colony_of(cid)
    lines = [t.hdr("شورش مردمی", "🔥"),
             f"🌍 کشور: {c['flag']} {c['name']}"
             + (f" ({regime_of(cid)})" if regime_of(cid) else ""),
             f"🏷 رژیم فعلی: {regime_of(cid) or 'وضع موجود'}"]
    if col:
        lines.append(f"⛓ زیر یوغ دست‌نشانده‌ی "
                     f"{__import__('countries').COUNTRIES[col]['name']} — "
                     "استقلال به بازپس‌گیری شهرها نیاز دارد.")
    if rv:
        sup = len(rv.get("sup", []))
        left = max(0, int(rv["ts"]) + REVOLT_WINDOW - db.now()) // 60
        lines += [t.DASH,
                  f"🔥 شورش فعال است! رهبر: {texts.mention(int(rv['by']), 'سرباز')}",
                  f"✊ حمایت: {t.fa(sup)}/{t.fa(need)}",
                  f"⏱ {t.fa(left)} دقیقه فرصت",
                  "", "دکمه‌ی «✊ حمایت» را بزن — نیمی از کشور کافی است!"]
    else:
        lines += [t.DASH,
                  f"💰 هزینه‌ی آغاز شورش: {t.money(cid, REVOLT_COST)}",
                  f"✊ لازم: حمایت {t.fa(need)} نفر از اعضای کشور",
                  "🏆 پیروزی = تغییر رژیم" + (" بدون انتقال خودکار شهرهای اشغال‌شده" if col else ""),
                  "", "هر شهروندی می‌تواند آغاز کند."]
    return "\n".join(lines)


@db.atomic
def revolt_start(uid) -> str:
    """🔥 آغاز شورش — هزینه دارد، ریسک دارد."""
    import json as _json
    import db
    import texts
    from game import state
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    cid = p["country"]
    if db.now()-db.integer(db.kv_get(f"revolt_cd:{cid}")) < 86400:
        return "⏳ شروع جنبش تازه هر ۲۴ ساعت یک بار."
    if _revolt(cid):
        return "🔥 شورش از قبل فعال است — همکاری کن!"
    if p["money"] < REVOLT_COST:
        return f"💰 آغاز شورش {texts.money(cid, REVOLT_COST)} می‌خواهد."
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (REVOLT_COST, uid))
    db.kv_set(f"revolt_cd:{cid}", db.now())
    db.kv_set(f"revolt:{cid}", _json.dumps(
        {"by": uid, "ts": db.now(), "sup": [uid]}, ensure_ascii=False))
    return revolt_view(uid) + "\n\n📣 شهروندان! بیایید!"


@db.atomic
def revolt_support(uid):
    from game import notifications,geo
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    cid=p['country'];rv=_revolt(cid)
    if not rv:return '🔥 شورشی فعال نیست.'
    members={r['uid'] for r in db.q('SELECT uid FROM users WHERE country=?',(cid,))}
    supporters=set(rv.get('sup',[])) & members
    supporters.add(uid)
    rv['sup']=sorted(supporters)
    import json
    db.kv_set(f'revolt:{cid}',json.dumps(rv))
    need=max(1,(len(members)+1)//2)
    if len(supporters)<need or db.now()-rv['ts']<6*3600:
        return revolt_view(uid)+'\n⏳ علاوه بر اکثریت واقعی، ۶ ساعت سازمان‌دهی لازم است.'
    db.kv_del(f'revolt:{cid}')
    i=db.integer(db.kv_get(f'regime_i:{cid}'));lst=REGIMES.get(cid,_GENERIC)
    ni=(i+1)%len(lst);db.kv_set(f'regime_i:{cid}',ni)
    msg=f"🏛 حکومت {countries.COUNTRIES[cid]['name']} با رأی بازیکنان و پس از سازمان‌دهی تغییر کرد: {lst[ni] or 'وضع موجود'}."
    if geo.colony_of(cid):msg+='\nاشغال نظامی هنوز برقرار است؛ تغییر حکومت جای بازپس‌گیری شهرها را نمی‌گیرد.'
    notifications.emit(msg,cids=[cid],uids=[uid])
    return msg
