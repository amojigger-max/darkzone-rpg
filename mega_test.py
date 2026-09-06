# -*- coding: utf-8 -*-
"""🧪 مگا-تست v21 — همه‌ی مسیرها: دستورها، دکمه‌ها، جریان‌های کامل، حالت‌های مرزی."""
import sys
sys.path.insert(0, ".")
import re
import asyncio
import db
db.init(":memory:")
import countries
countries.init_items()
import handlers
handlers.TEST_MODE = True
import config
from game import state as st, war, military, defense, ai, economy, politics, quests, geo, guide, events

PASS, FAIL = [], []


class U:
    def __init__(self, uid, name="N"):
        self.id, self.username, self.first_name = uid, "x", name


class Chat:
    def __init__(self):
        self.type, self.id = "supergroup", -100


class Msg:
    def __init__(self, text, uid):
        self.text, self.from_user, self.chat, self.message_id = text, U(uid), Chat(), 1
        self.out = ""
    async def answer(self, txt, **kw):
        self.out = txt
        return self
    async def answer_photo(self, *a, caption=None, **kw):
        self.out = caption or "PHOTO"
        return self
    async def edit_text(self, txt, **kw):
        self.out = txt
        return self
    async def edit_reply_markup(self, **kw):
        return self
    async def delete(self):
        return self


class CB:
    def __init__(self, uid, data):
        self.data, self.from_user, self.message = data, U(uid), Msg("", uid)
        self.answered = ""
    async def answer(self, txt=None, **kw):
        self.answered = txt or "ok"
        return True


def T(name, cond, detail=""):
    if cond:
        PASS.append(name)
    else:
        FAIL.append(f"{name} {('— ' + str(detail)[:160]) if detail else ''}")


async def cmd(text, uid):
    m = Msg(text, uid)
    await handlers.fa_words(m)
    return m.out


async def cb(uid, data):
    c = CB(uid, data)
    # مسیریابی مستقیم مثل ربات
    key = data.split(":")[0]
    fn = {"ad": handlers.cb_admin, "cyp": handlers.cb_cy_page, "cy": handlers.cb_country,
          "hp": handlers.cb_helppage, "df": handlers.cb_defense, "mn": handlers.cb_menu,
          "br": handlers.cb_branch, "wp": handlers.cb_buy, "wp5": handlers.cb_buy,
          "up": handlers.cb_upgrade, "spy": handlers.cb_spy, "ally": handlers.cb_ally,
          "st": handlers.cb_strike, "du": handlers.cb_duel, "dac": handlers.cb_duel_accept,
          "pac": handlers.cb_peace_accept, "aac": handlers.cb_ally_accept,
          "sur": handlers.cb_surrender, "sury": handlers.cb_surrender_yes,
          "dwr": handlers.cb_declare_war, "snc": handlers.cb_sanction,
          "str": handlers.cb_strait, "bb": handlers.cb_buy_black,
          "qc": handlers.cb_quest_claim, "pj": handlers.cb_party_join,
          "pnew": handlers.cb_party_new, "pcancel": handlers.cb_pcancel,
          "tp": handlers.cb_target_page}[key]
    try:
        await fn(c)
        return (c.message.out or "") + "|" + (c.answered or "")
    except Exception as e:
        return f"CRASH:{e}"


OWNER, P1, P2, P3, NOOB = config.OWNER_ID, 111, 222, 333, 999


async def main():
    # ═══ ۱. ثبت‌نام کامل هر ۲۱ کشور ═══
    uids = iter(range(1000, 1100))
    reg = {}
    for i, cid in enumerate(countries.COUNTRIES):
        uid = next(uids)
        out = await cb(uid, f"cy:{cid}")
        p = st.active(uid)
        T(f"ثبت‌نام {cid}", p and p["country"] == cid, out)
        reg[cid] = uid
    # ثبت‌نام دوباره → بلاک
    out = await cb(reg["ir"], "cy:us")
    T("ثبت‌نام دوباره بلاک", "قبلاً" in out, out)

    # ═══ ۲. جریان کامل یک بازیکن: شاخه → خرید → رزم ═══
    uid = reg["hz"]
    out = await cb(uid, "br:1")
    T("شاخه", "رضوان" in out or "پیوست" in out or out, out)
    p = st.get(uid)
    T("شاخه ذخیره", p["branch"] is not None)
    db.ex("UPDATE users SET money=99999 WHERE uid=?", (uid,))
    out = await cb(uid, "wp:fajr5")
    T("خرید فجر-۵", "خریداری" in out or "از قبل" in out or "🛒" in out, out)
    out = await cb(uid, "mn:battle")
    T("رزم (دکمه)", "پیروزی" in out or "عقب‌نشینی" in out or "شاخه" in out, out)
    out = await cb(uid, "mn:rest")
    T("استراحت (دکمه)", out and "CRASH" not in out, out)
    out = await cb(uid, "mn:repair")
    T("تعمیر (دکمه)", out and "CRASH" not in out, out)
    out = await cb(uid, "mn:ration")
    T("جیره (دکمه)", "جیره" in out, out)

    # ═══ ۳. همه‌ی کلیدهای منو (mn:) ═══
    mn_keys = ["main", "mil", "pol", "world", "me", "help", "battle", "rest", "arsenal",
               "repair", "ration", "branch", "parties", "rebel", "stmt", "spy", "ally",
               "war", "wstat", "lb", "market", "map", "cguide", "news", "front", "army",
               "def", "quest", "black", "duel", "peace", "helpally"]
    for k in mn_keys:
        out = await cb(uid, f"mn:{k}")
        T(f"mn:{k}", out and "CRASH" not in out, out)

    # ═══ ۴. صفحه‌بندی راهنما + کشورها ═══
    for pg in (1, 2, 3, 4):
        out = await cb(uid, f"hp:{pg}")
        T(f"hp:{pg}", f"{pg}/۴" in out or "راهنما" in out, out)
    for pg in (0, 1, 2):
        out = await cb(uid, f"cyp:{pg}")
        T(f"cyp:{pg}", "CRASH" not in out, out)

    # ═══ ۵. سپر ملی: هر ۶ لایه ═══
    for layer in defense.LAYERS:
        out = await cb(uid, f"df:{layer}")
        T(f"df:{layer}", "تقویت" in out or "پول" in out or "اوج" in out, out)

    # ═══ ۶. جنگ کامل: اعلام → ۵ نوع حمله → جبهه → صلح ═══
    db.ex("UPDATE users SET is_leader=1, money=999999, hp=100 WHERE uid=?", (uid,))
    # منوی جنگ در حال صلح → انتخاب کشور
    out = await cb(uid, "mn:war")
    T("منو جنگ (بی‌جنگ)", "در جنگ نیست" in out, out)
    out = await cb(uid, "dwr:il")
    T("اعلام جنگ (دکمه)", "اعلام جنگ" in out, out)
    for kind in ("موشکی", "هوایی", "دریایی", "زمینی", "پهپادی"):
        db.kv_set(f"strike:{uid}", "0")
        out = await cb(uid, f"st:{kind}:3")
        T(f"حمله {kind} (دکمه)", out and "CRASH" not in out, out)
    out = await cb(uid, "mn:front")
    T("جبهه (دکمه)", "امتیاز جبهه" in out, out)
    # اتحاد + کمک + صلح — همه دکمه‌ای
    other = reg["ir"]
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (other,))
    out = await cb(other, "ally:hz")
    T("پیشنهاد اتحاد (دکمه)", "اتحاد" in out and "ارسال شد" in out, out)
    out = await cb(uid, "aac:ir")
    T("قبول اتحاد (دکمه)", "اتحاد رسمی" in out, out)
    out = await cb(uid, "mn:helpally")
    T("کمک اتحاد", "اتحاد" in out or "جبهه" in out or "اتحادی" in out, out)
    out = await cb(uid, "mn:peace")
    T("درخواست صلح (دکمه)", "ارسال شد" in out, out)
    out = await cb(reg["il"], "pac:")
    T("قبول صلح (دکمه)", "پیمان صلح" in out or "درخواست صلحی" in out, out)

    # ═══ ۷. سیاست کامل ═══
    # حزب جدید: دکمه → pending → متن آزاد
    db.ex("UPDATE users SET money=999999 WHERE uid=?", (uid,))
    out = await cb(uid, "pnew:")
    T("حزب جدید (پرامپت)", "نام حزب" in out, out)
    out = await cmd("میهن‌دوستان | ملی", uid)
    T("تأسیس حزب (pending)", "تأسیس شد" in out, out)
    out = await cb(uid, "mn:parties")
    T("احزاب (دکمه)", "حزب" in out or "حزبی" in out, out)
    pid = db.one("SELECT id FROM parties WHERE name LIKE '%میهن%'")["id"]
    st.ensure(555, "هم‌کشور"); st.enlist(555, "hz", "هم‌کشور")
    db.ex("UPDATE users SET branch='sepah' WHERE uid=555")
    out = await cb(555, f"pj:{pid}")
    T("عضویت حزب (دکمه)", "پیوستی" in out, out)
    # بیانیه: دکمه → pending → متن آزاد
    out = await cb(uid, "mn:stmt")
    T("بیانیه (پرامپت)", "متن بیانیه" in out, out)
    out = await cmd("ما برای آبادی این سرزمین می‌جنگیم", uid)
    T("بیانیه (pending)", "بیانیه‌ی رسمی" in out, out)
    out = await cb(uid, "spy:il")
    T("جاسوسی دکمه", "جاسوسی" in out or (out and "CRASH" not in out), out)
    out = await cb(reg["us"], "mn:rebel")
    T("شورش (دکمه)", out and "CRASH" not in out, out)
    # لغو pending
    await cb(uid, "mn:stmt")
    out = await cmd("لغو", uid)
    T("لغو pending (متن)", "لغو شد" in out, out)
    await cb(uid, "mn:stmt")
    out = await cb(uid, "pcancel:")
    T("لغو pending (دکمه)", "لغو شد" in out, out)
    handlers.TEST_MODE = False
    m_silent = Msg("متن رهاشده", uid)
    await handlers.fa_words(m_silent)
    T("pending پاک شد", m_silent.out == "", m_silent.out)
    handlers.TEST_MODE = True

    # ═══ ۸. مأموریت + بازار سیاه + ارتقا + نبرد ═══
    out = await cb(uid, "mn:quest")
    T("مأموریت (دکمه)", "مأموریت" in out, out)
    out = await cb(uid, "qc:")
    T("دریافت جایزه (دکمه)", out and "CRASH" not in out, out)
    out = await cb(uid, "mn:black")
    T("بازار سیاه (دکمه)", "سیاه" in out and "دکمه" in out, out)
    sample = military.black_sample(uid)
    out = await cb(uid, f"bb:{sample[0]}")
    T("خرید قاچاق (دکمه)", out and "CRASH" not in out, out)
    out = await cb(uid, "up:fajr5")
    T("ارتقا دکمه", out and "CRASH" not in out, out)
    await cb(reg["ir"], "br:0")
    out = await cb(uid, "mn:duel")
    T("نبرد (پیکر حریف)", "حریفت" in out or "نبرد" in out, out)
    out = await cb(uid, f"du:{reg['ir']}")
    T("نبرد چالش (دکمه)", "چالش" in out, out)
    out = await cb(reg["ir"], "dac:")
    T("قبول نبرد (دکمه)", "نبرد" in out or "چالش" in out or "سرباز" in out, out)

    # ═══ ۹. پنل مالک ═══
    out = await cmd("مدیریت", OWNER)
    T("پنل مالک", "پنل مدیریت" in out, out)
    out = await cmd(f"ثبت {OWNER} ایران", OWNER)
    T("ثبت مالک", "ثبت شد" in out or "قبلاً" in out, out)
    out = await cmd(f"تغییر {OWNER} روسیه", OWNER)
    T("تغییر مالک", "روسیه" in out, out)
    for data in ("ad:stats", "ad:players"):
        out = await cb(OWNER, data)
        T(data, "CRASH" not in out, out)
    out = await cb(P3, "ad:stats")
    T("ad غیرمالک", "فقط مالک" in out, out)

    # ═══ ۱۰. حالت‌های مرزی ═══
    out = await cmd("منو", NOOB)
    T("تازه‌وارد منو", "کشورت را انتخاب کن" in out or "WELCOME" in out or "جنگ جهانی" in out, out)
    out = await cb(NOOB, "mn:battle")
    T("تازه‌وارد بلاک", "شروع" in out, out)
    out = await cb(NOOB, "wp:fajr5")
    T("خرید بدون ثبت‌نام بلاک", "شروع" in out, out)
    out = await cb(P3, "dwr:us")
    T("جنگ غیررهبر (دکمه)", "رهبر" in out, out)
    out = await cb(P3, "st:موشکی:1")
    T("حمله غیررهبر (دکمه)", "رهبر" in out, out)
    # بدون پول
    db.ex("UPDATE users SET money=0 WHERE uid=?", (reg["jp"],))
    out = await cb(reg["jp"], "wp:izumo")
    T("خرید بی‌پول", "پول کم" in out, out)
    # مهمات صفر
    db.ex("UPDATE users SET is_leader=1, money=999999 WHERE uid=?", (reg["kp"],))
    await cb(reg["kp"], "wp:hwasong")
    await cb(reg["kp"], "dwr:kr")
    wid = db.one("SELECT id FROM wars WHERE status='active' AND a='kp'")["id"]
    db.kv_set(f"ammo:{wid}:kp", "0")
    db.kv_set(f"strike:{reg['kp']}", "0")
    out = await cb(reg["kp"], "st:موشکی:1")
    T("مهمات صفر", "مهمات" in out, out)
    # کوول‌داون
    db.kv_set(f"ammo:{wid}:kp", "50")
    await cb(reg["kp"], "st:موشکی:1")          # موج اول می‌رود
    db.kv_set(f"ammo:{wid}:kp", "50")
    out = await cb(reg["kp"], "st:موشکی:1")     # بلافاصله → کوول‌داون
    T("کوول‌داون ۴۵ث", "۴۵" in out or "ثانیه" in out, out[:80])
    # جنگ دوم همزمان
    out = await cb(reg["kp"], "dwr:jp")
    T("جنگ دوم بلاک", "درگیر" in out, out)

    # ═══ ۱۱. جهان/راهنما/اخبار برای هر ۲۱ کشور ═══
    for cid in countries.COUNTRIES:
        g = guide.guide(cid)
        T(f"guide:{cid}", "تخصص" in g and "راهبرد" in g, g[:80])
    out = await cb(uid, "mn:cguide")
    T("راهنمای کشور (دکمه)", "راهنمای" in out, out)
    out = await cb(uid, "mn:power")
    T("قدرت کشورها (دکمه)", "قدرت نظامی" in out, out)
    out = await cb(uid, "mn:colonies")
    T("مستعمره‌ها (دکمه)", "مستعمره" in out, out)
    # تسلیم: تأیید دومرحله‌ای
    out = await cb(uid, "sur:")
    T("تسلیم (تأیید)", "مطمئنی" in out, out)
    out = await cb(uid, "sury:")
    T("تسلیم (نهایی)", out and "CRASH" not in out, out)
    # تحریم و تنگه — دکمه‌ای
    out = await cb(uid, "snc:")
    T("تحریم (پیکر)", "کدام کشور" in out, out)
    out = await cb(uid, "snc:il")
    T("تحریم (اجرا)", "تحریم" in out, out)
    out = await cb(uid, "str:")
    T("تنگه (پیکر)", "کدام تنگه" in out, out)
    out = await cb(uid, "str:هرمز")
    T("تنگه هرمز (اجرا)", "تنگه" in out, out)
    out = await cb(uid, "mn:power")
    T("mn:power", "قدرت نظامی" in out, out)
    out = war.world_status()
    T("جهان ۲۱ کشور", out.count("🤖") + out.count(":") >= 20, out[:100])
    for _ in range(30):
        ai.tick()
    T("اخبار AI", "اخبار" in ai.news_feed() or "خبر" in ai.news_feed())

    # ═══ ۱۲. اعداد فارسی در خروجی‌های کلیدی ═══
    for fn_out in (st.card(uid), war.front(uid), economy.market(), quests.view(uid),
                   defense.status("hz"), war.army(uid)):
        latin = re.findall(r"[0-9]", fn_out)
        T(f"فارسی: {fn_out.split(chr(10))[0][:24]}", not latin, latin)

    # ═══ ۱۳. دستورهای مرده = سکوت مطلق · زنده‌ها = پاسخ ═══
    handlers.TEST_MODE = False
    dead = ["پروفایل", "کارنامه", "کارت", "ارتشی", "سرباز", "تجهیزات", "زرادخانه",
            "خرید", "رزم", "جنگیدن", "استراحت", "درمان", "تعمیر", "جیره", "دستمزد",
            "احزاب", "عضویت x", "شورش", "جاسوسی", "جهان", "رتبه", "برترین", "نقشه",
            "بازار", "اقتصاد", "پدافند", "جبهه", "اخبار", "ارتش", "ماموریت",
            "مأموریت", "چالش", "جایزه", "بازارسیاه", "سیاه", "نبرد x", "صلح",
            "راهنما", "کمک", "تحریم", "تنگه", "قبول", "تسلیم", "بیانیه", "حزب",
            "جنگ آمریکا", "حمله موشکی", "خریدسیاه f35", "اتحاد روسیه"]
    leak = []
    for c in dead:
        m_d = Msg(c, uid)
        await handlers.fa_words(m_d)
        if m_d.out:
            leak.append(f"{c}→{str(m_d.out)[:30]}")
    T(f"دستورهای مرده ساکت ({len(dead)})", not leak, leak)
    alive = ["شروع", "منو", "تحویل", "اعزام", "رمزگشایی"]
    silent = []
    for c in alive:
        m_a = Msg(c, uid)
        await handlers.fa_words(m_a)
        if not m_a.out:
            silent.append(c)
    T("دستورهای زنده پاسخ‌گو", not silent, silent)
    m_chat = Msg("سلام بچه‌ها چی کار میکنید؟", uid)
    await handlers.fa_words(m_chat)
    T("گفتگوی عادی ساکت", m_chat.out == "", m_chat.out)
    handlers.TEST_MODE = True

    # ═══ v24.5: حساب‌وکتاب — نفت، تحریم، تعادل هزینه‌ها ═══
    from game import economy as _e
    T("سهم نفت ایران > ۰", _e.oil_share("ir") > 0, _e.oil_share("ir"))
    T("سهم نفت بدون‌بازیکن = ۰", _e.oil_share("kp") == 0)
    T("سهم نفت سقف ۲۰۰", _e.oil_share("sa") <= 200, _e.oil_share("sa"))
    # جیره با سهم نفت — بازیکن تازه در کشور نفت‌خیز
    st.ensure(558, "نفت"); st.enlist(558, "sa", "نفت")
    db.kv_set("ration:558", str(db.now() // 86400 - 1))
    out = st.ration(558)
    T("جیره سهم نفت دارد", "سهم نفت" in out, out[:80])
    # تحریم: یک سیستم واحد — نفت نصف، ارز ضعیف (ایزوله با قطر)
    db.kv_set("sanction:qa", "0")
    st.ensure(557, "قطر"); st.enlist(557, "qa", "قطر")
    db.ex("UPDATE users SET is_leader=1 WHERE uid=555")   # رهبر عربستان تحریم می‌کند
    share0 = _e.oil_share("qa")
    r_sanc = _e.sanction(555, "qa")
    T("تحریم قطر", "تحریم" in r_sanc and _e.sanctioned("qa") is True, r_sanc)
    share_qa = _e.oil_share("qa")
    T("تحریم نفت را نصف کرد", share_qa * 2 in (share0, share0 - 1, share0 + 1),
      f"{share0}→{share_qa}")
    fx_ir = _e.fx("ir")
    db.kv_set("sanction:ir", str(db.now()))
    T("تحریم ارز را ضعیف کرد", _e.fx("ir") > fx_ir * 1.15,
      f"{fx_ir:.0f}→{_e.fx('ir'):.0f}")
    db.kv_set("sanction:ir", "0")
    r_un = _e.sanction(555, "qa")
    T("برداشتن تحریم", "برداشته شد" in r_un and not _e.sanctioned("qa"), r_un)
    T("نفت برگشت", _e.oil_share("qa") == share0, f"{share_qa}→{share0}")
    db.ex("UPDATE users SET is_leader=0 WHERE uid=557")
    db.ex("UPDATE users SET is_leader=0 WHERE uid=555")
    # تعادل: حزب با ۱۲۰۰ قابل خرید
    from game import politics as _po
    T("حزب ۱۲۰۰", _po.PARTY_COST == 1200, _po.PARTY_COST)
    st.ensure(556, "حزب"); st.enlist(556, "ir", "حزب")
    db.ex("UPDATE users SET branch=0, money=1200 WHERE uid=556")
    r_party = _po.found(556, "حزب آزمون", "ملی")
    T("حزب با پول دقیق خریدنی", "تأسیس شد" in r_party, r_party)
    db.ex("UPDATE users SET money=5000 WHERE uid=556")
    # تعادل: تقویت سپر
    r_def = defense.strengthen(556, "ضد موشک")
    T("تقویت سپر ارزان‌تر", "تقویت شد" in r_def, r_def)
    db.ex("UPDATE users SET money=300 WHERE uid=556")
    r_def2 = defense.strengthen(556, "ضد موشک")
    T("تقویت گران‌تر از ۳۰۰", "پول کم" in r_def2, r_def2)

    # ═══ v24.4: صفحه‌بندی پیکر کشورها ═══
    for data in ("tp:spy:1", "tp:spy:2", "tp:ally:3", "tp:dwr:0", "tp:snc:4", "tp:spy:99"):
        out = await cb(uid, data)
        T(f"صفحه‌بندی {data}", "CRASH" not in out, out)
    kb_p = handlers.kb_targets(uid, "spy", 0)
    n_btns = sum(len(r) for r in kb_p.inline_keyboard)
    T("پیکر ≤۱۴ دکمه", n_btns <= 14, n_btns)   # ۱۰ کشور + ناوبری + منو

    # ═══ v24.3: ارتقا +۲۵٪ واقعی · جایزه‌ی رویداد صادق ═══
    from game import events as _ev
    T("جایزه‌ی تحویل = ۴۰۰", _ev.EVENTS[0][2] == 400, _ev.EVENTS[0][2])
    st.ensure(666, "ارتقا"); st.enlist(666, "hz", "ارتقا")
    db.ex("UPDATE users SET money=99999 WHERE uid=666")
    military.buy(666, "kornet", 1)
    _, _, atk1, _, _, _ = military.loadout(666)
    up1 = military.upgrade(666, "kornet")
    T("ارتقا سطح ۲", "سطح جدید" in up1 and "۲" in up1, up1)
    _, _, atk2, _, _, _ = military.loadout(666)
    T("ارتقا +۲۵٪ واقعی", atk2 == atk1 * 5 // 4, f"{atk1}→{atk2}")
    up2 = military.upgrade(666, "kornet")
    _, _, atk3, _, _, _ = military.loadout(666)
    T("ارتقا سطح ۳ +۵۰٪", atk3 == atk1 * 3 // 2, f"{atk1}→{atk3}")
    up3 = military.upgrade(666, "kornet")
    T("سقف ارتقا ۳", "حداکثر" in up3, up3)
    # تعمیر قیمت‌محور: خراب کن → تعمیر → گزارش
    db.ex("UPDATE inventory SET dur=40 WHERE uid=666 AND iid='kornet'")
    rep = military.repair(666)
    T("تعمیر گزارش‌دار", "تعمیرشده" in rep and "هزینه" in rep, rep)
    T("تعمیر دوام ۱۰۰", db.one("SELECT dur FROM inventory WHERE uid=666 "
                               "AND iid='kornet'")["dur"] == 100)

    # ═══ v24.1: خرید ×۵ + سقف + فیلتر دستور + AI رهبر ═══
    import countries as _co
    st.ensure(777, "تست"); st.enlist(777, "hz", "تست")
    db.ex("UPDATE users SET money=99999, is_leader=0 WHERE uid=777")
    r1 = military.buy(777, "kornet", 1)
    r5 = military.buy(777, "kornet", 5)
    T("خرید ×۱", "خریداری" in r1, r1)
    T("خرید ×۵ تخفیف", "×۵" in r5, r5)
    q = db.one("SELECT qty FROM inventory WHERE uid=777 AND iid='kornet'")["qty"]
    T("موجودی ۶", q == 6, q)
    r9 = military.buy(777, "kornet", 5)
    T("سقف ۹", "سقف" in r9, r9)
    m0 = st.get(777)
    price5 = int(economy.real_price(_co.ITEMS['kornet'][5]) * 5 * 0.9)
    p1 = int(economy.real_price(_co.ITEMS['kornet'][5]))
    T("هزینه ×۵ درست", m0["money"] == 99999 - p1 - price5, m0["money"])
    # پول شروع ۱۰۰۰
    st.ensure(888, "نو"); st.enlist(888, "ir", "نو")
    T("پول شروع ۱۰۰۰", st.get(888)["money"] == 1000, st.get(888)["money"])
    # فیلتر دستورها در حالت واقعی
    handlers.TEST_MODE = False
    class M2:
        def __init__(s2, tx, u2):
            s2.text, s2.from_user, s2.chat, s2.message_id = tx, U(u2), Chat(), 1
            s2.out = ""
        async def answer(s2, txt=None, **kw):
            s2.out = txt; return s2
    mm = M2("رزم", 777)
    r = await handlers.fa_words(mm)
    T("دستور حذف‌شده بی‌پاسخ", r is None, r)
    mm2 = M2("سلام بچه‌ها", 777)
    r2 = await handlers.fa_words(mm2)
    T("گفتگوی عادی ساکت", r2 is None, r2)
    mm3 = M2("منو", 777)
    await handlers.fa_words(mm3)
    T("منو زنده", mm3.out and "پرونده" in mm3.out, mm3.out)
    mm4 = M2("تحویل", 777)
    await handlers.fa_words(mm4)
    T("رویداد زنده", mm4.out is not None and mm4.out != "", getattr(mm4, "out", ""))
    handlers.TEST_MODE = True
    # AI: کشور رهبر‌دار جنگ NPC نمی‌گیرد
    from game import ai as _ai
    db.ex("UPDATE users SET is_leader=1 WHERE uid=777")
    T("AI رهبر-دار", _ai._has_leader("hz") is True)
    db.ex("UPDATE wars SET status='done'")
    for _ in range(30):
        _ai.tick()
    got_war = db.one("SELECT 1 FROM wars WHERE status='active' AND (a='hz' OR b='hz')")
    T("NPC به رهبر‌دار جنگ نمی‌دهد", not got_war, "hz جنگ گرفت!")
    print(f"\n{'═' * 20} نتیجه {'═' * 20}")
    print(f"✅ موفق: {len(PASS)}")
    if FAIL:
        print(f"❌ خراب: {len(FAIL)}")
        for f in FAIL:
            print("  •", f)
        sys.exit(1)
    print("🎯 مگا-تست کامل سبز — صفر خطا")


asyncio.run(main())
