#!/usr/bin/env python3
"""mk.py <name> <overrides.json> [more overrides.json ...] [--show=x0,y0,x1,y1[,x0,y0,x1,y1...]]
Builds runs/<name>_gu.json = lead_merge/merged3_gu.json + overrides (later files win; {ref:[x,y,abs_rot]}),
converts it to the scorecard format runs/<name>_score.json, runs placelib.check (courtyard / edge / peg) and
optionally renders placement pictures (courtyards, pads by net) of the given windows to img/<name>_<i>.png."""
import sys, os, json, subprocess
H = os.path.dirname(os.path.abspath(__file__)); A = os.path.dirname(H)
args = [a for a in sys.argv[1:] if not a.startswith('--')]; opts = [a for a in sys.argv[1:] if a.startswith('--')]
name, ovs = args[0], args[1:]
P = json.load(open(f'{A}/lead_merge/merged3_gu.json'))
for o in ovs:
    for r, v in json.load(open(o)).items():
        if r.startswith('_'): continue
        assert r in P, r; P[r] = v
os.makedirs(f'{H}/runs', exist_ok=True); os.makedirs(f'{H}/img', exist_ok=True)
gu = f'{H}/runs/{name}_gu.json'; sc = f'{H}/runs/{name}_score.json'
json.dump(P, open(gu, 'w'), indent=0)
subprocess.run(['python3', f'{A}/rebuild/gu/gu_to_score.py', gu, sc, f'{A}/rebuild/runs/v5_build/base.json'], check=True)
os.chdir(f'{A}/stage'); sys.path.insert(0, f'{A}/stage')
import placelib
errs, miss = placelib.check({r: tuple(v) for r, v in P.items()})
print('CHECK', 'clean' if not errs else f'{len(errs)} errors')
for o in opts:
    if o.startswith('--show='):
        v = list(map(float, o[7:].split(',')))
        for i in range(0, len(v), 4):
            for side in ('F', 'B'):
                out = f'{H}/img/{name}_{i // 4}{side}.png'
                placelib.show({r: tuple(x) for r, x in P.items()}, out, tuple(v[i:i + 4]), scale=40, padnames=True, netlabels=True, side=side)
                print(out)
