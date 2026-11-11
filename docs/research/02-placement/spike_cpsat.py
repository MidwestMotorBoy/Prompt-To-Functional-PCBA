"""Spike C: can CP-SAT place one block's support parts jointly, and does it beat the one-at-a-time greedy placer?
Block: the 24 passives of the port 1 charger controller (place_p1stage.py), same pin targets as typed there.
Everything else on F.Cu stays where placement.json has it.  Objective: summed Manhattan distance pad -> target pad.
The greedy placer (placelib.auto) is re-run here on the same block, same order and arguments as place_p1stage.py,
with the same clear band round U403, so the two are compared under one rule set.
Usage: spike_cpsat.py <groundup dir> [seconds] [ring mm round U403]"""
import sys, os, re, json, time
g = sys.argv[1]; T = float(sys.argv[2]) if len(sys.argv) > 2 else 60
sys.path.insert(0, g); os.chdir(g)
from fpdb import DB, rotv
from ortools.sat.python import cp_model
db = DB('base.json'); P = {r: tuple(v) for r, v in json.load(open('placement.json')).items()}
src = open('place_p1stage.py').read(); job = {}
for m in re.finditer(r"A\('(\w+)',pins=\{([^}]*)\}", src):
    job[m.group(1)] = {a: (b, c) for a, b, c in re.findall(r"'(\w+)':'(\w+)\.(\w+)'", m.group(2))}
U = 100                                   # integer units per mm (0.01 mm)
STEP = 5                                  # positions on a 0.05 mm grid
BOX = (103.0, 95.0, 120.5, 119.5)
def I(v): return int(round(v * U))
def padw(ref, n, x, y, rot):
    p = next(p for p in db.fp[ref]['pads'] if p['n'] == n); dx, dy = rotv(p['lx'], p['ly'], rot); return x + dx, y + dy
def cost_of(Pl):
    c = 0
    for r, pins in job.items():
        for n, (tr, tn) in pins.items():
            a = padw(r, n, *Pl[r]); b = padw(tr, tn, *Pl[tr]); c += abs(a[0] - b[0]) + abs(a[1] - b[1])
    return c
print('parts in block:', len(job), ' pad targets:', sum(len(v) for v in job.values()))
RINGMM = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
print('recorded placement.json cost (settings of that run unknown): %.2f mm' % cost_of(P))
# re-run the greedy placer on this block under known settings
import placelib as pl
pl.GAP = 0.0; pl.RING = 0.0; pl.RINGS.clear(); pl.RINGS['U403'] = RINGMM; pl.KEEPV = []; pl.GHOST[:] = []
G = {r: v for r, v in P.items() if r not in job}; t0 = time.time()
for mm_ in re.finditer(r"^A\((.*)\)\s*$", src, re.M):
    try: eval('pl.auto(G,' + mm_.group(1) + ',verbose=False)', {'pl': pl, 'G': G})
    except Exception as e: print('  greedy failed:', mm_.group(1)[:30], e)
print('greedy re-run, ring %.1f mm: cost %.2f mm  (%.1f s)' % (RINGMM, cost_of(G) if all(r in G for r in job) else float('nan'), time.time() - t0))
m = cp_model.CpModel(); SH = 3            # shrink courtyards 0.03 mm a side: the greedy placer tolerates 0.05 mm overlap
xi, yi = [], []; var = {}; FIX = []   # fixed parts may overlap each other, so they are not put in NoOverlap2D
for r in P:
    if r in job or db.fp[r]['layer'] != 'F.Cu': continue
    bb = db.world(r, *P[r])['bb']
    if bb[2] < BOX[0] or bb[0] > BOX[2] or bb[3] < BOX[1] or bb[1] > BOX[3]: continue
    k_ = I(RINGMM) if r == 'U403' else 0
    FIX.append((I(bb[0]) + SH - k_, I(bb[1]) + SH - k_, I(bb[2]) - SH + k_, I(bb[3]) - SH + k_))
print('fixed obstacles in window:', len(FIX))
for r in job:
    kx = m.NewIntVar(I(BOX[0]) // STEP, I(BOX[2]) // STEP, r + 'x'); ky = m.NewIntVar(I(BOX[1]) // STEP, I(BOX[3]) // STEP, r + 'y')
    x = m.NewIntVar(I(BOX[0]), I(BOX[2]), ''); y = m.NewIntVar(I(BOX[1]), I(BOX[3]), ''); m.Add(x == STEP * kx); m.Add(y == STEP * ky)
    rb = [m.NewBoolVar(f'{r}r{k}') for k in range(4)]; m.AddExactlyOne(rb); b = db.fp[r]['box']
    for k, rot in enumerate((0, 90, 180, 270)):
        cs = [rotv(cx, cy, rot) for cx, cy in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        x0, x1, y0, y1 = I(min(c[0] for c in cs)) + SH, I(max(c[0] for c in cs)) - SH, I(min(c[1] for c in cs)) + SH, I(max(c[1] for c in cs)) - SH
        xi.append(m.NewOptionalIntervalVar(x + x0, x1 - x0, x + x1, rb[k], '')); yi.append(m.NewOptionalIntervalVar(y + y0, y1 - y0, y + y1, rb[k], ''))
        m.Add(x + x0 >= I(BOX[0])).OnlyEnforceIf(rb[k]); m.Add(x + x1 <= I(BOX[2])).OnlyEnforceIf(rb[k])
        m.Add(y + y0 >= I(BOX[1])).OnlyEnforceIf(rb[k]); m.Add(y + y1 <= I(BOX[3])).OnlyEnforceIf(rb[k])
    ex0 = m.NewIntVar(0, 10 ** 6, ''); ex1 = m.NewIntVar(0, 10 ** 6, ''); ey0 = m.NewIntVar(0, 10 ** 6, ''); ey1 = m.NewIntVar(0, 10 ** 6, '')
    for k, rot in enumerate((0, 90, 180, 270)):
        cs = [rotv(cx, cy, rot) for cx, cy in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        m.Add(ex0 == x + I(min(c[0] for c in cs)) + SH).OnlyEnforceIf(rb[k]); m.Add(ex1 == x + I(max(c[0] for c in cs)) - SH).OnlyEnforceIf(rb[k])
        m.Add(ey0 == y + I(min(c[1] for c in cs)) + SH).OnlyEnforceIf(rb[k]); m.Add(ey1 == y + I(max(c[1] for c in cs)) - SH).OnlyEnforceIf(rb[k])
    for fx0, fy0, fx1, fy1 in FIX:
        s4 = [m.NewBoolVar('') for _ in range(4)]; m.AddBoolOr(s4)
        m.Add(ex1 <= fx0).OnlyEnforceIf(s4[0]); m.Add(ex0 >= fx1).OnlyEnforceIf(s4[1]); m.Add(ey1 <= fy0).OnlyEnforceIf(s4[2]); m.Add(ey0 >= fy1).OnlyEnforceIf(s4[3])
    var[r] = (x, y, rb, kx, ky)
m.AddNoOverlap2D(xi, yi)
def padexpr(ref, n):
    """(xvar, yvar) of a pad of a moving part, or constants for a fixed part"""
    if ref not in var: a = padw(ref, n, *P[ref]); return I(a[0]), I(a[1])
    x, y, rb, _, _ = var[ref]; p = next(p for p in db.fp[ref]['pads'] if p['n'] == n)
    px = m.NewIntVar(0, 10 ** 6, ''); py = m.NewIntVar(0, 10 ** 6, '')
    for k, rot in enumerate((0, 90, 180, 270)):
        dx, dy = rotv(p['lx'], p['ly'], rot); m.Add(px == x + I(dx)).OnlyEnforceIf(rb[k]); m.Add(py == y + I(dy)).OnlyEnforceIf(rb[k])
    return px, py
terms = []
for r, pins in job.items():
    for n, (tr, tn) in pins.items():
        a = padexpr(r, n); b = padexpr(tr, tn)
        for u, v in zip(a, b):
            d = m.NewIntVar(0, 10 ** 5, ''); m.AddAbsEquality(d, u - v); terms.append(d)
m.Minimize(sum(terms))
for r in job:                              # warm start from the greedy answer
    x, y, rot = (G if r in G else P)[r]; m.AddHint(var[r][3], I(x) // STEP); m.AddHint(var[r][4], I(y) // STEP)
    for k in range(4): m.AddHint(var[r][2][k], int(k == round(rot % 360 / 90) % 4))
s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = T; s.parameters.num_workers = 4
t = time.time(); st = s.Solve(m)
print('CP-SAT status', s.StatusName(st), ' %.1f s' % (time.time() - t))
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print('  objective %.2f mm   proven lower bound %.2f mm' % (s.ObjectiveValue() / U, s.BestObjectiveBound() / U))
    Q = dict(P)
    for r in job: Q[r] = (s.Value(var[r][0]) / U, s.Value(var[r][1]) / U, 90 * [s.Value(b) for b in var[r][2]].index(1))
    print('  re-scored with the float geometry: %.2f mm' % cost_of(Q))
    json.dump({r: Q[r] for r in job}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spike_cpsat_result_ring%.1f.json' % RINGMM), 'w'))
