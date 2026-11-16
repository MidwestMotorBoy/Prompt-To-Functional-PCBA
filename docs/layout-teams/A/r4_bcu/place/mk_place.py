#!/usr/bin/env python3
"""mk_place.py <moves.json> <out_dir> [--base=best_gu.json] [--render]
r4_bcu stage moves on top of team A's best placement (groundup format {ref: [x, y, absolute rot]}).

moves.json: {"anchor": "Q401", "parts": {ref: {"dx":, "dy":, "rot": absolute rot, "rule": "..."}}, "keep_free": [...]}
  every pose is relative to the port-1 anchor switch (Q401, itself hung from the fixed inductor by the stage template)
  and is applied to port 2 by the template's ref map (4xx -> 5xx) relative to Q501: the same description on both
  ports, a pure translation (both switches have the same rotation).
Then: parts the moved ones now overlap are re-placed by groundup's greedy placer (placelib.auto, as stage/apply_stage.py
does), placelib.check (courtyards, edge, lip, pegs) must be clean, and the outputs are written:
  <out_dir>/placement_gu.json   full groundup placement
  <out_dir>/override_gu.json    only the refs that differ from the base ({ref: [x, y, abs rot]}, groundup format,
                                usable as an overrides/*.json file for final/build.sh-style builds)
  <out_dir>/placement.json      scorecard format (tools/gu_to_score.py with the template dump base.json)
  <out_dir>/p1.png, p2.png      placelib renders of both stages (--render)"""
import sys, os, json, re
here = os.path.dirname(os.path.abspath(__file__)); os.chdir(here); sys.path.insert(0, here)
import placelib
a = [x for x in sys.argv[1:] if not x.startswith('--')]; opt = dict((x[2:].split('=', 1) + [''])[:2] for x in sys.argv[1:] if x.startswith('--'))
M = json.load(open(a[0])); out = os.path.abspath(a[1]); os.makedirs(out, exist_ok=True)
base = json.load(open(opt.get('base') or 'best_gu.json'))
P = {k: list(v) for k, v in base.items()}
anc = M.get('anchor', 'Q401')
mp = lambda r: re.sub(r'^([A-Z]+)4(\d\d)$', r'\g<1>5\2', r)
moved = set()
for port in ('Port 1', 'Port 2'):
    A = anc if port == 'Port 1' else mp(anc); ax, ay, ar = P[A]
    assert abs(ar - P[anc][2]) < 1e-6, 'anchors must have the same rotation'
    for ref, q in M['parts'].items():
        r = ref if port == 'Port 1' else mp(ref)
        P[r] = [round(ax + q['dx'], 3), round(ay + q['dy'], 3), float(q['rot'])]; moved.add(r)
for r, v in M.get('abs', {}).items():
    P[r] = list(v); moved.add(r)
# keep-free boxes (anchor frame, both ports): no re-placed neighbour may land there
for port in ('Port 1', 'Port 2'):
    A = anc if port == 'Port 1' else mp(anc); ax, ay, _ = P[A]
    for k in M.get('keep_free', []): placelib.GHOST.append((ax + k[0], ay + k[1], ax + k[2], ay + k[3]))
Q = {k: tuple(v) for k, v in P.items()}
evicted = []
for it in range(4):
    errs, _ = placelib.check(Q, verbose=False); ch = False
    for e in errs:
        m = re.match(r'overlap (\S+)/(\S+)', e)
        if not m: continue
        x, y = m.groups(); v = y if (x in moved and y not in moved) else x if (y in moved and x not in moved) else None
        if v is None or v in placelib.FIXED or v not in Q: continue
        old = Q.pop(v); print('  evict', v, 'from', x if v == y else y)
        try: placelib.auto(Q, v, verbose=True); evicted.append(v)
        except Exception as ex: print('   cannot re-place', v, ex); Q[v] = old
        ch = True
    if not ch: break
errs, missing = placelib.check(Q, verbose=False)
print(f'CHECK {"clean" if not errs and not missing else f"{len(errs)} errors"}'); [print('  !', e) for e in errs]
P = {k: list(v) for k, v in Q.items()}
json.dump(P, open(f'{out}/placement_gu.json', 'w'), indent=0)
ov = {r: P[r] for r in sorted(P) if r not in base or max(abs(float(u) - float(w)) for u, w in zip(P[r], base[r])) > 1e-6}
ov['_rules'] = {r: q.get('rule', '') for r, q in M['parts'].items()}
json.dump(ov, open(f'{out}/override_gu.json', 'w'), indent=0)
os.system(f'python3 /home/claude/repo/docs/layout-teams/A/tools/gu_to_score.py {out}/placement_gu.json {out}/placement.json {here}/base.json')
print('moved', len(moved), 'evicted', evicted, 'override refs', len(ov) - 1)
if 'render' in opt:
    placelib.show(Q, f'{out}/p1.png', (100, 86, 122, 113), 40, padnames=True, netlabels=True)
    placelib.show(Q, f'{out}/p2.png', (77, 86, 99, 113), 40, padnames=True, netlabels=True)
sys.exit(1 if errs else 0)
