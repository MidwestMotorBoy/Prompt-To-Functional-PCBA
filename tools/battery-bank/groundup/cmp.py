import json,math,sys
from fpdb import DB
db=DB('base.json')
pb=json.load(open('placement.json')); P={r:tuple(v) for r,v in pb.items()}
bad=[]
for r in P:
    if db.fp[r]['layer']!='F.Cu' or len(db.fp[r]['pads'])>3: continue
    for p in db.fp[r]['pads']:
        if not p['net'] or p['net'] in('GND','PACK_P','3V3'): continue
        x,y=db.pad(P,r,p['n']); best=None
        for q in P:
            if q==r: continue
            for pp in db.fp[q]['pads']:
                if pp['net']==p['net']:
                    X,Y=db.pad(P,q,pp['n']); d=abs(X-x)+abs(Y-y)
                    if best is None or d<best[0]: best=(round(d,1),q+'.'+pp['n'])
        if best and best[0]>6: bad.append((best[0],r,p['net'].split('/')[-1],best[1]))
print(len(bad),'pads >6 mm from the nearest pad of their net:',sorted(bad,reverse=True)[:40])
