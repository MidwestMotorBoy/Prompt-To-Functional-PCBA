"""vsite.py cu.json net x,y [rad=1.2] [--ignore=netregex] [--n=6] [--layer=F]: legal via sites near a pad, nearest first.
A site is legal when a 0.45 mm via clears every other net's copper on all six layers (0.15 mm; 0.25 mm from high-current
tracks, vias and pours) and a straight 0.15 mm stub on the pad's layer from x,y to the site is legal too. Plane pours
(GND, 3V3, PACK_P zones) refill round a via and are not obstacles. Nets matching --ignore are treated as absent."""
import json, sys, math, re
from matplotlib.path import Path
a = [v for v in sys.argv[1:] if not v.startswith('--')]; o = dict(v[2:].split('=', 1) for v in sys.argv[1:] if v.startswith('--'))
d = json.load(open(a[0])); net = a[1]; tx, ty = [float(v) for v in a[2].split(',')]; rad = float(a[3]) if len(a) > 3 else 1.2
ign = re.compile(o['ignore']) if 'ignore' in o else None; SL = o.get('layer', 'F'); NOUT = int(o.get('n', 6))
HC = re.compile(r'^(PACK_P|CELL_N)$|/Cells and Gauge/(CELL|FET_MID)|/(VBAT_SYS|PPHV|VBUS|SW1|SW2|AC_SNS_N|BAT_SNS_P)$')
EXC = re.compile(r'^(GND|3V3)$|REGN$|SW_5V$|SW_3V3$|PP5V$|/(HG|LG)[12]$|HIDRV|LODRV|_G$|(ACP|ACN|SRP|SRN)(_F)?$')     # classes the 0.25 rule leaves out
PLANE = ('GND', '3V3', 'PACK_P')
me_hc = bool(HC.search(net)); me_exc = bool(EXC.search(net))
def clr(n, pad=False):
    if pad: return 0.15
    if HC.search(n) and not me_hc and not me_exc: return 0.25
    if me_hc and not HC.search(n) and not EXC.search(n): return 0.25
    return 0.15
R = rad + 1.5
skip = lambda n: n == net or (ign and ign.search(n))
T = [t for t in d['tracks'] if not skip(t['net']) and min(abs(t['x1'] - tx), abs(t['x2'] - tx)) < R + 3 and min(abs(t['y1'] - ty), abs(t['y2'] - ty)) < R + 3]
V = [v for v in d['vias'] if not (ign and ign.search(v['net'])) and abs(v['x'] - tx) < R and abs(v['y'] - ty) < R]
Pd = [(p, L, Path(poly)) for p in d['pads'] if p['net'] != net and abs(p['x'] - tx) < R + 2 and abs(p['y'] - ty) < R + 2 for L, poly in p['L'].items() if poly]
Fl = [(f, Path(pts)) for f in d['fills'] if not skip(f['net']) and not (f['net'] in PLANE) for pts, hs in f['polys']
      if min(q[0] for q in pts) < tx + R and max(q[0] for q in pts) > tx - R and min(q[1] for q in pts) < ty + R and max(q[1] for q in pts) > ty - R]
def dseg(x, y, t):
    ax, ay, bx, by = t['x1'], t['y1'], t['x2'], t['y2']; L2 = (bx - ax) ** 2 + (by - ay) ** 2
    u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2)); return math.hypot(x - ax - u * (bx - ax), y - ay - u * (by - ay)) - t['w'] / 2
def dpoly(x, y, path):
    if path.contains_point((x, y)): return -1
    vs = path.vertices; m = 9
    for i in range(len(vs)):
        ax, ay = vs[i]; bx, by = vs[(i + 1) % len(vs)]; L2 = (bx - ax) ** 2 + (by - ay) ** 2
        u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2)); m = min(m, math.hypot(x - ax - u * (bx - ax), y - ay - u * (by - ay)))
    return m
def worst(x, y, r, layers):          # smallest (gap - needed) of a disc of radius r at x,y on the given layers
    w = (9, '')
    for t in T:
        if t['l'] in layers:
            g = dseg(x, y, t) - r - clr(t['net'])
            if g < w[0]: w = (g, '%s trk %s' % (t['l'], t['net'].split('/')[-1]))
    for v in V:
        dd = math.hypot(v['x'] - x, v['y'] - y)
        if v['net'] == net:
            if 0.01 < dd < 0.5 and r > 0.2: w = min(w, (dd - 0.5, 'own via hole'))
            continue
        g = dd - v['d'] / 2 - r - clr(v['net'])
        if r > 0.2: g = min(g, dd - 0.5 - 0.02)
        if g < w[0]: w = (g, 'via %s (%.2f,%.2f)' % (v['net'].split('/')[-1], v['x'], v['y']))
    for p, L, path in Pd:
        if L in layers:
            g = dpoly(x, y, path) - r - 0.15
            if g < w[0]: w = (g, '%s pad %s.%s %s' % (L, p['ref'], p['n'], p['net'].split('/')[-1]))
    for f, path in Fl:
        if f['l'] in layers:
            g = dpoly(x, y, path) - r - clr(f['net'])
            if g < w[0]: w = (g, '%s pour %s' % (f['l'], f['net'].split('/')[-1]))
    return w
ALL = ('F', 'In1', 'In2', 'In3', 'In4', 'B'); res = []; st = 0.025; n = int(rad / st)
if 'check' in o:
    print('via', worst(tx, ty, 0.225, ALL)); sys.exit()
for iy in range(-n, n + 1):
    for ix in range(-n, n + 1):
        x, y = tx + ix * st, ty + iy * st; dd = math.hypot(x - tx, y - ty)
        if dd > rad: continue
        g = worst(x, y, 0.225, ALL)
        if g[0] < 0.01: continue
        k = max(1, int(dd / 0.05)); gs = min(worst(tx + (x - tx) * i / k, ty + (y - ty) * i / k, 0.075, (SL,))[0] for i in range(k + 1))
        if gs < 0.01: continue
        res.append((dd, round(x, 3), round(y, 3), round(g[0], 3), g[1], round(gs, 3)))
res.sort()
seen = []
for r in res:
    if all(math.hypot(r[1] - s[1], r[2] - s[2]) > 0.25 for s in seen): seen.append(r)
    if len(seen) >= NOUT: break
for r in seen: print('site (%.3f,%.3f) dist %.2f  via margin %.3f (%s)  stub margin %.3f' % (r[1], r[2], r[0], r[3], r[4], r[5]))
if not seen:
    g = worst(tx, ty, 0.225, ALL); print('no site within', rad, '; at the pad centre the blocker is', g)
