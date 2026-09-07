"""Callback schema and season validation, run BEFORE aiogram route filters."""
import re
import db
import countries
from game import catalog, defense, infra, rules, straits, operations, un


def sign_markup(markup):
    if markup is None or not hasattr(markup,'inline_keyboard'):return markup
    epoch=db.kv_get('season_epoch','0')
    rows=[]
    for row in markup.inline_keyboard:
        new=[]
        for button in row:
            raw=button.callback_data
            if raw:
                raw=raw.split('~',1)[0]+f'~{epoch}'
                if len(raw.encode('utf-8'))>64:
                    raise ValueError('callback exceeds Telegram 64-byte limit')
                button=button.model_copy(update={'callback_data':raw})
            new.append(button)
        rows.append(new)
    return markup.model_copy(update={'inline_keyboard':rows})


def unwrap(data):
    if not isinstance(data,str) or len(data.encode('utf-8'))>64:return None
    epoch=db.kv_get('season_epoch','0')
    if '~' in data:
        raw,got=data.rsplit('~',1)
        return raw if got==epoch else None
    return data if epoch=='0' else None


def _num(s,lo=0,hi=2**63-1):
    return bool(re.fullmatch(r'[0-9]{1,19}',s or '')) and lo<=int(s)<=hi


def valid(raw):
    if not isinstance(raw,str) or ':' not in raw:return False
    parts=raw.split(':');prefix=parts[0];arg=parts[1:]
    empty={'dac','pac','sur','sury','dl','wk','tct','qc','pnew','pcancel','pay','inv','ivc','toll','tollpay','tolltog','tollget','aim','supply','cities','staging','contracts','gifts','adout','glist','ops','opnew','un','unnew','sg','allymanage','en','fv','fbld','finbox','fet','grstock','scraps','srcancel'}
    if prefix in empty and arg==['']:return True
    if prefix in ('hp','cyp','br','pj','du','pay','city','acity','lib'):
        return len(arg)==1 and _num(arg[0],0 if prefix in ('br','city','acity','cyp','lib') else 1)
    if prefix in ('cy','ally','aac','spy','dwr','ct','ctac','stage','snc','sapply','slift','opt','unt','aquit'):
        return (prefix=='snc' and arg==['']) or (len(arg)==1 and arg[0] in countries.COUNTRIES)
    if prefix in ('wp','wp5','bb','up'):return len(arg)==1 and arg[0] in countries.ITEMS
    if prefix in ('opgo','opcancel','unr','unpage','dpage','ppage','upage'):
        return len(arg)==1 and _num(arg[0],0 if prefix in ('unpage','dpage','ppage','upage') else 1)
    if prefix in ('sg','sgget','sgpay'):return len(arg)==1 and arg[0] in straits.CONTROLS
    if prefix=='sgact':return len(arg)==2 and arg[0] in straits.CONTROLS and arg[1] in ('open','close')
    if prefix=='sgfee':return len(arg)==2 and arg[0] in straits.CONTROLS and _num(arg[1],0,100) and int(arg[1]) in straits.FEES
    if prefix=='opkind':return len(arg)==2 and arg[0] in countries.COUNTRIES and arg[1] in operations.DOCTRINES
    if prefix=='opmode':return len(arg)==3 and arg[0] in countries.COUNTRIES and arg[1] in operations.DOCTRINES and arg[2] in rules.MODES
    if prefix=='unprop':return len(arg)==2 and arg[0] in un.KINDS and arg[1] in countries.COUNTRIES
    if prefix=='unvote':return len(arg)==2 and _num(arg[0],1) and arg[1] in ('yes','no','abstain')
    if prefix=='undonate':return len(arg)==1 and _num(arg[0],1,5000)
    if prefix=='scpage':return len(arg)==1 and _num(arg[0],0,10000)
    if prefix=='scprep':return len(arg)==1 and arg[0] in countries.ITEMS
    if prefix=='scrok':return len(arg)==1 and bool(re.fullmatch('[a-f0-9]{12}',arg[0]))
    if prefix=='fipage':return len(arg)==1 and _num(arg[0],0,10000)
    if prefix in ('en','ftypes'):return len(arg)==1 and _num(arg[0],0,4)
    if prefix in ('ebuy','esell','ecrude'):return len(arg)==2 and _num(arg[0],0,4) and _num(arg[1],1,20 if prefix=='ecrude' else 200)
    if prefix in ('fsend','fvr','facc','fcancel','frp','fatk'):return len(arg)==1 and _num(arg[0],1)
    if prefix=='fname':return len(arg)==2 and _num(arg[0],0,4) and arg[1] in ('coastal','product','aframax','vlcc')
    if prefix in ('fcar','fdest','fport','foqty','foesc'):
        sizes={'fcar':2,'fdest':3,'fport':4,'foqty':5,'foesc':6}
        return len(arg)==sizes[prefix] and _num(arg[0],1) and arg[1] in ('crude','fuel') and (len(arg)<3 or arg[2] in countries.COUNTRIES) and (len(arg)<4 or _num(arg[3],0,4)) and (len(arg)<5 or _num(arg[4],1,180)) and (len(arg)<6 or _num(arg[5],0,3))
    if prefix=='fat':return len(arg)==3 and _num(arg[0],1) and arg[1] in ('naval','air','multi','drone','missile') and _num(arg[2],1,3)
    if prefix=='wmode':return len(arg)==2 and arg[0] in countries.COUNTRIES and arg[1] in rules.MODES
    if prefix=='gw':return len(arg)==1 and bool(re.fullmatch(r'-[0-9]{1,19}',arg[0]))
    if prefix=='df':return len(arg)==1 and arg[0] in defense.LAYERS
    if prefix=='gno':return arg in (['land'],['sea'])
    if prefix=='rv':return arg in ([''],['s'],['go'],['x'])
    if prefix=='evc':return len(arg)==1 and arg[0] in ('تحویل','اعزام','رمزگشایی')
    if prefix=='str':return arg in ([''],['هرمز'],['باب‌المندب'],['تایوان'],['سوئز'])
    if prefix=='ad':return ':'.join(arg) in ('stats','players','callup','troops','reg','chg','lead','tog:bl','tog:ev')
    if prefix in ('tb','ts'):
        from game import economy
        return len(arg)==2 and arg[0] in economy.GOODS_MAP and _num(arg[1],1,5)
    if prefix=='tp':return len(arg)==2 and arg[0] in ('dwr','spy','ally','snc','ct','stage','opt') and _num(arg[1],0,49)
    if prefix=='st':return len(arg) in (2,3) and arg[0] in catalog.KINDS and _num(arg[1],1,5) and (len(arg)==2 or _target(arg[2]))
    if prefix=='aimk':return len(arg)==1 and _target(arg[0])
    if prefix in ('cbld','cfix'):return len(arg)==2 and _num(arg[0],0,4) and arg[1] in (infra._B if prefix=='cbld' else infra.TARGETS)
    if prefix in ('ibld','ifix'):return len(arg)==1 and arg[0] in (infra._B if prefix=='ibld' else infra.TARGETS)
    if prefix=='ivb':return len(arg)==1 and arg[0] in ('mine','oil','ref','fac','bank')
    if prefix=='wbuild':return len(arg)==1 and arg[0] in ('hospital','mosque','church','temple','housing')
    if prefix=='pm':return len(arg)==1 and arg[0] in ('menu','help','welf','toll','inv','war')
    if prefix=='mn':return len(arg)==1 and arg[0] in {'main','mil','pol','world','me','battle','rest','arsenal','repair','ration','branch','parties','rebel','stmt','spy','ally','war','wstat','power','colonies','lb','market','map','help','cguide','news','trade','howto','events','front','army','def','quest','black','upgrade','duel','peace','helpally','infra','welf'}
    return False


def _target(s):
    parts=s.split('.')
    return (len(parts)==1 and s in infra.TARGETS) or (len(parts)==2 and _num(parts[0],0,4) and parts[1] in infra.TARGETS)
