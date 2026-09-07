# -*- coding: utf-8 -*-
"""🔄 ریست بزرگ v35 — فقط کشورِ بازیکنان می‌ماند؛ همه‌چیز از صفر با ۱٬۰۰۰ دلار."""
import contextlib

import db


def _reset_world():
    """ریست یک دنیا — بازیکنان کشوردار فقط کشور و نامشان را نگه می‌دارند."""
    with contextlib.suppress(Exception):
        # ۱) تازه‌واردهای بی‌کشور حذف
        db.ex("DELETE FROM users WHERE country IS NULL OR country = ''")
        # ۲) بازیکنان کشوردار: تازه‌ساز — فقط کشور و نام می‌ماند
        db.ex("UPDATE users SET money=1000, level=1, xp=0, rank=1, "
              "hp=100, max_hp=100, kills=0, spy_ops=0, branch=NULL, "
              "party_id=NULL, last_active=?", (db.now(),))
        # ۳) دارایی‌ها، جنگ‌ها، سیاست و اخبار — پاک
        for t in ("inventory", "wars", "alliances", "parties",
                  "statements", "spyops", "defense", "news", "logs"):
            db.ex(f"DELETE FROM {t}")
        # ۴) کلیدهای کهنه (منو، دارایی، اقتصاد، رویداد) — پاک
        db.ex("DELETE FROM kv")
        db.kv_set("reset_v35", "1")


def run_all():
    """در بوت روی همه‌ی دنیاها — فقط یک بار برای هر دنیا."""
    for g in db.list_games():
        db.GAME.set(g)
        if not db.kv_get("reset_v35"):
            _reset_world()
    db.GAME.set(None)
