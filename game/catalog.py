"""Explicit game roles and bounded balance. These are game stats, not real capabilities."""
import math

KINDS = ("زمینی", "توپخانه", "هوایی", "چندمنظوره", "پهپادی", "موشکی", "دریایی", "آبی‌خاکی")
_EMOJI = {"🚀": "موشکی", "🛩": "پهپادی", "🚢": "دریایی", "🤿": "دریایی",
          "🚤": "دریایی", "🚁": "هوایی", "🔫": "زمینی", "🎯": "زمینی", "🚜": "زمینی", "🛻": "زمینی", "💥": "توپخانه", "🛡": "پدافندی", "✈": "هوایی"}


def _kind(iid,item):
    if iid in {'kornet','almas','almas_e','atkng','carl_g'}:return 'زمینی'
    if iid in {'fajr5','fadi','fadi_e','mx_hydra'}:return 'توپخانه'
    name,emoji=item[0],item[1].replace('\ufe0f','')
    if any(x in name.lower() for x in ('توپخانه','هویتزر','himars','pzh','های mars')):return 'توپخانه'
    return _EMOJI.get(emoji,'زمینی')


def primary(iid):
    import countries
    item=countries.ITEMS.get(iid)
    return _kind(iid,item) if item else None


def roles(iid):
    import countries
    kind=primary(iid)
    if kind is None:return frozenset()
    item=countries.ITEMS[iid]
    if kind=='هوایی' and ('جنگنده' in item[0] or iid.startswith('std_fighter_')):
        return frozenset(('هوایی','چندمنظوره'))
    return frozenset((kind,))


def supports(iid, kind):
    return kind in roles(iid)


def country_factor(cid):
    import countries
    c = countries.COUNTRIES.get(cid)
    if not c:
        return 1.0
    return round(max(0.97, min(1.04, 1 + (c['mil'] + c['tech'] + c['eco'] - 9) / 150)), 3)


def apply(items, nations):
    """Retain every original item/id/image; normalize comparable tiers, add missing roles."""
    for cid, nation in nations.items():
        own = [items[i] for i in nation['items'] if i in items]
        if not any(v[1].replace('\ufe0f', '') == '🛡' for v in own):
            iid = f"sam_{cid}"
            items[iid] = ("سامانهٔ دفاع هوایی استاندارد", "🛡", cid, 12, 48, 5000, "cat_ads.jpg")
            nation['items'].append(iid)
    # US equipment is deliberately scoped to its own arsenal, not a foreign THAAD id.
    if 'thaad_us' not in items:
        items['thaad_us'] = ("سامانهٔ تاد آمریکا — نسخهٔ بازی", "🛡", 'us', 16, 57, 8000, "cat_ads.jpg")
        nations['us']['items'].append('thaad_us')
    from game import geo
    templates={
      'زمینی':('std_ground','یگان زرهی استاندارد — مدل بازی','🚜',4200,'cat_tank.jpg'),
      'هوایی':('std_fighter','جنگندهٔ استاندارد — مدل بازی','✈',4200,'cat_jet.jpg'),
      'موشکی':('std_missile','موشک منطقه‌ای استاندارد — مدل بازی','🚀',4200,'cat_missile.jpg'),
      'توپخانه':('std_artillery','توپخانهٔ استاندارد — مدل بازی','💥',4200,'cat_arty.jpg'),
      'دریایی':('std_ship','شناور استاندارد — مدل بازی','🚢',4200,'cat_ship.jpg'),
    }
    for cid,nation in nations.items():
        present={_kind(i,items[i]) for i in nation['items'] if i in items}
        for kind,(prefix,name,emoji,price,img) in templates.items():
            if kind in present or (kind=='دریایی' and not geo.coastal(cid)):continue
            iid=f'{prefix}_{cid}'
            if iid not in items:
                items[iid]=(name,emoji,cid,35,20,price,img)
                nation['items'].append(iid)
    for iid, v in list(items.items()):
        name, em, cid, old_atk, old_def, price, img = v
        if iid.startswith('drone_'):
            atk, guard = 10, 6
        else:
            # Price levels are comparable in all nations; elite equipment has a bounded ceiling.
            tier = min(4, max(1, int(math.ceil(price / 2200))))
            elite = iid.endswith('_e')
            stat = 22 + tier * 7 + (6 if elite else 0)
            kind = _kind(iid,v)
            if kind == 'پدافندی':
                atk, guard = 10 + tier, stat + 5
            elif kind == 'دریایی':
                atk, guard = stat - 2, stat - 5
            elif kind in ('موشکی','هوایی','پهپادی','توپخانه'):
                atk, guard = stat + 2, 10 + tier * 2
            else:
                atk, guard = stat, 15 + tier * 5
        items[iid] = (name, em, cid, atk, guard, price, img)


def range_band(iid):
    """Operational classes, not a real-world weapon range estimate."""
    kind=primary(iid)
    if kind is None:return 0
    if kind not in ('موشکی','هوایی','پهپادی'):return 3
    base=iid[:-2] if iid.endswith('_e') else iid
    # Exact identifiers: TB2 is NOT B-2. No accidental substring promotion.
    return 3 if base in {'b2','h20','hwasong18','agni','agni5'} else 2
