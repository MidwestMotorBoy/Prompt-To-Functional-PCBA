"""trunk.py <spec.json> <bare.json or cu.json> <out spec.json> [options]
A HARD wide power trunk on an outer layer, so that a high-current path keeps its resistance after the full trial route.

Why: score_board.sh routes with --softnets=GND,PACK_P,3V3, so every zone of those nets is soft: signal tracks may
cross it and the last refill carves round them. On r4 the half-ounce In2 PACK_P sheet west of J113 is cut by three
north-south signal nets, and J113 (10 A) and R427 (5 A) go from about 2.2 to 15.5 mohm. The router never crosses
another net's track, so a trunk written as TRACKS is hard: whatever the route does, the trunk stays. On an outer
layer (2 oz, 0.25 mohm per square, four times In2) a 2 to 3 mm trunk of 30 mm is about 3 mohm by itself.

What it does:
  1. The terminals: --source and each --to name a part (or "x,y" for the net's via group nearest to that point). A
     terminal's items are the part's --net pads on --layer or through-hole, the net's vias within --near mm of its
     pads, and the net's planned zones on --layer that touch those vias or pads.
  2. Free room on --layer: everything except other nets' pads (on the layer, and every through-hole pad), vias,
     planned tracks and pours on the layer, holes, keep-outs that forbid tracks there, and the board edge (0.25 mm).
     The net's own pours, pads, vias and tracks are free (the trunk merges with them). Near small pads of other nets
     (--esc mm, both outer layers: their via escapes) a step costs --near_sig times more; within --under mm of a
     small pad on --layer the room is closed (the pad must keep its escape).
  3. The width that fits at each cell (distance transform, minus --clr), capped at --w; cells where --wmin does not
     fit are closed. A Steiner tree on the grid (8 directions, --turn grid steps per 45 degree turn): from the source,
     the cheapest path to the next terminal of --to (in that order: put the largest current first), and so on. A step costs its length times
     --w / (width that fits): the search looks for the path of least RESISTANCE, not the shortest one.
  4. Straight runs of the path become tracks, split where the fitting width changes (widths on a --wstep ladder);
     every track is checked exactly (shapely) against every obstacle and narrowed by --wstep until it clears (a
     fault if --wmin does not clear), then appended to the plan's 'tracks'.
  5. --stitch=MM: PACK_P through vias along the trunk every MM mm, only where a through via is free on EVERY layer
     (no other net's pad, track, via or pour within --clr on F.Cu, In3.Cu and --layer, inside the net's pour on
     --stitch_layer (In2.Cu), 0.75 mm from other vias' centres, 1.1 mm from through-hole pads, away from small pads).
     GND planes on In1/In4 are not obstacles (a via gets its antipad there). 0 = no stitching (default).
  6. Writes the plan with a 'trunks' record (terminals, length, width profile, faults); --png draws the result.
Options: --net=PACK_P --layer=B.Cu --source=Q102 --to=J113,R427 --w=3.0 --wmin=1.0 --wstep=0.25 --clr=0.25
         --g=0.1 --turn=15 --near=1.5 --margin=6 --esc=0.6 --near_sig=2 --under=0.3 --stitch=0 --stitch_layer=In2.Cu
         --pw=1.5 (a step costs (w / width that fits)^pw) --nearest (next terminal = the nearest, not the --to order)
         --png=<file>
Exit 1 when a terminal could not be reached or a track has a clearance fault (the plan is still written)."""
import sys, json, math, time
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from scipy.ndimage import distance_transform_edt

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 3: print(__doc__); sys.exit(2)
NET = O.get("net", "PACK_P"); LAY = O.get("layer", "B.Cu"); SRC = O.get("source", "Q102")
TO = [t for t in O.get("to", "J113,R427").split(";" if ";" in O.get("to", "") else ",") if t]
W, WMIN, WSTEP, CLR, G = (float(O.get(k, d)) for k, d in (("w", 3.0), ("wmin", 1.0), ("wstep", 0.25), ("clr", 0.25), ("g", 0.1)))
TURN, NEAR, MARGIN = float(O.get("turn", 15)), float(O.get("near", 1.5)), float(O.get("margin", 6))
ESC, NEAR_SIG, UNDER = float(O.get("esc", 0.6)), float(O.get("near_sig", 2)), float(O.get("under", 0.3))
STITCH, SLAY = float(O.get("stitch", 0)), O.get("stitch_layer", "In2.Cu")
TOL = 0.03
S = json.load(open(A[0])); D = json.load(open(A[1])); t0 = time.time()
def poly(r): return Polygon(r["ring"], r.get("holes", [])).buffer(0)
def parts(g): return [g] if isinstance(g, Polygon) else [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon)]

# ---- terminals
def pads_of(ref): return [p for p in D["pads"] if p["ref"] == ref and p["net"] == NET]
def pad_geom(p, lay=None):
    gs = [poly(r) for L, rs in p["shapes"].items() for r in rs if lay is None or L == lay or p.get("drill", 0) > 0]
    return unary_union(gs) if gs else Point(p["x"], p["y"]).buffer(0.2)
NVIAS = [v for v in S["vias"] if v["net"] == NET]
NZONES = [poly(p) for z in S["zones"] if z["net"] == NET and z["layer"] == LAY for p in z["polys"]]
def terminal(name):
    """geometry (on LAY) of a terminal: pads on the layer / through-hole, vias near its pads, net pours touching them"""
    if "," in name and name.replace(",", "").replace(".", "").replace("-", "").isdigit():
        x, y = map(float, name.split(",")); vs = sorted(NVIAS, key=lambda v: math.dist((v["x"], v["y"]), (x, y)))[:1]
        ps = []
    else:
        ps = pads_of(name)
        if not ps: raise SystemExit(f"trunk: {name} has no {NET} pad")
        pg = unary_union([pad_geom(p) for p in ps])
        onl = [p for p in ps if p.get("drill", 0) > 0 or LAY in p["shapes"]]
        # a pad on the layer (or through-hole) is the terminal itself; else the vias next to its pads carry it down
        vs = [] if onl else [v for v in NVIAS if pg.distance(Point(v["x"], v["y"])) <= NEAR]
    g = [Point(v["x"], v["y"]).buffer(v["size"] / 2, 16) for v in vs]
    g += [pad_geom(p, LAY) for p in ps if p.get("drill", 0) > 0 or LAY in p["shapes"]]
    core = unary_union(g) if g else Polygon()
    if core.is_empty: raise SystemExit(f"trunk: {name}: no via or pad of {NET} reaches {LAY}")
    zs = [z for z in NZONES if z.intersects(core)]
    return unary_union([core] + zs), len(vs)
TERMS = [(SRC,) + terminal(SRC)] + [(t,) + terminal(t) for t in TO]

# ---- obstacles on LAY
obst = []
for v in S["vias"]:
    if v["net"] != NET: obst.append(Point(v["x"], v["y"]).buffer(v["size"] / 2, 16))
for p in D["pads"]:
    if p["net"] == NET and not p.get("npth") and p["net"]: continue
    if p.get("drill", 0) > 0 or LAY in p["shapes"]:
        obst += [poly(r) for r in p["shapes"].get(LAY, [])]
        if p.get("drill", 0) > 0: obst.append(Point(p["x"], p["y"]).buffer(p["drill"] / 2 + 0.05, 16))
for t in S["tracks"]:
    if t["layer"] == LAY and t["net"] != NET: obst.append(LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 8))
for z in S["zones"]:
    if z["layer"] == LAY and z["net"] != NET: obst += [poly(p) for p in z["polys"]]
for k in D.get("keepouts", []):
    if LAY in k["layers"] and k.get("no_tracks"): obst += [poly(p) for p in k["poly"]]
OBST = unary_union(obst)
BOARD = unary_union([poly(o) for o in D["outline"]])
smallp = [poly(r) for p in D["pads"] if p["net"] not in (NET, "GND", "") for L in ("F.Cu", "B.Cu") for r in p["shapes"].get(L, []) if poly(r).area < 1.0]
smallL = [poly(r) for p in D["pads"] if p["net"] not in (NET, "GND", "") for r in p["shapes"].get(LAY, []) if poly(r).area < 1.0]
SM, SML = unary_union(smallp), unary_union(smallL)

# ---- grid over the terminals' box + margin
bx = unary_union([t[1] for t in TERMS]).bounds
X0, Y0 = bx[0] - MARGIN, bx[1] - MARGIN; NX, NY = int((bx[2] - bx[0] + 2 * MARGIN) / G) + 1, int((bx[3] - bx[1] + 2 * MARGIN) / G) + 1
def raster(geom):
    im = Image.new("1", (NX, NY), 0); dr = ImageDraw.Draw(im)
    for g in parts(geom):
        if g.is_empty: continue
        dr.polygon([((x - X0) / G, (y - Y0) / G) for x, y in g.exterior.coords], fill=1)
        for h in g.interiors: dr.polygon([((x - X0) / G, (y - Y0) / G) for x, y in h.coords], fill=0)
    return np.array(im, dtype=bool)
def cxy(c): return (X0 + (c % NX) * G, Y0 + (c // NX) * G)
WIN = box(X0, Y0, X0 + NX * G, Y0 + NY * G)
blocked = raster(OBST.intersection(WIN.buffer(1))) | ~raster(BOARD.buffer(-0.25))
if not SML.is_empty: blocked |= raster(SML.buffer(UNDER))
# distance (mm) from each cell centre to the nearest blocked cell, minus half a cell (raster error), minus clearance
dist = distance_transform_edt(~blocked) * G - G * 0.75
WFIT = np.clip(2 * (dist - CLR - TOL), 0, None)
FREE = WFIT >= WMIN
WEFF = np.minimum(WFIT, W)
mult = np.ones((NY, NX))
if not SM.is_empty: mult[raster(SM.buffer(ESC + W / 2))] = NEAR_SIG
PW = float(O.get("pw", 1.5))                         # narrow spots cost (W/w)^PW: current crowds there
cost = np.where(FREE, mult * (W / np.maximum(WEFF, 1e-3)) ** PW, np.inf)

# ---- graph: node = cell * 8 + direction
N = NX * NY; idx = np.arange(N); ii, jj = idx % NX, idx // NX
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
fr = FREE.ravel(); cr = cost.ravel()
rows, cols, vals = [], [], []
for d, (dx, dy) in enumerate(DIRS):
    ok = fr & (ii + dx >= 0) & (ii + dx < NX) & (jj + dy >= 0) & (jj + dy < NY)
    s_ = idx[ok]; t_ = s_ + dx + dy * NX; ok2 = fr[t_]; s_, t_ = s_[ok2], t_[ok2]
    if dx and dy:                                   # a diagonal step must not cut a blocked corner
        ok3 = fr[s_ + dx] & fr[s_ + dy * NX]; s_, t_ = s_[ok3], t_[ok3]
    L = math.hypot(dx, dy)
    rows.append(s_ * 8 + d); cols.append(t_ * 8 + d); vals.append(L * 0.5 * (cr[s_] + cr[t_]))
    for e in ((d + 1) % 8, (d - 1) % 8, (d + 2) % 8, (d - 2) % 8):
        c_ = idx[fr]; rows.append(c_ * 8 + d); cols.append(c_ * 8 + e); vals.append(np.full(len(c_), TURN * (1 if abs((e - d + 4) % 8 - 4) == 1 else 2.5)))
GR = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(N * 8, N * 8))

def cells_of(geom):
    m = raster(geom) & FREE
    if not m.any(): m = raster(geom.buffer(WMIN / 2 + CLR)) & FREE   # a via disc next to the free room
    return np.flatnonzero(m.ravel())
TC = [cells_of(t[1]) for t in TERMS]
tree = set(TC[0].tolist()); paths, missed = [], []
todo = list(range(1, len(TERMS)))
while todo:
    srcs = np.array(sorted(tree)); srcs = np.concatenate([srcs * 8 + d for d in range(8)])
    dd, pred, _ = dijkstra(GR, directed=True, indices=srcs, min_only=True, return_predecessors=True)
    best = None
    for k in (todo if "nearest" in O else todo[:1]):     # terminals in the order of --to (the main current first)
        if not len(TC[k]): continue
        nodes = np.concatenate([TC[k] * 8 + d for d in range(8)]); n_ = nodes[np.argmin(dd[nodes])]
        if np.isfinite(dd[n_]) and (best is None or dd[n_] < best[0]): best = (dd[n_], k, n_)
    if best is None: missed = todo; break
    _, k, n_ = best; path = []
    while n_ >= 0 and (n_ // 8) not in tree: path.append(n_ // 8); n_ = pred[n_]
    if n_ >= 0: path.append(n_ // 8)
    path = path[::-1]
    # drop the cells inside the target terminal past the first one (the trunk ends where it meets the terminal)
    tset = set(TC[k].tolist())
    for q, c in enumerate(path):
        if c in tset: path = path[:q + 1]; break
    tree |= set(path) | tset; paths.append((TERMS[k][0], path)); todo.remove(k)
    if "debug" in O: print("  path to", TERMS[k][0], len(path), "cells, from", cxy(path[0]), "to", cxy(path[-1]), "terminal cells", len(TC[k]))

# ---- runs -> tracks with a width ladder
wf = WFIT.ravel()
def ladder(w): return max(WMIN, min(W, math.floor((w + 1e-6) / WSTEP) * WSTEP)) if w >= WMIN else WMIN
def to_segs(path):
    pts = [c for q, c in enumerate(path) if q == 0 or c != path[q - 1]]
    if len(pts) < 2: return []
    # width at each cell: the least fitting width within +-3 cells along the path (no saw-tooth at a narrow spot)
    wl = [ladder(min(wf[pts[max(0, q - 3):q + 4]])) for q in range(len(pts))]
    out = []; q0 = 0
    def dirn(a, b): return ((b % NX) - (a % NX), (b // NX) - (a // NX))
    while q0 < len(pts) - 1:
        d0 = dirn(pts[q0], pts[q0 + 1]); w0 = min(wl[q0], wl[q0 + 1]); q1 = q0 + 1
        while q1 < len(pts) - 1 and dirn(pts[q1], pts[q1 + 1]) == d0 and min(wl[q1], wl[q1 + 1]) == w0: q1 += 1
        out.append([cxy(pts[q0]), cxy(pts[q1]), w0]); q0 = q1
    return out
segs = []
for name, path in paths: segs += [s + [name] for s in to_segs(path)]
# exact check; narrow a track until it clears
REG = BOARD.buffer(-0.25)
bad = []
for s in segs:
    while True:
        g = LineString([s[0], s[1]]).buffer(s[2] / 2, 16) if s[0] != s[1] else Point(s[0]).buffer(s[2] / 2, 16)
        dmin = g.distance(OBST) if not OBST.is_empty else 9
        if (dmin >= CLR - 0.002 and REG.contains(g)) or s[2] - WSTEP < WMIN - 1e-6: break
        s[2] = round(s[2] - WSTEP, 3)
    if dmin < CLR - 0.002 or not REG.contains(g): bad.append((s[0], s[1], s[2], round(dmin, 3)))
segs = [s for s in segs if s[0] != s[1]]
TR = unary_union([LineString([s[0], s[1]]).buffer(s[2] / 2, 16) for s in segs]) if segs else Polygon()

# ---- stitching vias to the net's sheet on SLAY, where a through via is free on every layer
stitches = []
if STITCH > 0 and segs:
    VD, VDR = 0.45, 0.3
    obs_all = []
    for p in D["pads"]:
        if p["net"] == NET and p["net"]: continue
        for L, rs in p["shapes"].items():
            if L in ("F.Cu", "B.Cu", "In2.Cu", "In3.Cu") or p.get("drill", 0) > 0: obs_all += [poly(r) for r in rs]
    for t in S["tracks"]:
        if t["net"] != NET: obs_all.append(LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 8))
    for z in S["zones"]:
        if z["net"] != NET and z["layer"] in ("F.Cu", "B.Cu", "In2.Cu", "In3.Cu"): obs_all += [poly(p) for p in z["polys"]]
    for k in D.get("keepouts", []):
        if k.get("no_vias") or k.get("no_tracks"): obs_all += [poly(p) for p in k["poly"]]
    OA = unary_union(obs_all)
    SHEET = unary_union([poly(p) for z in S["zones"] if z["net"] == NET and z["layer"] == SLAY for p in z["polys"]])
    vpts = [(v["x"], v["y"]) for v in S["vias"]]; tht = [(p["x"], p["y"]) for p in D["pads"] if p.get("drill", 0) > 0]
    def via_ok(x, y):
        c = Point(x, y); disc = c.buffer(VD / 2, 16)
        if not TR.buffer(-0.05).contains(disc) or not SHEET.buffer(-0.3).contains(c): return False
        if disc.distance(OA) < CLR + 0.02: return False
        if not SM.is_empty and c.distance(SM) < ESC + VD / 2: return False
        if any(math.dist((x, y), q) < 0.75 for q in vpts): return False
        if any(math.dist((x, y), q) < 1.1 for q in tht): return False
        return True
    for a, b, w, name in segs:
        L = math.dist(a, b); n = int(L // STITCH)
        for q in range(n + 1):
            f = (q + 0.5) / (n + 1); x, y = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
            if any(math.dist((x, y), s_) < STITCH * 0.8 for s_ in stitches): continue
            if via_ok(x, y): stitches.append((round(x, 3), round(y, 3))); vpts.append((x, y))
    S["vias"] = S["vias"] + [dict(net=NET, x=x, y=y, size=VD, drill=VDR) for x, y in stitches]

new = [dict(net=NET, layer=LAY, a=[round(a[0], 4), round(a[1], 4)], b=[round(b[0], 4), round(b[1], 4)], w=w) for a, b, w, n in segs]
S["tracks"] = S["tracks"] + new
Ltot = sum(math.dist(a, b) for a, b, w, n in segs)
sq = sum(math.dist(a, b) / w for a, b, w, n in segs)
prof = {}
for a, b, w, n in segs: prof[w] = round(prof.get(w, 0) + math.dist(a, b), 1)
rec = dict(net=NET, layer=LAY, source=SRC, to=TO, reached=[n for n, p in paths], missed=[TERMS[k][0] for k in missed],
           segments=len(new), length_mm=round(Ltot, 1), squares=round(sq, 1), width_mm=dict(sorted(prof.items(), reverse=True)),
           stitch_vias=len(stitches), clearance_faults=bad, area_mm2=round(TR.area, 1))
S.setdefault("trunks", []).append(rec)
json.dump(S, open(A[2], "w"), indent=1)
print(f"trunk {NET} on {LAY}: {SRC} -> {','.join(n for n, p in paths)}; missed {rec['missed']}; {len(new)} tracks, {Ltot:.1f} mm, "
      f"{sq:.1f} squares (track only, about {sq * 0.25:.1f} mohm at 2 oz), widths {rec['width_mm']}; stitch vias {len(stitches)}; "
      f"clearance faults {len(bad)}; {time.time() - t0:.0f} s")
for b_ in bad: print("  CLEARANCE", b_)

if "png" in O:                                       # free room (white), obstacles (red), terminals (blue), trunk (green), stitches (black)
    k = 4; im = Image.new("RGB", (NX * k, NY * k), (235, 235, 235)); dr = ImageDraw.Draw(im)
    P = lambda x, y: ((x - X0) / G * k, (y - Y0) / G * k)
    ys_, xs_ = np.nonzero(FREE)
    for x_, y_ in zip(xs_, ys_): dr.rectangle([x_ * k, y_ * k, x_ * k + k - 1, y_ * k + k - 1], fill=(255, 255, 255) if mult[y_, x_] == 1 else (250, 240, 180))
    def fillg(g, col):
        for q in parts(g):
            if not q.is_empty: dr.polygon([P(*c) for c in q.exterior.coords], fill=col)
    fillg(OBST.intersection(WIN), (230, 120, 120))
    for t in TERMS: fillg(t[1].intersection(WIN), (90, 120, 230))
    fillg(TR, (0, 160, 0))
    for x, y in stitches:
        c = P(x, y); dr.ellipse([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=(0, 0, 0))
    im.save(O["png"])
sys.exit(1 if missed or bad else 0)
