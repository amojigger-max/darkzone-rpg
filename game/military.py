"""🪖 جنگ جهانی — نظامی: شاخه‌ها، تجهیزات، تعمیر، رزم."""
import random

import db
import countries
import texts
from game import economy, state


def branch_name(p) -> str:
    c = countries.COUNTRIES.get(p["country"])
    if not c or p["branch"] in (None, ""):
        return ""
    b = p["branch"]
    if isinstance(b, int) or (isinstance(b, str) and b.isdigit()):
        try:
            return c["branches"][int(b)]
        except Exception:
            return ""
    return b if b in c["branches"] else ""


@db.atomic
def join_branch(uid, idx: int) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if p["branch"]:
        return "🔒 قبلاً عضو شده‌ای."
    c = countries.COUNTRIES[p["country"]]
    if idx < 0 or idx >= len(c["branches"]):
        return "⛔ شاخه نامعتبر."
    db.ex("UPDATE users SET branch=? WHERE uid=?", (idx, uid))
    t = texts
    k, rname, reff = role_of(state.active(uid))
    role_line = f"\n🎖 نقش: <b>{rname}</b> — {reff}" if k else ""
    return "\n".join([
        t.hdr("عضویت نظامی", "🪖"),
        t.row("شاخه", c["branches"][idx]),
        t.row("کشور", f"{c['flag']} {c['name']}"),
        role_line,
        "", "اکنون سرباز این شاخه‌ای — درجه با رزم بالا می‌رود.",
        "🛒 گام بعد: تجهیزات بخر و رزم کن — از «منو»"])


# ═══ 🎖 نقش شاخه‌ها — هر شاخه یک اثر واقعی و دقیق ═══

BRANCH_ROLE_DEFS = {
    "atk":  ("🗡 خط مقدم", "+۱۵٪ قدرت همه‌ی ضربت‌های تو در جنگ"),
    "miss": ("🚀 موشکی‌انداز", "+۱۰٪ قدرت ضربت موشکی"),
    "air":  ("✈️ خلبان", "+۱۰٪ قدرت ضربت هوایی و پهپادی"),
    "sea":  ("🚢 ناوگان", "+۱۰٪ قدرت ضربت دریایی"),
    "grd":  ("🚜 زرهی", "+۱۰٪ قدرت ضربت زمینی"),
    "def":  ("🛡 سپر وطن", "کشورت به‌ازای هر عضو ۵٪ کمتر آسیب می‌بیند (تا ۱۵٪)"),
    "eco":  ("⚙️ لجستیک", "+۱۰٪ درآمد شیفت کاری و جیره‌ی تو"),
}

# نام شاخه → نقش تخصصی همان حوزه؛ بدون تطبیق، نقش جایگاهی
_NAME_RULES = (
    ("موشکی", "miss"), ("هوایی", "air"), ("پرواز", "air"), ("هواپیمایی", "air"),
    ("دریایی", "sea"), ("ناو", "sea"), ("نگ ", "sea"), ("نگ‌", "sea"),
    ("زرهی", "grd"), ("تانک", "grd"), ("پدافند", "def"), ("پدафند", "def"),
    ("مارینز", "atk"), ("دلتا", "atk"), ("اسپتس", "atk"), ("واگنر", "atk"),
    ("کماندو", "atk"), ("تکاور", "atk"), ("چتر", "atk"), ("ویژه", "atk"),
)
_DEFAULT_BY_IDX = ("atk", "def", "eco")


def role_of(p) -> tuple:
    """🎖 نقش شاخه‌ی بازیکن — (کلید، نام، متن اثر)؛ دقیق و همیشه معتبر."""
    if not p or p["branch"] in (None, ""):
        return ("", "", "")
    nm = branch_name(p)
    for word, key in _NAME_RULES:
        if word in nm:
            k = key
            break
    else:
        idx = int(p["branch"]) if str(p["branch"]).isdigit() else 0
        k = _DEFAULT_BY_IDX[idx % len(_DEFAULT_BY_IDX)]
    name, eff = BRANCH_ROLE_DEFS[k]
    return (k, name, eff)


def atk_mult(p, kind: str):
    """⚔️ ضریب ضربتهای بازیکن از نقش شاخه — (ضریب، نشانه)."""
    k, name, _ = role_of(p)
    if not k:
        return 1.0, ""
    if k == "atk":
        return 1.15, f" {name}"
    if kind == "پهپادی" and k == "air":
        return 1.10, f" {name}"
    pairs = {"miss": "موشکی", "air": "هوایی", "sea": "دریایی", "grd": "زمینی"}
    if pairs.get(k) == kind:
        return 1.10, f" {name}"
    return 1.0, ""


def def_mult(cid: str) -> float:
    """🛡 سپر کشور — هر عضو «سپر وطن» ۵٪ آسیب کمتر، سقف ۱۵٪."""
    n = 0
    for r in db.q("SELECT branch FROM users WHERE country=? AND branch IS NOT NULL",
                  (cid,)):
        p = {"branch": r["branch"], "country": cid}
        if role_of(p)[0] == "def":
            n += 1
    return 1 - min(0.15, 0.05 * n)


def eco_mult(uid) -> float:
    """⚙️ لجستیک — ۱۰٪ درآمد بیشتر از کار و جیره."""
    p = state.active(uid)
    return 1.10 if p and role_of(p)[0] == "eco" else 1.0


# ═══════════ تجهیزات ═══════════

def arsenal(uid) -> str:
    """زرادخانه‌ی مخصوص کشور بازیکن."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    c = countries.COUNTRIES[p["country"]]
    sp = countries.spec_of(p["country"])
    lines = [texts.hdr(f"زرادخانه {c['name']}", "🛒"),
             f"🎖 تخصص کشور: {sp[2]} — +{texts.fa(sp[1])}٪ در حمله‌ی {sp[0]}",
             f"💰 خزانه: {texts.money(p['country'], p['money'])}", ""]
    from game import economy,catalog
    for iid in c["items"]:
        it = countries.ITEMS[iid]
        own = db.one("SELECT qty,dur FROM inventory WHERE uid=? AND iid=?", (uid, iid))
        price = economy.real_price(it[5])
        mark = (f"✅ {texts.fa(own['qty'])}× · دوام {texts.fa(own['dur'])}٪"
                if own else f"💰 {texts.fa(price)}")
        lines.append(f"{it[1]} <b>{it[0]}</b> — ⚔️{texts.fa(it[3])} "
                     f"🛡{texts.fa(it[4])} · {mark}" + (" · برد راهبردی" if catalog.range_band(iid)==3 else " · برد منطقه‌ای") if catalog.primary(iid) in ("هوایی","پهپادی","موشکی") else f"{it[1]} <b>{it[0]}</b> — ⚔️{texts.fa(it[3])} 🛡{texts.fa(it[4])} · {mark}")
    deals = economy.daily_deals(p["country"])
    if deals:
        lines += ["", "🔥 <b>پیشنهاد ویژه‌ی امروز — ۲۰٪ تخفیف</b> (فقط امروز):"]
        for diid in deals:
            it2 = countries.ITEMS[diid]
            dp = economy.deal_price(economy.real_price(it2[5]))
            lines.append(f"   {it2[1]} {it2[0]} — 💰 {texts.fa(dp)} دلار")
    lines += ["", "🛒 خرید با دکمه‌های زیر — ×۱ یا ×۵ (سقف ۹ عدد)"]
    return "\n".join(lines)


MAX_QTY = 9


@db.atomic
def buy(uid, iid: str, qty: int = 1) -> str:
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if type(qty) is not int or not 1<=qty<=5:return '⛔ تعداد باید عدد صحیح ۱ تا ۵ باشد.'
    it=countries.ITEMS.get(iid)
    if not it or iid not in countries.COUNTRIES[p['country']]['items']:return '⛔ تجهیز در زرادخانهٔ کشورت نیست.'
    from game import infra,quests
    if not infra.power_ok(p['country']) and it[5]>=3000:return '⚡ برق کشور ضعیف است؛ خرید سنگین ممکن نیست.'
    row=db.one('SELECT qty,dur FROM inventory WHERE uid=? AND iid=?',(uid,iid))
    have=row['qty'] if row else 0
    if have+qty>MAX_QTY:return f'📦 سقف هر تجهیز {MAX_QTY} عدد است.'
    cost=it[5]*qty
    if qty==5:cost=cost*90//100
    if iid in economy.daily_deals(p['country']):cost=economy.deal_price(cost)
    if not db.debit(uid,cost):return f'💰 پول کم است؛ لازم: {texts.money(p["country"],cost)}'
    dur=(have*(row['dur'] if row else 100)+qty*100)//(have+qty)
    db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qty=excluded.qty,dur=excluded.dur',(uid,iid,have+qty,dur))
    quests.on_event(uid,'خرید')
    db.audit('equipment_purchase',uid,item=iid,qty=qty,cost=cost)
    return f'🛒 {it[1]} {it[0]} ×{qty} خریداری شد؛ موجودی {have+qty}، سلامت میانگین {dur}٪.\n💰 هزینه: {texts.money(p["country"],cost)}'


def black_sample(uid) -> list:
    p=state.active(uid)
    if not p:return []
    rng=random.Random(f'{db.GAME.get()}:{db.now()//3600}:{uid}')
    foreign=[iid for iid,it in countries.ITEMS.items() if it[2]!=p['country']]
    return rng.sample(foreign,k=min(8,len(foreign)))


def blackmarket(uid) -> str:
    """بازار سیاه — تجهیزات کشورهای دیگر با قیمت ۱.۷ برابر."""
    from game import economy
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    lines = [texts.hdr("بازار سیاه", "☠"), "قیمت ×۱.۷ — قاچاق است، رسمی نیست!", ""]
    for iid in black_sample(uid):
        it = countries.ITEMS[iid]
        price = int(economy.real_price(it[5]) * 1.7)
        c = countries.COUNTRIES[it[2]]
        own = db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid))
        mark = "✅ از قبل داری" if own else f"💰 {texts.money(p['country'], price)}"
        lines.append(f"{it[1]} {it[0]} ({c['flag']}) — {mark}")
    lines += ["", "🛒 خرید با دکمه‌های زیر — هر ساعت لیست عوض می‌شود."]
    return "\n".join(lines)


@db.atomic
def buy_black(uid,iid):
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if iid not in black_sample(uid):return '⏳ این تجهیز در عرضهٔ همین ساعت نیست؛ منو را تازه کن.'
    if db.one('SELECT 1 FROM inventory WHERE uid=? AND iid=? AND qty>0',(uid,iid)):return '✅ از قبل داری.'
    it=countries.ITEMS[iid]
    from game import infra
    if not infra.power_ok(p['country']) and it[5]>=3000:return '⚡ بازار سیاه هم محدودیت برق تجهیزات سنگین را دور نمی‌زند.'
    cost=it[5]*17//10
    if not db.debit(uid,cost):return f'💰 پول کافی نیست؛ {texts.money(p["country"],cost)} لازم است.'
    db.ex('INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100) ON CONFLICT(uid,iid) DO UPDATE SET qty=1,dur=100',(uid,iid))
    db.audit('black_market_purchase',uid,item=iid,cost=cost)
    return f'☠ {it[0]} خریداری شد؛ سلامت ۱۰۰٪.'


def item_level(uid, iid: str) -> int:
    return int(db.kv_get(f"itlvl:{uid}:{iid}", "1"))


def _lvl_mult(uid, iid: str) -> int:
    """ضریب قدرت ارتقا — هر سطح +۲۵٪: سطح ۱=۱۰۰٪ · ۲=۱۲۵٪ · ۳=۱۵۰٪."""
    return 100 + 25 * (item_level(uid, iid) - 1)


@db.atomic
def upgrade(uid, iid: str) -> str:
    """ارتقای تجهیز — ۳ سطح، هر سطح +۲۵٪ قدرت."""
    from game import economy
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    it = countries.ITEMS.get(iid)
    if not it or not db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid)):
        return "⛔ این تجهیز را نداری."
    from game import fleet
    if fleet.escort_locked(uid,iid):return '⚓ بخشی از این تجهیز در اسکورت دریایی است؛ ارتقا بعد از بازگشت.'
    lvl = item_level(uid, iid)
    if lvl >= 3:
        return "⭐ تجهیز در حداکثر سطح (۳) است."
    # Shared technology for this item type, including later-produced units.
    cost = int(economy.real_price(it[5]) * 0.6 * lvl)
    if p["money"] < cost:
        return (f"💰 ارتقا {texts.money(p['country'], cost)} می‌ارزد — "
                f"داری: {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (cost, uid))
    db.kv_set(f"itlvl:{uid}:{iid}", str(lvl + 1))
    t = texts
    return "\n".join([
        t.hdr("ارتقای تجهیز", "⬆️"),
        t.row("تجهیز", f"{it[1]} {it[0]}"),
        t.row("سطح جدید", f"{t.fa(lvl + 1)} از ۳"),
        t.row("قدرت", f"+{t.fa(25 * lvl)}٪"),
        t.row("هزینه", f"💰 {t.money(p['country'], cost)}")])


@db.atomic
def repair(uid) -> str:
    """تعمیر همه‌ی تجهیزات خراب — هزینه‌ی واقعی."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    from game import economy
    rows = db.q("SELECT i.iid, i.dur, i.qty FROM inventory i WHERE i.uid=? AND i.dur<100", (uid,))
    if not rows:
        return "🔧 همه‌ی تجهیزات سالم‌اند."
    total, fixed, locked = 0, 0, 0
    for r in rows:
        from game import fleet
        if fleet.escort_locked(uid,r["iid"]):
            locked+=1;continue
        it = countries.ITEMS.get(r["iid"])
        if not it:
            continue
        # هزینه‌ی تعمیر متناسب با قیمت واقعی تجهیز
        cost = max(10, economy.real_price(it[5]) * r["qty"] * (100 - r["dur"]) // 100)
        if p["money"] < total + cost:
            break
        total += cost
        fixed += 1
        db.ex("UPDATE inventory SET dur=100 WHERE uid=? AND iid=?", (uid, r["iid"]))
    if total == 0 and locked==len(rows):return "⚓ تجهیزات خراب در اسکورت هستند؛ پس از بازگشت تعمیر کن."
    if total == 0:
        return "💰 پول تعمیر کافی نیست — جیره‌ی روزانه‌ات را بگیر (منو)."
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (total, uid))
    t = texts
    return "\n".join([
        t.hdr("تعمیرگاه", "🔧"),
        t.row("تجهیزات تعمیرشده", fixed),
        t.row("هزینه", f"💰 {t.money(p['country'], total)}"),
        "", "✅ همه‌ی آن‌ها با دوام ۱۰۰٪ برگشتند."])


def loadout(uid):
    from game import fleet
    rows=[r for r in db.q('SELECT iid,dur,qty FROM inventory WHERE uid=? AND qty>0 AND dur>10',(uid,)) if r['iid'] in countries.ITEMS and r['qty']>fleet.escort_locked(uid,r['iid'])]
    if not rows:return None,None,0,0,None,None
    a=max(rows,key=lambda r:countries.ITEMS[r['iid']][3]*r['dur']*_lvl_mult(uid,r['iid']))
    d=max(rows,key=lambda r:countries.ITEMS[r['iid']][4]*r['dur']*_lvl_mult(uid,r['iid']))
    ai,di=countries.ITEMS[a['iid']],countries.ITEMS[d['iid']]
    return ai,di,int(ai[3]*a['dur']/100*_lvl_mult(uid,a['iid'])/100),int(di[4]*d['dur']/100*_lvl_mult(uid,d['iid'])/100),a['iid'],d['iid']


# ═══════════ رزم ═══════════


@db.atomic
def battle(uid,tier=None):
    """Retained combat button becomes a drill; no NPC opponent or fictional loot."""
    p=state.active(uid)
    if not p:return '⛔ اول «شروع»'
    if p['branch'] in (None,''):return '🪖 ابتدا عضو شاخهٔ نظامی شو.'
    if tier is not None and (type(tier) is not int or not 0<=tier<=7):return '⛔ تمرین نامعتبر.'
    if db.now()-db.integer(db.kv_get(f'drill:{uid}'))<3600:return '⏳ هر ساعت یک تمرین سازمانی.'
    a,d,atk,guard,ai,di=loadout(uid)
    if not ai:return '🛒 دست‌کم یک تجهیز سالم لازم است.'
    db.kv_set(f'drill:{uid}',db.now())
    for iid in set(i for i in (ai,di) if i):db.ex('UPDATE inventory SET dur=MAX(0,dur-2) WHERE uid=? AND iid=?',(uid,iid))
    state.gain_xp(uid,25)
    from game import quests
    quests.on_event(uid,'تمرین')
    return '🎯 تمرین سازمانی کامل شد: ۲۵ تجربه؛ بدون پول، کشتار یا دشمن NPC.\nبرای نبرد واقعی، جنگ یا چالش یک بازیکن را انتخاب کن.'


@db.atomic
def rest(uid) -> str:
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if db.now() - int(db.kv_get(f"rest:{uid}", "0")) < 120:
        return "⏳ استراحت داده شد — ۲ دقیقه صبر کن."
    cost = 100                                   # سخت‌تر — درمان دیگر رایگان نیست
    if p["money"] < cost:
        return f"💰 درمان {texts.money(p['country'], cost)} می‌ارزد — جیره بگیر یا بجنگ."
    db.kv_set(f"rest:{uid}", str(db.now()))
    db.ex("UPDATE users SET hp=max_hp, money=money-? WHERE uid=?", (cost, uid))
    return (f"🏥 جان کامل شد: ❤️ {texts.fa(p['max_hp'])}/{texts.fa(p['max_hp'])}\n"
            f"هزینه: {texts.money(p['country'], cost)}")


@db.atomic
def retire_offer(uid,iid,qty=1):
    """Optional disposal of personal equipment, with a scoped single-use confirmation."""
    import secrets,json
    from game import fleet
    p=state.active(uid)
    if not p:return '⛔ ابتدا کشور انتخاب کن.',None
    if iid not in countries.ITEMS or type(qty) is not int or not 1<=qty<=9:return '⛔ تجهیز یا تعداد نامعتبر.',None
    inv=db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))
    if not inv or inv['qty']-fleet.escort_locked(uid,iid)<qty:return '⚓ تجهیز آزاد کافی نیست؛ اسکورتِ در سفر قابل حذف نیست.',None
    nonce=secrets.token_hex(6)
    db.kv_set(f'retire:{uid}',json.dumps({'nonce':nonce,'iid':iid,'qty':qty,'country':p['country'],'expires':db.now()+300}))
    return f'⚠️ تأیید حذف از زرادخانه: {countries.ITEMS[iid][0]} ×{qty}\nاین کار پولی نمی‌دهد و تجهیز حذف‌شده بازنمی‌گردد؛ فقط برای آزادکردن جاست.\nتأیید تا پنج دقیقه و فقط یک بار معتبر است.',nonce


@db.atomic
def retire_confirm(uid,nonce):
    from game import fleet
    p=state.active(uid);key=f'retire:{uid}';pending=db.jload(db.kv_get(key),{}) or {}
    if not p or not isinstance(nonce,str) or pending.get('nonce')!=nonce or pending.get('expires',0)<db.now() or pending.get('country')!=p['country']:
        return '⛔ تأیید حذف نامعتبر، منقضی یا قبلاً استفاده شده است؛ چیزی حذف نشد.'
    iid=pending['iid'];qty=pending['qty']
    inv=db.one('SELECT qty FROM inventory WHERE uid=? AND iid=?',(uid,iid))
    if not inv or inv['qty']-fleet.escort_locked(uid,iid)<qty:return '⚓ موجودی آزاد تغییر کرده است؛ چیزی حذف نشد.'
    db.ex('UPDATE inventory SET qty=qty-? WHERE uid=? AND iid=?',(qty,uid,iid))
    db.kv_del(key);db.audit('equipment_retired',uid,item=iid,qty=qty)
    return f'🗑 {countries.ITEMS[iid][0]} ×{qty} با تأیید خودت حذف شد. پولی پرداخت نشد؛ اکنون می‌توانی هدیهٔ ذخیره‌شده را دریافت کنی.'
