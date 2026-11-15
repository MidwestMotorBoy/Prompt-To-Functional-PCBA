#!/usr/bin/env python3
"""place_rules.py (team A onecmd copy of generic/place_generic.py) - adds anchor rules from rules.py:
  anchors.json entries {"stage": true} (pose from --stage template hung from the fixed inductor), {"pd_chip": [x, y]}
  (rotation derived), {"rule": "sense"|"tvs"} (pose derived from the PD chip pads), {"auto": true} (placed by the
  greedy placer like a support part); and support-part rules: power-pin caps aimed off-centre, walled-pin pull-ups.
place_generic.py - whole-board placement with no typed coordinates for support parts and no typed mechanical numbers.

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
import glib, rules as RU

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
ap.add_argument('--stage', help='stage template json (anchor_from a fixed inductor)')
ap.add_argument('--rules', default='pincap,pullup,bigpad,caprot,exit,bulk,kelvin,rcfilter', help='support-part rules: bigpad (a cap of a net with a big chip pad goes to that pad), caprot (power-pin cap axis along the row normal), exit (corridor off the sense resistor toward the consumer), pincap (power-pin cap one pitch off-centre), pullup (walled-pin pull-ups in front of the pin)')
ap.add_argument('--foreign-w', type=float, default=0.3, help='weight of a pad target on a net with no partner in the part\'s own sheet')
ap.add_argument('--pin-gap0', type=int, default=1, help='1: no courtyard gap for parts placed at their pins (hot-loop caps, power-pin caps, rule parts)')
ap.add_argument('--bigpad-rot', type=int, default=0, help='1: caps at a big chip pad get their axis along the pad normal (and --bigpad-out)')
ap.add_argument('--bigpad-out', type=float, default=0.0, help='aim a big-pad cap this far outward of the pad (mm)')
ap.add_argument('--bigpad-ring', type=int, default=0, help='1: big-pad caps keep the pin rows escape band')
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
drop = set(filter(None, a.anchor_only.split(','))) | {r for r, e in AN.items() if isinstance(e, dict) and e.get('auto')}
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
# ---------------------------------------------------------------- rule anchors (rules.py): stage template, PD chip rotation
STAGE_T = json.load(open(a.stage)) if a.stage else None
if STAGE_T:
    sp_, keeps = RU.stage_poses(STAGE_T, pl.P)
    for r, v in sp_.items():
        if r in FIXED: continue
        pl.P[r] = v; how[r] = 'stage template (hung from the fixed inductor)'
    for b in keeps: pl.extra.append(('F.Cu', b))
    log(f'stage template: {len(sp_)} parts from the fixed inductors, keep boxes {keeps}')
for r in ANCH:
    if r in drop or not isinstance(AN.get(r), dict): continue
    e = AN[r]
    if 'stage' in e and r not in pl.P: sys.exit(f'{r}: anchors.json says stage but the template does not place it')
    if 'pd_chip' in e:
        at = tuple(e['pd_chip']); rot, why = RU.pd_rotation(db, r, at, pl.P, C, cnets, norm)
        pl.P[r] = (at[0], at[1], rot); how[r] = why; typed_anchor.append(r); log(r, why, '->', pl.P[r])
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
def chip_of(r):
    """the IC with a big power pad on one of r's nets (the PD chip that a sense resistor / TVS belongs to)"""
    nets = {p['net'] for p in db.fp[r]['pads'] if p['net']}
    for q in sorted(pl.P):
        if q.startswith('U') and any(p['net'] in nets for p in RU.big_power_pads(db, q, cnets, norm)): return q
for r in ANCH:
    e = AN.get(r)
    if r in drop or not isinstance(e, dict) or 'rule' not in e: continue
    q = chip_of(r)
    if q is None: sys.exit(f'{r}: rule {e["rule"]} found no chip')
    res = RU.sense_targets(db, pl.P, r, q, C, cnets, norm, C.get('serves', {})) if e['rule'] == 'sense' else RU.tvs_targets(db, pl.P, r, q, cnets, norm)
    if res is None: sys.exit(f'{r}: rule {e["rule"]} gave no targets')
    T_, why = res
    pl.noring = True
    best = pl.place(r, T_, at=tuple(np.mean([t[1][0] for t in T_], 0)), gap=0.0)
    pl.noring = False
    how[r] = why; log(f'{r} rule {why} -> {pl.P[r]} cost {best[0]:.2f}')
    if e['rule'] == 'sense' and 'exit' in a.rules:
        net_, boxes_, to_ = RU.exit_band(db, pl.P, r, q, cnets, norm)
        for b_ in boxes_: pl.corr.append((db.fp[r]['layer'], b_, net_))
        log(f'{r} exit band {net_} to {to_}: {len(boxes_)} boxes')
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
    if k == 'C' and 'bulk' in a.rules and q in DRAW_ALL: return True   # onecmd: a stage's bulk caps (constraints draw cin/cout) carry the planner's pour
    if k in ('R', 'RS'): return q in SENSE_R
    if k in ('U', 'IC'):
        ar = [x['sx'] * x['sy'] for x in db.fp[q]['pads']]
        big = pd['sx'] * pd['sy'] >= 3 * float(np.median(ar)) and pd['sx'] * pd['sy'] >= 0.3
        # onecmd: only the IC's largest pad on that net is a corridor end (a small pin of the same net, e.g. the PD chip's
        # VBUS pin 32 beside PP5V pin 34, must not get a 4 x 4 mm no-other-net box that keeps the PP5V cap off its pin)
        return big and pd['sx'] * pd['sy'] >= max(x['sx'] * x['sy'] for x in db.fp[q]['pads'] if x['net'] == pd['net']) - 1e-9
    return False
DRAW_ALL = {c for st in C.get('draw', {}).values() for role in ('cin', 'cout') for c in st.get(role, [])}
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
        wt = 1.0
        if own and not a.no_sheet: mates = own        # a net that has partners in the part's own block pulls only toward those
        elif not own: wt = a.foreign_w                # a pad whose net leaves the block pulls less: the part stays in its own block
        pts = [db.pad(pl.P, q, n) for q, n in mates if q in pl.P]
        if pts: T.append((p['n'], np.array(pts), wt, 'net'))
    return T

def targets(r):
    """per-pad targets of part r from the circuit data, and the rule that gave them"""
    f = db.fp[r]
    if r in RULE: return [(t[0], t[1], t[2], 'rule') for t in RULE[r][0]], RULE[r][3]
    if r in HOTC:                             # first caps of a hot loop: across the switch pins
        s, g, name = HOTC[r]; T = []
        for spec in (s, g):
            q, ns = pin_pads(spec); net = padnet(q, ns[0])
            for n in pads_on(r, net): T.append((n, pts_of(q, ns), 1.0, 'hot'))
        if T: return T, 'hot_loop ' + name
    if r in SERVES:                           # decoupling: the pad on the served pin's net at that pin
        q, ns = pin_pads(SERVES[r]); net = padnet(q, ns[0]); T = []
        if r in BIGPAD: ns = [BIGPAD[r][1]]
        mine = pads_on(r, net)
        for n in mine: T.append((n, pts_of(q, ns) + (PINCAP[r][0] if r in PINCAP else 0), 1.0, 'serves'))
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
            rest = default_targets(r, skip=done)
            if 'kelvin' in a.rules: rest = [(n_, p_, w_ * 0.3, k_) for n_, p_, w_, k_ in rest]   # the filter sits at the sense resistor
            return T + rest, 'kelvin'
    if r.startswith('TH') and len(f['pads']) == 2:  # thermistor: at the hottest part of its sheet on its side
        hs = [(v['w'], h) for h, v in HEAT.items() if h in pl.P and sheet(h) == sheet(r) and db.fp[h]['layer'] == f['layer']]
        if hs:
            h = max(hs)[1]; allp = pts_of(h, [p['n'] for p in db.fp[h]['pads']])
            return [(p['n'], allp, 1.0, 'heat') for p in f['pads']], f'thermistor at {h}'
    T = default_targets(r)
    if 'rcfilter' in a.rules and r.startswith('R') and len([p for p in f['pads'] if p['n']]) == 2:
        # RC filter in front of an IC input: the pad whose net holds an IC pin and a capacitor is the filter node; the
        # resistor sits there and its other (long) net is the wire, so that pad pulls with weight 0.3
        fn = [p['n'] for p in f['pads'] if p['net'] and p['net'] not in PLANE_RAW
              and any(q.startswith('U') for q, n in db.netpads[p['net']]) and any(q.startswith('C') for q, n in db.netpads[p['net']])]
        if len(fn) == 1 and len(T) == 2:
            return [(n_, p_, w_ if n_ == fn[0] else 0.3 * w_, k_) for n_, p_, w_, k_ in T], 'rc filter at ' + fn[0]
    return T, 'netlist'

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
    if r in RULE: return (RULE[r][2], 0)
    if r in PINCAP or r in BIGPAD: return (0.4, cap_value(r))
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

APRON = []
if 'apron' in a.rules.split(','):
    # an apron outward of every big power pad of a placed IC (2 mm deep, pad width + 0.4): the power net leaves the chip
    # there, so support parts of other nets stay out (merged3: the VBUS / PPHV side of the PD chips was kept free by hand)
    for q in sorted(r for r in pl.P if r.startswith('U') and r not in FIXED):
        for bp in RU.big_power_pads(db, q, cnets, norm):
            if bp['sx'] * bp['sy'] < 0.5: continue
            w = db.pads_world(q, *pl.P[q]); pw = [x for x in w if x['n'] == bp['n']][0]
            n = RU._axis(np.array([pw['x'], pw['y']]) - np.array(pl.P[q][:2])); hx, hy = pw['sx'] / 2 + 0.2, pw['sy'] / 2 + 0.2
            if n[0]: b = (pw['x'] + (pw['sx'] / 2 if n[0] > 0 else -pw['sx'] / 2 - 2.0), pw['y'] - hy, pw['x'] + (pw['sx'] / 2 + 2.0 if n[0] > 0 else -pw['sx'] / 2), pw['y'] + hy)
            else: b = (pw['x'] - hx, pw['y'] + (pw['sy'] / 2 if n[1] > 0 else -pw['sy'] / 2 - 2.0), pw['x'] + hx, pw['y'] + (pw['sy'] / 2 + 2.0 if n[1] > 0 else -pw['sy'] / 2))
            pl.corr.append((db.fp[q]['layer'], b, bp['net'])); APRON.append((q, bp['n'], [round(v, 2) for v in b]))
log('aprons at big power pads:', APRON)
RULE = {}   # ref -> (targets, rots, tier, why): support parts placed by a rules.py rule, not the netlist targets
rl = set(filter(None, a.rules.split(',')))
if 'pullup' in rl:
    for q in sorted(r for r in pl.P if r.startswith('U') and r not in FIXED):
        for pin, g in RU.walled_pins(db, q, PLANE_RAW, cnets, norm):
            for (r2, n2) in db.netpads.get(pin['net'], []):
                if r2 in pl.P or r2 == q or len([p for p in db.fp[r2]['pads'] if p['n']]) != 2 or not r2.startswith('R'): continue
                res = RU.pullup_targets(db, pl.P, r2, q, pin, PLANE_RAW, cnets, norm)
                if res and r2 not in RULE:
                    RULE[r2] = (res[0], res[1], 0.45 + 0.01 * g, res[2] + f' (edge gap {g:.2f})')   # most walled pin first
log('pull-up rule:', {k: v[3] for k, v in RULE.items()})
PINCAP = {}; BIGPAD = {}
if 'pincap' in rl:
    for c, spec in SERVES.items():
        if c in pl.P or c in HOTC or not serves_power(c): continue
        q, ns = pin_pads(spec)
        if q not in pl.P or len(ns) != 1: continue
        bp = RU.biggest_pad_on(db, q, padnet(q, ns[0]))
        if 'bigpad' in rl and bp is not None and bp['n'] != ns[0] and bp['sx'] * bp['sy'] > 1.5 * [p['sx'] * p['sy'] for p in db.fp[q]['pads'] if p['n'] == ns[0]][0]:
            BIGPAD[c] = (q, bp['n'])          # decouple the net at its largest pad on the chip (outside the pin rows)
            if not a.bigpad_rot: continue      # r8 behaviour: big-pad caps only re-aimed at the big pad
            _pw = np.array(db.pad(pl.P, q, bp['n'])); _n = np.array(RU._axis(_pw - np.array(pl.P[q][:2])))
            PINCAP[c] = (_n * a.bigpad_out, 'at big pad ' + bp['n'] + f' (aimed {a.bigpad_out} mm outward)', RU.bigpad_rots(db, pl.P, c, q, bp['n']) if 'caprot' in rl else (0, 90, 180, 270)); continue
        sh, why = RU.pincap_shift(db, pl.P, q, ns[0], PLANE_RAW, cnets, norm)
        rots_ = (0, 90, 180, 270)
        if 'caprot' in rl: rots_ = RU.cap_rots(db, pl.P, c, q, ns[0]) if why != 'no row' or not q.startswith('U') or not a.bigpad_rot else RU.bigpad_rots(db, pl.P, c, q, ns[0])
        PINCAP[c] = (sh, why, rots_)
log('power-pin cap shift:', {k: (list(np.round(v[0], 2)), v[1], v[2]) for k, v in PINCAP.items()}, 'at the big pad:', BIGPAD)
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
    else: at = centre([t for t in T if t[2] >= 1.0] or T)   # onecmd: search round the full-weight targets
    twin = None
    q = TWIN.get(r)
    if q and q not in pl.P and not a.no_twins and q in todo and r not in RULE and q not in RULE and r not in PINCAP:
        own = owner_parts(T)
        offs = [pair_offset(o) for o in own]
        if own and None not in offs and len({(round(d[0], 2), round(d[1], 2)) for d in offs}) == 1:
            d = offs[0]; twin = (q, d[0], d[1])
    gap = a.gap if len(db.fp[r]['pads']) <= 3 else 0.0
    if os.environ.get('DBG_REF') == r:      # debug: why is the pose DBG_POSE=x,y,rot illegal?
        x_, y_, rt_ = map(float, os.environ['DBG_POSE'].split(',')); pl.noring = True
        b_ = db.bbox(r, x_, y_, rt_); print('DBG', r, 'box', np.round(b_, 2), 'limits ok', pl.lim.cy_ok(db.fp[r]['layer'], np.array([b_[0]]), np.array([b_[1]]), np.array([b_[2]]), np.array([b_[3]])))
        for o in pl.obstacles(db.fp[r]['layer'], skip=(r,), nets={p['net'] for p in db.fp[r]['pads']}):
            if min(b_[2] + gap, o[2]) - max(b_[0] - gap, o[0]) > 0.05 and min(b_[3] + gap, o[3]) - max(b_[1] - gap, o[1]) > 0.05: print('DBG hit', np.round(o, 2))
        for L_, bb_, n_ in pl.corr:
            if min(b_[2], bb_[2]) - max(b_[0], bb_[0]) > 0.05 and min(b_[3], bb_[3]) - max(b_[1], bb_[1]) > 0.05: print('DBG corr', n_, np.round(bb_, 2))
    try:
        pl.noring = (r not in BIGPAD or not a.bigpad_ring) and (r in HOTC or r in RULE or (r in SERVES and (a.serves_noring == 1 or (a.serves_noring == 2 and serves_power(r)))))   # onecmd: a cap at a big pad keeps the pin rows' escape band; hot-loop first caps (and decoupling caps) sit at their pins, inside any escape band
        if pl.noring and a.pin_gap0: gap = 0.0          # parts that sit at their pins: courtyards may touch (merged3 C407: 0.08 mm from U405)
        best = pl.place(r, [(t[0], t[1], t[2]) for t in T], at=at, gap=gap, twin=twin, **({'rots': RULE[r][1]} if r in RULE else {'rots': PINCAP[r][2]} if r in PINCAP else {}))
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
