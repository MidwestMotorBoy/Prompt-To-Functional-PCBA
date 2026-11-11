"""Spike B: pre-route placement metrics on the Monolith dump, hand placement (base.json positions) against the
scripted placement (placement.json).  Usage: spike_metrics.py <groundup dir>
Metrics per signal net (plane nets and single-pad nets left out): HPWL, minimum spanning tree (Manhattan and
Euclidean), and the number of crossings between MST edges of different nets on the same side-agnostic plane."""
import sys, json, math, re, itertools
sys.path.insert(0, sys.argv[1]); import os; os.chdir(sys.argv[1])
from fpdb import DB, rotv
db = DB('base.json')
PLANE = re.compile(r'(^|/)(GND|PACK_P|3V3|CELL_P|PACK_N|VBUS\d*|VSYS\d*|.*PGND.*)$')
def pads(P):
    nets = {}
    for r, (x, y, rot) in P.items():
        for p in db.fp[r]['pads']:
            if not p['net'] or p['net'].startswith('unconnected'): continue
            dx, dy = rotv(p['lx'], p['ly'], rot); nets.setdefault(p['net'], []).append((x + dx, y + dy))
    return nets
def mst(pts, man=True):
    n = len(pts); inT = [False] * n; d = [1e18] * n; par = [-1] * n; d[0] = 0; tot = 0; edges = []
    for _ in range(n):
        i = min((k for k in range(n) if not inT[k]), key=lambda k: d[k]); inT[i] = True; tot += d[i]
        if par[i] >= 0: edges.append((pts[par[i]], pts[i]))
        for k in range(n):
            if inT[k]: continue
            w = abs(pts[i][0] - pts[k][0]) + abs(pts[i][1] - pts[k][1]) if man else math.dist(pts[i], pts[k])
            if w < d[k]: d[k] = w; par[k] = i
    return tot, edges
def cross(a, b):
    (p, q), (r, s) = a, b
    def o(a, b, c): return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r) * o(p, q, s) < -1e-12 and o(r, s, p) * o(r, s, q) < -1e-12
def score(P, name, big=12):
    nets = {n: v for n, v in pads(P).items() if len(v) > 1 and not PLANE.search(n) and len(v) <= big}
    hp = sum(max(x for x, _ in v) - min(x for x, _ in v) + max(y for _, y in v) - min(y for _, y in v) for v in nets.values())
    E = []; mm = me = 0
    for n, v in nets.items():
        t, _ = mst(v, True); mm += t; t, e = mst(v, False); me += t; E += [(n, x) for x in e]
    c = sum(1 for (n1, a), (n2, b) in itertools.combinations(E, 2) if n1 != n2 and cross(a, b))
    print(f'{name:10s} nets {len(nets):4d}  HPWL {hp:7.1f}  MST-Manhattan {mm:7.1f}  MST-Euclid {me:7.1f}  MST-edge crossings {c}')
hand = {r: f['base'] for r, f in db.fp.items()}
scr = {r: tuple(v) for r, v in json.load(open('placement.json')).items()}
moved = sum(1 for r in scr if max(abs(scr[r][0] - hand[r][0]), abs(scr[r][1] - hand[r][1])) > 0.01 or (scr[r][2] - hand[r][2]) % 360)
print('parts', len(hand), 'moved between the two placements', moved)
score(hand, 'hand'); score(scr, 'scripted')
