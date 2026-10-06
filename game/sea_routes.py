"""Named sea regions and chokepoints. Travel hours are game units, not navigation advice."""
import heapq
from game import geo,straits

SEAS={'atlantic':'اطلس','pacific':'آرام','indian':'اقیانوس هند','gulf':'خلیج فارس',
      'med':'مدیترانه','red':'دریای سرخ','black':'دریای سیاه','baltic':'بالتیک','west_pacific':'شمال غرب آرام','south_china':'دریای چین جنوبی'}
# Undirected edges: two capes permit slower detours instead of pretending Suez controls all oceans.
EDGES=[('gulf','indian','hormuz',3600),('red','indian',None,3600),
       ('med','red','suez',3600),('black','med','bosporus',3600),
       ('indian','south_china','malacca',5400),('med','atlantic',None,3600),
       ('baltic','atlantic',None,3600),('atlantic','indian',None,14400),
       ('atlantic','pacific',None,21600),('indian','south_china',None,18000),
       ('west_pacific','south_china','taiwan',3600),
       ('west_pacific','pacific',None,10800),('south_china','pacific',None,10800)]
DEFAULT={
 **dict.fromkeys('us ca mx br ar de gb nl be pt es ng'.split(),'atlantic'),
 **dict.fromkeys('cn kp kr jp'.split(),'west_pacific'),
 **dict.fromkeys('vn ph id my'.split(),'south_china'),
 **dict.fromkeys('ir iq ae qa kw'.split(),'gulf'),
 **dict.fromkeys('fr it tr il sy hz eg gr'.split(),'med'),
 **dict.fromkeys('pk in au za th'.split(),'indian'),
 **dict.fromkeys('se fi pl ru'.split(),'baltic'),
 'no':'atlantic','dk':'atlantic','ua':'black','sa':'red',
}
PORT_OVERRIDES={
 ('cn',2):'south_china',('us',2):'pacific',('ca',2):'pacific',('mx',2):'pacific',
 ('ru',3):'west_pacific',('tr',1):'black',('sa',3):'gulf',
 ('au',1):'pacific',('au',2):'pacific',
 ('za',2):'atlantic',('my',1):'indian',('my',2):'indian',
 ('id',0):'indian',('id',2):'indian',
 ('se',1):'atlantic',('se',2):'baltic',
}
AIR_REGIONS={
 'west_asia':{'gulf','red','med','black','indian'},
 'europe':{'atlantic','med','black','baltic'},
 'south_asia':{'indian','gulf'},'east_asia':{'pacific','indian','west_pacific','south_china'},
 'africa':{'atlantic','indian','red','med'},'americas':{'atlantic','pacific'},
 'oceania':{'pacific','indian','south_china'},
}


def port_sea(cid,city):
    if not geo.is_port(cid,city) or not geo.coastal(cid):return None
    return PORT_OVERRIDES.get((cid,city),DEFAULT.get(cid))


def route(source,dest,allow_closed=False):
    if source not in SEAS or dest not in SEAS:return None
    if source==dest:return [{'a':source,'b':dest,'gate':None,'seconds':7200}]
    heap=[(0,0,source,[])];seen=set();serial=0
    while heap:
        total,_,node,path=heapq.heappop(heap)
        if node==dest:return path
        if node in seen:continue
        seen.add(node)
        for a,b,gate,seconds in EDGES:
            if node not in (a,b):continue
            other=b if node==a else a
            if gate and not allow_closed and not straits.is_open(gate):continue
            serial+=1
            heapq.heappush(heap,(total+seconds,serial,other,path+[{'a':node,'b':other,'gate':gate,'seconds':seconds}]))
    return None


def reverse(path):return [{'a':p['b'],'b':p['a'],'gate':p['gate'],'seconds':p['seconds']} for p in reversed(path)]


def coastal_reach(source,dest):
    return source==dest or any({a,b}=={source,dest} and seconds<=5400 and (not gate or straits.is_open(gate)) for a,b,gate,seconds in EDGES)


def air_band(cid,sea):return 2 if sea in AIR_REGIONS.get(geo.zone(cid),set()) else 3
