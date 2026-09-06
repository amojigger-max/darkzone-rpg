"""🗺 جنگ جهانی — ۲۰ کشور: تجهیزات و شاخه‌های نظامی مخصوص هر کشور."""
import db

# cid → تعریف کامل کشور
COUNTRIES = {
    "ir": dict(flag="🇮🇷", name="ایران", eco=3, mil=4, tech=4,
               branches=["ارتش جمهوری اسلامی", "سپاه پاسداران", "بسیج مردمی"],
               items=["sejjil", "shahed", "dhow"]),
    "us": dict(flag="🇺🇸", name="آمریکا", eco=5, mil=5, tech=5,
               branches=["ارتش آمریکا", "مارینز", "نیروی دلتا"],
               items=["f35", "abrams", "carrier"]),
    "ru": dict(flag="🇷🇺", name="روسیه", eco=3, mil=5, tech=4,
               branches=["ارتش روسیه", "اسپتس‌ناز", "گروه واگنر"],
               items=["s400", "t90", "yasen"]),
    "cn": dict(flag="🇨🇳", name="چین", eco=5, mil=4, tech=4,
               branches=["PLA", "نیروی موشکی", "نیروی دریایی"],
               items=["j20", "shandong", "df21"]),
    "de": dict(flag="🇩🇪", name="آلمان", eco=5, mil=3, tech=5,
               branches=["بوندس‌ور", "کماندو", "نیروی زرهی"],
               items=["leopard", "u212", "puma"]),
    "gb": dict(flag="🇬🇧", name="بریتانیا", eco=4, mil=4, tech=5,
               branches=["ارتش بریتانیا", "SAS", "نگ سلطنتی"],
               items=["challenger", "astute", "typhoon"]),
    "fr": dict(flag="🇫🇷", name="فرانسه", eco=4, mil=4, tech=5,
               branches=["ارتش فرانسه", "لژیون خارجی", "ناوبری"],
               items=["rafale", "degaulle", "leclerc"]),
    "tr": dict(flag="🇹🇷", name="ترکیه", eco=3, mil=4, tech=4,
               branches=["ارتش ترکیه", "کماندو کوهستان", "نیروی بوزقورت"],
               items=["bayraktar", "altay", "anadolu"]),
    "il": dict(flag="🇮🇱", name="اسرائیل", eco=3, mil=4, tech=5,
               branches=["IDF", "سایرت متکال", "موساد"],
               items=["iron_dome", "merkava", "f16i"]),
    "kp": dict(flag="🇰🇵", name="کره‌ی شمالی", eco=1, mil=4, tech=2,
               branches=["ارتش خلق", "گارد مرزی", "نیروی ویژه"],
               items=["hwasong", "m1989", "sub_yono"]),
    "kr": dict(flag="🇰🇷", name="کره‌ی جنوبی", eco=4, mil=4, tech=5,
               branches=["ارتش کره", "نیروی ویژه ROK", "تفنگداران"],
               items=["k2", "k9", "kf21"]),
    "jp": dict(flag="🇯🇵", name="ژاپن", eco=5, mil=3, tech=5,
               branches=["نیروی دفاع‌خود", "نیروی دریایی", "نیروی هوایی"],
               items=["izumo", "soryu", "type10"]),
    "in": dict(flag="🇮🇳", name="هند", eco=4, mil=4, tech=3,
               branches=["ارتش هند", "نیروی کوهستانی", "کماندو پارا"],
               items=["brahmos", "vikrant", "arjun"]),
    "pk": dict(flag="🇵🇰", name="پاکستان", eco=2, mil=4, tech=3,
               branches=["ارتش پاکستان", "SSG", "نیروی مرزی"],
               items=["jf17", "al_khalid", "babur"]),
    "sa": dict(flag="🇸🇦", name="عربستان", eco=4, mil=3, tech=3,
               branches=["ارتش سعودی", "گارد سلطنتی", "نیروی هوایی"],
               items=["patriot_sa", "f15sa", "al_hazm"]),
    "ae": dict(flag="🇦🇪", name="امارات", eco=4, mil=3, tech=4,
               branches=["ارتش امارات", "گارد ریاست", "نیروی تدخل"],
               items=["wing_loong", "leclerc_ae", "ghanthaq"]),
    "iq": dict(flag="🇮🇶", name="عراق", eco=2, mil=2, tech=2,
               branches=["ارتش عراق", "الحشد الشعبی", "نیروی ضدترور"],
               items=["m1_iq", "ptrs", "ababil"]),
    "sy": dict(flag="🇸🇾", name="سوریه", eco=1, mil=2, tech=2,
               branches=["ارتش عربی", "ببرها", "نیروی دفاع ملی"],
               items=["t72_sy", "pantir", "mig23"]),
    "ua": dict(flag="🇺🇦", name="اوکراین", eco=2, mil=4, tech=3,
               branches=["ارتش اوکراین", "آزوف", "نیروی پدافند"],
               items=["neptune", "bayraktar_ua", "olhant"]),
    "it": dict(flag="🇮🇹", name="ایتالیا", eco=4, mil=3, tech=4,
               branches=["ارتش ایتالیا", "کول موسرین", "برساگلیری"],
               items=["cavour", "aries", "freccia"]),
}

# iid → مشخصات تجهیزات (فقط همان کشور می‌تواند بخرد — منحصربه‌فرد)
ITEMS = {
    # 🇮🇷
    "sejjil": ("موشک سجیل", "🚀", "ir", 42, 8, 5200, "sejjil.jpg"),
    "shahed": ("پهپاد شاهد-۱۳۶", "🛩", "ir", 30, 6, 2600, "shahed.jpg"),
    "dhow": ("قایق تندرو", "🚤", "ir", 18, 14, 1400, "dhow.jpg"),
    # 🇺🇸
    "f35": ("جنگنده F-35", "✈️", "us", 48, 20, 8000, "f35.jpg"),
    "abrams": ("تانک ابرامز", "🚜", "us", 36, 30, 5000, "abrams.jpg"),
    "carrier": ("ناو نیمیتز", "🚢", "us", 50, 44, 9500, "carrier.jpg"),
    # 🇷🇺
    "s400": ("پدافند S-400", "🛡", "ru", 12, 52, 6000, "s400.jpg"),
    "t90": ("تانک T-90", "🚜", "ru", 34, 28, 4200, "t90.jpg"),
    "yasen": ("زیردریایی یاسن", "🤿", "ru", 46, 36, 8800, "yasen.jpg"),
    # 🇨🇳
    "j20": ("جنگنده J-20", "✈️", "cn", 44, 22, 7000, "j20.jpg"),
    "shandong": ("ناو شاندونگ", "🚢", "cn", 42, 40, 8500, "shandong.jpg"),
    "df21": ("موشک DF-21", "🚀", "cn", 40, 10, 5400, "df21.jpg"),
    # 🇩🇪
    "leopard": ("تانک لئوپارد ۲", "🚜", "de", 35, 30, 4800, "leopard.jpg"),
    "u212": ("زیردریایی ۲۱۲", "🤿", "de", 38, 34, 6800, "u212.jpg"),
    "puma": ("زرهی پوما", "🛻", "de", 22, 26, 3200, "puma.jpg"),
    # 🇬🇧
    "challenger": ("تانک چلنجر ۳", "🚜", "gb", 34, 32, 4900, "challenger.jpg"),
    "astute": ("زیردریایی آستیوت", "🤿", "gb", 40, 33, 7200, "astute.jpg"),
    "typhoon": ("جنگنده تایفون", "✈️", "gb", 42, 20, 6600, "typhoon.jpg"),
    # 🇫🇷
    "rafale": ("جنگنده رافال", "✈️", "fr", 43, 21, 6900, "rafale.jpg"),
    "degaulle": ("ناو شارل دوگل", "🚢", "fr", 41, 38, 8200, "degaulle.jpg"),
    "leclerc": ("تانک لکلرک", "🚜", "fr", 33, 29, 4600, "leclerc.jpg"),
    # 🇹🇷
    "bayraktar": ("پهپاد بایراکتار", "🛩", "tr", 32, 8, 3400, "bayraktar.jpg"),
    "altay": ("تانک آلتای", "🚜", "tr", 31, 27, 4000, "altay.jpg"),
    "anadolu": ("ناو آنادولو", "🚢", "tr", 38, 35, 7400, "anadolu.jpg"),
    # 🇮🇱
    "iron_dome": ("گنبد آهنین", "🛡", "il", 8, 50, 6400, "iron_dome.jpg"),
    "merkava": ("تانک مرکاوا", "🚜", "il", 34, 31, 5000, "merkava.jpg"),
    "f16i": ("جنگنده F-16I", "✈️", "il", 41, 19, 6200, "f16i.jpg"),
    # 🇰🇵
    "hwasong": ("موشک هواسونگ", "🚀", "kp", 45, 6, 4800, "hwasong.jpg"),
    "m1989": ("توپخانه Koksan", "💥", "kp", 28, 12, 2400, "m1989.jpg"),
    "sub_yono": ("زیردریایی یونو", "🤿", "kp", 22, 20, 3000, "yono.jpg"),
    # 🇰🇷
    "k2": ("تانک K2 پلنگ", "🚜", "kr", 36, 30, 5100, "k2.jpg"),
    "k9": ("توپخانه K9", "💥", "kr", 30, 14, 3600, "k9.jpg"),
    "kf21": ("جنگنده KF-21", "✈️", "kr", 40, 20, 6300, "kf21.jpg"),
    # 🇯🇵
    "izumo": ("ناو ایزومو", "🚢", "jp", 39, 37, 7600, "izumo.jpg"),
    "soryu": ("زیردریایی سوریو", "🤿", "jp", 37, 33, 6700, "soryu.jpg"),
    "type10": ("تانک تایپ ۱۰", "🚜", "jp", 33, 28, 4500, "type10.jpg"),
    # 🇮🇳
    "brahmos": ("موشک برهموس", "🚀", "in", 43, 9, 5600, "brahmos.jpg"),
    "vikrant": ("ناو ویکرانت", "🚢", "in", 37, 34, 7000, "vikrant.jpg"),
    "arjun": ("تانک آرجون", "🚜", "in", 30, 28, 3900, "arjun.jpg"),
    # 🇵🇰
    "jf17": ("جنگنده JF-17", "✈️", "pk", 33, 16, 4200, "jf17.jpg"),
    "al_khalid": ("تانک الحضر", "🚜", "pk", 29, 26, 3500, "al_khalid.jpg"),
    "babur": ("موشک بابر", "🚀", "pk", 38, 8, 4400, "babur.jpg"),
    # 🇸🇦
    "patriot_sa": ("پدافند پاتریوت", "🛡", "sa", 10, 48, 6100, "patriot.jpg"),
    "f15sa": ("جنگنده F-15SA", "✈️", "sa", 42, 22, 7000, "f15sa.jpg"),
    "al_hazm": ("سامانه الحزم", "🛡", "sa", 11, 40, 4800, "al_hazm.jpg"),
    # 🇦🇪
    "wing_loong": ("پهپاد وینگ‌لانگ", "🛩", "ae", 31, 7, 3300, "wing_loong.jpg"),
    "leclerc_ae": ("تانک لکلرک اماراتی", "🚜", "ae", 32, 29, 4700, "leclerc_ae.jpg"),
    "ghanthaq": ("سامانه غنثق", "💥", "ae", 26, 18, 3100, "ghanthaq.jpg"),
    # 🇮🇶
    "m1_iq": ("تانک M1 عراقی", "🚜", "iq", 26, 24, 3000, "m1_iq.jpg"),
    "ptrs": ("توپ PTRS", "💥", "iq", 20, 8, 1600, "ptrs.jpg"),
    "ababil": ("پهپاد ابابیل", "🛩", "iq", 22, 6, 1900, "ababil.jpg"),
    # 🇸🇾
    "t72_sy": ("تانک T-72 سوری", "🚜", "sy", 24, 22, 2400, "t72_sy.jpg"),
    "pantir": ("پدافند پانتسیر", "🛡", "sy", 9, 36, 3800, "pantir.jpg"),
    "mig23": ("جنگنده میگ-۲۳", "✈️", "sy", 27, 12, 2600, "mig23.jpg"),
    # 🇺🇦
    "neptune": ("موشک نپتون", "🚀", "ua", 39, 8, 4600, "neptune.jpg"),
    "bayraktar_ua": ("پهپاد بایراکتار TB2", "🛩", "ua", 30, 7, 3200, "tb2.jpg"),
    "olhant": ("توپخانه هایمارس", "💥", "ua", 34, 10, 4900, "himars.jpg"),
    # 🇮🇹
    "cavour": ("ناو کاوور", "🚢", "it", 36, 33, 6900, "cavour.jpg"),
    "aries": ("تانک آریته", "🚜", "it", 31, 27, 4100, "aries.jpg"),
    "freccia": ("زرهی فرچیا", "🛻", "it", 23, 24, 2900, "freccia.jpg"),
}

# درجات نظامی — با XP
RANKS = [(1, "سرباز تازه‌کار"), (2, "سرباز"), (3, "گروهبان"), (4, "استوار"),
         (5, "ستوان"), (6, "سرگرد"), (7, "سرهنگ"), (8, "سرتیپ"),
         (9, "سپهبد"), (10, "سرلشکر"), (12, "ارتشبد"), (15, "فرمانده کل")]


def init_items():
    for iid, (nm, em, ctry, atk, guard, price, img) in ITEMS.items():
        db.ex("INSERT OR IGNORE INTO items(iid,name,emoji,country,atk,guard,price,max_dur,img) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              (iid, nm, em, ctry, atk, guard, price, 100, img))


def rank_name(level: int) -> str:
    nm = RANKS[0][1]
    for lv, r in RANKS:
        if level >= lv:
            nm = r
    return nm
