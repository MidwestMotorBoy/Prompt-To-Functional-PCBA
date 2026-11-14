#!/usr/bin/env python3
"""repair.py: local placement repair of a skeleton board driven by router FAILED lines (worker 4).

usage: repair.py --log route.log --place q7s2.json --cu q7s2_cu.json --fz q7s2_fz_dump.json --spec q7s2_spec.json
                 --out w4_x.json [--ics U503,U403,U401,U501] [--margin 0.3] [--radius 14] [--evict 1] [--move-ic U503]

Moves only small signal parts (court < 9 mm2, not skeleton, not J/H/TP/SW, not in hot loops / power draw lists).
A move is legal when the courtyard stays inside the board, off no-footprint keep-outs, off every other courtyard on
its side and off the final outer-layer power copper of its side (spec zones/tracks/vias grown by --margin).
Cost of a part = sum of half-perimeters of its signal nets (< 12 pads) + spring to its 'serves' pad.
"""
import json, re, sys, argparse, math
from collections import defaultdict
import numpy as np
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

SKEL = set("C206 C420 C423 C430 C431 C434 C438 C444 C446 C520 C523 C530 C531 C534 C538 C544 C546 F102 L401 L402 L501 "
           "L502 Q101 Q102 Q401 Q402 Q501 Q502 R424 R427 R524 R527 RS101 U204 U401 U404 U501 U504".split())
FIXPFX = ('J', 'H', 'TP', 'SW', 'TH')   # TH: NTCs sit where they sense heat
CONS = '/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/constraints.json'

ap = argparse.ArgumentParser()
ap.add_argument('--log', action='append', default=[])
ap.add_argument('--place', required=True); ap.add_argument('--cu', required=True)
ap.add_argument('--fz', required=True); ap.add_argument('--spec', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--ics', default='')
ap.add_argument('--margin', type=float, default=0.3)
ap.add_argument('--edge', type=float, default=0.3)
ap.add_argument('--gap', type=float, default=0.0, help='extra spacing between courtyards')
ap.add_argument('--radius', type=float, default=14.0)
ap.add_argument('--step', type=float, default=0.25)
ap.add_argument('--evict', type=int, default=1)
ap.add_argument('--minfrac', type=float, default=0.15, help='accept a move only if cost drops by this fraction')
ap.add_argument('--mingain', type=float, default=1.0)
ap.add_argument('--passes', type=int, default=3)
ap.add_argument('--longnet', type=float, default=6.0)
ap.add_argument('--move-ic', default='')
ap.add_argument('--freeze', default='', help='extra refs that must not move')
ap.add_argument('--maxmoves', type=int, default=999)
ap.add_argument('--viz', default='')
ap.add_argument('--hand', default='', help='hand board dump (m3_cu.json): transplant each part offset from its home IC')
ap.add_argument('--wh', type=float, default=0.5)
ap.add_argument('--debug', type=int, default=0)
ap.add_argument('--metric', default='near', help='near (pad to nearest partner pad) or hp (half-perimeter)')
ap.add_argument('--softkinds', default='', help='zone kind prefixes a courtyard may sit on (e.g. mirror,via stub)')
ap.add_argument('--trap', type=float, default=40.0, help='penalty per signal net whose pad lands in a pocket its partners cannot reach')
ap.add_argument('--vizbox', default='78,62,122,138')
A = ap.parse_args()

P = {r: list(v) for r, v in json.load(open(A.place)).items()}
P0 = {r: list(v) for r, v in P.items()}
cu = json.load(open(A.cu)); fz = json.load(open(A.fz)); spec = json.load(open(A.spec)); cons = json.load(open(CONS))
FREEZE = set(x for x in A.freeze.split(',') if x)

def rot(lx, ly, k):
    for _ in range(k % 4): lx, ly = -ly, lx
    return lx, ly

fpc = {f['ref']: f for f in cu['fps']}
side = {r: f['layer'] for r, f in fpc.items()}
# pad offsets in the q7 frame (angle P0[r][2])
pads = defaultdict(list)   # ref -> [(num, net, lx, ly, pinfn, multilayer)]
for p in cu['pads']:
    r = p['ref']
    if r not in P: continue
    ml = len(p['shapes']) > 1
    pads[r].append((p['num'], p['net'], p['x'] - P0[r][0], p['y'] - P0[r][1], p['pinfn'], ml))
# courtyard local in q7 frame from fz dump
fzf = {f['ref']: f for f in fz['fps']}; fzp = defaultdict(list)
for p in fz['pads']: fzp[p['ref']].append(p)
court = {}
bad = []
for r in P:
    f = fzf.get(r)
    mine = sorted((round(lx, 2), round(ly, 2)) for (n, net, lx, ly, _, _) in pads[r] if n)
    best = None
    if f:
        c = f['court']; corners = [(c[0] - f['x'], c[1] - f['y']), (c[2] - f['x'], c[3] - f['y'])]
        for k in range(4):
            pp = sorted((round(a, 2), round(b, 2)) for a, b in (rot(q['x'] - f['x'], q['y'] - f['y'], k) for q in fzp[r] if q['num']))
            if len(pp) == len(mine) and all(abs(a[0] - b[0]) + abs(a[1] - b[1]) < 0.03 for a, b in zip(pp, mine)):
                cc = [rot(x, y, k) for x, y in corners]
                best = (min(cc[0][0], cc[1][0]), min(cc[0][1], cc[1][1]), max(cc[0][0], cc[1][0]), max(cc[0][1], cc[1][1]))
                break
    if best is None:
        xs = [lx for (_, _, lx, ly, _, _) in pads[r]] or [0]; ys = [ly for (_, _, lx, ly, _, _) in pads[r]] or [0]
        best = (min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5); bad.append(r)
    court[r] = best
if bad: print('court from pads (no fz match):', ' '.join(bad))

def court_at(r, x, y, a):
    k = int(round((a - P0[r][2]) / 90)) % 4
    c = court[r]; cc = [rot(c[0], c[1], k), rot(c[2], c[3], k)]
    return (x + min(cc[0][0], cc[1][0]), y + min(cc[0][1], cc[1][1]), x + max(cc[0][0], cc[1][0]), y + max(cc[0][1], cc[1][1]))

def pads_at(r, x, y, a):
    k = int(round((a - P0[r][2]) / 90)) % 4
    out = []
    for (n, net, lx, ly, fn, ml) in pads[r]:
        u, v = rot(lx, ly, k); out.append((n, net, x + u, y + v, fn))
    return out

def area(r):
    c = court[r]; return (c[2] - c[0]) * (c[3] - c[1])

# nets
netpads = defaultdict(list)
for r in P:
    for (n, net, lx, ly, fn, ml) in pads[r]:
        if net: netpads[net].append(r)
signal = {n for n, rs in netpads.items() if len(rs) < 12 and len(rs) >= 2}
power_kind = {n.lstrip('/') for n, v in cons['nets'].items() if isinstance(v, dict) and v.get('kind') == 'power'}
power_kind |= {n for n, v in cons['nets'].items() if isinstance(v, dict) and v.get('kind') == 'power'}
signal = {n for n in signal if n not in power_kind and n.lstrip('/') not in power_kind}
nets_of = defaultdict(set)
for n in signal:
    for r in set(netpads[n]): nets_of[r].add(n)

# protected power parts
protect = set(SKEL) | FREEZE
for k, d in cons.get('draw', {}).items():
    protect.add(k)
    for v in d.values():
        if isinstance(v, list): protect |= set(v)
        elif isinstance(v, str) and re.match(r'^[A-Z]+\d+$', v): protect.add(v)
for k, d in cons.get('hot_loops', {}).items():
    protect |= set(d.get('caps', []))
    for s in d.get('switch_pins', []): protect.add(s.split('.')[0])
for k, d in cons.get('kelvin', {}).items(): protect.add(d['resistor'])
for r in P:
    if r.rstrip('0123456789') in FIXPFX: protect.add(r)
heat = set(cons.get('heat', {}).keys()); protect |= heat
protect |= set('R425 R426 R428 R429 R525 R526 R528 R529 R107 R108'.split())   # router SEALED Kelvin tap parts

def movable(r):
    if r in protect: return False
    if any(ml for (*_, ml) in pads[r]): return False
    return area(r) < 9.0

# serves springs
pin2 = {}
for r in P:
    for (n, net, lx, ly, fn, ml) in pads[r]:
        if fn: pin2.setdefault((r, fn), n); pin2.setdefault((r, re.sub(r'_\d+$', '', fn)), n)
serves = {}
for c, t in cons.get('serves', {}).items():
    tr, fn = t.split('.', 1)
    if c in P and tr in P:
        serves[c] = (tr, pin2.get((tr, fn)))
served_by = defaultdict(list)
for c, (tr, _) in serves.items(): served_by[tr].append(c)

PADPOS = {r: pads_at(r, *P[r]) for r in P}
def padxy(r, num):
    for (n, net, x, y, fn) in PADPOS[r]:
        if n == num: return x, y
    return P[r][0], P[r][1]

def net_hp(n, over=None):
    xs = []; ys = []
    for r in set(netpads[n]):
        pl = over[r] if over and r in over else PADPOS[r]
        for (num, net, x, y, fn) in pl:
            if net == n: xs.append(x); ys.append(y)
    return (max(xs) - min(xs)) + (max(ys) - min(ys)) if xs else 0.0

def spring(c, over=None):
    tr, num = serves[c]
    cp = over[c] if over and c in over else PADPOS[c]
    tp = over[tr] if over and tr in over else PADPOS[tr]
    t = next(((x, y) for (n, net, x, y, fn) in tp if n == num), (P[tr][0], P[tr][1]))
    # nearest pad of c that shares a net with the target pin
    tnet = next((net for (n, net, x, y, fn) in tp if n == num), None)
    cand = [(x, y) for (n, net, x, y, fn) in cp if net == tnet] or [(x, y) for (n, net, x, y, fn) in cp]
    return min(abs(x - t[0]) + abs(y - t[1]) for x, y in cand)

def near_cost(r, n, over=None):
    pl = over[r] if over and r in over else PADPOS[r]
    mine = [(x, y) for (num, net, x, y, fn) in pl if net == n]
    oth = [(x, y) for q in set(netpads[n]) if q != r for (num, net, x, y, fn) in (over[q] if over and q in over else PADPOS[q]) if net == n]
    if not oth: return 0.0
    return sum(min(abs(x - a) + abs(y - b) for a, b in oth) for x, y in mine)

def cost(r, over=None):
    c = sum((near_cost(r, n, over) if A.metric == 'near' else net_hp(n, over)) for n in nets_of[r])
    if r in serves: c += spring(r, over)
    for s in served_by[r]: c += spring(s, over)
    if 'CLS' in globals() and A.trap: c += trap_pen(r, over)
    if r in HT:
        pl = over[r] if over and r in over else PADPOS[r]
        cx = sum(p[2] for p in pl) / len(pl); cy = sum(p[3] for p in pl) / len(pl)
        c += A.wh * (abs(cx - HT[r][0]) + abs(cy - HT[r][1]))
    return c

def total_sig():
    return sum(net_hp(n) for n in signal)

# hand transplant targets
HT = {}
if A.hand:
    hd = {f['ref']: (f['x'], f['y']) for f in json.load(open(A.hand))['fps']}
    for r in P:
        if r not in hd or r.startswith('U'): continue
        sc = defaultdict(float)
        for n in nets_of[r]:
            for q in set(netpads[n]):
                if q.startswith('U') and q in hd: sc[q] += 1.0 / max(1, len(set(netpads[n])) - 1)
        if r in serves and serves[r][0].startswith('U'): sc[serves[r][0]] += 1.0
        if not sc: continue
        u = max(sc, key=lambda q: (sc[q], -math.hypot(hd[q][0] - hd[r][0], hd[q][1] - hd[r][1])))
        if math.hypot(hd[u][0] - hd[r][0], hd[u][1] - hd[r][1]) > 15: continue
        k = int(round(P[u][2] / 90)) % 4
        dx, dy = rot(hd[r][0] - hd[u][0], hd[r][1] - hd[u][1], k)
        HT[r] = (P[u][0] + dx, P[u][1] + dy, (P[u][2]) % 360, u)
    print('hand transplant targets', len(HT))

# obstacles
outline = Polygon(cu['outline'][0]['ring'], [h for h in cu['outline'][0].get('holes', [])]).buffer(-A.edge)
outline_p = prep(outline)
obst = {}
for L in ('F.Cu', 'B.Cu'):
    g = []
    for z in spec['zones']:
        if z['layer'] != L or any('plane' in k for k in z.get('kinds', [])): continue
        SK = [x for x in A.softkinds.split(',') if x]
        if SK and all(any(k.startswith(p) for p in SK) for k in z.get('kinds', [])): continue
        for pg in z['polys']:
            try: g.append(Polygon(pg['ring'], pg.get('holes', [])).buffer(A.margin))
            except Exception: pass
    for t in spec['tracks']:
        if t['layer'] == L: g.append(LineString([t['a'], t['b']]).buffer(t['w'] / 2 + A.margin))
    for v in spec['vias']: g.append(Point(v['x'], v['y']).buffer(v['size'] / 2 + A.margin))
    for k in cu['keepouts']:
        if k.get('no_footprints') and L in k['layers']:
            for pg in k['poly']: g.append(Polygon(pg['ring'], pg.get('holes', [])))
    obst[L] = unary_union(g); print(L, 'obstacle area mm2', round(obst[L].area, 1))
obst_p = {L: prep(g) for L, g in obst.items()}
THT = {r for r in P if any(ml for (*_, ml) in pads[r])}

# ---- escape model: hard (non-soft-net) copper per router layer from the spec, F/B free components, via access
from PIL import Image, ImageDraw
from scipy import ndimage
SOFTN = {'GND', 'PACK_P', '3V3'}
RES = 0.1; GX0, GY0 = 78.0, 62.0; NXR, NYR = 450, 770
def rast_layer(L):
    im = Image.new('L', (NXR, NYR), 0); d = ImageDraw.Draw(im)
    tr = lambda pts: [((x - GX0) / RES, (y - GY0) / RES) for x, y in pts]
    for z in spec['zones']:
        if z['layer'] != L or z['net'] in SOFTN or any('plane' in k for k in z.get('kinds', [])): continue
        for pg in z['polys']:
            d.polygon(tr(pg['ring']), fill=1)
            for h in pg.get('holes', []): d.polygon(tr(h), fill=0)
    for t in spec['tracks']:
        if t['layer'] == L and t['net'] not in SOFTN: d.line(tr([t['a'], t['b']]), fill=1, width=max(1, int(t['w'] / RES)))
    for v in spec['vias']:
        if v['net'] in SOFTN: continue
        cx, cy = (v['x'] - GX0) / RES, (v['y'] - GY0) / RES; rr = v['size'] / 2 / RES
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=1)
    # board outline: outside is hard
    o = Image.new('L', (NXR, NYR), 1); ImageDraw.Draw(o).polygon(tr(cu['outline'][0]['ring']), fill=0)
    return np.maximum(np.array(im, bool), np.array(o, bool))
HARD = {L: rast_layer(L) for L in ('F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu')}
DIST = {L: ndimage.distance_transform_edt(~h) * RES for L, h in HARD.items()}
VIA = np.ones((NYR, NXR), bool)
for L in DIST: VIA &= DIST[L] > 0.375
CLS = {}
for L in ('F.Cu', 'B.Cu'):
    free = DIST[L] > 0.25
    lab, nl = ndimage.label(free)
    hv = np.zeros(nl + 1, bool); hv[np.unique(lab[VIA & free])] = True; hv[0] = False
    cls = np.where(hv[lab], 0, lab); cls[~free] = -1
    # every cell -> class of the nearest free cell within 0.5 mm
    dd, (iy, ix) = ndimage.distance_transform_edt(~free, return_indices=True)
    c2 = cls[iy, ix]; c2[dd * RES > 0.5] = -1
    CLS[L] = c2
    print(L, 'free components', nl, 'with via access', int(hv.sum()), 'via-able area mm2', round(VIA.sum() * RES * RES, 1))
def cls_at(L, x, y):
    i = int(round((y - GY0) / RES)); j = int(round((x - GX0) / RES))
    if 0 <= i < NYR and 0 <= j < NXR: return int(CLS[L][i, j])
    return -1
def cls_vec(L, x, y):
    i = np.clip(np.round((y - GY0) / RES).astype(int), 0, NYR - 1); j = np.clip(np.round((x - GX0) / RES).astype(int), 0, NXR - 1)
    return CLS[L][i, j]
def pad_cls(q, num_net_xy):
    return cls_at(side[q] if not q in THT else 'F.Cu', num_net_xy[0], num_net_xy[1])
def other_classes(r, n, over=None):
    s = set()
    for q in set(netpads[n]):
        if q == r: continue
        pl = over[q] if over and q in over else PADPOS[q]
        for (num, net, x, y, fn) in pl:
            if net == n:
                if q in THT: s.add(0)
                else: s.add(cls_at(side[q], x, y))
    return s
def trap_pen(r, over=None):
    pen = 0.0
    pl = over[r] if over and r in over else PADPOS[r]
    for n in nets_of[r]:
        oc = other_classes(r, n, over)
        for (num, net, x, y, fn) in pl:
            if net != n: continue
            c = cls_at(side[r], x, y)
            if c < 0 or c not in oc: pen += A.trap
    return pen

def court_list(L, skip):
    out = []
    for r in P:
        if r in skip: continue
        if side[r] == L or r in THT: out.append((r, court_at(r, *P[r])))
    return out

WHY = defaultdict(int)
def legal(r, x, y, a, skip=()):
    c = court_at(r, x, y, a); L = side[r]
    b = box(*c)
    if not outline_p.contains(b): WHY['edge'] += 1; return False
    if obst_p[L].intersects(b): WHY['copper'] += 1; return False
    WHY['court'] += 1
    g = A.gap
    for q in P:
        if q == r or q in skip: continue
        if side[q] != L and q not in THT: continue
        d = CB[q]
        if c[0] < d[2] + g and d[0] < c[2] + g and c[1] < d[3] + g and d[1] < c[3] + g: return False
    return True

CB = {r: court_at(r, *P[r]) for r in P}

def search(r, center, radius, forbid=None):
    """best legal (x, y, a) for r near center minimising cost(r)"""
    cx, cy = center; st = A.step; best = None
    xs = np.arange(-radius, radius + 1e-9, st)
    cands = []
    nets = list(nets_of[r])
    # precompute other pins per net
    others = {}
    for n in nets:
        pts = [(x, y) for q in set(netpads[n]) if q != r for (num, net, x, y, fn) in PADPOS[q] if net == n]
        others[n] = np.array(pts) if pts else None
    sv = []
    if r in serves:
        tr, num = serves[r]; t = padxy(tr, num)
        tnet = next((net for (n_, net, x, y, fn) in PADPOS[tr] if n_ == num), None); sv.append((t, tnet))
    sb = []
    for s in served_by[r]:
        tr, num = serves[s]; t = padxy(r, num); tnet = next((net for (n_, net, x, y, fn) in PADPOS[r] if n_ == num), None)
        sb.append((s, num, tnet))
    gx, gy = np.meshgrid(xs + cx, xs + cy); gx = gx.ravel(); gy = gy.ravel()
    keep = (gx - cx) ** 2 + (gy - cy) ** 2 <= radius ** 2; gx = gx[keep]; gy = gy[keep]
    allc = []
    for a in (0, 90, 180, 270):
        k = int(round((a - P0[r][2]) / 90)) % 4
        pl = [(n, net, *rot(lx, ly, k)) for (n, net, lx, ly, fn, ml) in pads[r]]
        c = np.zeros_like(gx)
        for n in nets:
            mine = [(u, v) for (num, net, u, v) in pl if net == n]
            o = others[n]
            if A.metric == 'near':
                if o is not None:
                    for u, v in mine:
                        c += np.min(np.abs(gx[None, :] + u - o[:, 0:1]) + np.abs(gy[None, :] + v - o[:, 1:2]), axis=0)
            else:
             xmin = np.min([gx + u for u, v in mine], axis=0); xmax = np.max([gx + u for u, v in mine], axis=0)
             ymin = np.min([gy + v for u, v in mine], axis=0); ymax = np.max([gy + v for u, v in mine], axis=0)
             if o is not None:
                xmin = np.minimum(xmin, o[:, 0].min()); xmax = np.maximum(xmax, o[:, 0].max())
                ymin = np.minimum(ymin, o[:, 1].min()); ymax = np.maximum(ymax, o[:, 1].max())
             c += xmax - xmin + ymax - ymin
            if A.trap:
                oc = np.array(sorted(other_classes(r, n)) or [-99])
                for u, v in mine:
                    cl = cls_vec(side[r], gx + u, gy + v)
                    c += A.trap * ((cl < 0) | ~np.isin(cl, oc))
        for (t, tnet) in sv:
            mine = [(u, v) for (num, net, u, v) in pl if net == tnet] or [(u, v) for (num, net, u, v) in pl]
            c += np.min([np.abs(gx + u - t[0]) + np.abs(gy + v - t[1]) for u, v in mine], axis=0)
        for (s, num, tnet) in sb:
            tl = next(((u, v) for (n_, net, u, v) in pl if n_ == num), (0, 0))
            spt = [(x, y) for (n_, net, x, y, fn) in PADPOS[s] if net == tnet] or [(x, y) for (n_, net, x, y, fn) in PADPOS[s]]
            c += np.min([np.abs(gx + tl[0] - x) + np.abs(gy + tl[1] - y) for x, y in spt], axis=0)
        c += 0.02 * (np.abs(gx - P[r][0]) + np.abs(gy - P[r][1]))   # tie break: stay close
        if r in HT:
            mx = np.mean([u for (n_, net, u, v) in pl]); my = np.mean([v for (n_, net, u, v) in pl])
            c += A.wh * (np.abs(gx + mx - HT[r][0]) + np.abs(gy + my - HT[r][1]))
            if a != HT[r][2]: c += 0.3
        if a != P[r][2]: c += 0.05
        allc.append(np.stack([gx, gy, np.full_like(gx, a), c], 1))
    allc = np.concatenate(allc); order = np.argsort(allc[:, 3])
    WHY.clear()
    for i in order[:20000]:
        x, y, a, c = allc[i]
        if forbid is not None and forbid(r, x, y, a): continue
        if legal(r, x, y, a): return (round(float(x), 3), round(float(y), 3), int(a)), float(c)
    return None, None

def apply(r, pos):
    P[r] = list(pos); PADPOS[r] = pads_at(r, *pos); CB[r] = court_at(r, *pos)

# ---------- failures
fails = []
rx = re.compile(r"FAILED (.+?) ([\d.]+),([\d.]+) \((?:PTH )?[Pp]ad (\S+)\s+of (\S+?)\s*\) -> ([\d.]+),([\d.]+) \((?:PTH )?[Pp]ad (\S+)\s+of (\S+?)\s*\)")
for lg in A.log:
    for line in open(lg):
        m = rx.search(line)
        if m: fails.append((m.group(1), m.group(5), m.group(4), m.group(9), m.group(8)))
print('FAILED lines', len(fails))
ICS = [x for x in A.ics.split(',') if x]

def big(r): return not movable(r)

offenders = defaultdict(lambda: [0, None])     # ref -> [failures, (target ref, pad)]
for (n, ra, pa, rb, pb) in fails:
    for (r, o, po) in ((ra, rb, pb), (rb, ra, pa)):
        if not movable(r): continue
        if ICS and not (o in ICS or any(o2 in ICS for n2 in nets_of[r] for o2 in netpads[n2])): continue
        offenders[r][0] += 1
        if offenders[r][1] is None or big(o): offenders[r][1] = (o, po)
# long 2/3-pad signal nets
for n in signal:
    rs = list(set(netpads[n]))
    if len(rs) > 3 or net_hp(n) < A.longnet: continue
    for r in rs:
        if not movable(r): continue
        bigs = [q for q in rs if q != r and big(q)]
        if ICS and not any(q in ICS for n2 in nets_of[r] for q in netpads[n2]): continue
        if r not in offenders: offenders[r] = [0, None]
        if offenders[r][1] is None and bigs:
            q = bigs[0]; num = next(nn for (nn, net, *_r) in pads[q] if net == n); offenders[r][1] = (q, num)

def ring_count(ic, d=2.5):
    c = CB[ic]; cnt = 0
    for (n, net, x, y, fn) in [pp for q in P if q != ic and side[q] == side[ic] for pp in PADPOS[q]]:
        pass
    seen = set()
    for q in P:
        if q == ic or (side[q] != side[ic]): continue
        for (n, net, x, y, fn) in PADPOS[q]:
            dx = max(c[0] - x, 0, x - c[2]); dy = max(c[1] - y, 0, y - c[3])
            if math.hypot(dx, dy) <= d: seen.add(q); break
    return len(seen)

REPORT_ICS = ['U503', 'U403', 'U401', 'U501', 'U405', 'U505', 'U406', 'U506', 'U404', 'U504', 'U101']
before_sig = total_sig(); before_ring = {ic: ring_count(ic) for ic in REPORT_ICS if ic in P}
print(f'before: signal half-perimeter {before_sig:.0f} mm over {len(signal)} nets; offenders {len(offenders)}')

# optional IC move (step 4): move IC + its support parts by a common translation
for ic in [x for x in A.move_ic.split(',') if x]:
    grp = [ic] + [q for q in P if movable(q) and any(ic in netpads[n] for n in nets_of[q])]
    print('IC move group', ic, grp)

moved = {}
def center_of(r):
    if r in HT and A.hand: return HT[r][0], HT[r][1]
    t = offenders[r][1] if r in offenders else None
    if t: return padxy(*t)
    pts = [(x, y) for n in nets_of[r] for q in set(netpads[n]) if q != r for (num, net, x, y, fn) in PADPOS[q] if net == n]
    if r in serves: pts.append(padxy(*serves[r]))
    if not pts: return P[r][0], P[r][1]
    return float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts]))

def try_move(r, forbid=None, rad=None):
    c0 = cost(r)
    pos, c = search(r, center_of(r), rad or A.radius, forbid)
    if pos is None: return False
    over = {r: pads_at(r, *pos)}; c1 = cost(r, over)
    if c1 < c0 - A.mingain and c1 < c0 * (1 - A.minfrac):
        apply(r, pos); moved[r] = (round(c0, 1), round(c1, 1)); return True
    return False

def gain_est(r):
    return cost(r) * (1 + offenders[r][0])

for ps in range(A.passes):
    order = sorted(offenders, key=lambda r: -gain_est(r)); nm = 0
    for r in order:
        if len(moved) >= A.maxmoves: break
        if try_move(r): nm += 1; continue
        if ps == 0 and offenders[r][0] and A.debug: print(f'  stuck {r} fails {offenders[r][0]} cost {cost(r):.1f} target {offenders[r][1]} why(top 20000) {dict(WHY)}')
        if A.evict and offenders[r][1]:
            # evict unrelated parts within 3 mm of the target pad, then retry
            tr, tp = offenders[r][1]; tx, ty = padxy(tr, tp)
            mynets = nets_of[r]
            vict = [q for q in P if q != r and movable(q) and side[q] == side[r] and q not in moved and q not in offenders
                    and not (nets_of[q] & nets_of[tr] if tr in nets_of else False)
                    and not any(tr in netpads[n] for n in nets_of[q])
                    and math.hypot(P[q][0] - tx, P[q][1] - ty) < 3.5]
            if not vict: continue
            save = {q: list(P[q]) for q in vict + [r]}
            ok = []
            for q in vict:
                c0 = cost(q)
                def forbid(qq, x, y, a, tx=tx, ty=ty): return math.hypot(x - tx, y - ty) < 4.5
                pos, c = search(q, center_of(q), A.radius, forbid)
                if pos is None: continue
                c1 = cost(q, {q: pads_at(q, *pos)})
                if c1 <= c0 + 4.0: apply(q, pos); ok.append((q, c0, c1))
            if ok and try_move(r):
                nm += 1
                for q, c0, c1 in ok: moved[q] = (round(c0, 1), round(c1, 1))
                print(f'  evicted for {r}:', ' '.join(q for q, _, _ in ok))
            else:
                for q, v in save.items(): apply(q, v)
    print(f'pass {ps}: moved {nm}')
    if nm == 0: break

after_sig = total_sig(); after_ring = {ic: ring_count(ic) for ic in REPORT_ICS if ic in P}
print(f'after:  signal half-perimeter {after_sig:.0f} mm (before {before_sig:.0f})')
print('IC ring (parts with a pad within 2.5 mm):', ' '.join(f'{ic} {before_ring[ic]}->{after_ring[ic]}' for ic in before_ring))
mv = [r for r in P if P[r] != P0[r]]
print(f'parts moved {len(mv)}:', ' '.join(f'{r}({moved.get(r, ("", ""))[0]}->{moved.get(r, ("", ""))[1]})' for r in mv))
assert not (set(mv) & protect), 'protected part moved'
json.dump({r: [round(v[0], 3), round(v[1], 3), int(v[2])] for r, v in P.items()}, open(A.out, 'w'))
print('wrote', A.out)
if A.viz:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    bx = [float(v) for v in A.vizbox.split(',')]
    for L in ('F.Cu', 'B.Cu'):
        fig, ax = plt.subplots(figsize=(14, 14 * (bx[3] - bx[1]) / (bx[2] - bx[0])))
        geoms = getattr(obst[L], 'geoms', [obst[L]])
        for gg in geoms:
            xs, ys = gg.exterior.xy; ax.fill(xs, ys, color='#f4c27a', alpha=0.6, lw=0)
        for r in P:
            if side[r] != L and r not in THT: continue
            c = CB[r]; col = 'red' if r in mv else ('k' if r in protect else 'b')
            ax.add_patch(plt.Rectangle((c[0], c[1]), c[2] - c[0], c[3] - c[1], fill=False, ec=col, lw=0.6))
            if bx[2] - bx[0] < 60 or r.startswith('U'): ax.text((c[0] + c[2]) / 2, (c[1] + c[3]) / 2, r, fontsize=5 if not r.startswith('U') else 8, ha='center', va='center', color=col)
        for n in signal:
            pts = [(x, y) for q in set(netpads[n]) for (num, net, x, y, fn) in PADPOS[q] if net == n and (side[q] == L or q in THT)]
            if len(pts) < 2: continue
            pts.sort(); 
            for (a, b) in zip(pts, pts[1:]): ax.plot([a[0], b[0]], [a[1], b[1]], color='g', lw=0.4)
        ax.set_xlim(bx[0], bx[2]); ax.set_ylim(bx[3], bx[1]); ax.set_aspect('equal')
        fig.savefig(A.viz.replace('.png', '_' + L[0] + '.png'), dpi=110, bbox_inches='tight'); plt.close(fig)
