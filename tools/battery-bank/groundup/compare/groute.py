import json, os, collections
from board import *
from run_all_defs import GATES
out={}
for name,nets,U,dp,rp,R,Q,qp in GATES:
    ly=collections.Counter(); wmin=9; nv=0
    drv=[n for n in nets if n!='GND' and 'SW' not in n.split('/')[-1]]
    for s in SEG:
        if s['net'] in drv: ly[s['layer'].replace('.Cu','')]+=seglen(s); wmin=min(wmin,s['w'])
    nv=sum(1 for v in VIA if v['net'] in drv)
    out[name]=dict(layers={k:round(v,1) for k,v in ly.items()},wmin=wmin,vias=nv,total=round(sum(ly.values()),1))
json.dump(out,open(f'groute_{os.environ["TAG"]}.json','w'),indent=1)
for k,v in out.items(): print(k,v)
