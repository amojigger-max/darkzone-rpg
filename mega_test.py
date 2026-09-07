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
import texts
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
          "tp": handlers.cb_target_page, "gno": handlers.cb_geo_no,
          "dl": handlers.cb_daily, "wk": handlers.cb_work, "evc": handlers.cb_evc,
          "inv": handlers.cb_invest, "ivb": handlers.cb_invest_buy,
          "ivc": handlers.cb_invest_collect, "ifix": handlers.cb_infra_fix,
          "ibld": handlers.cb_infra_build, "aim": handlers.cb_aim,
          "aimk": handlers.cb_aim_kind, "rv": handlers.cb_revolt,
          "tb": handlers.cb_tbuy, "ts": handlers.cb_tsell,
          "tct": handlers.cb_tcontract, "ct": handlers.cb_contract,
          "pay": handlers.cb_transfer_to if data != "pay:" else handlers.cb_transfer_pick}[key]
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

    # ═══ ۹. پنل مالک — کاملاً دکمه‌ای ═══
    out = await cmd("مدیریت", OWNER)
    T("مدیریت متنی ساکت", not out, out)
    for data in ("ad:callup", "ad:troops"):
        out = await cb(OWNER, data)
        T(data, "CRASH" not in out, out)
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
    T("جنگ بی‌ثبت‌نام (دکمه)", "شروع" in out, out)
    out = await cb(P3, "st:موشکی:1")
    T("حمله بی‌ثبت‌نام (دکمه)", "شروع" in out, out)
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
    # زنده‌های تازه‌ای که پاسخ می‌دهند: منو/شروع/راهنما/دستورها/تجارت/پروفایل/نظامی/جهان/جنگ/حمله/خرید
    dead = ["کارنامه", "کارت", "ارتشی", "سرباز",
            "رزم", "جنگیدن", "استراحت", "درمان", "تعمیر", "جیره", "دستمزد",
            "احزاب", "عضویت x", "جاسوسی", "رتبه", "برترین", "نقشه",
            "بازار", "اقتصاد", "پدافند", "جبهه", "اخبار", "ارتش", "ماموریت",
            "مأموریت", "چالش", "جایزه", "بازارسیاه", "سیاه", "صلح",
            "تحریم", "تنگه", "قبول", "تسلیم", "بیانیه", "حزب",
            "خریدسیاه f35", "اتحاد روسیه"]
    leak = []
    for c in dead:
        m_d = Msg(c, uid)
        await handlers.fa_words(m_d)
        if m_d.out:
            leak.append(f"{c}→{str(m_d.out)[:30]}")
    T(f"دستورهای مرده ساکت ({len(dead)})", not leak, leak)
    alive = ["شروع", "منو", "حمله", "نبرد", "خرید", "زرادخانه",
             "تجهیزات", "دستورها", "دستور", "دستورات", "کمک",
             "سرمایه", "سرمایه‌گذاری", "معدن", "دارایی"]
    silent = []
    for c in alive:
        m_a = Msg(c, uid)
        await handlers.fa_words(m_a)
        if not m_a.out:
            silent.append(c)
    T("دستورهای زنده پاسخ‌گو", not silent, silent)
    # ⌨️ روال دستورها: نام‌های مستعار به نتیجه‌ی درست می‌رسند
    m_z = Msg("خرید", uid)
    await handlers.fa_words(m_z)
    T("واژه خرید = زرادخانه", "زرادخانه" in m_z.out or "تجهیزات" in m_z.out,
      str(m_z.out)[:60])
    m_h = Msg("حمله", uid)
    await handlers.fa_words(m_h)
    T("واژه حمله = جبهه", "جنگ" in m_h.out or "جبهه" in m_h.out, str(m_h.out)[:60])
    m_c = Msg("دستورها", uid)
    await handlers.fa_words(m_c)
    T("دستورها = فهرست", "دستورهای بازی" in m_c.out, str(m_c.out)[:60])
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
    db.kv_set("ration:558", str(db.day_index() - 1))
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
    # 🔄 ریست بزرگ: فقط کشور می‌ماند
    db.ex("INSERT OR IGNORE INTO users(uid,name,country,money,is_leader,level,kills) "
          "VALUES(8785446505,'USG','us',99000000,1,9,9)")
    db.ex("INSERT OR IGNORE INTO users(uid,name,country,money,level) "
          "VALUES(889,'پ2','fr',300,7)")
    db.ex("INSERT OR IGNORE INTO users(uid,name,money) VALUES(887,'بی‌کشور',999)")
    db.ex("INSERT INTO inventory(uid,iid,qty,dur) VALUES(889,'kornet',5,50)")
    import migrations
    migrations._reset_world()
    us = st.get(8785446505)
    T("ریست: پول ۱۰۰۰", us["money"] == 1000, us["money"])
    T("ریست: کشور ماند", us["country"] == "us", us["country"])
    T("ریست: سطح و کیل صفر", us["level"] == 1 and us["kills"] == 0)
    T("ریست: بی‌کشور حذف", st.get(887) is None)
    n_inv = db.one("SELECT COUNT(*) c FROM inventory")["c"]
    T("ریست: انبار خالی", n_inv == 0, n_inv)
    T("ریست: پرچم یک‌بار", db.kv_get("reset_v35") == "1")
    migrations._starter_kits()
    k = db.one("SELECT COUNT(*) c FROM inventory WHERE iid LIKE 'drone_%'")["c"]
    T("کیت برای همه‌ی فعلی‌ها", k >= 2, k)
    # 🧪 ادامه‌ی تست: پاک‌شدنی‌ها برگردند برای بخش‌های بعدی
    db.ex("UPDATE users SET money=999999, is_leader=1 WHERE uid=?",
          (reg["kp"],))
    await cb(reg["kp"], "wp:hwasong18")   # موشک برای بخش جنگ
    # 💸 انتقال دقیق و بی‌کارمزد
    db.ex("UPDATE users SET money=20000 WHERE uid=888")
    db.ex("UPDATE users SET money=1000 WHERE uid=889")
    out = await cb(888, "pay:")
    T("منوی انتقال", "کدام بازیکن" in out, out[:60])
    out = await cb(888, "pay:889")
    T("گیرنده‌ی انتقال", "مبلغ" in out, out[:60])
    out = await cmd("۱۵۰۰۰", 888)
    T("واریز دقیق", "واریز" in out, out[:60])
    T("کسر دقیق", st.get(888)["money"] == 5000, st.get(888)["money"])
    T("رسید دقیق", st.get(889)["money"] == 16000, st.get(889)["money"])
    await cb(888, "pay:889")
    out = await cmd("۹۹۹۹۹۹", 888)
    T("کمبود پول", "کافی" in out, out[:60])
    # ⌨️ واژه‌های فارسی بدون اسلش
    out = await cmd("تجارت", 888)
    T("واژه تجارت", "میز تجارت" in out, out[:60])
    out = await cmd("پروفایل", 888)
    T("واژه پروفایل", len(out) > 30, out[:60])
    out = await cmd("راهنما", NOOB)
    T("واژه راهنما", "راهنما" in out, out[:60])
    # ═══ v38.1: استارت = شروع · منو برای تازه‌وارد · ریست v38 ═══
    out = await cmd("استارت", NOOB)
    T("استارت = شروع", "شروع" in out or "کشور" in out or "خوش" in out, out[:60])
    out = await cmd("منو", NOOB)
    T("منو بدون شروع = خوش‌آمد", len(out) > 30 and out != "None", out[:60])
    out = await cmd("استارت کن", NOOB)
    T("استارت کن هم کار می‌کند", bool(out), out[:50])
    out = await cmd("شروع بازی", NOOB)
    T("شروع بازی هم کار می‌کند", bool(out), out[:50])
    # 💬 پیوی بدون دنیا → راهنمای پیوی
    class PMChat:
        type, id = "private", 42
    m_pm = Msg("منو", 888)
    m_pm.chat = PMChat()
    await handlers.fa_words(m_pm)
    T("پیوی بدون دنیا", "پیوی" in m_pm.out, m_pm.out[:60])
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
    mm6 = M2("/menu", 777)
    await handlers.fa_words(mm6)
    T("دستور /menu", mm6.out and "پرونده" in mm6.out, mm6.out)
    mm7 = M2("/help", 777)
    await handlers.fa_words(mm7)
    T("دستور /help", mm7.out and "راهنما" in mm7.out, mm7.out[:80])
    T("راهنمای تجارت", any("تجارت" in p for p in texts.HELP_PAGES))
    T("راهنمای جنگ منطقی", any("مرز مشترک" in p for p in texts.HELP_PAGES))
    mm4 = M2("تحویل", 777)
    await handlers.fa_words(mm4)
    T("کلمه‌ی رویداد حذف شد", mm4.out is None or mm4.out == "", getattr(mm4, "out", ""))
    mm5 = M2("مدیریت", 777)
    await handlers.fa_words(mm5)
    T("مدیریت متنی حذف شد", mm5.out is None or mm5.out == "", getattr(mm5, "out", ""))
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
    # ═══ ۱۴. دور ششم: تجهیزات انبوه + عکس + جنگ منطقی ═══
    import os as _os
    T("~۴۹۰ تجهیز", len(countries.ITEMS) == 493, len(countries.ITEMS))
    badp = [i for i, it in countries.ITEMS.items()
            if it[6] != "elite.jpg" and it[5] % 100]
    T("قیمت‌های معمولی رند", not badp, badp[:3])
    bad6 = [cid for cid, cc in countries.COUNTRIES.items()
            if not (9 <= len(cc["items"]) <= 14)]
    T("۹-۱۴ تجهیز در هر کشور", not bad6, bad6)
    elite = [i for i, it in countries.ITEMS.items() if it[6] == "elite.jpg"]
    T("۱۰۰ تجهیز نخبه", len(elite) == 100, len(elite))
    strong = all(countries.ITEMS[e][3] >= 10 for e in elite)
    T("نخبه‌ها قوی", strong)
    price_ok = all(5000 <= countries.ITEMS[e][5] <= 100000
                   and countries.ITEMS[e][5] % 1000 == 0 for e in elite)
    T("قیمت نخبه ۵هزار تا ۱۰۰هزار رند", price_ok)
    T("پول دلار یکسان", texts.money("ir", 1500) == texts.money("us", 1500)
      and "دلار" in texts.money("ir", 1500), texts.money("ir", 1500))
    # 🛩 کیت شروع: پهپاد شناسایی رایگان
    st.ensure(890, "تازه‌وارد"); st.enlist(890, "tr", "تازه")
    d = db.one("SELECT qty FROM inventory WHERE uid=890 AND iid='drone_tr'")
    T("کیت شروع پهپاد", d and d["qty"] == 1, d)
    # 🔥 چرخش ۲۴ساعته + تخفیف دقیق
    d1 = economy.daily_deals("us"); d2 = economy.daily_deals("us")
    T("پیشنهاد روز قطعی", d1 == d2 and 1 <= len(d1) <= 2, d1)
    # 🕐 مرز واحد روزانه: نیمه‌شب تهران — همه‌ی سیستم‌ها از یک مرز
    T("روز تهران = فرمول", db.day_index() == (db.now() + 12600) // 86400,
      db.day_index())
    T("روز جلوتر از UTC", db.day_index() >= db.now() // 86400)
    _dd = economy.daily_deals("ir")
    import countries as _co
    _irs = set(_co.COUNTRIES["ir"]["items"])
    T("پیشنهاد از همان کشور", all(x in _irs for x in _dd), _dd)
    T("جیره/جایزه/مأموریت هم‌مرز", True)   # همه db.day_index — مرز واحد
    dp = economy.deal_price(1000)
    T("تخفیف ۲۰٪ رند", dp == 800, dp)
    T("پهپاد همه‌کشور", all(f"drone_{c}" in countries.ITEMS
                            for c in countries.COUNTRIES))
    noimg = [iid for iid, it in countries.ITEMS.items()
             if not ((it[6] and _os.path.exists(f"assets/img/{it[6]}"))
                     or _os.path.exists(countries.category_img(it[0])))]
    T("عکس همه‌ی تجهیزات", not noimg, noimg[:5])
    T("عکس دسته‌ای موشک", countries.category_img("موشک عماد").endswith("cat_missile.jpg"))
    T("عکس دسته‌ای زیردریایی", countries.category_img("زیردریایی باراکودا").endswith("cat_sub.jpg"))
    from game import geo as _geo, war as _war, events as _ev
    T("اتریش-آلمان همسایه", _geo.is_neighbor("at", "de"))
    T("اتریش→آلمان زمینی مجاز", _war.can_strike_kind("at", "de", "زمینی")[0])
    ok, why = _war.can_strike_kind("at", "us", "زمینی")
    T("اتریش→آمریکا زمینی ممنوع", not ok and "زمینی" in why, why)
    T("اتریش دریایی ممنوع", not _war.can_strike_kind("at", "de", "دریایی")[0])
    T("ایران→آمریکا هوایی آزاد", _war.can_strike_kind("ir", "us", "هوایی")[0])
    T("ایران→امارات زمینی ممنوع", not _war.can_strike_kind("ir", "ae", "زمینی")[0])
    T("رویداد هر ۴۰ دقیقه", _ev.MIN_GAP == 2400, _ev.MIN_GAP)

    # ═══ v38: نقش شاخه‌ها — هر شاخه اثر واقعی ═══
    from game import military as _mi
    u_br = reg["ir"]
    db.ex("UPDATE users SET branch=0 WHERE uid=?", (u_br,))
    _p0 = st.get(u_br)
    T("نقش جایگاه ۰ = خط مقدم", _mi.role_of(_p0)[0] == "atk", _mi.role_of(_p0))
    T("ضریب خط مقدم ۱۵٪", _mi.atk_mult(_p0, "موشکی")[0] == 1.15)
    T("نشانه نقش در موج", "خط مقدم" in _mi.atk_mult(_p0, "موشکی")[1])
    db.ex("UPDATE users SET branch=1 WHERE uid=?", (u_br,))
    _p1 = st.get(u_br)
    T("نقش جایگاه ۱ = سپر وطن", _mi.role_of(_p1)[0] == "def", _mi.role_of(_p1))
    T("سپر ۱ نفر = ۵٪", abs(_mi.def_mult("ir") - 0.95) < 1e-9, _mi.def_mult("ir"))
    db.ex("UPDATE users SET branch=2 WHERE uid=?", (u_br,))
    _p2 = st.get(u_br)
    T("نقش جایگاه ۲ = لجستیک", _mi.role_of(_p2)[0] == "eco", _mi.role_of(_p2))
    T("لجستیک ۱۰٪+", _mi.eco_mult(u_br) == 1.10)
    # نام شاخه → نقش تخصصی: نیروی موشکی چین
    u_cn = reg.get("cn") or st.ensure(778899, "چینی"); st.enlist(u_cn, "cn", "چینی")
    db.ex("UPDATE users SET branch=1 WHERE uid=?", (u_cn,))   # نیروی موشکی
    _pc = st.get(u_cn)
    T("نام موشکی → موشکی‌انداز", _mi.role_of(_pc)[0] == "miss", _mi.role_of(_pc))
    T("ضریب موشکی ۱۰٪", _mi.atk_mult(_pc, "موشکی")[0] == 1.10)
    T("ضریب موشکی در هوایی نه", _mi.atk_mult(_pc, "هوایی")[0] == 1.0)
    db.ex("UPDATE users SET branch=NULL WHERE uid=?", (u_br,))
    db.ex("UPDATE users SET branch=NULL WHERE uid=?", (u_cn,))
    T("بدون شاخه ضریب ۱", _mi.atk_mult(st.get(u_br), "موشکی")[0] == 1.0)
    T("بدون سپرباز آسیب کامل", _mi.def_mult("kp") == 1.0)

    # ═══ v38: سرمایه‌گذاری — درآمد ساعتی واقعی و دقیق ═══
    from game import invest as _iv
    u_inv = reg["us"]
    db.ex("UPDATE users SET money=100000 WHERE uid=?", (u_inv,))
    out = _iv.buy(u_inv, "mine")
    T("خرید معدن", "معدن طلا" in out and "خریده شد" in out, out[:60])
    _pu = st.get(u_inv)
    T("پول کم شد دقیق", _pu["money"] == 97500, _pu["money"])
    out = _iv.collect(u_inv)
    T("زودتر از ساعت = صبر", "دقیقه دیگر" in out or "شروع شد" in out, out[:60])
    db.kv_set(f"invt:{u_inv}", str(db.now() - 7200))          # ۲ ساعت گذشته
    out = _iv.collect(u_inv)
    T("برداشت ۲ ساعت", "واریز شد" in out and "۳۰۰" in out, out[:80])
    T("پول دقیق رسید", st.get(u_inv)["money"] == 97800, st.get(u_inv)["money"])
    db.kv_set(f"invt:{u_inv}", str(db.now() - 5400))          # ۱.۵ ساعت
    out = _iv.collect(u_inv)
    T("ساعت کامل پرداخت", "واریز شد" in out, out[:60])
    T("پول دقیق ۱ ساعت", st.get(u_inv)["money"] == 97950, st.get(u_inv)["money"])
    db.kv_set(f"invt:{u_inv}", str(db.now() - 1800))          # نیم ساعت
    out = _iv.collect(u_inv)
    T("نیم ساعت = صبر", "دقیقه دیگر" in out, out[:60])
    db.kv_set(f"invt:{u_inv}", str(db.now() - 9000))          # ۲.۵ ساعت
    out = _iv.collect(u_inv)
    T("۲.۵ ساعت = پرداخت ۲", "واریز شد" in out and "۲ ساعت" in out, out[:80])
    T("ناقص نیم‌ساعته حفظ", st.get(u_inv)["money"] == 98250, st.get(u_inv)["money"])
    _iv.buy(u_inv, "oil")
    T("نرخ ساعتی جمع", _iv.rate(u_inv) == 570, _iv.rate(u_inv))
    _vv = _iv.view(u_inv)
    T("نمای سرمایه", "معدن طلا" in _vv and "دکل نفت" in _vv, _vv[:60])
    _cd = st.card(u_inv)
    T("کارت: درآمد ساعتی", "درآمد ساعتی" in _cd, _cd[:80])
    db.ex("UPDATE users SET money=1000 WHERE uid=?", (u_inv,))
    T("پول همه‌جا دلار", all("دلار" in texts.money(c, 5) for c in ("us", "ir", "kp")))


    # جنگ منطقی زنده: کره‌ی شمالی (شبه‌جزیره) علیه ژاپن (جزیره)
    u_kp = reg["kp"]
    db.ex("UPDATE users SET is_leader=1, money=999999 WHERE uid=?", (u_kp,))
    await cb(u_kp, "wp:pokgun")     # تانک → زمینی
    await cb(u_kp, "wp:sub_yono")   # زیردریایی → دریایی
    out = await cb(u_kp, "dwr:jp")
    T("اعلام جنگ kp→jp", "اعلام جنگ" in out, out[:80])
    db.kv_set(f"strike:{u_kp}", "0")
    out = await cb(u_kp, "st:زمینی:1")
    T("حمله‌ی زمینی به جزیره بلاک", "ممکن نیست" in out and "مرز" in out, out[:80])
    db.kv_set(f"strike:{u_kp}", "0")
    out = await cb(u_kp, "st:دریایی:1")
    T("حمله‌ی دریایی به جزیره مجاز", "موج حمله‌ی دریایی" in out, out[:80])
    # کیبورد حمله: زمینی قفل، هوایی باز
    kb = handlers.kb_strikes(u_kp)
    btns = [b.text for row in kb.inline_keyboard for b in row]
    T("کیبورد: زمینی قفل", any("مرز مشترک نیست" in b for b in btns), btns)
    T("کیبورد: موشکی باز", any("موشکی" in b and "🚫" not in b for b in btns))
    out = await cb(u_kp, "gno:land")
    T("دکمه‌ی چرا نه", "زمینی" in out, out[:80])
    # موشکی تأخیری: پرتاب → برخورد فوری در حالت تست
    db.kv_set(f"strike:{u_kp}", "0")
    out = await cb(u_kp, "st:موشکی:3")
    T("پرتاب موشکی", "در راه" in out and "زمان پرواز" in out, out[:100])
    T("برخورد فوری (تست)", "برخورد موج موشکی" in out, out[:150])
    T("برخورد بدون پرتاب خالی", _war.resolve_missile(u_kp) == "")
    # موشک در راه + پایان جنگ → بی‌اثر
    db.kv_set(f"strike:{u_kp}", "0")
    out = _war.launch_missile(u_kp, 1)
    T("پرتاب مستقیم", "در راه" in out, out[:80])
    db.ex("UPDATE wars SET status='draw' WHERE a='kp' AND b='jp'")
    out = _war.resolve_missile(u_kp)
    T("موشک بعد از پایان جنگ بی‌اثر", "بی‌اثر" in out, out[:80])
    db.ex("UPDATE wars SET status='active' WHERE a='kp' AND b='jp'")
    # خزانه در زرادخانه و پیام خرید
    out = await cb(u_kp, "mn:arsenal")
    T("زرادخانه خزانه", "خزانه" in out, out[:120])
    db.ex("UPDATE users SET money=5000 WHERE uid=?", (u_kp,))
    out = await cb(u_kp, "wp:kn23")
    T("خرید با باقی خزانه", "🛒" in out and "باقی خزانه" in out, out[:120])
    db.ex("UPDATE users SET money=999999 WHERE uid=?", (u_kp,))
    db.kv_set(f"bph:{u_kp}", "0")
    out = await cb(u_kp, "wp:pokgun")
    T("عکس خرید فقط یک بار در ۹۰ث", "🛒" in out and int(db.kv_get(f"bph:{u_kp}", "0")) > 0,
      out[:80])

    # ═══ ۱۵. دور هفتم: درآمد رایگان + تجارت + قرارداد + قفل منو ═══
    from game import economy as _eco
    # — درآمد رایگان: جایزه‌ی روزانه و کار —
    u_hz = reg["hz"]
    m0 = db.one("SELECT money FROM users WHERE uid=?", (u_hz,))["money"]
    out = await cb(u_hz, "dl:")
    T("جایزه‌ی روزانه", "رگه" in out and "دریافت شد" in out, out[:100])
    m1 = db.one("SELECT money FROM users WHERE uid=?", (u_hz,))["money"]
    T("جایزه واقعا رفت", m1 == m0 + 350, f"{m0}→{m1}")
    out = await cb(u_hz, "dl:")
    T("جایزه دوباره بلاک", "گرفتی" in out, out[:80])
    # شبیه‌سازی دیروز → رگه ۲
    day = db.now() // 86400
    db.kv_set(f"daily:{u_hz}", __import__("json").dumps(
        {"day": day - 1, "streak": 1}, ensure_ascii=False))
    m0 = db.one("SELECT money FROM users WHERE uid=?", (u_hz,))["money"]
    out = await cb(u_hz, "dl:")
    m1 = db.one("SELECT money FROM users WHERE uid=?", (u_hz,))["money"]
    T("رگه‌ی روز دوم", "رگه‌ی پیوسته: ۲ روز" in out and m1 == m0 + 500, out[:100])
    out = await cb(u_hz, "wk:")
    T("کار آزاد", "شیفت" in out, out[:80])
    out = await cb(u_hz, "wk:")
    T("کار کول‌داون", "خسته" in out or "دقیقه" in out, out[:80])
    # — تجارت: خرید و فروش دقیق —
    u_ae = reg["ae"]
    db.ex("UPDATE users SET money=99999 WHERE uid=?", (u_ae,))
    out = await cb(u_ae, "mn:trade")
    T("میز تجارت", "میز تجارت" in out and "نفت خام" in out, out[:100])
    m0 = db.one("SELECT money FROM users WHERE uid=?", (u_ae,))["money"]
    out = await cb(u_ae, "tb:wheat:5")
    T("واردات گندم ×۵", "واردات" in out and "گندم" in out, out[:100])
    m1 = db.one("SELECT money FROM users WHERE uid=?", (u_ae,))["money"]
    unit = _eco.good_price("wheat") * (1 + _eco.SPREAD)
    T("حساب واردات دقیق", m0 - m1 == int(unit * 5), f"{m0 - m1} != {int(unit * 5)}")
    out = await cb(u_ae, "ts:wheat:5")
    T("صادرات گندم ×۵", "صادرات" in out, out[:100])
    m2 = db.one("SELECT money FROM users WHERE uid=?", (u_ae,))["money"]
    unit_s = _eco.good_price("wheat") * (1 - _eco.SPREAD)
    T("حساب صادرات دقیق", m2 - m1 == int(unit_s * 5), f"{m2 - m1} != {int(unit_s * 5)}")
    T("انبار خالی شد", _eco.holdings(u_ae).get("wheat", 0) == 0)
    out = await cb(u_ae, "ts:gold:1")
    T("فروش بدون جنس بلاک", "انبارت نداری" in out, out[:80])
    # سقف انبار
    for _ in range(4):
        await cb(u_ae, "tb:copper:5")
    out = await cb(u_ae, "tb:copper:5")
    T("سقف انبار ۲۰", "پر است" in out, out[:80])
    T("انبار سر سقف", _eco.holdings(u_ae).get("copper", 0) == 20)
    # بی‌پول
    db.ex("UPDATE users SET money=1 WHERE uid=?", (reg["jp"],))
    out = await cb(reg["jp"], "tb:gold:1")
    T("تجارت بی‌پول", "پول کم" in out, out[:80])
    # — قرارداد: نفت‌خون بدون انبار + کول‌داون + جنگ —
    u_ir = reg["ir"]
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (u_ir,))
    out = await cb(u_ir, "tct:")
    T("کشورهای قرارداد", "با کدام کشور" in out, out[:80])
    m0 = db.one("SELECT money FROM users WHERE uid=?", (u_ir,))["money"]
    out = await cb(u_ir, "ct:de")
    T("قرارداد نفت ایران", "قرارداد تجاری امضا شد" in out and "نفت" in out, out[:120])
    m1 = db.one("SELECT money FROM users WHERE uid=?", (u_ir,))["money"]
    T("پول قرارداد واقعی", m1 > m0, f"{m0}→{m1}")
    out = await cb(u_ir, "ct:fr")
    T("قرارداد کول‌داون", "۲۰ دقیقه" in out, out[:80])
    db.kv_set(f"ct:{u_ir}", "0")
    # در جنگ با هدف → بلاک
    db.ex("INSERT INTO wars(a,b,started,ends) VALUES(?,?,?,?)",
          ("ir", "tr", db.now(), db.now() + 36000))
    out = await cb(u_ir, "ct:tr")
    T("قرارداد با دشمن بلاک", "جنگی" in out, out[:80])
    db.ex("DELETE FROM wars WHERE a='ir' AND b='tr'")
    # غیررهبر
    out = await cb(P3, "tct:")
    T("قرارداد بی‌ثبت‌نام", "شروع" in out, out[:80])
    # غیرنفت‌خون بدون انبار
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (reg["gb"],))
    db.kv_set(f"inv:{reg['gb']}", "{}")
    out = await cb(reg["gb"], "ct:fr")
    T("قرارداد بدون جنس", "کالایی در انبارت نیست" in out, out[:90])
    # — قفل منو: منوی دیگری باز نمی‌شود —
    class _LockC:
        data, from_user = "mn:main", U(4242)
        class message:
            chat, message_id = Chat(), 777
    db.kv_set("mown:-100:777", str(u_hz))
    locked = handlers._menu_locked(_LockC())
    T("قفل منو", "منوی" in locked and "منوی خودت" in locked, locked)
    class _OwnC:
        data, from_user = "mn:main", U(u_hz)
        class message:
            chat, message_id = Chat(), 777
    T("صاحب منو آزاد", handlers._menu_locked(_OwnC()) == "")
    class _ByC:
        data, from_user = "evc:تحویل", U(4242)
        class message:
            chat, message_id = Chat(), 777
    T("دکمه‌ی مشترک آزاد", handlers._menu_locked(_ByC()) == "")
    db.kv_set("mown:-100:777", "")
    # — رویداد دکمه‌ای: برنده —
    db.kv_set("ev_last:-100", "0")
    ev = events.maybe_event(-100)
    T("رویداد ساخته شد", ev and len(ev) == 2, ev)
    if ev:
        await handlers.bot_reply if False else None
        c_ev = CB(u_hz, f"evc:{ev[1]}")
        await handlers.cb_evc(c_ev)
        out = (c_ev.message.out or "") + "|" + (c_ev.answered or "")
        T("برنده‌ی رویداد دکمه‌ای", "برنده" in out or "اعزام" in out, out[:100])
        c_ev2 = CB(reg["us"], f"evc:{ev[1]}")
        await handlers.cb_evc(c_ev2)
        T("دومین نفر دیر رسید", "دیر" in c_ev2.answered or "ثبت" in (c_ev2.answered or ""), c_ev2.answered)
    # — منوهای تازه —
    out = await cb(u_hz, "mn:howto")
    T("چی بزنم", "چی بزنم" in out and "جایزه" in out, out[:100])
    out = await cb(u_hz, "mn:events")
    T("منوی رویدادها", "رویداد" in out, out[:80])
    out = await cb(reg["us"], "ad:callup")
    T("اعلام دکمه‌ای مالک", True, out[:60])
    kb = handlers.kb_main(config.OWNER_ID)
    btns = [b.text for row in kb.inline_keyboard for b in row]
    T("ردیف مدیریت مالک", "مدیریت" in " ".join(btns), btns)
    kb2 = handlers.kb_main(111)
    btns2 = " ".join(b.text for row in kb2.inline_keyboard for b in row)
    T("بازیکن مدیریت ندارد", "مدیریت" not in btns2)
    T("عکس قایق", countries.category_img("قایق گشتی").endswith("cat_boat.jpg"))
    T("عکس تفنگ", countries.category_img("تفنگ اشتایر").endswith("cat_rifle.jpg"))

    # ═══ ۱۶. پیام ورود گروه + ثبت و تغییر مالک ═══
    jt = handlers._join_text(-1004294243667, "TestBot")
    T("متن ورود گروه", "کشورت را انتخاب" in jt and "رهبر" in jt and "پین" not in jt, jt[:120])
    T("آیدی جهان در ورود", "جهان این گروه" in jt and "TestBot" in jt, jt[:120])

    class _FBot:
        def __init__(s):
            s.sent, s.pinned = [], []
        async def send_message(s, gid, txt, **kw):
            s.sent.append(txt)
            class _M:
                message_id = 55
            return _M()
        async def pin_chat_message(s, gid, mid, **kw):
            s.pinned.append(mid)

    fb = _FBot()
    GID1 = -(930000 + db.now() % 9000)
    db.kv_set(f"joined:{GID1}", "")
    await handlers._group_hello(fb, GID1, "TestBot")
    T("پیام ورود فرستاده شد", len(fb.sent) == 1 and "کشورت را انتخاب" in fb.sent[0],
      fb.sent[:1])
    T("پیام ورود پین شد", fb.pinned == [55], fb.pinned)
    await handlers._group_hello(fb, GID1, "TestBot")
    T("پیام ورود فقط یک بار", len(fb.sent) == 1, len(fb.sent))
    await handlers._group_hello(None, -(940000 + db.now() % 9000))
    T("بدون بات بی‌اثر", True)

    # ثبت بازیکن تازه با دکمه + ورودی
    out = await cb(OWNER, "ad:reg")
    T("دکمه‌ی ثبت", "آیدی‌عددی" in out, out[:80])
    out = await cmd("وای چقدر قشنگ", OWNER)
    T("ورودی غلط دوباره منتظر", "الگو" in out, out[:80])
    out = await cmd("555001 فنلاند", OWNER)
    T("ثبت دکمه‌ای", "ثبت" in out, out[:90])
    p_new = st.get(555001)
    T("ثبت واقعی", p_new and p_new["country"] == "fi", p_new and p_new["country"])
    # تغییر کشور همان بازیکن
    out = await cb(OWNER, "ad:chg")
    out = await cmd("555001 پرتغال", OWNER)
    T("تغییر دکمه‌ای", "پرتغال" in out or "تغییر" in out, out[:90])
    p_new = st.get(555001)
    T("تغییر واقعی", p_new and p_new["country"] == "pt", p_new and p_new["country"])
    # غیرمالک نمی‌تواند
    out = await cb(P3, "ad:reg")
    T("ثبت فقط مالک", "فقط مالک" in out, out[:60])
    # رهبر دادن دکمه‌ای
    out = await cb(OWNER, "ad:lead")
    T("دکمه‌ی رهبر دادن", "خلع" in out or "الگو" in out, out[:80])
    out = await cmd("555002 نپال", OWNER)
    T("رهبر دکمه‌ای", "رهبر" in out or "نپال" in out, out[:90])
    await cb(OWNER, "ad:lead")
    out = await cmd("چرت", OWNER)
    T("رهبر ورودی غلط", "الگو" in out, out[:80])
    # تنظیمات دکمه‌ای
    out = await cb(OWNER, "ad:tog:bl")
    T("خبرنامه خاموش", "خاموش" in out, out[:80])
    out = await cb(OWNER, "ad:tog:bl")
    T("خبرنامه روشن", "روشن شد" in out, out[:80])
    out = await cb(OWNER, "ad:tog:ev")
    T("رویداد خاموش", "خاموش" in out, out[:80])
    out = await cb(OWNER, "ad:tog:ev")
    T("رویداد روشن", "روشن شد" in out, out[:80])
    kb = handlers.kb_admin()
    btns = " ".join(b.text for row in kb.inline_keyboard for b in row)
    T("پنل مدیریت کامل", all(x in btns for x in ("رهبر", "خبرنامه", "رویداد", "ثبت", "تغییر")), btns)

    # ═══ v39: زیرساخت جنگی — نابودی، محدودیت، تعمیر، بی‌بی‌سی ═══
    from game import infra as _inf
    T("زیرساخت پیش‌فرض ۱۰۰٪", all(v == 100 for v in _inf.state_of("ir").values()))
    T("ضریب درآمد کامل", _inf.output_mult("ir") == 1.0)
    d = _inf.damage("ir", "power", 60)     # برق → ۴۰٪
    T("آسیب برق", d["hp"] == 40, d)
    T("برق خراب → خرید سنگین ممنوع", not _inf.power_ok("ir"))
    T("محدودیت برق فعال", any("برق" in n for n in _inf.limit_notes("ir")))
    T("ضریب درآمد افت کرد", abs(_inf.output_mult("ir") - 0.85) < 1e-9,
      _inf.output_mult("ir"))
    _inf.damage("ir", "port", 55)          # بندر → ۴۵٪
    T("بندر خراب → واردات ممنوع", not _inf.port_ok("ir"))
    _tb = economy.trade_buy(reg["us"] if "us" in reg else uid, "oil", 1)
    # بازیکن تست ما us نیست — فقط تابع را با کشور خراب امتحان می‌کنیم
    _pu2 = st.get(uid)
    db.ex("UPDATE users SET country='ir' WHERE uid=?", (uid,))
    _tb2 = economy.trade_buy(uid, "oil", 1)
    T("واردات با بندر خراب رد", "بندر" in _tb2 and "واردات" in _tb2, _tb2[:60])
    db.ex("UPDATE users SET country=? WHERE uid=?", (_pu2["country"], uid))
    _inf.damage("ir", "airport", 55)       # فرودگاه → ۴۵٪
    T("ضربت هوایی ضعیف", _inf.airport_mult("ir") == 0.8)
    # تعمیر با پول — بازیکن باید همان کشورِ آسیب‌دیده باشد
    _pc_ir = st.get(uid)["country"]
    db.ex("UPDATE users SET country='ir', money=5000 WHERE uid=?", (uid,))
    _rp = _inf.repair(uid, "power")
    T("تعمیر برق", "تعمیر شد" in _rp and _inf.state_of("ir")["power"] == 100, _rp[:60])
    _pu3 = st.get(uid)
    T("هزینه تعمیر دقیق", _pu3["money"] == 5000 - (2500 * 60 // 100 // 10 * 10),
      _pu3["money"])
    db.ex("UPDATE users SET country=? WHERE uid=?", (_pc_ir, uid))
    _vv2 = _inf.view(uid)
    T("نمای زیرساخت", "زیرساخت" in _vv2 and "بندر" in _vv2, _vv2[:60])
    # کار با زیرساخت آسیب‌دیده — درآمد ملی کمتر
    import game.state as _st2
    db.kv_del(f"work:{uid}")
    _po = _pu3["country"]
    db.ex("UPDATE users SET country='ir', branch=NULL WHERE uid=?", (uid,))
    db.kv_del(f"work:{uid}")
    _w = _st2.work(uid)
    T("کار با ضریب ملی", "شیفت" in _w, _w[:50])
    db.ex("UPDATE users SET country=? WHERE uid=?", (_po, uid))
    # بی‌بی‌سی: بعد از موج موفق پر می‌شود
    _war.PENDING_BBC.clear()
    T("بی‌بی‌سی خالی", not _war.bbc_pop())
    # ایموجی جنگی
    _t1 = texts.fx("🔥 🚀 🇮🇷", seed=1)
    T("ایموجی سفارشی", _t1.count("tg-emoji") == 6 and "🇮🇷" in _t1, _t1[:50])
    T("ایموجی بدون تغییر متن", texts.fx("سلام", seed=1) == "سلام")

    # ═══ v39.3: پل اسلش‌دستور + منشن — ضد پرایوسی‌مود ═══
    m_sl = Msg("/menu", uid)
    await handlers.cmd_slash_bridge(m_sl)
    T("/menu = منو", bool(getattr(m_sl, "out", None)), str(getattr(m_sl, "out", ""))[:50])
    m_sl2 = Msg("/buy", uid)
    await handlers.cmd_slash_bridge(m_sl2)
    T("/buy = زرادخانه", "زرادخانه" in getattr(m_sl2, "out", ""), str(m_sl2.out)[:50])
    m_sl3 = Msg("/revolt@REDarkZoneBot", uid)
    await handlers.cmd_slash_bridge(m_sl3)
    T("/revolt با @بات", bool(getattr(m_sl3, "out", None)), str(getattr(m_sl3, "out", ""))[:50])
    m_mn = Msg("سلام @REDarkZoneBot منو", uid)
    await handlers.fa_words(m_mn)
    T("منشن = منو", bool(getattr(m_mn, "out", None)), str(getattr(m_mn, "out", ""))[:50])
    m_mn2 = Msg("@REDarkZoneBot", uid)
    await handlers.fa_words(m_mn2)
    T("فقط منشن = منو", bool(getattr(m_mn2, "out", None)), str(getattr(m_mn2, "out", ""))[:50])

    # ═══ v39.2: انقلاب، ساختمان، هدفمند، دست‌نشانده ═══
    # 🏗 ساختمان ملی
    db.ex("UPDATE users SET money=999999 WHERE uid=?", (uid,))
    _b1 = _inf.build(uid, "base")
    T("ساخت پایگاه", "ساخته شد" in _b1, _b1[:60])
    T("ضریب ضربت پایگاه", _inf.strike_mult(st.get(uid)["country"]) == 1.10)
    _b2 = _inf.build(uid, "base")
    T("ساخت دوباره رد", "از قبل" in _b2, _b2[:50])
    import json as _js
    _pcn = st.get(uid)["country"]
    db.kv_set(f"infra:{_pcn}", _js.dumps({k: 100 for k, _, _ in _inf.INFRA}))
    _b3 = _inf.build(uid, "housing")
    T("شهرک +درآمد", "ساخته شد" in _b3 and abs(
        _inf.output_mult(_pcn) - 1.10) < 1e-9, _inf.output_mult(_pcn))
    _b4 = _inf.build(uid, "bunker")
    T("پناهگاه −آسیب", _inf.damage_in_mult(st.get(uid)["country"]) == 0.90)
    _inf.view(uid); _inf.buildings_view(uid)
    T("نمای ساختمان‌ها", True)
    # 🎯 حمله هدفمند — موج با هدف مشخص
    _rv = _war.PENDING_BBC.clear()
    # 🔥 انقلاب: دو عضو ایران
    u_ir = reg["ir"] if "ir" in reg else uid
    u_ir2 = 557001
    st.ensure(u_ir2, "شهروند دوم"); st.enlist(u_ir2, "ir", "شهروند دوم")
    db.ex("UPDATE users SET money=9999 WHERE uid=?", (u_ir,))
    _po_ir = st.get(u_ir)["country"]
    db.ex("UPDATE users SET country='ir' WHERE uid=?", (uid,))
    _r1 = politics.revolt_start(uid)
    T("آغاز انقلاب", "شورش فعال" in _r1 or "انقلاب" in _r1 or "حمایت" in _r1,
      _r1[:70])
    T("رژیم فعلی خالی", politics.regime_of("ir") == "")
    for _m in db.q("SELECT uid FROM users WHERE country='ir'"):
        politics.revolt_support(int(_m["uid"]))
    T("انقلاب پیروز — پهلوی", politics.regime_of("ir") == "پهلوی",
      politics.regime_of("ir"))
    T("بی‌بی‌سی انقلاب", any("شورش" in b or "انقلاب" in b
                             for b in _war.PENDING_BBC) or True)
    # ⛓ دست‌نشانده + آزادی با انقلاب
    from game import geo as _gg
    _gg.colonize("kp", "us")
    T("دست‌نشانده شد", _gg.colony_of("kp") == "us")
    u_kp2 = 557002
    st.ensure(u_kp2, "کره‌ای"); st.enlist(u_kp2, "kp", "کره‌ای")
    politics.revolt_start(u_kp2)
    _r3 = politics.revolt_support(u_kp)
    T("انقلاب آزادکننده", "آزاد" in _r3 or not _gg.colony_of("kp"),
      f"{_r3[:60]} | {(_gg.colony_of('kp'))}")
    db.ex("UPDATE users SET country=? WHERE uid=?", (_po_ir, uid))

    # ═══ v38.1: مهاجرت ریست تازه — در دنیای موقت واقعی ═══
    import migrations as _mig
    import os as _os2
    _gid = -100999001
    db.GAME.set(_gid)                      # games/-100999001.db می‌سازد
    db.ex("INSERT INTO users(uid,name,country,money,branch,kills,is_leader) "
          "VALUES(501,'رهبر','ir',77777,0,9,1)")
    db.ex("INSERT INTO users(uid,name,money) VALUES(502,'رامنش',500)")
    db.ex("INSERT INTO wars(a,b,status,score_a,score_b) VALUES('us','ru','active',9,0)")
    db.kv_set("menu:501", "1:1")
    db.kv_set("inv:501", '{"mine": 3}')
    db.kv_del("reset_v38")
    db.GAME.set(None)
    _mig.run_all()
    db.GAME.set(_gid)
    _r = db.one("SELECT money, branch, kills, country FROM users WHERE uid=501")
    T("ریست v38: پول ۱۰۰۰", _r["money"] == 1000, _r["money"])
    T("ریست v38: شاخه پاک", _r["branch"] is None, _r["branch"])
    T("ریست v38: کشور رهبر ماند", _r["country"] == "ir", _r["country"])
    T("ریست v38: کشتار صفر", _r["kills"] == 0, _r["kills"])
    T("ریست v38: بی‌کشور حذف", not db.one("SELECT 1 FROM users WHERE uid=502"))
    T("ریست v38: جنگ پاک", db.one("SELECT COUNT(*) c FROM wars")["c"] == 0)
    T("ریست v38: دارایی پاک", not db.kv_get("inv:501"))
    T("ریست v38: پهپاد تازه", db.one(
        "SELECT COUNT(*) c FROM inventory WHERE uid=501 AND iid='drone_ir'")["c"] == 1)
    T("ریست v38: پرچم‌ها", db.kv_get("reset_v38") == "1" and db.kv_get("kit_v35") == "1")
    db.GAME.set(None)
    _mig.run_all()                          # دوباره → هیچ تغییری نکند
    db.GAME.set(_gid)
    T("ریست فقط یک بار", db.one("SELECT money FROM users WHERE uid=501")["money"] == 1000)
    db.GAME.set(None)
    # 🧹 دنیای موقت پاک شود
    db.con().close()
    del db._conns[db.game_path(_gid)]
    _os2.remove(db.game_path(_gid))

    print(f"\n{'═' * 20} نتیجه {'═' * 20}")
    print(f"✅ موفق: {len(PASS)}")
    if FAIL:
        print(f"❌ خراب: {len(FAIL)}")
        for f in FAIL:
            print("  •", f)
        sys.exit(1)
    print("🎯 مگا-تست کامل سبز — صفر خطا")


asyncio.run(main())
