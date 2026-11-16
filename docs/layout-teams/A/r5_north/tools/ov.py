#!/usr/bin/env python3
"""ov.py <moves.json> <out_dir> [--render] [--with=extra_override.json ...]
r5_north: north-row support-part moves for the charger U403 (port 1), copied to port 2 by the stage translation
(U403 -> U503: dx -23.026, dy 0, same rotation).

moves.json: {ref: [x, y, absolute rot], ...} for port-1 refs (groundup format); keys starting with '_' are kept as notes.
Base placement = final/deliver/best_placement_gu.json + r4_bcu/overrides/60_r4_bcu.json (= r4_bcu k1), plus any --with files
applied before the moves. Writes:
  <out_dir>/70_r5_north.json   override (both ports, groundup format) for build_r4.sh
  <out_dir>/placement_gu.json  full groundup placement
  <out_dir>/placement.json     scorecard format (gu_to_score with the template dump)
  <out_dir>/p1.png, p2.png     courtyard/pad renders of both charger north rows (--render)
and prints placelib.check (courtyards, edges, pegs) errors."""
import sys, os, json, re, subprocess
A = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
LIB = f'{A}/r4_bcu/place'
args = [x for x in sys.argv[1:] if not x.startswith('--')]
opt = {}
withs = []
for x in sys.argv[1:]:
    if x.startswith('--with='): withs.append(os.path.abspath(x[7:]))
    elif x.startswith('--'): k, _, v = x[2:].partition('='); opt[k] = v or '1'
M = json.load(open(args[0])); out = os.path.abspath(args[1]); os.makedirs(out, exist_ok=True)
P = json.load(open(f'{A}/final/deliver/best_placement_gu.json'))
for o in [f'{A}/r4_bcu/overrides/60_r4_bcu.json'] + withs:
    for r, v in json.load(open(o)).items():
        if not r.startswith('_'): P[r] = list(v)
DX, DY = -23.026, 0.0     # U403 -> U503 (the stage FETs use dy +0.007; the north-row parts follow U403)
mp = lambda r: re.sub(r'^([A-Z]+)4(\d\d)$', r'\g<1>5\2', r)
ov = {}
for r, v in M.items():
    if r.startswith('_'): ov[r] = v; continue
    ov[r] = [float(v[0]), float(v[1]), float(v[2])]
    r2 = mp(r)
    if r2 != r and r2 in P and not r2 in M:
        ov[r2] = [round(v[0] + DX, 3), round(v[1] + DY, 3), float(v[2])]
for r, v in ov.items():
    if r.startswith('_'): continue
    if r not in P: sys.exit(f'unknown ref {r}')
    P[r] = v
json.dump(ov, open(f'{out}/70_r5_north.json', 'w'), indent=1)
json.dump(P, open(f'{out}/placement_gu.json', 'w'), indent=0)
os.chdir(LIB); sys.path.insert(0, LIB)
import placelib
Q = {k: tuple(v) for k, v in P.items()}
errs, miss = placelib.check(Q, verbose=False)
moved = {r for r in ov if not r.startswith('_')}
mine = [e for e in errs if any(re.search(r'\b%s\b' % r, e) for r in moved)]
print(f'CHECK {len(errs)} errors ({len(mine)} involve moved refs), {len(miss)} missing')
for e in errs: print('  !', e)
B = f'{A}/r4_port1/runs/build0/b'
subprocess.run(['python3', 'gu_to_score.py', f'{out}/placement_gu.json', f'{out}/placement.json', 'base.json'], cwd=B, check=True,
               capture_output=True)
if 'render' in opt:
    for tag, x0 in (('p1', 102.5), ('p2', 102.5 + DX)):
        placelib.show(Q, f'{out}/{tag}.png', box=(x0, 96.5, x0 + 15, 113.0), scale=50, padnames=True, netlabels=True)
sys.exit(1 if errs or miss else 0)
