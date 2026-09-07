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
    from game import economy
    for iid in c["items"]:
        it = countries.ITEMS[iid]
        own = db.one("SELECT qty,dur FROM inventory WHERE uid=? AND iid=?", (uid, iid))
        price = economy.real_price(it[5])
        mark = (f"✅ {texts.fa(own['qty'])}× · دوام {texts.fa(own['dur'])}٪"
                if own else f"💰 {texts.fa(price)}")
        lines.append(f"{it[1]} <b>{it[0]}</b> — ⚔️{texts.fa(it[3])} "
                     f"🛡{texts.fa(it[4])} · {mark}")
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


def buy(uid, iid: str, qty: int = 1) -> str:
    """خرید ×۱ یا ×۵ — عمده ۱۰٪ تخفیف، سقف ۹ عدد از هر تجهیز."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    it = countries.ITEMS.get(iid)
    if not it or iid not in countries.COUNTRIES[p["country"]]["items"]:
        return "⛔ این تجهیز در زرادخانه‌ی کشورت نیست."
    qty = max(1, min(5, int(qty)))
    deal = iid in economy.daily_deals(p["country"])
    if qty >= 5:
        qty = 5
        cost = economy.real_price(it[5]) * 5 * 0.9     # عمده: ۱۰٪ تخفیف
    else:
        cost = economy.real_price(it[5])
    cost = int(cost)
    if deal:                                           # 🔥 تخفیف روزانه: ۲۰٪
        cost = economy.deal_price(cost)
    row = db.one("SELECT qty FROM inventory WHERE uid=? AND iid=?", (uid, iid))
    have = row["qty"] if row else 0
    if have + qty > MAX_QTY:
        return f"📦 سقف نگهداری {texts.fa(MAX_QTY)} عدد است — داری: {texts.fa(have)}"
    if p["money"] < cost:
        return (f"💰 پول کم داری — لازم: {texts.money(p['country'], cost)} · "
                f"داری: {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (cost, uid))
    db.ex("INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,?,100) "
          "ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+?", (uid, iid, qty, qty))
    from game import quests
    quests.on_event(uid, "خرید")
    t = texts
    return (f"🛒 <b>{it[0]}</b> {it[1]} ×{t.fa(qty)} خریداری شد — "
            f"موجودی: {t.fa(have + qty)} · دوام ۱۰۰٪\n"
            f"💰 باقی خزانه: {t.money(p['country'], p['money'] - cost)}")


def black_sample(uid) -> list:
    """نمونه‌ی ساعتی بازار سیاه — همین لیست در متن و دکمه‌ها."""
    p = state.active(uid)
    if not p:
        return []
    import random as _r
    _r.seed(db.now() // 3600 + uid)      # هر ساعت تغییر
    foreign = [iid for iid, it in countries.ITEMS.items()
               if it[2] != p["country"]]
    return _r.sample(foreign, k=min(8, len(foreign)))


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


def buy_black(uid, iid: str) -> str:
    from game import economy
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    it = countries.ITEMS.get(iid)
    if not it or it[2] == p["country"]:
        return "⛔ این تجهیز در بازار سیاه نیست (یا مال کشور خودت است — زرادخانه)"
    if db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid)):
        return "✅ از قبل داری."
    price = int(economy.real_price(it[5]) * 1.7)
    if p["money"] < price:
        return (f"💰 پول کم — لازم: {texts.money(p['country'], price)} · "
                f"داری: {texts.money(p['country'], p['money'])}")
    db.ex("UPDATE users SET money=money-? WHERE uid=?", (price, uid))
    db.ex("INSERT OR REPLACE INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100)", (uid, iid))
    return f"☠ {it[0]} {it[1]} قاچاق شد — دوام ۱۰۰٪"


def item_level(uid, iid: str) -> int:
    return int(db.kv_get(f"itlvl:{uid}:{iid}", "1"))


def _lvl_mult(uid, iid: str) -> int:
    """ضریب قدرت ارتقا — هر سطح +۲۵٪: سطح ۱=۱۰۰٪ · ۲=۱۲۵٪ · ۳=۱۵۰٪."""
    return 100 + 25 * (item_level(uid, iid) - 1)


def upgrade(uid, iid: str) -> str:
    """ارتقای تجهیز — ۳ سطح، هر سطح +۲۵٪ قدرت."""
    from game import economy
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    it = countries.ITEMS.get(iid)
    if not it or not db.one("SELECT 1 FROM inventory WHERE uid=? AND iid=?", (uid, iid)):
        return "⛔ این تجهیز را نداری."
    lvl = item_level(uid, iid)
    if lvl >= 3:
        return "⭐ تجهیز در حداکثر سطح (۳) است."
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


def repair(uid) -> str:
    """تعمیر همه‌ی تجهیزات خراب — هزینه‌ی واقعی."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    from game import economy
    rows = db.q("SELECT i.iid, i.dur FROM inventory i WHERE i.uid=? AND i.dur<100", (uid,))
    if not rows:
        return "🔧 همه‌ی تجهیزات سالم‌اند."
    total, fixed = 0, 0
    for r in rows:
        it = countries.ITEMS.get(r["iid"])
        if not it:
            continue
        # هزینه‌ی تعمیر متناسب با قیمت واقعی تجهیز
        cost = max(10, economy.real_price(it[5]) * (100 - r["dur"]) // 100)
        if p["money"] < total + cost:
            break
        total += cost
        fixed += 1
        db.ex("UPDATE inventory SET dur=100 WHERE uid=? AND iid=?", (uid, r["iid"]))
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
    """بهترین تجهیز تهاجمی + دفاعی بازیکن → (atk_item, def_item, atk, guard, a_iid, d_iid)."""
    rows = db.q("SELECT n.iid, n.dur FROM inventory n WHERE n.uid=? AND n.dur>10", (uid,))
    if not rows:
        return None, None, 0, 0, None, None
    best_a = max(rows, key=lambda r: countries.ITEMS[r["iid"]][3] * r["dur"] // 100
                 * _lvl_mult(uid, r["iid"]) // 100)
    best_d = max(rows, key=lambda r: countries.ITEMS[r["iid"]][4] * r["dur"] // 100
                 * _lvl_mult(uid, r["iid"]) // 100)
    a = countries.ITEMS[best_a["iid"]]
    d = countries.ITEMS[best_d["iid"]]
    return a, d, (a[3] * best_a["dur"] // 100) * _lvl_mult(uid, best_a["iid"]) // 100, \
        (d[4] * best_d["dur"] // 100) * _lvl_mult(uid, best_d["iid"]) // 100, \
        best_a["iid"], best_d["iid"]


# ═══════════ رزم ═══════════

ENEMIES = [("گروه شبه‌نظامی", 70, 12), ("گروه شناسایی دشمن", 105, 16),
           ("کاروان زرهی", 160, 23), ("پایگاه مرزی", 230, 30),
           ("نیروی ویژه دشمن", 320, 39), ("تکاوران گارد ویژه", 410, 48),
           ("لشکر مکانیزه", 530, 58), ("ستاد فرماندهی دشمن", 690, 69)]


def battle(uid, tier: int = None) -> str:
    """نبرد خودکار با گزارش کوتاه — تجهیزات واقعی دوام می‌بازند."""
    p = state.active(uid)
    if not p:
        return "⛔ اول «شروع»"
    if not p["branch"]:
        return "🪖 اول عضو شاخه شو — منو → عضویت نظامی"
    if db.now() - int(db.kv_get(f"battle:{uid}", "0")) < 20:
        return "⏳ ۲۰ ثانیه بین نبردها صبر کن."
    db.kv_set(f"battle:{uid}", str(db.now()))
    tier = tier if tier is not None else random.randint(0, min(4, p["level"]))
    name, ehp, eatk = ENEMIES[tier]
    a, d, atk, guard, a_iid, d_iid = loadout(uid)
    wpn = a[0] if a else "تفنگ سبک"
    # 🎖 تخصص کشور در رزم
    mspec, mpct, mname = countries.spec_of(p["country"])
    spec_mult = 1 + mpct / 200          # نصف اثر در رزم
    log = []
    turn = 0
    while turn < 14 and ehp > 0 and p["hp"] > 0:
        turn += 1
        dmg = max(4, int((atk + 10 + p["level"] * 3) * spec_mult
                         * random.uniform(0.7, 1.3)))
        crit = random.random() < 0.15   # 🎯 شلیک مرگبار
        if crit:
            dmg *= 2
        ehp -= dmg
        log.append(f"{'🎯 مرگبار! ' if crit else '⚔️ '}{wpn} → −{texts.fa(dmg)}")
        if ehp <= 0:
            break
        edmg = max(3, int(eatk * random.uniform(0.6, 1.1)) - guard // 2)
        db.ex("UPDATE users SET hp=MAX(0,hp-?) WHERE uid=?", (edmg, uid))
        p = state.active(uid)
        log.append(f"🩸 ضدحمله → −{texts.fa(edmg)}")
    # فرسایش دوام تجهیزات استفاده‌شده — سلاح و سپر، هر دو
    for iid in (a_iid, d_iid):
        if iid:
            db.ex("UPDATE inventory SET dur=MAX(0,dur-?) WHERE uid=? AND iid=?",
                  (random.randint(4, 10), uid, iid))
    t = texts
    if ehp <= 0:
        loot = (tier + 1) * 160
        xp = 60 + tier * 40
        db.ex("UPDATE users SET money=money+?, kills=kills+1, hp=MAX(20,hp) WHERE uid=?",
              (loot, uid))
        state.gain_xp(uid, xp)
        from game import quests
        quests.on_event(uid, "رزم")
        quests.on_event(uid, "پیروزی")
        return "\n".join([
            t.hdr("پیروزی در رزم", "🏆"),
            t.row("دشمن", name),
            t.row("تخصص", f"🎖 {mname}"), "",
            *log[:6], "",
            t.row("غنیمت", f"💰 {t.money(p['country'], loot)} · ⭐ {t.fa(xp)} XP"),
            t.row("جان", f"❤️ {p['hp']}/{p['max_hp']}")])
    db.ex("UPDATE users SET hp=MAX(10,hp) WHERE uid=?", (uid,))
    return "\n".join([
        t.hdr("عقب‌نشینی", "💨"),
        t.row("دشمن", name), "",
        *log[:6], "",
        "💨 جان کم آمد — از منو: 🏥 استراحت یا 🔧 تعمیر."])


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
