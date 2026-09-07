"""🧪 جنگ جهانی — تست انتها-به-انتها: همه‌ی مسیرها بدون کرش."""
import asyncio
import random
import sys

sys.path.insert(0, ".")
random.seed(42)

import db
db.init(":memory:")
import countries
countries.init_items()

import handlers
handlers.TEST_MODE = True  # noqa — ثبت router
from game import economy, events, geo, military, politics, state, war

DONE, FAILS = 0, []


class U:
    def __init__(self, uid, name):
        self.id, self.username, self.first_name = uid, f"u{uid}", name


class Chat:
    def __init__(self, ct="supergroup", cid=-100):
        self.type, self.id = ct, cid


SENT = []


class M:
    def __init__(self, text, uid=1, name="امیر", ct="supergroup", cid=-100):
        self.text, self.from_user, self.chat = text, U(uid, name), Chat(ct, cid)
        self.message_id = 1

    async def answer(self, txt, **kw):
        SENT.append(txt)
        return self

    async def answer_photo(self, photo, caption=None, **kw):
        SENT.append(caption or "")
        return self


class CB:
    def __init__(self, data, uid=1, name="امیر"):
        self.data, self.from_user = data, U(uid, name)
        self.message = M("cb", uid, name)

    async def answer(self, txt=None, **kw):
        SENT.append(txt or "")
        return self


class CBMsg:
    """message با edit_text/edit_reply_markup"""
    def __init__(self, m):
        self._m = m
        self.chat = m.chat

    async def edit_text(self, txt, **kw):
        SENT.append(txt)
        return self

    async def edit_reply_markup(self, reply_markup=None, **kw):
        return self

    async def delete(self):
        return self

    async def answer(self, txt, **kw):
        SENT.append(txt)
        return self


def wrap_cb(data, uid=1, name="امیر"):
    c = CB(data, uid, name)
    c.message = CBMsg(M("cb", uid, name))
    return c


async def run(kind, tag, coro):
    global DONE
    try:
        await coro
        DONE += 1
    except Exception as e:
        FAILS.append((kind, tag, traceback_str(e)))
        print(f"✗ {kind} «{tag}»: {e}")


def traceback_str(e):
    import traceback
    return traceback.format_exc()[-200:]


async def main():
    # ═══ ۱) شروع و ثبت‌نام ═══
    await run("msg", "شروع", handlers.fa_words(M("شروع", 1, "امیر")))
    await run("cb", "cy:ir", handlers.cb_country(wrap_cb("cy:ir", 1)))
    await run("cb", "cy:us", handlers.cb_country(wrap_cb("cy:us", 2, "John")))
    await run("cb", "cy:ru", handlers.cb_country(wrap_cb("cy:ru", 3, "Ivan")))
    await run("msg", "شروع دوباره", handlers.fa_words(M("شروع", 1)))

    # ═══ ۲) منوها ═══
    for what in ("main", "mil", "pol", "world", "me", "help", "battle", "rest",
                 "arsenal", "repair", "ration", "branch", "parties", "rebel",
                 "stmt", "spy", "ally", "war", "wstat", "lb", "market", "map"):
        await run("cb", f"mn:{what}", handlers.cb_menu(wrap_cb(f"mn:{what}", 1)))

    # ═══ ۳) نظامی ═══
    db.ex("UPDATE users SET money=999999 WHERE uid=1")
    await run("cb", "br:1 سپاه", handlers.cb_branch(wrap_cb("br:1", 1)))
    for iid in ("sejjil", "shahed", "dhow"):
        await run("cb", f"wp:{iid}", handlers.cb_buy(wrap_cb(f"wp:{iid}", 1)))
    for what in ("battle", "rest", "repair", "ration", "quest", "black", "duel",
                 "wstat", "power", "colonies", "front", "army", "def", "cguide",
                 "news", "upgrade", "peace", "helpally"):
        await run("cb", f"mn:{what}", handlers.cb_menu(wrap_cb(f"mn:{what}", 1)))
    await run("msg", "رزم", handlers.fa_words(M("رزم", 1)))
    await run("msg", "رزم دوباره", handlers.fa_words(M("رزم", 1)))

    # ═══ ۴) سیاست ═══
    await run("msg", "حزب", handlers.fa_words(M("حزب", 1)))
    await run("msg", "حزب+نام", handlers.fa_words(M("حزب میهن‌دوستان ملی", 1)))
    await run("msg", "احزاب", handlers.fa_words(M("احزاب", 1)))
    await run("msg", "عضویت", handlers.fa_words(M("عضویت میهن‌دوستان", 2, "John")))
    await run("msg", "بیانیه", handlers.fa_words(M("بیانیه ما برای آبادی میهن می‌جنگیم", 1)))
    await run("msg", "شورش", handlers.fa_words(M("شورش", 1)))
    await run("msg", "جاسوسی", handlers.fa_words(M("جاسوسی", 1)))
    await run("cb", "spy:us", handlers.cb_spy(wrap_cb("spy:us", 1)))
    db.kv_set("spy:1", "0")
    await run("cb", "spy:us دوباره", handlers.cb_spy(wrap_cb("spy:us", 1)))

    # ═══ ۵) جنگ و اتحاد و اقتصاد ═══
    db.ex("UPDATE users SET is_leader=1 WHERE uid IN (1,2,3)")
    await run("msg", "اتحاد", handlers.fa_words(M("اتحاد روسیه", 1)))
    await run("msg", "قبول اتحاد", handlers.fa_words(M("قبول اتحاد ایران", 3, "Ivan")))
    await run("msg", "جنگ آمریکا", handlers.fa_words(M("جنگ آمریکا", 1)))
    for k in ("موشکی", "هوایی", "دریایی", "زمینی", "پهپادی"):
        db.kv_set("strike:1", "0")
        await run("cb", f"st:{k}", handlers.cb_strike(wrap_cb(f"st:{k}", 1)))
    await run("msg", "حمله موشکی", handlers.fa_words(M("حمله موشکی", 1)))
    await run("msg", "کمک", handlers.fa_words(M("کمک", 1)))
    await run("msg", "تحریم", handlers.fa_words(M("تحریم روسیه", 2, "John")))
    await run("msg", "تنگه هرمز", handlers.fa_words(M("تنگه هرمز", 1)))
    await run("msg", "بازار", handlers.fa_words(M("بازار", 1)))
    await run("msg", "جهان", handlers.fa_words(M("جهان", 1)))
    await run("msg", "رتبه", handlers.fa_words(M("رتبه", 1)))
    await run("msg", "نقشه", handlers.fa_words(M("نقشه", 1)))

    # ═══ ۶) رویداد گروهی ═══
    for w in ("تحویل", "اعزام", "رمزگشایی"):
        await run("msg", w, handlers.fa_words(M(w, 1)))

    # ═══ ۷) ورودی‌های خراب ═══
    for t in ("جنگ چرت", "جاسوسی فلان", "عضویت هیچ", "حزب", "بیانیه", "خرید",
              "حمله لاله", "تنگه مریخ", "قبول هیچ", "اتحاد", "۱۲۳", "!!!",
              "<script>alert(1)</script>", "منو منو منو"):
        await run("msg", f"خراب:{t[:12]}", handlers.fa_words(M(t, 9, "ناشناس")))

    # ═══ ۸) بازیکن بدون ثبت‌نام ═══
    for t in ("رزم", "تجهیزات", "حزب تستی", "احزاب", "جاسوسی", "جنگ آمریکا",
              "نقشه", "تعمیر", "جیره"):
        await run("msg", f"بی‌ثبت:{t[:10]}", handlers.fa_words(M(t, 99, "مهمان")))

    # ═══ ۹. دور هفتم: تجارت، درآمد رایگان، رویداد دکمه‌ای ═══
    await run("cb", "dl:", handlers.cb_daily(wrap_cb("dl:", 1)))
    await run("cb", "wk:", handlers.cb_work(wrap_cb("wk:", 1)))
    for what in ("trade", "howto", "events"):
        await run("cb", f"mn:{what}", handlers.cb_menu(wrap_cb(f"mn:{what}", 1)))
    for data in ("tb:wheat:5", "tb:gold:1", "tb:چرت:1"):
        await run("cb", data, handlers.cb_tbuy(wrap_cb(data, 1)))
    for data in ("ts:wheat:5", "ts:oil:1"):
        await run("cb", data, handlers.cb_tsell(wrap_cb(data, 1)))
    await run("cb", "tct:", handlers.cb_tcontract(wrap_cb("tct:", 1)))
    await run("cb", "ct:de", handlers.cb_contract(wrap_cb("ct:de", 1)))
    db.kv_set("ev_last:-100", "0")
    ev = events.maybe_event(-100)
    if ev:
        await run("cb", f"evc:{ev[1]}", handlers.cb_evc(wrap_cb(f"evc:{ev[1]}", 1)))
        await run("cb", f"evc دوباره", handlers.cb_evc(wrap_cb(f"evc:{ev[1]}", 2, "John")))
    await run("cb", "ad:callup غیرمالک", handlers.cb_admin(wrap_cb("ad:callup", 1)))
    await run("cb", "ad:reg غیرمالک", handlers.cb_admin(wrap_cb("ad:reg", 1)))

    # ═══ گزارش ═══
    print(f"\n═══ نتیجه‌ی E2E ═══")
    print(f"موفق: {DONE} | کرش: {len(FAILS)}")
    for kind, tag, tb in FAILS[:8]:
        print(f"  ✗ {kind} «{tag}»\n    {tb}")


asyncio.run(main())
