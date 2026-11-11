import sys,collections
sys.argv=['x']
exec(open('place.py').read())
by=collections.defaultdict(list)
for r,f in db.fp.items():
    if r in P and r not in FIXED: continue
    by[f['sheet']].append(r)
import re
def key(r):
    m=re.match(r'([A-Z]+)(\d+)',r); return (m.group(1),int(m.group(2)))
for s in sorted(by):
    print('##',s)
    for r in sorted(by[s],key=key):
        f=db.fp[r]
        if re.match(r'[A-Z]+5\d\d$',r) and r not in('U501',): continue
        nets=collections.OrderedDict()
        for p in f['pads']:
            nets.setdefault(p['net'],[]).append(p['n'])
        if len(f['pads'])<=3:
            s2=' '.join(f"{p['n']}={p['net']}" for p in f['pads'])
        else:
            s2=' '.join(f"{n}:{','.join(v)}" for n,v in nets.items())
        fx='*' if r in FIXED else ''
        print(f" {r}{fx} {f['val'][:14]} [{f['fp'].split(':')[-1][:22]}] {s2}")
