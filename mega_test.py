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
          "br": handlers.cb_branch, "wp": handlers.cb_buy, "up": handlers.cb_upgrade,
          "spy": handlers.cb_spy, "ally": handlers.cb_ally, "st": handlers.cb_strike}[key]
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
    T("خرید فجر-۵", "خریداری" in out or "از قبل" in out, out)
    out = await cmd("رزم", uid)
    T("رزم", "رزم" in out or "پیروزی" in out or "شکست" in out, out)
    out = await cmd("استراحت", uid)
    T("استراحت", out and "CRASH" not in out, out)
    out = await cmd("تعمیر", uid)
    T("تعمیر", out and "CRASH" not in out, out)
    out = await cmd("جیره", uid)
    T("جیره", "جیره" in out, out)

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
    out = await cmd("تقویت ضد موشک", uid)
    T("تقویت متنی", "تقویت" in out or "پول" in out, out)

    # ═══ ۶. جنگ کامل: اعلام → ۵ نوع حمله → جبهه → صلح ═══
    db.ex("UPDATE users SET is_leader=1, money=999999, hp=100 WHERE uid=?", (uid,))
    out = await cmd("جنگ اسرائیل", uid)
    T("اعلام جنگ", "اعلام جنگ" in out, out)
    for kind in ("موشکی", "هوایی", "دریایی", "زمینی", "پهپادی"):
        db.kv_set(f"strike:{uid}", "0")
        out = await cmd(f"حمله {kind} 3", uid)
        T(f"حمله {kind}", out and "CRASH" not in out, out)
    # دکمه‌های st:
    for data in ("st:موشکی:1", "st:هوایی:3", "st:پهپادی:1"):
        db.kv_set(f"strike:{uid}", "0")
        out = await cb(uid, data)
        T(f"{data}", "CRASH" not in out, out)
    out = await cmd("جبهه", uid)
    T("جبهه", "امتیاز جبهه" in out, out)
    # اتحاد + کمک + صلح
    other = reg["ir"]
    db.ex("UPDATE users SET is_leader=1 WHERE uid=?", (other,))
    out = await cb(other, "ally:hz")
    T("پیشنهاد اتحاد", "اتحاد" in out, out)
    out = await cmd("قبول اتحاد حزب‌الله", other)
    T("قبول اتحاد", "اتحاد" in out, out)
    out = await cb(uid, "mn:helpally")
    T("کمک اتحاد (فیکس‌شده)", "اتحاد" in out or "جبهه" in out or "اتحادی" in out, out)
    out = await cmd("صلح", uid)
    T("درخواست صلح", "صلح" in out, out)
    out = await cmd("قبول صلح", other)
    T("قبول صلح", "صلح" in out or "جنگی نیست" in out, out)

    # ═══ ۷. سیاست کامل ═══
    out = await cmd("حزب میهن‌دوستان ملی", uid)
    T("تأسیس حزب", "حزب" in out, out)
    out = await cmd("احزاب", uid)
    T("احزاب", "حزب" in out or "حزبی" in out, out)
    out = await cmd("بیانیه ما برای آبادی می‌جنگیم", uid)
    T("بیانیه", "بیانیه" in out, out)
    out = await cb(uid, "spy:il")
    T("جاسوسی دکمه", "جاسوسی" in out or "CRASH" not in out and out != "", out)
    out = await cmd("شورش", reg["us"])
    T("شورش", out and "CRASH" not in out, out)

    # ═══ ۸. مأموریت + بازار سیاه + ارتقا + نبرد ═══
    out = await cmd("ماموریت", uid)
    T("ماموریت", "مأموریت" in out or "ماموریت" in out, out)
    out = await cmd("جایزه", uid)
    T("جایزه", out and "CRASH" not in out, out)
    out = await cmd("بازارسیاه", uid)
    T("بازارسیاه", "سیاه" in out, out)
    out = await cmd("خریدسیاه sejjil", uid)
    T("خریدسیاه", out and "CRASH" not in out, out)
    out = await cmd("ارتقا fajr5", uid)
    T("ارتقا متنی", out and "CRASH" not in out, out)
    out = await cb(uid, "up:fajr5")
    T("ارتقا دکمه", out and "CRASH" not in out, out)
    await cb(reg["ir"], "br:0")
    out = await cmd("نبرد علی", uid)
    T("نبرد چالش", "چالش" in out, out)
    out = await cmd("قبول نبرد", reg["ir"])
    T("قبول نبرد", "نبرد" in out or "چالش" in out or "سرباز" in out, out)

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
    out = await cmd("جنگ آمریکا", P3)
    T("جنگ غیررهبر", "رهبر" in out, out)
    out = await cmd("حمله موشکی", P3)
    T("حمله غیررهبر", "رهبر" in out, out)
    # بدون پول
    db.ex("UPDATE users SET money=0 WHERE uid=?", (reg["jp"],))
    out = await cb(reg["jp"], "wp:izumo")
    T("خرید بی‌پول", "پول کم" in out, out)
    # مهمات صفر
    db.ex("UPDATE users SET is_leader=1, money=999999 WHERE uid=?", (reg["kp"],))
    await cb(reg["kp"], "wp:hwasong")
    await cmd("جنگ کره‌ی جنوبی", reg["kp"])
    wid = db.one("SELECT id FROM wars WHERE status='active' AND a='kp'")["id"]
    db.kv_set(f"ammo:{wid}:kp", "0")
    db.kv_set(f"strike:{reg['kp']}", "0")
    out = await cmd("حمله موشکی", reg["kp"])
    T("مهمات صفر", "مهمات" in out, out)
    # کوول‌داون
    db.kv_set(f"ammo:{wid}:kp", "50")
    await cmd("حمله موشکی", reg["kp"])          # موج اول می‌رود
    db.kv_set(f"ammo:{wid}:kp", "50")
    out = await cmd("حمله موشکی", reg["kp"])     # بلافاصله → کوول‌داون
    T("کوول‌داون ۴۵ث", "۴۵" in out or "ثانیه" in out, out[:80])
    # جنگ دوم همزمان
    out = await cmd("جنگ ژاپن", reg["kp"])
    T("جنگ دوم بلاک", "درگیر" in out, out)

    # ═══ ۱۱. جهان/راهنما/اخبار برای هر ۲۱ کشور ═══
    for cid in countries.COUNTRIES:
        g = guide.guide(cid)
        T(f"guide:{cid}", "تخصص" in g and "راهبرد" in g, g[:80])
    out = await cmd("راهنما آمریکا", uid)
    T("راهنما آمریکا", "راهنمای آمریکا" in out, out)
    out = await cmd("قدرت", uid)
    T("قدرت کشورها", "قدرت نظامی" in out, out)
    out = await cmd("مستعمره‌ها", uid)
    T("مستعمره‌ها", "مستعمره" in out, out)
    out = await cmd("تسلیم", uid)
    T("تسلیم", out and "CRASH" not in out, out)
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

    # ═══ ۱۳. همه‌ی دستورهای متنی — کرش‌صفر ═══
    all_cmds = ["شروع", "منو", "پروفایل", "کارنامه", "کارت", "ارتشی", "سرباز",
                "تجهیزات", "زرادخانه", "خرید", "رزم", "جنگیدن", "استراحت", "درمان",
                "تعمیر", "جیره", "دستمزد", "احزاب", "عضویت x", "شورش", "جاسوسی",
                "جهان", "رتبه", "برترین", "نقشه", "بازار", "اقتصاد", "پدافند",
                "جبهه", "اخبار", "ارتش", "ماموریت", "مأموریت", "چالش", "جایزه",
                "بازارسیاه", "سیاه", "نبرد x", "صلح", "راهنما", "کمک",
                "تحویل", "اعزام", "رمزگشایی"]
    crash = []
    for c in all_cmds:
        out = await cmd(c, uid)
        if not out or "CRASH" in out:
            crash.append(c)
    T(f"دستورها ({len(all_cmds)})", not crash, crash)

    print(f"\n{'═' * 20} نتیجه {'═' * 20}")
    print(f"✅ موفق: {len(PASS)}")
    if FAIL:
        print(f"❌ خراب: {len(FAIL)}")
        for f in FAIL:
            print("  •", f)
        sys.exit(1)
    print("🎯 مگا-تست کامل سبز — صفر خطا")


asyncio.run(main())
