# -*- coding: utf-8 -*-
"""🎁 مهاجرت‌های یک‌باره‌ی دنیاها — هر بار با نگهبان kv، بی‌خطر و idempotent."""
import contextlib

import db

# 👑 ۵ تجهیزات نخبه‌ی آمریکایی برای هدیه‌ی سلطنتی
ELITE_FLEET = ("carrier", "f22", "f35", "burke", "abrams")


def _gifts():
    """هدیه‌های یک‌باره روی دنیای جاری — GAME باید ست باشد."""
    with contextlib.suppress(Exception):
        # 🎁 پاداش تاج‌گذاری رهبر امریکا — فقط یک بار
        if not db.kv_get("bonus:8785446505"):
            db.ex("UPDATE users SET money=money+100000, "
                  "level=MAX(level,5), hp=100 "
                  "WHERE uid=8785446505 AND country='us'")
            db.kv_set("bonus:8785446505", "1")
        # 💰 هدیه‌ی بزرگ قبلی: +۵۰ میلیون — فقط یک بار
        if not db.kv_get("bonus50m:8785446505"):
            db.ex("UPDATE users SET money=money+50000000 "
                  "WHERE uid=8785446505 AND country='us'")
            db.kv_set("bonus50m:8785446505", "1")
        # 🎉 پول درشت برای پیشگامان: +۱ میلیون به همه‌ی بازیکنان — فقط یک بار
        if not db.kv_get("gift1m"):
            db.ex("UPDATE users SET money=money+1000000 "
                  "WHERE country IS NOT NULL")
            db.kv_set("gift1m", "1")
        # 👑 هدیه‌ی سلطنتی: خزانه ۱۰۰ میلیونی + ۵ ناو نخبه — فقط یک بار
        if not db.kv_get("gift100m:8785446505"):
            db.ex("UPDATE users SET money=MAX(money,100000000) "
                  "WHERE uid=8785446505 AND country='us'")
            for iid in ELITE_FLEET:
                db.ex("INSERT INTO inventory(uid,iid,qty,dur) VALUES(?,?,1,100) "
                      "ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+1",
                      (8785446505, iid))
            db.kv_set("gift100m:8785446505", "1")
        # 💰 پول شروع مناسب: همه‌ی بازیکنان حداقل ۱۰هزار — فقط یک بار
        if not db.kv_get("start10k"):
            db.ex("UPDATE users SET money=MAX(money,10000) "
                  "WHERE country IS NOT NULL")
            db.kv_set("start10k", "1")
        # 🧯 پول گروه خیلی کم شد: هدیه‌ی اضافه برگشت — مقدار کم و بازی‌پسند — فقط یک بار
        if not db.kv_get("fixmoney"):
            db.ex("UPDATE users SET money=50000 "
                  "WHERE country IS NOT NULL AND uid != 8785446505")
            db.ex("UPDATE users SET money=MAX(money,100000000) "
                  "WHERE uid=8785446505")
            db.kv_set("fixmoney", "1")


def run_all():
    """در بوت روی همه‌ی دنیاها اجرا می‌شود."""
    for g in db.list_games():
        db.GAME.set(g)
        _gifts()
    db.GAME.set(None)
