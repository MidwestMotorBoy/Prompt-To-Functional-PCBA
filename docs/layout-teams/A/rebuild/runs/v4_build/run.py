import sys
for _pass in (0,1):
    exec(open('place.py').read())
    for f in sys.argv[1].split(','):
        if f: exec(open(f).read())
    RESERVE=dict(EXPL)
errs,missing=check(P)
if len(sys.argv)>2:
    box=tuple(map(float,sys.argv[3:7])); sc=float(sys.argv[7]) if len(sys.argv)>7 else 40
    show(P,sys.argv[2],box,scale=sc,padnames=True,netlabels=True)

import json
json.dump({r:list(v) for r,v in P.items()},open('placement.json','w'),indent=0)
