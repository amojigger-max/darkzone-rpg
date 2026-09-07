"""Explicit, idempotent post-install rollout. No network call; new runtime drains the outbox."""
import config
import db
import migrations
from game import notifications,rewards,infra

RELEASE_ID='v4111-verified-payout-storage-20260907'

SUMMARY='''🎮 <b>خلاصهٔ دارک‌زون و آپدیت ۴۱٫۱٫۱</b>
مدیریت کشور با بازیکنان واقعی: اقتصاد، تجهیزات، شهرها، پایگاه‌ها، رفاه و دیپلماسی؛ بدون ارتش یا دولت NPC.

⚔️ چهار نوع جنگ چندمرحله‌ای؛ اخطار، تدارکات، تخریب زیرساخت، محاصره، تصرف تدریجی و تثبیت. حملهٔ اول کشور را تسلیم نمی‌کند.
🧭 عملیات با اسم دلخواه و چهار دکترین؛ آماده‌سازی یک ساعت و مزیت محدود ۱۰٪ برای شش موج.
🗺 مرز زمینی، پهنهٔ برد، پایگاه متحد، دریا و سرپل رعایت می‌شود. موشک: ۳ در نوبت، ۶ در ساعت و ۲۰ در جنگ؛ رهگیری تضمینی و صددرصدی نداریم.
🏙 ساخت پایگاه در شهر دلخواه، زمان ساخت، خرابی، اشغال، تعمیر و بازپس‌گیری.
💰 تجارت و سرمایه‌گذاری دو انبار مستقل دارند؛ نفت تجاری دکل نفت نیست. خرید و فروش تراکنشی و دارای موجودی واقعی بازار است.
🚫 دکمهٔ وضع و لغو تحریم جدا؛ هر کشور فقط تحریم خودش را لغو می‌کند، یا قطعنامهٔ معتبر جمعی اجرا می‌شود.
🌉 کنترل و صندوق تنگه‌ها مستقل و متعلق به کشور تعیین‌شده است؛ آلمان نمی‌تواند هرمز را ببندد یا عوارض ایران را بردارد.
🇺🇳 سازمان ملل با رأی واقعی کشورها، کمک از صندوق، بازبینی تحریم و آتش‌بس با رضایت دو طرف.

🎁 پاداش یک‌بارهٔ جدید: سایر بازیکنان ۳۰٬۰۰۰ دلار؛ آیدی مشخص‌شدهٔ آمریکا مجموعاً ۸۰٬۰۰۰ + پنج تجهیز و بهترین پدافند؛ آیدی مالک ایران مجموعاً ۹۰٬۰۰۰ + ده تجهیز. اینها جایگزین وعده‌های نقدی قبلی‌اند؛ موجودی آغازین جداست. حساب بدون کشور بعد از انتخاب کشور واجد شرایط پاداش می‌گیرد؛ جزئیات از /gifts.

⚡ تازه: نیروگاه شهری، پالایشگاه، مخزن سوخت، پایگاه موشکی و پدافند، مرکز فرماندهی و کشتی‌سازی؛ ساخت زمان‌دار و اثر واقعی در قواعد بازی.
🚢 نفت‌کش‌های نام‌گذاری‌شده، بار واقعی، پذیرش خریدار و پول امانی؛ مسیر و بسته‌شدن تنگه، اسکورت، آسیب، بازپرداخت و بازگشت کشتی ثبت می‌شوند.
⛽ تخریب نیروگاه برق و پدافند را ضعیف می‌کند؛ مخزنِ آسیب‌دیده ذخیرهٔ همان شهر را از دست می‌دهد. سوخت عملیات باید واقعاً موجود باشد.
📦 تازه: پر بودن زرادخانه پرداخت نقدی را متوقف نمی‌کند؛ تجهیزات اضافی در ذخیرهٔ هدایا محفوظ‌اند و با تأیید جداگانه می‌توان جا آزاد کرد.
💾 بررسی ذخیره پیش از اجرا سخت‌گیرانه‌تر شده؛ فایل قدیمی روی دادهٔ تازه بازنویسی نمی‌شود.
📖 راهنمای ۱۶صفحه‌ای شامل قیمت‌ها، شاخص دلار، تورم و انرژیِ مجازی: /help
/menu · /cities · /operations · /un · /straits · /trade · /energy · /fleet
📣 تگ‌ها حذف نمی‌شوند؛ پیام بلند در چند بخش فرستاده می‌شود.'''


def apply(game_id,*,confirmed=False):
    if not confirmed:raise PermissionError('explicit post-install rollout confirmation required')
    with db.world(game_id):
        if db.kv_get(f'release:{RELEASE_ID}'):return {'game':game_id,'changed':False}
        backup,digest=migrations.backup_world(game_id,RELEASE_ID)
        with db.transaction():
            for r in db.q("SELECT DISTINCT country FROM users WHERE country IS NOT NULL"):
                from game import geo
                if r["country"] in geo.CITIES:infra.ensure(r["country"])
            grants=rewards.award_all_existing()
            ids=[r['uid'] for r in db.q('SELECT uid FROM users ORDER BY uid')]
            notifications.emit(SUMMARY,uids=ids,key=f'release:{RELEASE_ID}')
            db.kv_set(f'release:{RELEASE_ID}',db.now())
            db.kv_set('installed_release',config.VERSION)
            db.audit('release_rollout',config.OWNER_ID,version=config.VERSION,backup_sha256=digest,grants=grants)
        return {'game':game_id,'changed':True,'grant_records_paid':grants,'recipients':len(ids),'backup':backup,'sha256':digest,'announcement':'queued, not claimed delivered'}
