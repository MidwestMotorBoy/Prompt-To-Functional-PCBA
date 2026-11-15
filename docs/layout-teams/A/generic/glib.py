"""glib.py - generic placement library (team A, worker 'generic').

Copied and generalised from tools/battery-bank/groundup/fpdb.py + placelib.py. Nothing in here knows Monolith:
  * DB        footprint geometry from a dump (gdump.py = groundup dump.py + board outline): local pads, courtyard box.
  * Limits    mechanical limits read from the board: Edge.Cuts outline (with its notches and cut-outs), no-footprint
              rule areas per side, the copper-to-edge rule (kicad_pro / kicad_dru), plus an optional enclosure file
              for limits the board does not hold (lips of a cup). Rasterised once at 0.05 mm; a courtyard is legal
              when every raster cell under it is inside, and every pad box is inside the outline inset by the edge rule.
  * Placer    the greedy per-pad-target search of placelib._auto (min Manhattan distance pad -> target over free grid
              spots and four rotations, courtyard gap, clear rings round fine-pitch ICs), with an optional
              translated twin (a repeated block: the copy must be legal too) and an exact check().
Rotation convention (KiCad, y down): dx = lx*cos + ly*sin, dy = -lx*sin + ly*cos.
"""
import json, math, re
import numpy as np

def rotv(lx, ly, rot):
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    return lx * c + ly * s, -lx * s + ly * c

def unrot(dx, dy, rot):
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    return dx * c - dy * s, dx * s + dy * c

# ------------------------------------------------------------------ footprint database
class DB:
    def __init__(s, path):
        s.d = json.load(open(path)); s.fp = {}
        for f in s.d['fps']:
            pads = []
            for p in f['pads']:
                lx, ly = unrot(p['x'] - f['x'], p['y'] - f['y'], f['rot'])
                r = (p['rot'] - f['rot']) % 180
                sx, sy = (p['sx'], p['sy']) if (abs(r) < 1 or abs(r - 180) < 1) else (p['sy'], p['sx'])
                pads.append(dict(n=p['n'], net=p['net'], lx=lx, ly=ly, sx=sx, sy=sy, drill=p['drill'], pinfn=p['pinfn'], type=p.get('type', 0)))
            x0, y0, x1, y1 = f['bb']; cs = [unrot(x - f['x'], y - f['y'], f['rot']) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            box = (min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs))
            s.fp[f['ref']] = dict(ref=f['ref'], val=f['val'], fp=f['fp'], layer=f['layer'], pads=pads, box=box,
                                  base=(f['x'], f['y'], f['rot']), locked=f['locked'], sheet=f['sheet'])
        s.netpads = {}
        for r, f in s.fp.items():
            for p in f['pads']:
                if p['net']: s.netpads.setdefault(p['net'], []).append((r, p['n']))

    def bbox(s, ref, x, y, rot):
        b = s.fp[ref]['box']
        cs = [rotv(cx, cy, rot) for cx, cy in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        return (x + min(c[0] for c in cs), y + min(c[1] for c in cs), x + max(c[0] for c in cs), y + max(c[1] for c in cs))

    def pads_world(s, ref, x, y, rot):
        out = []
        for p in s.fp[ref]['pads']:
            dx, dy = rotv(p['lx'], p['ly'], rot)
            sx, sy = (p['sx'], p['sy']) if round(rot / 90) % 2 == 0 else (p['sy'], p['sx'])
            out.append(dict(n=p['n'], net=p['net'], x=x + dx, y=y + dy, sx=sx, sy=sy))
        return out

    def pad(s, P, ref, n):
        x, y, rot = P[ref]
        for p in s.fp[ref]['pads']:
            if p['n'] == str(n):
                dx, dy = rotv(p['lx'], p['ly'], rot); return (x + dx, y + dy)
        raise KeyError((ref, n))

    def world(s, ref, x, y, rot):
        f = s.fp[ref]
        return dict(ref=ref, val=f['val'], fp=f['fp'], layer=f['layer'], x=x, y=y, rot=rot, bb=list(s.bbox(ref, x, y, rot)),
                    pads=[dict(p, rot=0, drill=0, pinfn='') for p in s.pads_world(ref, x, y, rot)], locked=f['locked'], sheet=f['sheet'])

# ------------------------------------------------------------------ design rules from the project files
def read_rules(pro_path, dru_path=None):
    p = json.load(open(pro_path)); ds = p['board']['design_settings']['rules']
    dflt = [c for c in p['net_settings']['classes'] if c['name'] == 'Default'][0]
    edge = ds.get('min_copper_edge_clearance', 0.2)
    if dru_path:
        try:
            for m in re.finditer(r'edge_clearance \(min ([0-9.]+)mm\)', open(dru_path).read()): edge = max(edge, float(m.group(1)))
        except OSError: pass
    return dict(edge=edge, clr=dflt['clearance'], track=dflt['track_width'], via=dflt['via_diameter'],
                via_pitch=dflt['via_diameter'] + dflt['clearance'], track_pitch=dflt['track_width'] + dflt['clearance'])

# ------------------------------------------------------------------ mechanical limits
class Limits:
    """Raster of where a courtyard may lie, per side, and where pad copper may lie, all read from the board."""
    RES = 0.05
    def __init__(s, dump, rules, enclosure=None):
        from shapely.geometry import Polygon, box
        from shapely.ops import unary_union
        from shapely import vectorized
        s.rules = rules
        rings = dump['outline']
        s.outline = unary_union([Polygon(o['ring'], o['holes']) for o in rings])
        x0, y0, x1, y1 = s.outline.bounds
        s.x0, s.y0 = x0 - 1.0, y0 - 1.0
        s.nx = int(math.ceil((x1 - x0 + 2.0) / s.RES)); s.ny = int(math.ceil((y1 - y0 + 2.0) / s.RES))
        xs = s.x0 + (np.arange(s.nx) + 0.5) * s.RES; ys = s.y0 + (np.arange(s.ny) + 0.5) * s.RES
        GX, GY = np.meshgrid(xs, ys)
        inside = vectorized.contains(s.outline, GX, GY)
        s.keep = {}   # layer -> list of (name, shapely poly, why)
        for z in dump['zones']:
            if z.get('rulearea') and z.get('no_fp') and z['pts']:
                for L in z['layers']:
                    if L in ('F.Cu', 'B.Cu'): s.keep.setdefault(L, []).append((z['name'], Polygon(z['pts']), 'board rule area (no footprints)'))
        if enclosure:
            for e in enclosure.get('keepout_boxes', []):
                for L in e['layers']: s.keep.setdefault(L, []).append((e['name'], box(*e['box']), e['why']))
        s.bad_cy = {}
        for L in ('F.Cu', 'B.Cu'):
            ok = inside.copy()
            for name, poly, why in s.keep.get(L, []):
                ok &= ~vectorized.contains(poly, GX, GY)
            s.bad_cy[L] = s._sat(~ok)
        inset = s.outline.buffer(-rules['edge'], join_style=2)
        s.bad_pad = s._sat(~vectorized.contains(inset, GX, GY))
        s.inset = inset
    @staticmethod
    def _sat(a):
        S = np.zeros((a.shape[0] + 1, a.shape[1] + 1), np.int32)
        S[1:, 1:] = np.cumsum(np.cumsum(a.astype(np.int32), 0), 1); return S
    def _count(s, S, x0, y0, x1, y1):
        """number of bad cells whose centre lies inside [x0,x1]x[y0,y1] (arrays ok)"""
        j0 = np.clip(np.ceil((x0 - s.x0) / s.RES - 0.5), 0, s.nx).astype(int); j1 = np.clip(np.floor((x1 - s.x0) / s.RES - 0.5) + 1, 0, s.nx).astype(int)
        i0 = np.clip(np.ceil((y0 - s.y0) / s.RES - 0.5), 0, s.ny).astype(int); i1 = np.clip(np.floor((y1 - s.y0) / s.RES - 0.5) + 1, 0, s.ny).astype(int)
        j1 = np.maximum(j1, j0); i1 = np.maximum(i1, i0)
        out = S[i1, j1] - S[i0, j1] - S[i1, j0] + S[i0, j0]
        beyond = (x0 < s.x0) | (y0 < s.y0) | (x1 > s.x0 + s.nx * s.RES) | (y1 > s.y0 + s.ny * s.RES)
        return np.where(beyond, 1, out)
    def cy_ok(s, layer, x0, y0, x1, y1, tol=0.02):
        return s._count(s.bad_cy[layer], x0 + tol, y0 + tol, x1 - tol, y1 - tol) == 0
    def pad_ok(s, x0, y0, x1, y1, m=0.06):
        # m: one raster cell plus a little, so a pad edge never ends up inside the copper-to-edge band by rounding
        return s._count(s.bad_pad, x0 - m, y0 - m, x1 + m, y1 + m) == 0
    def describe(s):
        out = {'outline_bounds': [round(v, 4) for v in s.outline.bounds], 'outline_vertices': len(s.outline.exterior.coords) - 1,
               'pad_to_edge_mm': s.rules['edge'], 'keepouts': {}}
        for L, ks in s.keep.items(): out['keepouts'][L] = [(n, [round(v, 3) for v in p.bounds], why) for n, p, why in ks]
        return out

# ------------------------------------------------------------------ escape ring round fine-pitch ICs
def _pins(db, ref):
    """the signal pins of a footprint: numbered SMD pads under 1 mm2 (no exposed pads, no via pads in them), one per number"""
    seen = {}; 
    for p in db.fp[ref]['pads']:
        if p['n'] and p['drill'] == 0 and p['sx'] * p['sy'] < 1.0 and p['n'] not in seen: seen[p['n']] = p
    return list(seen.values())

def side_pitch(db, ref):
    """smallest centre distance between neighbouring non-exposed pads of an IC"""
    pads = _pins(db, ref)
    if len(pads) < 2: return None
    pts = np.array([(p['lx'], p['ly']) for p in pads]); d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    d[d < 1e-6] = 99; return float(d.min())

def escape_ring(db, ref, rules, plane, k=1.0):
    """clear band (mm) round an IC so its fine-pitch pins can escape: a pin row at pitch p needs ceil(via_pitch/p)
    staggered via rows to change layer (one via per pin), each row one via pitch deep; scaled by the share of the
    row's pins that carry a signal (pins on plane nets drop straight into a plane via; unconnected pins need nothing).
    Only for ICs with more than 6 small pads (2-pin parts and SOT-23s escape by themselves)."""
    f = db.fp[ref]
    small = _pins(db, ref)
    if len(small) <= 6: return 0.0
    p = side_pitch(db, ref)
    if not p or p > 1.0: return 0.0
    sig = [q for q in small if q['net'] and q['net'] not in plane and not q['net'].startswith('unconnected')]
    nets = {q['net'] for q in sig}            # pins tied together share one escape
    share = len(nets) / len(small)
    rows = math.ceil(rules['via_pitch'] / p - 1e-9)
    return round(k * rows * rules['via_pitch'] * share, 2)

# ------------------------------------------------------------------ greedy placer
class Placer:
    def __init__(s, db, lim, rules, gap=0.25, rings=None, wpull=0.15, grid=0.05, radii=(4.0, 8.0, 14.0, 22.0)):
        s.db, s.lim, s.rules = db, lim, rules
        s.P = {}; s.gap = gap; s.rings = rings or {}; s.wpull = wpull; s.grid = grid; s.radii = radii
        s.extra = []          # (layer, box) extra blocked boxes
        s.corr = []           # (layer, box, net) power corridors: blocked for parts with no pad on that net
        s.log = []
        s.noring = False      # True: ignore the escape bands (for parts that must sit at the pins)
    def ring(s, r): return s.rings.get(r, 0.0)
    def obstacles(s, layer, skip=(), region=None, nets=()):
        out = [b for L, b, n in s.corr if L == layer and n not in nets]
        for r, (x, y, rot) in s.P.items():
            if r in skip or s.db.fp[r]['layer'] != layer: continue
            b = s.db.bbox(r, x, y, rot); g = 0.0 if s.noring else s.ring(r)
            out.append((b[0] - g, b[1] - g, b[2] + g, b[3] + g))
        out += [b for L, b in s.extra if L == layer]
        ob = np.array(out) if out else np.zeros((0, 4))
        if region is not None and len(ob):
            x0, y0, x1, y1 = region
            ob = ob[(ob[:, 2] > x0) & (ob[:, 0] < x1) & (ob[:, 3] > y0) & (ob[:, 1] < y1)]
        return ob
    def legal(s, ref, gx, gy, rot, gap, ob):
        """bool array: candidate centres (gx, gy) at rotation rot are free of obstacles and inside the limits"""
        f = s.db.fp[ref]; b = f['box']
        cs = [rotv(cx, cy, rot) for cx, cy in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        bx0 = min(c[0] for c in cs); bx1 = max(c[0] for c in cs); by0 = min(c[1] for c in cs); by1 = max(c[1] for c in cs)
        ok = s.lim.cy_ok(f['layer'], gx + bx0, gy + by0, gx + bx1, gy + by1)
        for p in f['pads']:
            if p['drill'] > 0 and p['type'] == 3: continue      # NPTH: no copper
            dx, dy = rotv(p['lx'], p['ly'], rot)
            sx, sy = (p['sx'], p['sy']) if round(rot / 90) % 2 == 0 else (p['sy'], p['sx'])
            idx = np.nonzero(ok)[0]
            if not len(idx): return ok
            ok[idx] = s.lim.pad_ok(gx[idx] + dx - sx / 2, gy[idx] + dy - sy / 2, gx[idx] + dx + sx / 2, gy[idx] + dy + sy / 2)
        idx = np.nonzero(ok)[0]
        if not len(idx): return ok
        hx, hy = gx[idx], gy[idx]
        x0 = hx + bx0 - gap; x1 = hx + bx1 + gap; y0 = hy + by0 - gap; y1 = hy + by1 + gap
        sub = np.ones(len(idx), bool)
        own = 0.0 if s.noring else s.ring(ref)   # an IC's own clear band must not cover other parts either
        e = max(own, 0.0)
        for o in ob:
            sub &= ~((np.minimum(x1 + e, o[2]) - np.maximum(x0 - e, o[0]) > 0.05) & (np.minimum(y1 + e, o[3]) - np.maximum(y0 - e, o[1]) > 0.05))
        ok[idx] = sub
        return ok
    def place(s, ref, targets, at=None, rots=(0, 90, 180, 270), gap=None, twin=None, box=None):
        """targets: list of (padnum, pts Nx2, weight). at: search centre (default: mean of the targets).
        twin = (ref2, dx, dy): ref2 is placed at the same rotation shifted by (dx, dy) and must be legal too."""
        f = s.db.fp[ref]; pads = {p['n']: p for p in f['pads']}
        T = [(pads[n]['lx'], pads[n]['ly'], np.asarray(pts, float), w) for n, pts, w in targets if len(pts)]
        if at is None:
            if not T: raise ValueError(f'{ref}: no targets and no centre')
            at = tuple(np.mean([t[2].mean(0) for t in T], 0))
        if gap is None: gap = s.gap
        err = None
        for R in s.radii:
            xs = np.arange(-R, R + 1e-9, s.grid); gx, gy = np.meshgrid(xs, xs)
            gx = gx.ravel() + round(at[0] / s.grid) * s.grid; gy = gy.ravel() + round(at[1] / s.grid) * s.grid
            reg = (at[0] - R - 15, at[1] - R - 15, at[0] + R + 15, at[1] + R + 15)
            ob = s.obstacles(f['layer'], skip=(ref,), region=reg, nets={p['net'] for p in f['pads']})
            if twin:
                r2, ddx, ddy = twin
                reg2 = (reg[0] + ddx, reg[1] + ddy, reg[2] + ddx, reg[3] + ddy)
                ob2 = s.obstacles(s.db.fp[r2]['layer'], skip=(r2,), region=reg2, nets={p['net'] for p in s.db.fp[r2]['pads']})
            best = None
            for rot in rots:
                ok = s.legal(ref, gx, gy, rot, gap, ob)
                if box:
                    bb = [s.db.bbox(ref, 0, 0, rot)]
                    ok &= (gx + bb[0][0] >= box[0]) & (gy + bb[0][1] >= box[1]) & (gx + bb[0][2] <= box[2]) & (gy + bb[0][3] <= box[3])
                if twin and ok.any():
                    idx = np.nonzero(ok)[0]
                    ok2 = s.legal(r2, gx[idx] + ddx, gy[idx] + ddy, rot, gap, ob2)
                    # the twin must not hit the original either
                    b1 = s.db.bbox(ref, 0, 0, rot); b2 = s.db.bbox(r2, ddx, ddy, rot)
                    sep = (not ((min(b1[2], b2[2]) - max(b1[0], b2[0]) > 0.05) and (min(b1[3], b2[3]) - max(b1[1], b2[1]) > 0.05))) or s.db.fp[r2]['layer'] != f['layer']
                    ok[idx] = ok2 & sep
                pull = s.wpull if T else 1.0
                idx = np.nonzero(ok)[0]
                if not len(idx): continue
                hx, hy = gx[idx], gy[idx]
                cost = pull * (np.abs(hx - at[0]) + np.abs(hy - at[1]))
                for lx, ly, pts, w in T:
                    dx, dy = rotv(lx, ly, rot); px = hx + dx; py = hy + dy
                    d = np.min(np.abs(px[:, None] - pts[None, :, 0]) + np.abs(py[:, None] - pts[None, :, 1]), axis=1)
                    cost = cost + w * d
                i = int(np.argmin(cost))
                if best is None or cost[i] < best[0] - 1e-6:
                    best = (float(cost[i]), round(float(hx[i]), 3), round(float(hy[i]), 3), rot)
            if best: break
            err = f'{ref}: no free spot within {R} mm of ({at[0]:.2f}, {at[1]:.2f})'
        if best is None: raise RuntimeError(err)
        s.P[ref] = best[1:]
        if twin:
            r2, ddx, ddy = twin; s.P[r2] = (round(best[1] + ddx, 3), round(best[2] + ddy, 3), best[3])
        return best

    # -------------------------------------------------------------- exact checks (port of placelib.check onto the derived limits)
    def check(s, fixed=()):
        errs = []; Wd = {r: (s.db.fp[r]['layer'], s.db.bbox(r, *v)) for r, v in s.P.items()}
        for L in ('F.Cu', 'B.Cu'):
            refs = [r for r in Wd if Wd[r][0] == L]
            for i, a in enumerate(refs):
                A = Wd[a][1]
                for b in refs[i + 1:]:
                    Bb = Wd[b][1]
                    ox = min(A[2], Bb[2]) - max(A[0], Bb[0]); oy = min(A[3], Bb[3]) - max(A[1], Bb[1])
                    if ox > 0.08 and oy > 0.08 and not (a in fixed and b in fixed): errs.append(f'overlap {a}/{b} {ox:.2f}x{oy:.2f}')
        for r, (L, bb) in Wd.items():
            if r in fixed: continue
            if not s.lim.cy_ok(L, np.array([bb[0]]), np.array([bb[1]]), np.array([bb[2]]), np.array([bb[3]]), tol=0.03)[0]: errs.append(f'limit {r} courtyard {[round(v,2) for v in bb]}')
            for p in s.db.pads_world(r, *s.P[r]):
                if not s.lim.pad_ok(np.array([p['x'] - p['sx'] / 2]), np.array([p['y'] - p['sy'] / 2]), np.array([p['x'] + p['sx'] / 2]), np.array([p['y'] + p['sy'] / 2]))[0]:
                    errs.append(f'edge {r}.{p["n"]}'); break
        missing = [r for r in s.db.fp if r not in s.P]
        return errs, missing
