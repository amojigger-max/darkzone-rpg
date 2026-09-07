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
    """Only actual game cities; old unowned generic fronts cannot become territory."""
    return [CITIES[b][i] for i in frontier_cities(a, b)] if b in CITIES else []


def occupied(cid: str):
    """شهرهای اشغال‌شده‌ی یک کشور."""
    import db
    occ = db.jload(db.kv_get(f"occupied:{cid}"), []) or []
    return occ


def occupy(cid: str, city: str, by: str):
    """Internal territorial write; never automatically turns a country into a colony."""
    import json
    import db
    import countries
    if cid == by or cid not in CITIES or by not in CITIES or city not in CITIES[cid]:
        raise ValueError("invalid occupation")
    with db.transaction():
        occs = db.jload(db.kv_get("occupations"), []) or []
        existing = next((o for o in occs if o.get('city') == city and o.get('cid') == cid), None)
        if existing and existing.get('by') == by:
            return None
        if existing:
            raise ValueError("city already held by another country")
        occs.append(dict(city=city, cid=cid, by=by, ts=db.now()))
        db.kv_set("occupations", json.dumps(occs, ensure_ascii=False))
        db.kv_set(f"occupied:{cid}", json.dumps([o['city'] for o in occs if o['cid']==cid], ensure_ascii=False))
        db.audit('city_capture', defender=cid, city=city, attacker=by)
    c = countries.COUNTRIES[by]
    return f"🚩 {city} تحت کنترل {c['flag']} {c['name']} قرار گرفت؛ کشور تسلیم نشده است."


def held_by(cid: str):
    import db
    return [o for o in db.jload(db.kv_get("occupations"), []) or []
            if o.get("by") == cid and o.get("city") in CITIES.get(o.get("cid"), [])]


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
    """Only a completed, sustained total-war campaign permits colonization."""
    import db
    import countries
    from game import campaign
    ok, reason = campaign.can_capitulate(cid, by)
    if not ok:
        raise ValueError(reason)
    # Reject chains/cycles: a dependent state cannot acquire dependencies itself.
    if colony_of(by) or cid == by:
        raise ValueError("invalid colonial relationship")
    for child in colonies_of(cid):
        free_colony(child)
    db.kv_set(f"colony:{cid}", by)
    db.audit('capitulation', loser=cid, winner=by)
    c,b = countries.COUNTRIES[cid],countries.COUNTRIES[by]
    return f"⛓ {c['flag']} {c['name']} پس از محاصرهٔ طولانی تابع {b['flag']} {b['name']} شد؛ حساب رهبر و کشورش حذف نمی‌شود."


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
    from game import infra
    import countries
    import texts
    if cid not in countries.COUNTRIES:
        return "⛔ کشور نامعتبر."
    lines = [texts.hdr(f"نقشهٔ {countries.COUNTRIES[cid]['name']}", "🗺")]
    for i, name in enumerate(CITIES[cid]):
        s=infra.city_state(cid, i)
        mark="🚩 اشغال‌شده" if name in occupied(cid) else "🟢 آزاد"
        lines.append(f"{i+1}. {name}{' 👑 پایتخت' if i == 0 else ''} — {mark}\n"
                     f"   برق {s['power']}٪ · صنعت {s['industry']}٪ · پادگان {s['garrison']}٪")
    neighbors=sorted(NEIGHBORS.get(cid,()))
    lines.append("مرز زمینی: "+("، ".join(countries.COUNTRIES[n]['name'] for n in neighbors) or "ندارد در نقشهٔ بازی"))
    lines.append("شهرهای مرزی و مسیر داخلی، انتزاعی و مخصوص بازی‌اند؛ شهر اشغال‌شده مسیر تدارکاتی می‌خواهد.")
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
    ("iq", "sy"), ("iq", "kw"),
    ("sy", "hz"),
    ("hz", "il"),
    ("ua", "pl"),
    ("it", "ch"), ("it", "at"),
    ("br", "ar"),
    ("id", "my"), ("my", "th"),
    ("es", "pt"),
    ("nl", "be"), ("be", "de"),
    ("pl", "ua"),
    ("ch", "at"),
    ("kz", "cn"),
    ("at", "it"), ("ru", "no"), ("ru", "pl"), ("ru", "az"),
    ("no", "se"), ("no", "fi"), ("se", "fi"),
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
    "nl", "be", "se", "no", "dk", "fi", "pl", "gr", "qa", "kw",
}


def is_neighbor(a: str, b: str) -> bool:
    """آیا دو کشور مرز زمینی مشترک دارند؟"""
    return b in NEIGHBORS.get(a, ())


def coastal(cid: str) -> bool:
    """آیا کشور به دریای آزاد دسترسی دارد؟"""
    return cid in COASTAL


# Abstract game port nodes. Caspian-only access is NOT access to the open ocean.
PORT_NODES = {
    'ir': [4], 'us': [1,2,3], 'ru': [1,3], 'cn': [1,2], 'de': [2],
    'gb': [2], 'fr': [1], 'tr': [1,2], 'il': [0,2], 'kp': [1], 'kr': [1,2],
    'jp': [0,1,2], 'in': [1,2], 'pk': [1], 'sa': [1,3], 'ae': [0,1,2],
    'iq': [1], 'sy': [2], 'ua': [2], 'it': [2], 'hz': [0], 'br': [2],
    'mx': [3], 'ar': [0], 'ca': [2,3], 'au': [1,2,3], 'eg': [1,2],
    'za': [2,3], 'ng': [1,3], 'id': [0,1], 'my': [1,2], 'th': [2,3],
    'vn': [2,3], 'ph': [0,1,2], 'es': [1,2], 'pt': [0,1,3], 'nl': [1],
    'be': [1], 'se': [0,1,2], 'no': [0,1,2,3], 'dk': [0,1,3],
    'fi': [0,2,3], 'pl': [2], 'gr': [0,1,2,3], 'qa': [0,2,3], 'kw': [0],
}


def is_port(cid, city):
    return cid in COASTAL and city in PORT_NODES.get(cid, [])


def frontier_cities(attacker, defender):
    """Game border ring, not a claim about real-world operational routes."""
    if not is_neighbor(attacker, defender):
        return []
    return list(range(1, len(CITIES.get(defender, []))))


def accessible_city(attacker, defender, city, amphibious=False):
    if city < 0 or city >= len(CITIES.get(defender, [])):
        return False
    own_holds = [o['city'] for o in held_by(attacker) if o['cid'] == defender]
    if city == 0:
        return bool(own_holds)  # capital cannot be the first landing/capture
    if amphibious:
        return is_port(defender, city)
    return city in frontier_cities(attacker, defender) or bool(own_holds)


def release_city(cid, city):
    import json
    import db
    with db.transaction():
        occs = [o for o in db.jload(db.kv_get('occupations'), []) or []
                if not (o.get('cid') == cid and o.get('city') == city)]
        db.kv_set('occupations', json.dumps(occs, ensure_ascii=False))
        db.kv_set(f'occupied:{cid}', json.dumps([o['city'] for o in occs if o['cid'] == cid], ensure_ascii=False))


# Operational zones are game abstractions, not precise real-world weapon ranges.
ZONES={
 'west_asia':set('ir tr il iq sy hz sa ae qa kw az'.split()),
 'europe':set('de gb fr ua it es pt nl be se no dk fi pl gr ch at ru'.split()),
 'south_asia':set('in pk'.split()),
 'east_asia':set('cn kp kr jp kz id my th vn ph'.split()),
 'africa':set('eg za ng'.split()),
 'americas':set('us br mx ar ca'.split()),
 'oceania':{'au'},
}

def zone(cid):return next((z for z,ids in ZONES.items() if cid in ids),'unknown')

def range_level(a,b):
    if a==b or is_neighbor(a,b):return 1
    if zone(a)==zone(b):return 2
    return 3
