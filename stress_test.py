"""⚡ تست استرس — شبیه‌سازی گروه ۱۰هزار نفره با فعالیت سنگین.

هدف: تضمین بدون-تأخیر و بدون-کرش بودن ربات در مقیاس بالا.
هر مرحله زمان می‌گیرد؛ اگر از سقف گذشت → خطا.
"""
import asyncio
import random
import sys
import time

sys.path.insert(0, ".")
random.seed(7)

import db
db.init(":memory:")
import countries
countries.init_items()

import handlers
handlers.TEST_MODE = True
from game import economy, events, state, war


DONE, FAILS = [], []


def T(name, cond, detail=""):
    (DONE if cond else FAILS).append(name if cond else f"{name} — {str(detail)[:150]}")
    print(("✅" if cond else "❌") + " " + name + ("" if cond else f"  ← {str(detail)[:150]}"))


class U:
    def __init__(self, uid, name="P"):
        self.id, self.username, self.first_name = uid, "x", name


class Chat:
    def __init__(self):
        self.type, self.id = "supergroup", -100


class Msg:
    def __init__(self, text, uid, mid=1):
        self.text, self.from_user, self.chat = text, U(uid), Chat()
        self.message_id = mid
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
    _n = 0
    def __init__(self, uid, data):
        CB._n += 1
        self.data, self.from_user = data, U(uid)
        self.message = Msg("", uid, CB._n)
        self.answered = ""
    async def answer(self, txt=None, **kw):
        self.answered = txt or "ok"
        return True


ROUTE = {"ad": handlers.cb_admin, "cyp": handlers.cb_cy_page, "cy": handlers.cb_country,
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
         "tb": handlers.cb_tbuy, "ts": handlers.cb_tsell,
         "tct": handlers.cb_tcontract, "ct": handlers.cb_contract}


async def cb(uid, data):
    c = CB(uid, data)
    try:
        await ROUTE[data.split(":")[0]](c)
        return (c.message.out or "") + "|" + (c.answered or "")
    except Exception as e:
        return f"CRASH:{type(e).__name__}:{e}"


async def main():
    t0 = time.time()

    # ═══ ۱) پرکردن دنیا با ۱۰٬۰۰۰ کاربر ═══
    cids = list(countries.COUNTRIES.keys())
    for i in range(10_000):
        db.ex("INSERT OR IGNORE INTO users(uid,name,money,joined,last_active) "
              "VALUES(?,?,?,?,?)",
              (5000 + i, f"P{i}", 100000 if i < 50 else 1000, db.now(), db.now()))
    n = db.one("SELECT COUNT(*) n FROM users")["n"]
    T("۱۰هزار کاربر در دیتابیس", n == 10_000, n)

    # ═══ ۲) ۵۰ ثبت‌نام هم‌زمان روی ۵۰ کشور — بدون قفلِ دوباره ═══
    async def reg(i):
        return await cb(5000 + i, f"cy:{cids[i]}")
    t = time.time()
    outs = await asyncio.gather(*(reg(i) for i in range(50)))
    dt = time.time() - t
    T("۵۰ ثبت‌نام هم‌زمان < ۲ث", dt < 2, f"{dt:.2f}s")
    T("ثبت‌نام‌ها موفق", all("ثبت‌نام تکمیل شد" in o for o in outs),
      [o[:60] for o in outs if "ثبت‌نام" not in o][:3])
    # دوباره زدن همان کشورها توسط دیگران → بلاک
    async def reg2(i):
        return await cb(9500 + i, f"cy:{cids[i]}")
    outs2 = await asyncio.gather(*(reg2(i) for i in range(50)))
    T("کشورهای قفل‌شده دوباره بلاک", all("گرفته شده" in o or "قبلاً" in o for o in outs2),
      [o[:60] for o in outs2 if "گرفته" not in o and "قبلاً" not in o][:3])

    # ═══ ۳) ۵۰۰ دکمه‌ی منو هم‌زمان — مخلوط بازیکن و مهمان ═══
    jobs = []
    for i in range(500):
        uid = 5000 + (i % 10_000)
        jobs.append(cb(uid, "mn:main"))
        jobs.append(cb(uid, "mn:mil" if i % 2 else "mn:trade"))
    t = time.time()
    outs = await asyncio.gather(*jobs)
    dt = time.time() - t
    T("۱۰۰۰ دکمه‌ی منو هم‌زمان < ۵ث", dt < 5, f"{dt:.2f}s")
    T("بدون کرش در منوها", not any(o.startswith("CRASH") for o in outs),
      [o[:80] for o in outs if o.startswith("CRASH")][:3])

    # ═══ ۴) جنگ سنگین: دو کشور + ۲۰۰ حمله و ۲۰۰ خرید هم‌زمان ═══
    await cb(5000, "dwr:" + cids[1])           # رهبر کشور ۰ → کشور ۱
    for iid in (countries.COUNTRIES[cids[0]]["items"]):
        await cb(5000, f"wp:{iid}")
        await cb(5000, f"wp:{iid}")
    db.kv_set(f"strike:{5000}", "0")
    jobs = []
    for i in range(100):
        jobs.append(cb(5000, f"st:موشکی:{(i % 5) + 1}"))
        jobs.append(cb(5000, "tb:wheat:5"))
        jobs.append(cb(5000, "dl:"))
    t = time.time()
    outs = await asyncio.gather(*jobs)
    dt = time.time() - t
    T("۴۰۰ عملیات جنگ و تجارت هم‌زمان < ۶ث", dt < 6, f"{dt:.2f}s")
    T("بدون کرش در جنگ و تجارت", not any(o.startswith("CRASH") for o in outs),
      [o[:80] for o in outs if o.startswith("CRASH")][:3])

    # ═══ ۵) ۳۰۰ پیام متنی هم‌زمان — منو و هرزه ═══
    async def word(i):
        m = Msg("منو" if i % 5 == 0 else f"چرت و پرت {i}", 6000 + (i % 9_000))
        await handlers.fa_words(m)
        return m.out
    t = time.time()
    outs = await asyncio.gather(*(word(i) for i in range(300)))
    dt = time.time() - t
    T("۳۰۰ پیام متنی هم‌زمان < ۳ث", dt < 3, f"{dt:.2f}s")

    # ═══ ۶) رویداد گروهی: ۲۰۰ نفر هم‌زمان می‌زنند — فقط یک برنده ═══
    db.kv_set("ev_last:-100", "0")
    ev = events.maybe_event(-100)
    T("رویداد ساخته شد", bool(ev), ev)
    if ev:
        word = ev[1]
        outs = await asyncio.gather(*(cb(7000 + i, f"evc:{word}") for i in range(200)))
        winners = [o for o in outs if "برنده" in o or "اعزام" in o]
        T("فقط یک برنده در هجوم ۲۰۰ نفره", len(winners) == 1, len(winners))
        T("بدون کرش در هجوم رویداد", not any(o.startswith("CRASH") for o in outs))

    # ═══ ۷) پرس‌وجوهای سنگین روی ۱۰هزار کاربر ═══
    from game import ai, military, politics
    t = time.time()
    for _ in range(20):
        war.power_rank()
        war.leaderboard()
        ai.news_feed()
        economy.market()
        military.arsenal(5000)
        politics.spy(5000, cids[1])
    dt = time.time() - t
    T("۱۲۰ پرس‌وجوی سنگین < ۴ث", dt < 4, f"{dt:.2f}s")

    # ═══ ۸) رشد kv کرشدار — منوهای تکراری ═══
    kv0 = db.one("SELECT COUNT(*) n FROM kv")["n"]
    for i in range(50):
        m = Msg("منو", 8000 + i, mid=10_000 + i)
        await handlers.fa_words(m)
    kv1 = db.one("SELECT COUNT(*) n FROM kv")["n"]
    T("حافظه‌ی منو کرشدار (+~۱۰۰ در ۵۰ منو)", kv1 - kv0 <= 120, f"{kv0}→{kv1}")

    # ═══ ۹) قفل منو زیر بار — ۲۰۰ دکمه از غیرصاحب ═══
    db.kv_set("mown:-100:778899", "5000")
    locked = sum(1 for i in range(200)
                 if "منوی" in handlers._menu_locked(_LK(i)) )
    T("قفل منو ۲۰۰ بار پایدار", locked == 200, locked)
    db.kv_set("mown:-100:778899", "")

    # ═══ ۱۰) پیام ورود گروه — یک بار + پین ═══
    class _FBot:
        def __init__(s):
            s.sent, s.pinned = [], []
        async def send_message(s, gid, txt, **kw):
            s.sent.append(txt)
            class _M:
                message_id = 1
            return _M()
        async def pin_chat_message(s, gid, mid, **kw):
            s.pinned.append(mid)
    fb = _FBot()
    GID = -(920000 + db.now() % 9000)
    db.kv_set(f"joined:{GID}", "")
    for _ in range(5):
        await handlers._group_hello(fb, GID, "TestBot")
    T("پیام ورود فقط یک بار", len(fb.sent) == 1, len(fb.sent))
    T("پیام ورود پین شد", fb.pinned == [1], fb.pinned)
    T("متن ورود درست", "کشورت را انتخاب" in fb.sent[0] and "رهبر" in fb.sent[0])

    print(f"\n═══ استرس: {len(DONE)} ✓ | {len(FAILS)} ✗ | کل {time.time() - t0:.1f}s ═══")
    for f in FAILS:
        print("  ❌", f)
    sys.exit(1 if FAILS else 0)


class _LK:
    """شبیه کالبک غیرصاحب منو."""
    def __init__(self, i):
        self.data, self.from_user = "mn:main", U(60000 + i)
        class M:
            chat, message_id = Chat(), 778899
        self.message = M()


asyncio.run(main())
