#!/usr/bin/env python3
"""apply_stage.py <in_abs.json> <stage_template.json> <out_abs.json> [--anchor=REF:x,y,rot ...] [--score=<out_score.json>] [--render=<png prefix>]
Patch the charger power stage of a groundup-style placement ({ref: [x, y, absolute KiCad rot]}) from a template of
poses RELATIVE to the switch (the template's "anchor", e.g. Q401):
    world_xy  = anchor_xy + rotv(dx, dy, anchor_rot)          (fpdb convention, KiCad y down)
    world_rot = anchor_rot + drot
The same description is applied to every port listed in the template ("ports": {name: {"map": [from, to]}}): the
port-2 copy renames each ref (Q401 -> Q501 by the regex map) and anchors it on that port's own switch, so with the
same switch rotation it is a pure translation. The only absolute coordinates are the anchors: taken from the input
placement, or overridden with --anchor=Q401:109.55,100.3,180 (then the port-2 anchor keeps its own offset from the
port-1 anchor as in the input, unless given too).
Then parts the stage now covers are reported (placelib.check: courtyard overlaps and keep-outs)."""
import sys, json, re, os, math
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here); os.chdir(here)
from fpdb import rotv
a = [x for x in sys.argv[1:] if not x.startswith('--')]; opts = [x for x in sys.argv[1:] if x.startswith('--')]
P = {k: list(v) for k, v in json.load(open(a[0])).items()}; T = json.load(open(a[1]))
anc = T['anchor']; over = {}
for o in opts:
    if o.startswith('--anchor='):
        r, v = o[9:].split(':'); over[r] = [float(t) for t in v.split(',')]
def mp(ref, m): return re.sub(m[0], m[1], ref) if m else ref
if 'anchor_from' in T and anc not in over:       # the stage hangs from a fixed part (the inductor): no typed coordinates
    f = T['anchor_from']; fx, fy, fr = P[f['ref']]; dx, dy = rotv(f['dx'], f['dy'], fr)
    over[anc] = [fx + dx, fy + dy, (fr + f['drot']) % 360]
    m2 = T['ports'].get('Port 2', {}).get('map')
    if m2 and mp(f['ref'], m2) in P:
        gx, gy, gr = P[mp(f['ref'], m2)]; dx, dy = rotv(f['dx'], f['dy'], gr); over[mp(anc, m2)] = [gx + dx, gy + dy, (gr + f['drot']) % 360]
base_anchor = P[anc][:]
for port, pd in T['ports'].items():
    m = pd.get('map'); A = mp(anc, m)
    if A in over: ax, ay, ar = over[A]
    elif anc in over:     # keep the port's offset from the port-1 anchor as it was in the input
        ax, ay, ar = over[anc][0] + P[A][0] - base_anchor[0], over[anc][1] + P[A][1] - base_anchor[1], over[anc][2]
    else: ax, ay, ar = P[A]
    for ref, q in T['parts'].items():
        r = mp(ref, m); dx, dy = rotv(q['dx'], q['dy'], ar)
        P[r] = [round(ax + dx, 3), round(ay + dy, 3), round((ar + q['drot'] + 180) % 360 - 180, 1)]
    for ref, q in T.get('extra', {}).get(port, {}).items(): P[ref] = q     # per-port moves of neighbours the stage displaced
import placelib
# neighbours the stage now covers: re-placed by groundup's greedy placer (placelib.auto) near their own nets,
# stage parts and fixed parts held. Only parts that overlap a stage part move.
stage = {mp(r, pd.get('map')) for pd in T['ports'].values() for r in T['parts']}
# keep boxes (switch frame): via sites and copper lanes no evicted part may take
for port, pd in T['ports'].items():
    A = mp(anc, pd.get('map')); ax, ay, ar = P[A]
    for k in T.get('keep', []):
        cs = [rotv(u, v, ar) for u, v in ((k[0], k[1]), (k[2], k[1]), (k[2], k[3]), (k[0], k[3]))]
        placelib.GHOST.append((ax + min(c[0] for c in cs), ay + min(c[1] for c in cs), ax + max(c[0] for c in cs), ay + max(c[1] for c in cs)))
Q = {k: tuple(v) for k, v in P.items()}
for it in range(3):
    errs, _ = placelib.check(Q, verbose=False); moved = False
    for e in errs:
        m = re.match(r'overlap (\S+)/(\S+)', e)
        if not m: continue
        x, y = m.groups(); v = y if (x in stage and y not in stage) else x if (y in stage and x not in stage) else None
        if v is None or v in placelib.FIXED or v not in Q: continue
        print('  evict', v, 'from', x if v == y else y); old = Q.pop(v)
        try: placelib.auto(Q, v, verbose=True)
        except Exception as ex: print('   cannot re-place', v, ex); Q[v] = old
        moved = True
    if not moved: break
P = {k: list(v) for k, v in Q.items()}
json.dump(P, open(a[2], 'w'), indent=0)
errs, missing = placelib.check(Q, verbose=False)
print(f'{len(errs)} placement errors'); [print('  !', e) for e in errs]
# copper lanes (switch frame) -> intent.json for plan_copper.py (kept free of power copper: gate escapes)
for o in opts:
    if o.startswith('--intent=') and T.get('lanes'):
        lanes = []
        for port, pd in T['ports'].items():
            A = mp(anc, pd.get('map')); ax, ay, ar = P[A]
            for ln in T['lanes']:
                pts = [[round(ax + rotv(u, v, ar)[0], 3), round(ay + rotv(u, v, ar)[1], 3)] for u, v in ln['points']]
                lanes.append(dict(layers=ln.get('layers', ['F.Cu']), points=pts, width_mm=ln['width_mm']))
        json.dump({'lanes': lanes}, open(o[9:], 'w'), indent=1); print(len(lanes), 'lanes ->', o[9:])
for o in opts:
    if o.startswith('--score='):
        os.system(f"python3 {here}/../tools/gu_to_score.py {a[2]} {o[8:]}")
    if o.startswith('--render='):
        Q = {k: tuple(v) for k, v in P.items()}
        placelib.show(Q, o[9:] + '_p1.png', (100, 84, 122, 110), 40, padnames=True, netlabels=True)
        placelib.show(Q, o[9:] + '_p2.png', (77, 84, 99, 110), 40, padnames=True, netlabels=True)
