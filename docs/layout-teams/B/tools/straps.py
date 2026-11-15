"""straps.py <spec.json> <bare.json or cu.json> <out spec.json> [options]
Hard strap tracks for a SOFT power pour, so that the full trial route cannot cut it into islands.

Why: score_board.sh routes with --softnets=GND,PACK_P,3V3, so the router treats those nets' zones as soft: signal
tracks may cross them and the last refill carves round the tracks. PACK_P's In2.Cu bus is crossed by the north-south
In2 signal lanes and falls apart (r3a routed: the five PACK_P vias at J113/R427.2 end on a 15.6 mm2 island, so J113
and R427 are open). Tracks are hard for the router (it never crosses another net's track), so a tree of tracks that
ties every group of the net's vias to the source's group keeps the net whole whatever the router does to the pour.

What it does:
  1. Groups the net's vias and through-hole pads that touch the planned pour on --layer. Items join one group when
     they are tied by copper the router cannot cut: a via in or next to a pad (gap under --join mm), two vias closer
     than --join mm edge to edge, a planned track that touches both. A pour on another layer does NOT join items
     (it is soft as well). The source group holds a pad of --source.
  2. Lays a greedy Steiner tree on a grid (--g mm): from the tree so far, the cheapest path to the nearest group not
     yet tied, again and again. Steps along the signal lanes of the layer (--lanes=V: In2 lanes run north-south) cost
     1; steps across them cost --across (they block every lane they cross), cut to --edge_across within --edge_mm of
     the board edge and under large pads (power parts: nothing routes there anyway). Each turn costs --turn grid steps.
     Near small pads of other nets (via escapes, --esc mm from the strap edge) a step costs --near_sig times more,
     right under one (--under mm) --under_pen times more: a strap under a pad takes away the pad's via escape.
  3. Width --w where it fits, never under --wmin (a narrower step costs --narrow times more). The track stays inside
     the planned pour outline and --clr mm from every other net's via, through-hole pad, planned track and pour on
     the layer, from holes and from keep-outs that forbid tracks there.
  4. Checks every strap segment exactly (shapely) and appends them to the plan's 'tracks'. The plan gets a 'straps'
     record (groups, tied, untied, lengths); --png draws the result.
Options: --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V (V or H) --w=1.0 --wmin=0.5 --clr=0.25 --g=0.1
         --across=6 --edge_across=1.5 --edge_mm=3 --turn=20 --near_sig=2.5 --esc=0.8 --under=0.3 --under_pen=15 --narrow=3 --join=0.5 --png=<file>
         --main=J113:4,R427:3 (wide straps from the source straight to these terminals; see below)
         Several nets: run it again on its own output with other options (each run adds one net's tree).
Exit 1 when a group could not be tied (the plan is still written, with the groups that could)."""
import sys, json, math, time
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from scipy.ndimage import binary_erosion

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 3: print(__doc__); sys.exit(2)
NET = O.get("net", "PACK_P"); LAY = O.get("layer", "In2.Cu"); SRC = O.get("source", "Q102"); LANES = O.get("lanes", "V")
W, WMIN, CLR, G = float(O.get("w", 1.0)), float(O.get("wmin", 0.5)), float(O.get("clr", 0.25)), float(O.get("g", 0.1))
ACROSS, EDGE_ACROSS, EDGE_MM, TURN = float(O.get("across", 6)), float(O.get("edge_across", 1.5)), float(O.get("edge_mm", 3)), float(O.get("turn", 20))
NEAR_SIG, NARROW, JOIN, ESC = float(O.get("near_sig", 2.5)), float(O.get("narrow", 3)), float(O.get("join", 0.5)), float(O.get("esc", 0.8))
UNDER, UNDER_PEN = float(O.get("under", 0.3)), float(O.get("under_pen", 15))
TOL = 0.05                                          # raster margin on top of every clearance

S = json.load(open(A[0])); D = json.load(open(A[1])); t0 = time.time()

def poly(r):                                        # {"ring", "holes"} -> shapely
    return Polygon(r["ring"], r.get("holes", [])).buffer(0)

# ---- the planned pour of NET on LAY (the straps stay inside it)
zs = [z for z in S["zones"] if z["net"] == NET and z["layer"] == LAY]
if not zs: print(f"straps: no planned {NET} zone on {LAY}; nothing to do"); json.dump(S, open(A[2], "w"), indent=1); sys.exit(0)
REGION = unary_union([poly(p) for z in zs for p in z["polys"]])

# ---- obstacles on LAY: other nets' vias, through-hole pads, tracks and zones; holes; keep-outs forbidding tracks
obst = []
for v in S["vias"]:
    if v["net"] != NET: obst.append(Point(v["x"], v["y"]).buffer(v["size"] / 2, 16))
for p in D["pads"]:
    if p["net"] == NET and not p.get("npth"): continue
    if p.get("drill", 0) > 0 or LAY in p["shapes"]:
        sh = p["shapes"].get(LAY)
        if sh: obst += [poly(r) for r in sh]
        if p.get("drill", 0) > 0: obst.append(Point(p["x"], p["y"]).buffer(p["drill"] / 2 + (0.25 - CLR if p.get("npth") or not p["net"] else 0), 16))
for t in S["tracks"]:
    if t["layer"] == LAY and t["net"] != NET: obst.append(LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 8))
for z in S["zones"]:
    if z["layer"] == LAY and z["net"] != NET: obst += [poly(p) for p in z["polys"]]
for k in D.get("keepouts", []):
    if LAY in k["layers"] and (k.get("no_tracks") or k.get("no_vias")): obst += [poly(p) for p in k["poly"]]
OBST = unary_union(obst)
BOARD = unary_union([poly(o) for o in D["outline"]])

# ---- grid
x0, y0, x1, y1 = REGION.bounds; X0, Y0 = x0 - 1, y0 - 1; NX, NY = int((x1 - x0 + 2) / G) + 1, int((y1 - y0 + 2) / G) + 1
def raster(geom, val=1, holes_small=False):     # holes_small: hole edges stay filled (an obstacle raster then errs large)
    im = Image.new("1", (NX, NY), 0); dr = ImageDraw.Draw(im)
    gs = [geom] if isinstance(geom, Polygon) else list(getattr(geom, "geoms", []))
    for g in gs:
        if not isinstance(g, Polygon) or g.is_empty: continue
        dr.polygon([((x - X0) / G, (y - Y0) / G) for x, y in g.exterior.coords], fill=1)
        for h in g.interiors:
            dr.polygon([((x - X0) / G, (y - Y0) / G) for x, y in h.coords], fill=0)
            if holes_small: dr.line([((x - X0) / G, (y - Y0) / G) for x, y in h.coords], fill=1, width=3)
    return np.array(im, dtype=bool)
def cxy(i, j): return (X0 + i * G, Y0 + j * G)        # cell (i column, j row) centre
def free_for(w):
    # PIL fills every pixel an edge touches, so a filled shape comes out up to a cell too large: the allowed area is
    # eroded by one cell so that it errs on the small side (obstacles err on the large side by themselves)
    inside = raster(REGION.buffer(-(w / 2 + TOL), 8)) & raster(BOARD.buffer(-(0.25 + w / 2 + TOL), 8))
    inside = binary_erosion(inside, np.ones((3, 3), bool))
    return inside & ~raster(OBST.buffer(CLR + w / 2 + TOL + (0.02 if w > 1.5 else 0), 8 if w <= 1.5 else 32), holes_small=w > 1.5)
FREE_W, FREE_MIN = free_for(W), free_for(WMIN)
FREE_W &= FREE_MIN

# ---- cost of a step into a cell, per direction (along / across the lanes)
edge_band = raster(BOARD) & ~raster(BOARD.buffer(-EDGE_MM, 8))
big = [poly(r) for p in D["pads"] for L in ("F.Cu", "B.Cu") for r in p["shapes"].get(L, []) if poly(r).area >= 2.0]
under_big = raster(unary_union(big).buffer(0.3)) if big else np.zeros((NY, NX), bool)
smallp = [poly(r) for p in D["pads"] if p["net"] not in (NET, "GND", "") for L in ("F.Cu", "B.Cu") for r in p["shapes"].get(L, []) if poly(r).area < 1.0]
SM = unary_union(smallp) if smallp else Polygon()
near_sig = raster(SM.buffer(ESC + W / 2)) if smallp else np.zeros((NY, NX), bool)
under_sig = raster(SM.buffer(UNDER + W / 2)) if smallp else np.zeros((NY, NX), bool)
mult = np.ones((NY, NX)); mult[near_sig & ~under_big] *= NEAR_SIG; mult[under_sig] *= UNDER_PEN / NEAR_SIG if NEAR_SIG else UNDER_PEN
mult[under_sig & ~near_sig] = UNDER_PEN; mult[FREE_MIN & ~FREE_W] *= NARROW
across = np.full((NY, NX), ACROSS); across[edge_band | under_big] = EDGE_ACROSS
along_c, across_c = mult, mult * across
# lanes V: steps in y run along the lanes; lanes H: steps in x do
cost_x, cost_y = (across_c, along_c) if LANES == "V" else (along_c, across_c)

# ---- groups of the net's items that touch the pour (union-find over hard ties)
items = []                                          # (kind, label, shapely geometry, on LAY?)
for v in S["vias"]:
    if v["net"] == NET: items.append(("via", f"via {v['x']:.2f},{v['y']:.2f}", Point(v["x"], v["y"]).buffer(v["size"] / 2, 16), True))
for p in D["pads"]:
    if p["net"] != NET: continue
    gs = [poly(r) for L, rs in p["shapes"].items() for r in rs]
    if not gs: continue
    items.append(("pad", f"{p['ref']}.{p['num']}", unary_union(gs), p.get("drill", 0) > 0 or LAY in p["shapes"]))
for t in S["tracks"]:
    if t["net"] == NET: items.append(("track", f"track {t['layer']}", LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 8), t["layer"] == LAY))
par = list(range(len(items)))
def find(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        a, b = items[i], items[j]
        if a[0] == "pad" and b[0] == "pad": gap = 0.0 if a[2].intersects(b[2]) else 9
        else: gap = a[2].distance(b[2])
        if gap < (0.01 if "track" in (a[0], b[0]) else JOIN): par[find(i)] = find(j)
groups = {}
for i, it in enumerate(items): groups.setdefault(find(i), []).append(i)
def reach(ix):                                      # does the item reach the pour on LAY (a via or THT pad inside it)?
    k, _, g, onl = items[ix]
    return onl and g.intersects(REGION)
G_ON = {r: [i for i in m if reach(i)] for r, m in groups.items()}
G_ON = {r: m for r, m in G_ON.items() if m}
src = [r for r, m in G_ON.items() if any(items[i][1].split(".")[0] == SRC for i in groups[r])]
if not src:                                         # source pads with no via of their own: the group nearest to them
    sp_ = unary_union([it[2] for it in items if it[0] == "pad" and it[1].split(".")[0] == SRC])
    src = [min(G_ON, key=lambda r: min(items[i][2].distance(sp_) for i in G_ON[r]))] if not sp_.is_empty else [max(G_ON, key=lambda r: len(G_ON[r]))]
SRC_G = src[0]
def gname(r):
    m = groups[r]; refs = sorted({items[i][1].split(".")[0] for i in m if items[i][0] == "pad"}); nv = sum(items[i][0] == "via" for i in m)
    c = unary_union([items[i][2] for i in G_ON[r]]).centroid
    return f"{'+'.join(refs) or 'vias'} ({nv} vias, at {c.x:.1f},{c.y:.1f})"

# target cells of a group: cells of FREE_MIN inside its items on LAY (a via disc, a THT pad)
def cells_of(geom):
    m = raster(geom) & FREE_MIN
    if not m.any():                                 # tiny via disc: the free cell nearest its centre within the disc
        m = raster(geom.buffer(0.05))
        m &= FREE_MIN
    return np.flatnonzero(m.ravel())
GCELLS = {r: np.unique(np.concatenate([cells_of(items[i][2]) for i in m])) for r, m in G_ON.items()}

# ---- graph: node = cell * 4 + dir (0 +x, 1 -x, 2 +y, 3 -y); moves keep dir, a turn changes it
N = NX * NY; idx = np.arange(N); ii, jj = idx % NX, idx // NX
def graph(cost_x, cost_y, fm):
    rows, cols, vals = [], [], []
    for d, (dx, dy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        ok = fm & (ii + dx >= 0) & (ii + dx < NX) & (jj + dy >= 0) & (jj + dy < NY)
        src_c = idx[ok]; dst_c = src_c + dx + dy * NX; ok2 = fm[dst_c]; src_c, dst_c = src_c[ok2], dst_c[ok2]
        c = (cost_x if dx else cost_y).ravel()[dst_c]
        rows.append(src_c * 4 + d); cols.append(dst_c * 4 + d); vals.append(c)
    for d in range(4):
        for e in ((2, 3) if d < 2 else (0, 1)):
            c_ = idx[fm]; rows.append(c_ * 4 + d); cols.append(c_ * 4 + e); vals.append(np.full(len(c_), TURN))
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(N * 4, N * 4))
GR = graph(cost_x, cost_y, FREE_MIN.ravel())

tree = set(GCELLS[SRC_G].tolist()); tied = {SRC_G}; paths = []; untied = []
todo = [r for r in G_ON if r != SRC_G]
while todo:
    left = [r for r in todo if not (set(GCELLS[r].tolist()) & tree)]
    for r in todo:
        if r not in left: tied.add(r)
    todo = left
    if not todo: break
    srcs = np.array(sorted(tree)); srcs = np.concatenate([srcs * 4 + d for d in range(4)])
    dist, pred, _ = dijkstra(GR, directed=True, indices=srcs, min_only=True, return_predecessors=True)
    best = None
    for r in todo:
        cs = GCELLS[r]
        if not len(cs): continue
        nodes = np.concatenate([cs * 4 + d for d in range(4)]); k = nodes[np.argmin(dist[nodes])]
        if np.isfinite(dist[k]) and (best is None or dist[k] < best[0]): best = (dist[k], r, k)
    if best is None:
        untied = todo; break
    _, r, k = best; path = []
    while k >= 0 and (k // 4) not in tree: path.append(k // 4); k = pred[k]
    if k >= 0: path.append(k // 4)
    path = path[::-1]; tree |= set(path); paths.append((r, path)); tied.add(r); todo.remove(r)

# ---- cells to segments: straight runs, split where the width changes
def to_segs(path, width_of, tag):
    """width_of(cell) -> width that fits at the cell; a piece gets the narrowest width of its cells."""
    out = []; pts = [(c % NX, c // NX) for k_, c in enumerate(path) if k_ == 0 or c != path[k_ - 1]]   # a turn repeats its cell
    wo = lambda p: width_of(p[1] * NX + p[0])
    def flush(run):
        k0 = 0
        while k0 < len(run) - 1:
            w0 = min(wo(run[k0]), wo(run[k0 + 1])); k1 = k0 + 1
            while k1 < len(run) - 1 and min(wo(run[k1]), wo(run[k1 + 1])) == w0: k1 += 1
            out.append((cxy(*run[k0]), cxy(*run[k1]), w0, tag)); k0 = k1
    run = [pts[0]]
    for p in pts[1:]:
        if len(run) >= 2 and (p[0] - run[-1][0], p[1] - run[-1][1]) != (run[-1][0] - run[-2][0], run[-1][1] - run[-2][1]):
            flush(run); run = [run[-1]]
        run.append(p)
    if len(run) >= 2: flush(run)
    return out
fw = FREE_W.ravel(); segs = []
for r, path in paths: segs += to_segs(path, lambda c: W if fw[c] else WMIN, r)

# ---- optional wide mains (--main=J113:4,R427:3): a wide strap from the source group straight to a high-current
#      terminal's group, so its current does not depend on what the router leaves of the soft pour. Width steps down
#      (w, 3/4 w, w/2, --w) where the full width does not fit; steps cost the same both ways (the current wants the
#      short way), a narrower step costs more, small pads of other nets cost as in the tree.
mains = []
for spec_ in [m for m in O.get("main", "").split(",") if m]:
    ref, wm = spec_.split(":"); wm = float(wm)
    tg = [r for r, m in G_ON.items() if any(items[i][0] == "pad" and items[i][1].split(".")[0] == ref for i in groups[r])]
    if not tg: print(f"  MAIN {ref}: no group of {NET} holds a pad of {ref} on the pour"); continue
    ladder = sorted({w for w in (wm, 0.75 * wm, 0.5 * wm, W) if w >= W}, reverse=True)
    cls = np.full(N, len(ladder), dtype=int)
    for ci in range(len(ladder) - 1, -1, -1): cls[free_for(ladder[ci]).ravel() & FREE_MIN.ravel()] = ci
    cls[FREE_MIN.ravel() & (cls == len(ladder))] = len(ladder)          # fits only --wmin
    wl = ladder + [WMIN]
    cst = (mult / np.where(FREE_MIN & ~FREE_W, NARROW, 1.0)).ravel() * (1.0 + 1.5 * cls)
    cst = cst.reshape(NY, NX)
    GM = graph(cst, cst, FREE_MIN.ravel())
    s0 = GCELLS[SRC_G]; srcs = np.concatenate([s0 * 4 + d for d in range(4)])
    dist, pred, _ = dijkstra(GM, directed=True, indices=srcs, min_only=True, return_predecessors=True)
    cs = GCELLS[tg[0]]; nodes = np.concatenate([cs * 4 + d for d in range(4)]); k = nodes[np.argmin(dist[nodes])]
    if not np.isfinite(dist[k]): print(f"  MAIN {ref}: no way"); continue
    path = []
    while k >= 0: path.append(k // 4); k = pred[k]
    ms = to_segs(path[::-1], lambda c: wl[cls[c]], tg[0]); segs += ms; mains.append((ref, wm, ms))

# ---- exact check of every segment, then write
bad = []
for a, b, w, r in segs:
    g = LineString([a, b]).buffer(w / 2, 16)
    dmin = g.distance(OBST) if not OBST.is_empty else 9
    if dmin < CLR - 0.005 or not REGION.buffer(0.005).contains(g): bad.append((a, b, w, round(dmin, 3)))
new = [dict(net=NET, layer=LAY, a=[round(a[0], 4), round(a[1], 4)], b=[round(b[0], 4), round(b[1], 4)], w=w) for a, b, w, r in segs]
S["tracks"] = S["tracks"] + new
L_tot = sum(math.dist(a, b) for a, b, w, r in segs)
L_across = sum(math.dist(a, b) for a, b, w, r in segs if (abs(a[1] - b[1]) < 1e-6 if LANES == "V" else abs(a[0] - b[0]) < 1e-6))
rec = dict(net=NET, layer=LAY, source=gname(SRC_G), groups=len(G_ON), tied=len(tied), untied=[gname(r) for r in untied],
           segments=len(new), length_mm=round(L_tot, 1), across_lanes_mm=round(L_across, 1),
           narrow_mm=round(sum(math.dist(a, b) for a, b, w, r in segs if w < W), 1), clearance_faults=bad,
           paths=[dict(to=gname(r), cells=len(p)) for r, p in paths],
           mains=[dict(to=ref, w=wm, length_mm=round(sum(math.dist(a, b) for a, b, w, r in ms), 1),
                       full_width_mm=round(sum(math.dist(a, b) for a, b, w, r in ms if w >= wm), 1)) for ref, wm, ms in mains])
S.setdefault("straps", []).append(rec)
json.dump(S, open(A[2], "w"), indent=1)
print(f"straps {NET} on {LAY}: {len(G_ON)} groups, {len(tied)} tied to {gname(SRC_G)}, untied {len(untied)}; "
      f"{len(new)} segments, {L_tot:.1f} mm ({L_across:.1f} mm across the lanes, {rec['narrow_mm']} mm at {WMIN} mm); "
      f"clearance faults {len(bad)}; {time.time() - t0:.0f} s")
for p in rec["paths"]: print("  tied", p["to"])
for u in rec["untied"]: print("  UNTIED", u)
for m in rec["mains"]: print("  main to", m["to"], m["length_mm"], "mm,", m["full_width_mm"], "mm at", m["w"], "mm")
for b_ in bad: print("  CLEARANCE", b_)

if "png" in O:                                      # picture: pour (grey), obstacles (red), groups (blue), straps (green)
    k = 4; im = Image.new("RGB", (NX * k, NY * k), "white"); dr = ImageDraw.Draw(im)
    P = lambda x, y: ((x - X0) / G * k, (y - Y0) / G * k)
    def fillg(g, col):
        for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
            if isinstance(q, Polygon) and not q.is_empty: dr.polygon([P(*c) for c in q.exterior.coords], fill=col)
    fillg(REGION, (225, 225, 225))
    ys_, xs_ = np.nonzero(near_sig & FREE_MIN)
    for x_, y_ in zip(xs_[::1], ys_[::1]): dr.rectangle([x_ * k - k / 2, y_ * k - k / 2, x_ * k + k / 2, y_ * k + k / 2], fill=(245, 235, 170))
    ys_, xs_ = np.nonzero(under_big & FREE_MIN)
    for x_, y_ in zip(xs_, ys_): dr.rectangle([x_ * k - k / 2, y_ * k - k / 2, x_ * k + k / 2, y_ * k + k / 2], fill=(190, 210, 240))
    fillg(OBST, (230, 120, 120))
    for r, m in G_ON.items():
        for i in m: fillg(items[i][2], (40, 80, 230) if r in tied else (250, 160, 0))
    for a, b, w, r in segs: dr.line([P(*a), P(*b)], fill=(0, 150, 0), width=max(1, int(w / G * k)))
    im.save(O["png"])
sys.exit(1 if untied or bad else 0)
