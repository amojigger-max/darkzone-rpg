"""Split a legacy collision: trade inventory and investment assets used the SAME inv:<uid> key."""
import json
import db


@db.atomic
def ensure(uid):
    marker=f'portfolio_split:{uid}'
    if db.kv_get(marker):return
    raw=db.jload(db.kv_get(f'inv:{uid}'),{}) or {}
    if not isinstance(raw,dict):raw={}
    # Legacy investment timestamps and exclusive asset keys identify oil-rig ownership.
    oil_is_asset=bool(db.kv_get(f'invt:{uid}')) or any(k in raw for k in ('mine','ref','fac','bank'))
    assets={k:db.integer(v,0,0,50) for k,v in raw.items() if k in ('mine','ref','fac','bank') or (k=='oil' and oil_is_asset)}
    goods={k:db.integer(v,0,0,20) for k,v in raw.items() if k in ('gold','wheat','steel','copper') or (k=='oil' and not oil_is_asset)}
    for key,bag in ((f'investment:{uid}',assets),(f'trade:{uid}',goods)):
        if db.kv_get(key) is None:db.kv_set(key,json.dumps(bag))
    db.kv_set(marker,1)
    if raw:db.audit('portfolio_split',uid,oil_to='investment' if oil_is_asset else 'trade',legacy_key_retained=True)
