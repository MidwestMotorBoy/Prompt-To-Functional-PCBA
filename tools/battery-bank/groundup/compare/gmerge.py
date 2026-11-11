"""Replace the P2 low-side leg A loop by its both-planes run (the adjacent-plane corridor cuts its ground return on the ground-up board)."""
import json, pickle, os, sys
K='P2 LS gate leg A (Q501)'
for t in sys.argv[1:]:
    a=json.load(open(f'gate3_{t}.json')); b=json.load(open(f'gate3b_{t}.json'))
    ma=pickle.load(open(f'gate3maps_{t}.pkl','rb')); mb=pickle.load(open(f'gate3mapsb_{t}.pkl','rb'))
    if 'L_adj' not in a[K]: old=a[K]['L']; a[K]=dict(b[K],both=True,L_adj=old); ma[K]=mb[K]
    a={k:a[k] for k in json.load(open('gate3_base.json')) if k in a} if t!='base' else a
    ma={k:ma[k] for k in a}
    json.dump(a,open(f'gate3_{t}.json','w'),indent=1); pickle.dump(ma,open(f'gate3maps_{t}.pkl','wb'))
    print(t,[(k[:8]+k[-13:-7],round(v['L']*1e9,2),v.get('h')) for k,v in a.items()])
