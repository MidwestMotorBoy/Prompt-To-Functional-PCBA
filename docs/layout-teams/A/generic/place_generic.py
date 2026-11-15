#!/usr/bin/env python3
"""place_generic.py - whole-board placement with no typed coordinates for support parts and no typed mechanical numbers.

  python3 place_generic.py --dump base.json --pro board.kicad_pro [--dru board.kicad_dru] --constraints constraints.json
        --anchors anchors.json --fixed fixed_parts.json [--enclosure enclosure.json] --out outdir [options]

Inputs a new board must supply:
  dump          gdump.py of the board (footprints with pads, nets, pin functions, courtyards; rule areas; outline)
  pro / dru     the KiCad project and custom rules (copper-to-edge, default netclass clearance / track / via)
  constraints   serves (cap -> IC pin it serves), hot_loops (caps in order + switch pins), pin_pads, kelvin, heat
  anchors       a pose (or a derivation) for each big part; WHICH parts are anchors is the rule anchor_rule() below
  fixed         the explicit list of parts fixed by the enclosure, with reasons (plus the rule: locked, B.Cu, J/H/TP/SW)
  enclosure     (optional) limits the board file does not hold, e.g. the lips of a cup
Writes outdir/placement_gu.json (absolute pose of every part), outdir/report.json, outdir/place.log.
"""
import argparse, json, math, os, re, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glib

ap = argparse.ArgumentParser()
ap.add_argument('--dump', required=True); ap.add_argument('--pro', required=True); ap.add_argument('--dru')
ap.add_argument('--constraints', required=True); ap.add_argument('--anchors', required=True); ap.add_argument('--fixed', required=True)
ap.add_argument('--enclosure'); ap.add_argument('--out', required=True)
ap.add_argument('--gap', type=float, default=0.25, help='courtyard gap round small parts (<= 3 pads), mm')
ap.add_argument('--ringk', type=float, default=1.0, help='scale of the derived escape ring round fine-pitch ICs')
ap.add_argument('--wgnd', type=float, default=0.5, help='weight of a decoupling cap plane pad toward the served part\'s pads on that plane')
ap.add_argument('--order', default='serves,kelvin,bridge', help='order of the middle tiers')
ap.add_argument('--no-sheet', action='store_true', help='net targets on any sheet, not only the part\'s own block')
ap.add_argument('--wpull', type=float, default=0.15)
ap.add_argument('--derive', default='', help='comma list of extra anchor derivations to try: fets (switch FETs at their fixed inductor)')
ap.add_argument('--no-twins', action='store_true', help='place port 2 support parts on their own instead of translating port 1')
ap.add_argument('--corr', type=float, default=0.3, help='power corridor width per amp (mm/A, clamped 0.8..2.0); 0 = off')
ap.add_argument('--corr-path', type=int, default=0, help='1: corridor follows the shortest free grid path round placed parts; 0: straight line; 2: both')
ap.add_argument('--corr-floor', type=float, default=1.4, help='narrowest corridor, mm (track + clearance + room for the planner to bend)')
ap.add_argument('--corr-maxlen', type=float, default=8.0, help='no corridor for a link longer than this (mm, straight line)')
ap.add_argument('--corr-pin', type=float, default=2.0, help='half-size (mm) of a no-other-net box round each IC power-pin end of a corridor')
ap.add_argument('--serves-noring', type=int, default=2, help='1: decoupling caps (constraints serves) ignore the escape bands, so they reach their pins; 2: only caps on a power-net pin')
ap.add_argument('--corr-max', type=float, default=1.5, help='corridor width cap, mm')
ap.add_argument('--corr-min', type=float, default=1.0, help='power nets of at least this current (constraints nets.current_a) get corridors')
ap.add_argument('--anchor-only', default='', help='comma list of anchors to drop (placed automatically instead)')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
LOG = open(os.path.join(a.out, 'place.log'), 'w')
def log(*x):
    s = ' '.join(str(v) for v in x); print(s, file=LOG); LOG.flush()
t0 = time.time()

dump = json.load(open(a.dump)); db = glib.DB(a.dump)
rules = glib.read_rules(a.pro, a.dru)
enc = json.load(open(a.enclosure)) if a.enclosure else None
C = json.load(open(a.constraints)); FX = json.load(open(a.fixed)); AN = json.load(open(a.anchors))['anchors']
lim = glib.Limits(dump, rules, enc)
norm = lambda n: n.lstrip('/')
import fnmatch
_ns = json.load(open(a.pro))['net_settings']
def _cls(net, dumped):
    """net class: the dump's, else the project's netclass_assignments / netclass_patterns (KiCad 10 dumps say Default)"""
    if dumped and dumped != 'Default': return dumped
    if net in (_ns.get('netclass_assignments') or {}): return _ns['netclass_assignments'][net]
    for pat in _ns.get('netclass_patterns') or []:
        if fnmatch.fnmatchcase(net, pat['pattern']): return pat['netclass']
    return 'Default'
netcls = {norm(k): _cls(k, v['cls']) for k, v in dump['nets'].items()}
npads = {norm(k): len(v) for k, v in db.netpads.items()}
cnets = {norm(k): v for k, v in C.get('nets', {}).items()}

# ---------------------------------------------------------------- rules: fixed parts, plane nets, anchors
def fixed_rule(r):
    f = db.fp[r]
    return f['locked'] or f['layer'] == 'B.Cu' or re.match(r'(J|H|TP|SW)\d', r) is not None
FIXED = {r for r in db.fp if fixed_rule(r)} | {e['ref'] for e in FX['explicit']}
PLANE = {n for n in npads if netcls.get(n) == 'GND' or (cnets.get(n, {}).get('kind') == 'power' and npads[n] >= 20)}
PLANE_RAW = {k for k in db.netpads if norm(k) in PLANE}
KELV_R = {k['resistor'] for k in C.get('kelvin', {}).values()}
KELV_NETS = {k[x] for k in C.get('kelvin', {}).values() for x in ('pos', 'neg')}
def is_shunt(r):   # 2-pad resistor whose both nets carry power current: a current-sense shunt
    f = db.fp[r]
    if not r.startswith('R') or len(f['pads']) != 2: return False
    return all(netcls.get(norm(p['net'])) in ('HighCurrent', 'GND') or cnets.get(norm(p['net']), {}).get('kind') == 'power' for p in f['pads']) \
        and any(netcls.get(norm(p['net'])) == 'HighCurrent' for p in f['pads'])
SENSE_R = KELV_R | {r for r in db.fp if r not in FIXED and is_shunt(r)}
def anchor_rule(r):
    """big parts: ICs, inductors, fuses, shunts / kelvin sense resistors, FETs and diodes with 8 or more pads"""
    if r in FIXED: return False
    k = re.match(r'[A-Z]+', r).group()
    return k in ('U', 'L', 'F') or r in SENSE_R or (k in ('Q', 'D') and len(db.fp[r]['pads']) >= 8)
ANCH = sorted(r for r in db.fp if anchor_rule(r))
drop = set(filter(None, a.anchor_only.split(',')))
log(f'fixed {len(FIXED)}  anchors by rule {len(ANCH)}  plane nets {sorted(PLANE)}  sense resistors {sorted(SENSE_R)}')
missing_anchor = [r for r in ANCH if r not in AN and r not in drop]
if missing_anchor: sys.exit(f'anchors.json lacks {missing_anchor}')

# ---------------------------------------------------------------- repeated blocks: twin map between sheets
def sheet(r): return db.fp[r]['sheet'].strip('/')
def twin_map():
    """match parts of sheets whose names differ only in a number ('USB Port 1' / 'USB Port 2'): same footprint and
    value and the same nets once the sheet prefix is swapped; ties broken by the reference number's last two digits"""
    sheets = sorted({sheet(r) for r in db.fp})
    M = {}
    for s1 in sheets:
        for s2 in sheets:
            if s1 >= s2 or re.sub(r'\d+', '#', s1) != re.sub(r'\d+', '#', s2): continue
            def sig(r, s):
                return (db.fp[r]['fp'], db.fp[r]['val'], tuple(sorted((p['n'], p['net'].replace(f'/{s}/', '/#/')) for p in db.fp[r]['pads'])))
            A1 = [r for r in db.fp if sheet(r) == s1]; A2 = [r for r in db.fp if sheet(r) == s2]
            by = {}
            for r in A2: by.setdefault(sig(r, s2), []).append(r)
            for r in A1:
                c = by.get(sig(r, s1), [])
                if len(c) > 1: c = [q for q in c if q[-2:] == r[-2:]] or c
                if len(c) == 1: M[r] = c[0]
    return M
TWIN = twin_map(); TWIN_INV = {v: k for k, v in TWIN.items()}
log(f'twin pairs found from the netlist: {len(TWIN)}')

# ---------------------------------------------------------------- placer state: fixed parts, then anchors
rings = {r: glib.escape_ring(db, r, rules, PLANE_RAW, a.ringk) for r in db.fp if r not in FIXED and r.startswith('U')}
log('escape rings (derived):', {r: v for r, v in rings.items() if v})
pl = glib.Placer(db, lim, rules, gap=a.gap, rings=rings, wpull=a.wpull)
for r in FIXED: pl.P[r] = tuple(db.fp[r]['base'])
how = {r: 'fixed' for r in FIXED}
typed_anchor = []
for r in ANCH:
    if r in drop: continue
    e = AN[r]
    if 'pose' in e:
        pl.P[r] = tuple(e['pose']); how[r] = 'anchor typed'; typed_anchor.append(r)
for r in ANCH:
    if r in drop: continue
    e = AN[r]
    if 'translate' in e:
        s, (fa, fb) = e['translate'], e['pair']
        dx = db.fp[fb]['base'][0] - db.fp[fa]['base'][0]; dy = db.fp[fb]['base'][1] - db.fp[fa]['base'][1]
        x, y, rot = pl.P[s]; pl.P[r] = (round(x + dx, 3), round(y + dy, 3), rot); how[r] = f'anchor = {s} + ({fa}->{fb})'
# ---------------------------------------------------------------- anchors that collide with fixed parts or leave the limits:
# move each to the nearest legal pose at its own rotation (target = its own typed pad positions); a translated twin moves with it
LEGAL_DONE = set()
def legalize():
    moved = {}
    errs, _ = pl.check(fixed=FIXED)
    bad = set()
    for e in errs:
        for r in re.findall(r'[A-Z]+\d+', e.split(' ', 1)[1]):
            if r in pl.P and r not in FIXED: bad.add(r)
    for r in sorted(bad):
        if how.get(r, '').startswith('anchor =') and how[r].split()[2] in bad: continue   # moved with its twin
        x, y, rot = pl.P[r]
        T = [(p['n'], np.array([db.pad(pl.P, r, p['n'])]), 1.0) for p in db.fp[r]['pads']]
        tw = [q for q in pl.P if how.get(q, '').startswith(f'anchor = {r} +') and q not in LEGAL_DONE]
        twin = None
        if tw:
            q = tw[0]; twin = (q, pl.P[q][0] - x, pl.P[q][1] - y)
        old = pl.P[r]; del pl.P[r]
        if twin: del pl.P[twin[0]]
        pl.noring = True
        try: pl.place(r, T, at=(x, y), rots=(rot,), gap=0.0, twin=twin)
        except RuntimeError:
            if not twin: raise
            # the pair has no common legal shift: legalise each on its own (the translation is broken for this pair, reported)
            q, ddx, ddy = twin; pl.place(r, T, at=(x, y), rots=(rot,), gap=0.0)
            Tq = [(n, pts + np.array([ddx, ddy]), w) for n, pts, w in T]
            pl.place(q, Tq, at=(x + ddx, y + ddy), rots=(rot,), gap=0.0); how[q] += ' (legalised on its own)'
            log(f'legalised {r} and its twin {q} separately: no common shift')
        pl.noring = False
        LEGAL_DONE.add(r)
        if twin: LEGAL_DONE.add(twin[0])
        moved[r] = (old, pl.P[r]); log(f'legalised anchor {r}: {old} -> {pl.P[r]}' + (f' (twin {twin[0]} -> {pl.P[twin[0]]})' if twin else ''))
    return moved
LEGAL = legalize()
# ---------------------------------------------------------------- pin helpers
_PC = {}
_pad_raw = db.pad
def _pad_cached(P, r, n):
    k = (r, str(n), P[r])
    v = _PC.get(k)
    if v is None: v = _PC[k] = _pad_raw(P, r, n)
    return v
db.pad = _pad_cached
def pin_pads(spec):
    r, name = spec.split('.', 1)
    if spec in C.get('pin_pads', {}): return r, list(C['pin_pads'][spec])
    ns = [p['n'] for p in db.fp[r]['pads'] if p['pinfn'] == name]
    if not ns: ns = [p['n'] for p in db.fp[r]['pads'] if p['n'] == name]
    return r, sorted(set(ns))
def pts_of(r, ns):
    if r not in pl.P: return np.zeros((0, 2))
    return np.array([db.pad(pl.P, r, n) for n in ns])
def padnet(r, n):
    for p in db.fp[r]['pads']:
        if p['n'] == n: return p['net']
def pads_on(r, net): return sorted({p['n'] for p in db.fp[r]['pads'] if p['net'] == net})

# ---------------------------------------------------------------- power corridors: keep the straight path between the placed
# parts of every power net (constraints nets: kind power, current_a >= corr-min, not a plane) free of support parts that are
# not on that net, so the copper planner finds a path (the generic placer once parked two resistors between L502 and U501's PP5V pins)
CORR = {}
def series_pad(q, pd):
    """does this pad carry the net's current (same rule as tools/copper/roles.py kind_of): connectors, inductors, fuses,
    FETs, diodes, switches always; resistors when they are sense resistors; IC pads only when their copper is at least
    3x the IC's median pad and 0.3 mm2 (power pins are big, sense pins are not); capacitors are shunts (no corridor)"""
    k = re.match(r'[A-Z]+', q).group()
    if k in ('J', 'L', 'F', 'Q', 'D', 'SW', 'K'): return True
    if k in ('R', 'RS'): return q in SENSE_R
    if k in ('U', 'IC'):
        ar = [x['sx'] * x['sy'] for x in db.fp[q]['pads']]
        return pd['sx'] * pd['sy'] >= 3 * float(np.median(ar)) and pd['sx'] * pd['sy'] >= 0.3
    return False
def grid_path(L, pa, pb, w, res=0.2, margin=6.0, ra=0.0, rb=0.0, net=None):
    """shortest 8-connected grid path from pa to pb on layer L that keeps w/2 clear of every placed courtyard and of the
    board edge (cells within w/2+0.6 mm of either end are free, so the path can reach a pin inside its own part's
    courtyard); None if there is none. This is where the copper planner will have to draw the net, so it is reserved."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    import shapely
    x0 = min(pa[0], pb[0]) - margin; y0 = min(pa[1], pb[1]) - margin; x1 = max(pa[0], pb[0]) + margin; y1 = max(pa[1], pb[1]) + margin
    xs = np.arange(x0, x1, res); ys = np.arange(y0, y1, res); GX, GY = np.meshgrid(xs, ys); ny, nx = GX.shape
    free = shapely.contains_xy(lim.inset.buffer(-w / 2), GX, GY)
    h = w / 2
    for q, v in pl.P.items():
        if db.fp[q]['layer'] != L: continue
        b = db.bbox(q, *v)
        if b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1: continue
        free &= ~((GX > b[0] - h) & (GX < b[2] + h) & (GY > b[1] - h) & (GY < b[3] + h))
    for L2, b, n2 in pl.corr:              # corridors of other nets reserved before this one
        if L2 != L or n2 == net or b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1: continue
        free &= ~((GX > b[0] - h) & (GX < b[2] + h) & (GY > b[1] - h) & (GY < b[3] + h))
    for e, re_ in ((pa, ra), (pb, rb)): free |= np.hypot(GX - e[0], GY - e[1]) < h + 0.6 + re_
    idx = np.arange(nx * ny).reshape(ny, nx); rows = []; cols = []; wts = []
    for dy, dx, c in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142)):
        xa0, xa1 = max(0, -dx), nx - max(0, dx)
        A_ = (slice(0, ny - dy), slice(xa0, xa1)); B_ = (slice(dy, ny), slice(xa0 + dx, xa1 + dx))
        m = free[A_] & free[B_]
        rows.append(idx[A_][m]); cols.append(idx[B_][m]); wts.append(np.full(int(m.sum()), c))
    G = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(nx * ny, nx * ny)).tocsr()
    ja = int(np.argmin(np.hypot(GX - pa[0], GY - pa[1]))); jb = int(np.argmin(np.hypot(GX - pb[0], GY - pb[1])))
    d, pred = dijkstra(G, directed=False, indices=ja, return_predecessors=True)
    if not np.isfinite(d[jb]): return None
    out = []; k = jb
    while k != ja and k >= 0: out.append((float(GX.flat[k]), float(GY.flat[k]))); k = pred[k]
    out.append((float(GX.flat[ja]), float(GY.flat[ja])))
    return out[::-1]
def corridors():
    from scipy.sparse.csgraph import minimum_spanning_tree
    EDGES = []
    for cn, v in C.get('nets', {}).items():
        if v.get('kind') != 'power' or v.get('current_a', 0) < a.corr_min or a.corr <= 0: continue
        raw = [k for k in db.netpads if norm(k) == norm(cn)]
        if not raw or norm(cn) in PLANE: continue
        net = raw[0]; w = min(max(a.corr * v['current_a'], a.corr_floor), max(a.corr_max, a.corr_floor))
        for L in ('F.Cu', 'B.Cu'):
            grp = {}; rad = {}
            for q, n in db.netpads[net]:
                if q not in pl.P: continue
                pd = [p for p in db.fp[q]['pads'] if p['n'] == n][0]
                if pd['drill'] == 0 and db.fp[q]['layer'] != L: continue
                if not series_pad(q, pd): continue
                grp.setdefault(q, []).append(db.pad(pl.P, q, n)); rad[db.pad(pl.P, q, n)] = max(pd['sx'], pd['sy']) / 2
            parts = sorted(grp)
            if len(parts) < 2: continue
            G = np.zeros((len(parts), len(parts)))
            pair = {}
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)):
                    A_ = np.array(grp[parts[i]]); B_ = np.array(grp[parts[j]])
                    D = np.hypot(A_[:, None, 0] - B_[None, :, 0], A_[:, None, 1] - B_[None, :, 1]); k = np.unravel_index(np.argmin(D), D.shape)
                    G[i, j] = D[k] + 1e-6; pair[(i, j)] = (A_[k[0]], B_[k[1]])
            T_ = minimum_spanning_tree(G).toarray()
            for i, j in zip(*np.nonzero(T_)):
                (x0, y0), (x1, y1) = pair[(min(i, j), max(i, j))]
                EDGES.append((math.hypot(x1 - x0, y1 - y0), cn, net, L, w, (x0, y0), (x1, y1), rad.get((x0, y0), 0), rad.get((x1, y1), 0), parts[min(i, j)], parts[max(i, j)]))
    # shortest edges first (they have the fewest ways round); each path keeps clear of the corridors already reserved
    for ln, cn, net, L, w, (x0, y0), (x1, y1), ra, rb, pi, pj in sorted(EDGES, key=lambda e: e[0]):
        if ln > a.corr_maxlen: CORR.setdefault(norm(cn), []).append((pi, pj, round(ln, 2), L, 'too long: none')); continue
        path = grid_path(L, (x0, y0), (x1, y1), w, ra=ra, rb=rb, net=net) if a.corr_path else None
        nstep = max(1, int(ln / 0.4))
        straight = [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in np.linspace(0, 1, nstep + 1)]
        if path is None: path = straight; kind = 'straight'
        elif a.corr_path == 2: path = path + straight; kind = 'path+straight'   # both: the planner may take either
        else: kind = 'path'
        pl_ = sum(math.hypot(path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1]) for k in range(len(path) - 1))
        for x, y in path[::2] + [path[-1]]:
            pl.corr.append((L, (x - w / 2, y - w / 2, x + w / 2, y + w / 2), net))
        for q, (ex, ey) in ((pi, (x0, y0)), (pj, (x1, y1))):    # approach zone at an IC power pin: the planner reaches a
            if q.startswith('U') and a.corr_pin > 0:               # fine-pitch pin only head-on, past the neighbours' escape room
                e = a.corr_pin; pl.corr.append((L, (ex - e, ey - e, ex + e, ey + e), net))
        CORR.setdefault(norm(cn), []).append((pi, pj, round(pl_, 2), L, kind))
corridors()
log('power corridors (net: part pairs):', CORR)
HOT = []   # (cap, supply pin spec, ret pin spec)
for name, h in C.get('hot_loops', {}).items():
    for c in h['caps']: HOT.append((c, h['switch_pins'][0], h['switch_pins'][1], name))
HOTC = {c: (s, g, n) for c, s, g, n in HOT}
SERVES = C.get('serves', {})
HEAT = C.get('heat', {})

def cap_value(r):
    m = re.match(r'([0-9.]+)\s*([pnuµm]?)', db.fp[r]['val'] or '')
    if not m: return 1.0
    return float(m.group(1)) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3, '': 1.0}[m.group(2)]

def default_targets(r, skip=()):
    T = []
    for p in db.fp[r]['pads']:
        if p['n'] in skip or not p['net'] or p['net'] in PLANE_RAW or p['net'].startswith('unconnected'): continue
        mates = [(q, n) for q, n in db.netpads[p['net']] if q != r]
        own = [(q, n) for q, n in mates if sheet(q) == sheet(r)]
        if own and not a.no_sheet: mates = own        # a net that has partners in the part's own block pulls only toward those
        pts = [db.pad(pl.P, q, n) for q, n in mates if q in pl.P]
        if pts: T.append((p['n'], np.array(pts), 1.0, 'net'))
    return T

def targets(r):
    """per-pad targets of part r from the circuit data, and the rule that gave them"""
    f = db.fp[r]
    if r in HOTC:                             # first caps of a hot loop: across the switch pins
        s, g, name = HOTC[r]; T = []
        for spec in (s, g):
            q, ns = pin_pads(spec); net = padnet(q, ns[0])
            for n in pads_on(r, net): T.append((n, pts_of(q, ns), 1.0, 'hot'))
        if T: return T, 'hot_loop ' + name
    if r in SERVES:                           # decoupling: the pad on the served pin's net at that pin
        q, ns = pin_pads(SERVES[r]); net = padnet(q, ns[0]); T = []
        mine = pads_on(r, net)
        for n in mine: T.append((n, pts_of(q, ns), 1.0, 'serves'))
        for p in f['pads']:
            if p['n'] in mine or not p['net']: continue
            if p['net'] in PLANE_RAW:
                qs = pads_on(q, p['net'])
                if qs and a.wgnd > 0: T.append((p['n'], pts_of(q, qs), a.wgnd, 'serves-plane'))
            else:
                T += default_targets(r, skip=[x['n'] for x in f['pads'] if x['n'] != p['n']])
        if T: return T, 'serves ' + SERVES[r]
    if len(f['pads']) <= 3 and r not in SENSE_R:   # kelvin / shunt filter: the pad on the sense resistor's net at that resistor's pad
        T = []
        kel = any(netcls.get(norm(p['net'])) == 'Kelvin' or norm(p['net']) in KELV_NETS for p in f['pads'] if p['net'])
        for p in f['pads']:
            for rs in SENSE_R:
                if kel and rs in pl.P and p['net'] and (p['net'] not in PLANE_RAW or r.startswith('R')):
                    k = pads_on(rs, p['net'])
                    if k: T.append((p['n'], pts_of(rs, k), 1.0, 'kelvin'))
        if T:
            done = {t[0] for t in T}
            return T + default_targets(r, skip=done), 'kelvin'
    if r.startswith('TH') and len(f['pads']) == 2:  # thermistor: at the hottest part of its sheet on its side
        hs = [(v['w'], h) for h, v in HEAT.items() if h in pl.P and sheet(h) == sheet(r) and db.fp[h]['layer'] == f['layer']]
        if hs:
            h = max(hs)[1]; allp = pts_of(h, [p['n'] for p in db.fp[h]['pads']])
            return [(p['n'], allp, 1.0, 'heat') for p in f['pads']], f'thermistor at {h}'
    return default_targets(r), 'netlist'

def serves_power(c):
    """the cap decouples a power pin: the served pin's net is a power net in constraints (it carries the IC's supply current)"""
    q, ns = pin_pads(SERVES[c]); net = padnet(q, ns[0])
    return cnets.get(norm(net), {}).get('kind') == 'power'
def centre(T):
    c0 = np.mean([t[1].mean(0) for t in T], 0)
    return tuple(np.mean([t[1][np.argmin(np.abs(t[1] - c0).sum(1))] for t in T], 0))

# ---------------------------------------------------------------- order and placement
todo = [r for r in db.fp if r not in pl.P]
ORD = {k: 0.7 + 0.1 * i for i, k in enumerate(a.order.split(','))}
DRAW = []      # power-stage input / output caps in the order constraints 'draw' lists them
for st in C.get('draw', {}).values():
    for role in ('cin', 'cout'):
        DRAW += [c for c in st.get(role, []) if c not in DRAW]
def tier(r, T=None, why=''):
    """placing order: hot-loop caps, power-stage bulk caps, small actives, kelvin filters, bridges, decoupling, the rest"""
    if r in HOTC: return (0, [h[0] for h in HOT].index(r))
    if r in DRAW: return (0.3, DRAW.index(r))
    npad = {p['n'] for p in db.fp[r]['pads'] if p['net'] and p['net'] not in PLANE_RAW and not p['net'].startswith('unconnected')}
    full = T is not None and npad and npad <= {t[0] for t in T}
    if re.match(r'(Q|U)\d', r) and T: return (0.5, 0)      # small active parts before the passives round them
    if r in SERVES: return (ORD['serves'], cap_value(r))
    if why == 'kelvin': return (ORD['kelvin'], 0)
    if full and len(npad) >= 2: return (ORD['bridge'], 0)   # bridges: every signal pad already has its partner placed
    return (2, 0)
def pair_offset(q):
    t = TWIN.get(q)
    if not t or t not in pl.P or q not in pl.P: return None
    (x1, y1, r1), (x2, y2, r2) = pl.P[q], pl.P[t]
    if r1 % 360 != r2 % 360: return None
    return (x2 - x1, y2 - y1)
# offsets of pairs placed so far (fixed pairs and translated anchors)
def owner_parts(T):
    """placed parts that hold any of the target points"""
    want = {(round(float(x), 3), round(float(y), 3)) for n, pts, w, k in T for x, y in pts}
    own = set()
    for q in pl.P:
        for x in db.fp[q]['pads']:
            p = db.pad(pl.P, q, x['n'])
            if (round(p[0], 3), round(p[1], 3)) in want: own.add(q); break
    return own

stats = {'twin': 0, 'own': 0, 'untargeted': 0}
rule_of = {}
fail = []
while todo:
    cand = []
    for r in todo:
        T, why = targets(r)
        T = [t for t in T if len(t[1])]      # targets on parts not placed yet do not count
        ok = len(T) > 0
        npad = len([p for p in db.fp[r]['pads'] if p['net'] and p['net'] not in PLANE_RAW]) or 1
        tr = tier(r, T, why)
        cand.append((0 if ok else 1, tr[0], tr[1], -len({t[0] for t in T}) / npad, -len(T), r, T, why))
    cand.sort(key=lambda c: c[:6])
    c = cand[0]; r, T, why = c[5], c[6], c[7]
    if c[0] == 1:   # nothing ties it to a placed part: put it at the centre of its sheet's placed parts
        same = [pl.P[q][:2] for q in pl.P if sheet(q) == sheet(r)]
        at = tuple(np.mean(same, 0)) if same else tuple(np.mean([v[:2] for v in pl.P.values()], 0))
        why = 'no target: centre of its sheet'; stats['untargeted'] += 1
    else: at = centre(T)
    twin = None
    q = TWIN.get(r)
    if q and q not in pl.P and not a.no_twins and q in todo:
        own = owner_parts(T)
        offs = [pair_offset(o) for o in own]
        if own and None not in offs and len({(round(d[0], 2), round(d[1], 2)) for d in offs}) == 1:
            d = offs[0]; twin = (q, d[0], d[1])
    gap = a.gap if len(db.fp[r]['pads']) <= 3 else 0.0
    try:
        pl.noring = r in HOTC or (r in SERVES and (a.serves_noring == 1 or (a.serves_noring == 2 and serves_power(r))))   # hot-loop first caps (and decoupling caps) sit at their pins, inside any escape band
        best = pl.place(r, [(t[0], t[1], t[2]) for t in T], at=at, gap=gap, twin=twin)
    except RuntimeError as e:
        if twin:
            try: best = pl.place(r, [(t[0], t[1], t[2]) for t in T], at=at, gap=gap); twin = None
            except RuntimeError as e2: fail.append(str(e2)); todo.remove(r); continue
        else: fail.append(str(e)); todo.remove(r); continue
    todo.remove(r); how[r] = why; rule_of[r] = why
    if twin:
        todo.remove(twin[0]); how[twin[0]] = f'twin of {r} +({twin[1]},{twin[2]})'; stats['twin'] += 1
    else: stats['own'] += 1
    log(f'{r:6s} {why:34s} -> {pl.P[r]} cost {best[0]:.2f}' + (f'  twin {twin[0]} -> {pl.P[twin[0]]}' if twin else ''))

# ---------------------------------------------------------------- checks
errs, missing = pl.check(fixed=FIXED)
dist = {}
for c, spec in SERVES.items():
    if c not in pl.P: continue
    q, ns = pin_pads(spec); net = padnet(q, ns[0]); mine = pads_on(c, net)
    if not mine or q not in pl.P: continue
    A = pts_of(c, mine); B = pts_of(q, ns)
    dist[c] = round(float(np.min(np.hypot(A[:, None, 0] - B[None, :, 0], A[:, None, 1] - B[None, :, 1]))), 2)
over3 = {c: d for c, d in sorted(dist.items(), key=lambda x: -x[1]) if d > 3.0}
ring_tab = {r: v for r, v in rings.items() if v}
rep = dict(corridors=CORR, legalised_anchors={k: [list(v[0]), list(v[1])] for k, v in LEGAL.items()}, placed=len(pl.P), total=len(db.fp), missing=missing, failures=fail, check_errors=errs,
           fixed=len(FIXED), anchors=len(ANCH), anchors_typed=len(typed_anchor), anchors_derived=len(ANCH) - len(typed_anchor) - len(drop),
           anchors_dropped=sorted(drop), support_parts=stats['own'] + stats['twin'] * 2, placed_own=stats['own'], twins=stats['twin'], untargeted=stats['untargeted'],
           serves_max_mm=max(dist.values()) if dist else None, serves_over_3mm=over3, serves_dist=dist, rings=ring_tab,
           limits=lim.describe(), plane_nets=sorted(PLANE), sense_resistors=sorted(SENSE_R), how=how, seconds=round(time.time() - t0, 1),
           args=vars(a))
json.dump(rep, open(os.path.join(a.out, 'report.json'), 'w'), indent=1)
json.dump({r: list(v) for r, v in sorted(pl.P.items())}, open(os.path.join(a.out, 'placement_gu.json'), 'w'), indent=0)
summary = (f'placed {len(pl.P)}/{len(db.fp)}  failures {len(fail)}  check errors {len(errs)}  anchors {len(ANCH)} '
           f'(typed {len(typed_anchor)}, derived {rep["anchors_derived"]})  support own {stats["own"]} twins {stats["twin"]}  untargeted {stats["untargeted"]}  '
           f'serves max {rep["serves_max_mm"]} mm, over 3 mm: {over3}  {rep["seconds"]} s')
log(summary); print(summary)
for e in errs[:30]: print('  !', e)
for e in fail: print('  FAIL', e)
