"""🗺 جنگ جهانی — جغرافیا: جبهه‌ها، شهرها، اشغال.

هر جنگ روی جبهه‌ها (شهرها و مناطق واقعی) جریان دارد؛
پیروزی در جبهه = اشغال شهر = غنیمت و منابع.
"""

# جبهه‌های مرزی بین جفت‌کشورهای کلیدی (بر اساس نقشه ۲۰۲۶)
FRONTS = {
    ("ir", "iq"): ["بصره", "شلمچه", "مهران"],
    ("ir", "tr"): ["حکاری", "مراوه‌تپه"],
    ("ir", "ae"): ["ابوموسی", "تنب بزرگ"],
    ("us", "cn"): ["تایوان", "اوکیناوا"],
    ("us", "ru"): ["کوریل", "آلاسکا"],
    ("ru", "ua"): ["دونتسک", "خارکوف", "زاپوریژیا", "کریمه"],
    ("cn", "in"): ["آروناچال", "لاداخ"],
    ("kp", "kr"): ["سئول", "پیونگ‌یانگ"],
    ("il", "sy"): ["جولان", "لبنان جنوبی"],
    ("pk", "in"): ["کشمیر", "پنجاب"],
    ("tr", "sy"): ["عفرین", "رقه"],
    ("sa", "iq"): ["صعده", "جیزان"],
}

# هر کشور: شهرهای اصلی (غنیمت اشغال)
CITIES = {
    "ir": ["تهران", "اصفهان", "شیراز", "تبریز", "بندرعباس"],
    "us": ["واشنگتن", "نیویورک", "لس‌آنجلس", "هیوستون"],
    "ru": ["مسکو", "سن‌پترزبورگ", "ولگوگراد", "ولادی‌وستوک"],
    "cn": ["پکن", "شانگهای", "شنژن", "اورومچی"],
    "de": ["برلین", "مونیخ", "هامبورگ"],
    "gb": ["لندن", "منچستر", "گلاسگو"],
    "fr": ["پاریس", "مارسی", "لیون"],
    "tr": ["آنکارا", "استانبول", "ازمیر", "دیاربکر"],
    "il": ["تل‌آویو", "قدس", "حیفا"],
    "kp": ["پیونگ‌یانگ", "هام‌هونگ"],
    "kr": ["سئول", "بوسان", "اینچئون"],
    "jp": ["توکیو", "اوساکا", "ناگازاکی"],
    "in": ["دهلی نو", "بمبئی", "کلکته"],
    "pk": ["اسلام‌آباد", "کراچی", "لاهور"],
    "sa": ["ریاض", "جده", "مکه", "ظهران"],
    "ae": ["ابوظبی", "دبی", "شارجه"],
    "iq": ["بغداد", "بصره", "موصل", "اربیل"],
    "sy": ["دمشق", "حلب", "لاذقیه"],
    "ua": ["کیف", "خارکوف", "اودسا"],
    "it": ["رم", "میلان", "ناپل"],
    "hz": ["بیروت", "ضاحیه بیروت", "بعلبک", "بنت جبیل"],
    # ───── شهرهای ۲۹ کشور تازه ─────
    "br": ["برازیلیا", "سائوپائولو", "ریودوژانیرو", "مانائوس"],
    "mx": ["مکزیکوسیتی", "گوادالاخارا", "تیخوانا", "کانکون"],
    "ar": ["بوئنوس‌آیرس", "کوردوبا", "روساریو", "مندوزا"],
    "ca": ["اتاوا", "تورنتو", "ونکوور", "مونترال"],
    "au": ["کانبرا", "سیدنی", "ملبورن", "پرت"],
    "eg": ["قاهره", "اسکندریه", "پورت‌سعید", "اسوان"],
    "za": ["پرتوریا", "ژوهانسبورگ", "کیپ‌تاون", "دوربان"],
    "ng": ["آبوجا", "لاگوس", "کانو", "پورت‌هارکورت"],
    "id": ["جاکارتا", "سورابایا", "مدان", "بالیک‌پاپان"],
    "my": ["کوالالامپور", "پنانگ", "جوهر", "کوچینگ"],
    "th": ["بانکوک", "چیانگ‌مای", "پوکت", "پاتایا"],
    "vn": ["هانوی", "هوشی‌مین", "دانانگ", "هایفونگ"],
    "ph": ["مانیل", "سبو", "داوائو", "کزون"],
    "es": ["مادرید", "بارسلون", "والنسیا", "سویا"],
    "pt": ["لیسبون", "پورتو", "براگا", "فارو"],
    "nl": ["آمستردام", "روتردام", "لاهه", "اوترخت"],
    "be": ["بروکسل", "آنتورپ", "گانت", "لیژ"],
    "se": ["استکهلم", "یوتبری", "مالمو", "اوپسالا"],
    "no": ["اسلو", "برگن", "تروندهایم", "ترومسو"],
    "dk": ["کپنهاگ", "آرهوس", "اودنسه", "آلبورگ"],
    "fi": ["هلسینکی", "تامپره", "تورکو", "اولو"],
    "pl": ["ورشو", "کراکوف", "گدانسک", "ووتسلاو"],
    "gr": ["آتن", "سالونیک", "پاتراس", "هراکلیون"],
    "ch": ["برن", "زوریخ", "ژنو", "بازل"],
    "at": ["وین", "گراتس", "لینتس", "زالتسبورگ"],
    "kz": ["آستانه", "آلماتی", "شیمکنت", "آقتائو"],
    "az": ["باکو", "گنجه", "سومقاییت", "نخجوان"],
    "qa": ["دوحه", "الریان", "الوکره", "الخور"],
    "kw": ["کویت‌سیتی", "حولی", "الفروانیه", "جهرا"],
}


def fronts_of(a: str, b: str):
    """جبهه‌های جنگ بین دو کشور — از هر دو جهت."""
    return FRONTS.get((a, b)) or FRONTS.get((b, a)) or ["جبهه‌ی شمالی", "جبهه‌ی جنوبی"]


def occupied(cid: str):
    """شهرهای اشغال‌شده‌ی یک کشور."""
    import db
    occ = db.jload(db.kv_get(f"occupied:{cid}"), []) or []
    return occ


def occupy(cid: str, city: str, by: str):
    import db
    occ = db.jload(db.kv_get(f"occupied:{cid}"), []) or []
    if city not in occ:
        occ.append(city)
        import json
        db.kv_set(f"occupied:{cid}", json.dumps(occ, ensure_ascii=False))
        occs = db.jload(db.kv_get("occupations"), []) or []
        occs = [o for o in occs if not (o.get("city") == city and o.get("cid") == cid)]
        occs.append(dict(city=city, cid=cid, by=by, ts=db.now()))
        db.kv_set("occupations", json.dumps(occs, ensure_ascii=False))
        # ⛓ آخرین شهر سقوط کند → مستعمره‌ی رسمی
        if occ and set(occ) >= set(CITIES.get(cid, [])) and not colony_of(cid):
            return colonize(cid, by)
        import countries
        c = countries.COUNTRIES[by]
        return (f"🏚 <b>{city}</b> اشغال شد توسط {c['flag']} {c['name']}!")
    return None


def held_by(cid: str):
    """شهرهای اشغال‌شده به دست این کشور."""
    import db
    return [o for o in db.jload(db.kv_get("occupations"), []) or []
            if o.get("by") == cid]
    """شهرهای اشغال‌شده به دست این کشور."""
    import db
    return [o for o in db.jload(db.kv_get("occupations"), []) or []
            if o.get("by") == cid]


def colony_of(cid: str):
    """اشغال‌گر این کشور — یا None."""
    import db
    v = db.kv_get(f"colony:{cid}", "")
    return v or None


def colonies_of(by: str) -> list:
    """مستعمره‌های یک کشور."""
    import db
    return [r["k"].split(":")[1] for r in
            db.q("SELECT k, v FROM kv WHERE k LIKE 'colony:%' AND v=?", (by,))
            if r["k"].split(":")[1] in __import__("countries").COUNTRIES]


def colonize(cid: str, by: str) -> str:
    import db, countries
    db.kv_set(f"colony:{cid}", by)
    c, b = countries.COUNTRIES[cid], countries.COUNTRIES[by]
    return (f"⛓ <b>{c['flag']} {c['name']} رسماً مستعمره‌ی "
            f"{b['flag']} {b['name']} شد!</b>\n"
            f"خراج روزانه جاری است — مردمش زیر یوغ‌اند.")


def free_colony(cid: str):
    """آزادسازی — شهرها آزاد، یوغ برداشته."""
    import db
    db.kv_set(f"colony:{cid}", "")
    db.kv_set(f"occupied:{cid}", "[]")
    occs = db.jload(db.kv_get("occupations"), []) or []
    occs = [o for o in occs if o.get("cid") != cid]
    import json
    db.kv_set("occupations", json.dumps(occs, ensure_ascii=False))


def country_map(cid: str) -> str:
    import countries
    import texts
    c = countries.COUNTRIES[cid]
    occ = occupied(cid)
    lines = [texts.hdr(f"نقشه‌ی {c['name']}", "🗺"), ""]
    for city in CITIES.get(cid, []):
        mark = "🚩 اشغال‌شده" if city in occ else "🟢 آزاد"
        lines.append(f"▫️ {city} — {mark}")
    return "\n".join(lines)

# ═══ مرزهای زمینی مشترک (جفت‌های متقارن؛ یک‌طرفه کافی است) ═══
_NEIGHBOR_PAIRS = [
    ("ir", "iq"), ("ir", "tr"), ("ir", "pk"), ("ir", "az"),
    ("us", "mx"), ("us", "ca"),
    ("ru", "cn"), ("ru", "kz"), ("ru", "ua"), ("ru", "kp"), ("ru", "fi"),
    ("cn", "in"), ("cn", "pk"), ("cn", "kp"), ("cn", "vn"), ("cn", "kz"),
    ("de", "fr"), ("de", "at"), ("de", "ch"), ("de", "pl"), ("de", "dk"), ("de", "nl"), ("de", "be"),
    ("fr", "es"), ("fr", "it"), ("fr", "ch"), ("fr", "be"),
    ("tr", "iq"), ("tr", "sy"), ("tr", "az"), ("tr", "gr"),
    ("il", "sy"), ("il", "eg"),
    ("kp", "kr"),
    ("in", "pk"),
    ("sa", "iq"), ("sa", "kw"), ("sa", "ae"), ("sa", "qa"),
    ("ae", "qa"),
    ("iq", "sy"), ("iq", "kw"),
    ("sy", "hz"),
    ("hz", "il"),
    ("ua", "pl"),
    ("it", "ch"), ("it", "at"),
    ("br", "ar"),
    ("id", "my"), ("my", "th"),
    ("es", "pt"),
    ("nl", "be"), ("fr", "nl"), ("be", "de"),
    ("pl", "ua"),
    ("ch", "at"),
    ("kz", "cn"),
    ("at", "it"),
]

# cid → مجموعه‌ی همسایه‌های زمینی
NEIGHBORS = {}
for _a, _b in _NEIGHBOR_PAIRS:
    NEIGHBORS.setdefault(_a, set()).add(_b)
    NEIGHBORS.setdefault(_b, set()).add(_a)

# ═══ کشورهای دارای دسترسی به آب‌های آزاد (برای حمله‌ی دریایی) ═══
# جزیره‌ای‌ها و ساحلی‌ها؛ فقط at (اتریش) و ch (سوئیس) زمین‌بسته‌اند.
COASTAL = {
    "ir", "us", "ru", "cn", "de", "gb", "fr", "tr", "il", "kp", "kr", "jp",
    "in", "pk", "sa", "ae", "iq", "sy", "ua", "it", "hz", "br", "mx", "ar",
    "ca", "au", "eg", "za", "ng", "id", "my", "th", "vn", "ph", "es", "pt",
    "nl", "be", "se", "no", "dk", "fi", "pl", "gr", "kz", "az", "qa", "kw",
}


def is_neighbor(a: str, b: str) -> bool:
    """آیا دو کشور مرز زمینی مشترک دارند؟"""
    return b in NEIGHBORS.get(a, ())


def coastal(cid: str) -> bool:
    """آیا کشور به دریای آزاد دسترسی دارد؟"""
    return cid in COASTAL

