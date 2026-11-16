"""lane_search.py <board.kicad_pcb> <cu.json> <spec.json> <out hand.json> [--keep=<plan board>] [--step=0.05] [--png=out.png]
Team B, phase 2 round 4 (EN_5V1 worker). One signal connection laid again on a ROUTED board by a multi-layer grid
search whose costs know the power pours: a path over In2 inside the PACK_P sheet costs what it does to the sheet,
not only its length. Writes a hand file for tools/handroute2.py (tracks per layer, vias), which then does the exact
check and the write. The search itself uses pinlib's exact free areas (copper 0.15, HighCurrent 0.25, edge, keep-outs,
hot-loop pours closed; with --keep the hot pours of the plan board too) rasterised at --step, and pinlib.check_via
for every via site (lazy, cached, on a 2-step lattice).

spec.json:
  {"net": "EN_5V1", "w": 0.15, "box": [x0, y0, x1, y1], "layers": ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"],
   "start": {"layer": "F.Cu", "box": [x0, y0, x1, y1]}          own copper of the net on that layer inside the box
   "goal_items": {"tracks": [...], "vias": [...]}               copper (hand-file form) that is NOT on the board yet
                                                                but will be (the part that stays); it is the goal
   "goal_pads": ["U301.12"],                                    pads that are a goal too
   "cost": {"len": 1.0, "via": 1.5,                             per mm; a via in mm-equivalent
            "soft": {"PACK_P": 40, "3V3": 30, "GND": 4},        extra per mm inside a filled pour of that net (any
                                                                layer; the track carves the pour on refill)
            "layer": {"F.Cu": 1.0, "B.Cu": 1.0}},               factor on the length per layer
   "via_soft": {"PACK_P": 0.5},                                 extra cost of a via inside a pour of that net (antipad)
   "grade": {"PACK_P": [K, R]},                                 extra K per mm at the pour edge, falling to 0 at R mm
                                                                out (how deep the refill carves goes with the distance)
   "extra_cost": [{"layer": "In2.Cu", "box": [x0, y0, x1, y1], "cost": 200}]}   dear areas set by hand (per mm)
Output: the hand file ("lift": [net], "tracks", "vias" with "rmun": true, the goal items that the path ends on or
beyond are copied in as they are), the path printed per layer, the cost split (mm per layer, mm inside each pour)."""
import sys, os, json, math, heapq, time
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinlib
from shapely.geometry import Polygon, Point, LineString, box as sbox, MultiPolygon
from shapely.ops import unary_union

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
pcb, cuj, specf, outf = A[:4]
S = json.load(open(specf)); NET = S["net"]; W = float(S.get("w", 0.15)); STEP = float(O.get("step", 0.05))
LAY = S.get("layers", ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"]); C = S.get("cost", {})
CL, CV = float(C.get("len", 1.0)), float(C.get("via", 1.5)); SOFT = C.get("soft", {"PACK_P": 40, "3V3": 30, "GND": 4})
LF = C.get("layer", {}); VSOFT = S.get("via_soft", {"PACK_P": 0.5})
t0 = time.time()
D, G, (Z0, T0, V0) = pinlib.load_board(pcb, cuj)
if "keep" in O:                                   # hot-loop pours of the plan board are obstacles (as handroute.py)
    sys.path.insert(0, os.path.join(pinlib.REPO, "tools/copper"))
    from dc_score import load_copper as _lc
    ZK, _, _ = _lc(O["keep"]); zk = {}
    for z in ZK:
        if len(z["pts"]) > 2 and z["layer"] in ("F.Cu", "B.Cu"):
            zk.setdefault((z["net"], z["layer"]), []).append(Polygon(z["pts"]).buffer(0))
    zks = [dict(net=n_, layer=L_, geoms=g_) for (n_, L_), g_ in zk.items()]
    for zi, pi in pinlib.hot_polys(zks, D["pads"]):
        z = zks[zi]; G.items[z["layer"]].append((z["net"], "hotzone", z["geoms"][pi], dict(z, soft=True)))
    G._index()
# goal copper: the items that stay (added to the world as the net's own copper)
GI = S.get("goal_items", {}); goal_geo = {L: [] for L in pinlib.CU}
for t in GI.get("tracks", []):
    for a, b in zip(t["points"], t["points"][1:]):
        g = G._track(NET, t["layer"], a, b, t["w"]); goal_geo[t["layer"]].append(g)
for v in GI.get("vias", []):
    g = G._via(NET, v["x"], v["y"])
    for L in pinlib.CU: goal_geo[L].append(g)
for pr in S.get("goal_pads", []):
    ref, num = pr.split(".")
    for p in pinlib.pad_of(D, ref, num):
        for L, rs in p["shapes"].items():
            for r in rs: goal_geo.setdefault(L, []).append(pinlib.poly(r))
G._index()
x0, y0, x1, y1 = S["box"]; nx, ny = int((x1 - x0) / STEP) + 1, int((y1 - y0) / STEP) + 1


def ras(g, shrink=0.0):
    im = Image.new("1", (nx, ny), 0); d = ImageDraw.Draw(im)
    if g is None or g.is_empty: return np.zeros((ny, nx), bool)
    if shrink: g = g.buffer(-shrink)
    for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
        if not isinstance(q, Polygon) or q.is_empty: continue
        d.polygon([((x - x0) / STEP, (y - y0) / STEP) for x, y in q.exterior.coords], fill=1)
        for h in q.interiors: d.polygon([((x - x0) / STEP, (y - y0) / STEP) for x, y in h.coords], fill=0)
    return np.array(im, dtype=bool)


FREE, COST, FREEG = {}, {}, {}
for L in LAY:
    # search width W + 0.016: the obstacle buffers of free_area are 12-segment polygons (up to 0.005 mm short on a
    # 0.55 mm radius) and the exact check keeps 3 um more than the rule, so a centre line inside this area passes it
    fr = G.free_area(NET, L, W + 0.016, (x0, y0, x1, y1), soft_ok=True); FREEG[L] = fr
    # PIL fills every pixel its outline touches (up to one pixel too many on each side): one pixel of erosion
    from scipy.ndimage import binary_erosion
    FREE[L] = binary_erosion(ras(fr), np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool))
    c = np.full((ny, nx), CL * float(LF.get(L, 1.0)))
    for z in G.zones:
        if z["layer"] != L or z["net"] not in SOFT or not z["soft"]: continue
        for g in z["geoms"]:
            if g.intersects(sbox(x0, y0, x1, y1)):
                c[ras(g.buffer(pinlib.CLR + W / 2))] += float(SOFT[z["net"]])
    for gn, (K, R) in S.get("grade", {}).items():     # graded: K per mm at the pour edge, falling to 0 at R mm out
        from scipy.ndimage import distance_transform_edt
        mk = np.zeros((ny, nx), bool)
        for z in G.zones:
            if z["layer"] == L and z["net"] == gn:
                for g in z["geoms"]:
                    if g.intersects(sbox(x0, y0, x1, y1)): mk |= ras(g)
        if mk.any():
            dd = distance_transform_edt(~mk) * STEP; c += float(K) * np.clip((float(R) - dd) / float(R), 0, 1)
    for e in S.get("extra_cost", []):              # hand-set dear areas: {"layer", "box": [x0, y0, x1, y1], "cost"}
        if e["layer"] == L: c[ras(sbox(*e["box"]))] += float(e["cost"])
    COST[L] = c
print("lane_search: free areas and cost maps of %s in %.1f s" % (LAY, time.time() - t0), flush=True)
# start / goal cells
sb = S["start"]; own = G.own(NET, sb["layer"], sb["box"])
START = [(LAY.index(sb["layer"]), j, i) for j, i in np.argwhere(ras(own.intersection(sbox(*sb["box"]))) & FREE[sb["layer"]])]
GOAL = {L: ras(unary_union(goal_geo.get(L, [])).intersection(FREEG[L].buffer(1e-3))) & FREE[L] if goal_geo.get(L) else np.zeros((ny, nx), bool) for L in LAY}
print("lane_search: %d start cells, goal cells %s" % (len(START), {L: int(GOAL[L].sum()) for L in LAY}), flush=True)
VC = {}


def via_ok(i, j):
    k = (i, j)
    if k not in VC:
        x, y = x0 + i * STEP, y0 + j * STEP
        f = G.check_via(NET, x, y, soft_ok=True)
        if f: VC[k] = None
        else:
            e = 0.0
            for z in G.zones:
                if z["net"] in VSOFT and z["layer"] in ("In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "F.Cu", "B.Cu"):
                    for g in z["geoms"]:
                        if g.distance(Point(x, y)) < 0.5: e += float(VSOFT[z["net"]]); break
            VC[k] = e
    return VC[k]


gy = [j for L in LAY for j, i in np.argwhere(GOAL[L])]
gmin, gmax = (min(gy), max(gy)) if gy else (0, ny)
D8 = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
dist = {}; prev = {}; q = []
for s in START:
    dist[s] = 0.0; heapq.heappush(q, (0.0, 0.0, s))
end = None; nexp = 0
while q:
    f, d, s = heapq.heappop(q)
    if d > dist.get(s, 1e18): continue
    l, j, i = s; nexp += 1
    if GOAL[LAY[l]][j, i]: end = s; break
    c0 = COST[LAY[l]]; fr = FREE[LAY[l]]
    for di, dj, m in D8:
        a, b = i + di, j + dj
        if 0 <= a < nx and 0 <= b < ny and fr[b, a]:
            nd = d + m * STEP * 0.5 * (c0[j, i] + c0[b, a])
            t = (l, b, a)
            if nd < dist.get(t, 1e18):
                dist[t] = nd; prev[t] = s; h = max(0, gmin - b, b - gmax) * STEP * CL
                heapq.heappush(q, (nd + h, nd, t))
    if i % 2 == 0 and j % 2 == 0:
        e = via_ok(i, j)
        if e is not None:
            for l2 in range(len(LAY)):
                if l2 == l or not FREE[LAY[l2]][j, i]: continue
                nd = d + CV + e; t = (l2, j, i)
                if nd < dist.get(t, 1e18):
                    dist[t] = nd; prev[t] = s; h = max(0, gmin - j, j - gmax) * STEP * CL
                    heapq.heappush(q, (nd + h, nd, t))
print("lane_search: search %s after %d nodes, %d via sites tested, %.1f s" % ("found" if end else "FAILED", nexp, len(VC), time.time() - t0), flush=True)
if not end: sys.exit(1)
cells = [end]
while cells[-1] in prev: cells.append(prev[cells[-1]])
cells = cells[::-1]
# runs per layer, straightened inside the exact free area
runs = [[cells[0]]]
for c in cells[1:]:
    if c[0] != runs[-1][-1][0]: runs.append([c])
    else: runs[-1].append(c)
xy = lambda c: (round(x0 + c[2] * STEP, 4), round(y0 + c[1] * STEP, 4))
tracks, vias = [], []
split = {}
for k, r in enumerate(runs):
    L = LAY[r[0][0]]; pts = [xy(c) for c in r]
    if k > 0: vias.append(dict(net=NET, x=pts[0][0], y=pts[0][1], rmun=True))
    if len(pts) < 2: continue
    # straightening: a shortcut must stay in the free area AND cost no more than the cells it replaces (+2 %), so a
    # straight piece does not slide into a dear pour edge that the search went round
    inside = FREEG[L].buffer(1e-4); out = [pts[0]]; a = 0; cm = COST[L]
    cum = [0.0]
    for p_, q_ in zip(r, r[1:]): cum.append(cum[-1] + math.hypot(p_[1] - q_[1], p_[2] - q_[2]) * STEP * 0.5 * (cm[p_[1], p_[2]] + cm[q_[1], q_[2]]))
    def segcost(p_, q_):
        n_ = max(2, int(math.dist(p_, q_) / (STEP / 2)) + 1); tot = 0.0
        for k_ in range(n_):
            x_ = p_[0] + (q_[0] - p_[0]) * k_ / (n_ - 1); y_ = p_[1] + (q_[1] - p_[1]) * k_ / (n_ - 1)
            tot += cm[min(ny - 1, max(0, int(round((y_ - y0) / STEP)))), min(nx - 1, max(0, int(round((x_ - x0) / STEP))))]
        return tot / n_ * math.dist(p_, q_)
    while a < len(pts) - 1:
        b = len(pts) - 1
        while b > a + 1 and not (inside.contains(LineString([pts[a], pts[b]])) and segcost(pts[a], pts[b]) <= (cum[b] - cum[a]) * 1.02 + 1e-6): b -= 1
        out.append(pts[b]); a = b
    tracks.append(dict(net=NET, layer=L, w=W, points=[list(p) for p in out]))
    ln = sum(math.dist(p, q) for p, q in zip(out, out[1:])); split[L] = split.get(L, 0) + ln
    print("  %s %.2f mm: %s" % (L, ln, " ".join("%.3f,%.3f" % p for p in out)))
print("  vias: %s" % " ".join("%.3f,%.3f" % (v["x"], v["y"]) for v in vias))
print("lane_search: cost %.2f, mm per layer %s, %d vias" % (dist[end], {k: round(v, 2) for k, v in split.items()}, len(vias)))
H = dict(board=O.get("for", pcb), note=S.get("note", ""), lift=[NET], tracks=tracks + GI.get("tracks", []),
         vias=vias + GI.get("vias", []))
json.dump(H, open(outf, "w"), indent=1)
print("lane_search: wrote", outf)
if "png" in O:
    sc = 8
    im = Image.new("RGB", (nx * len(LAY) // 1, ny), "white"); px = im.load()
    pics = []
    for L in LAY:
        a = np.full((ny, nx, 3), 255, np.uint8); a[~FREE[L]] = (200, 200, 200)
        a[(COST[L] > CL * 1.01) & FREE[L]] = (240, 210, 240)
        a[GOAL[L]] = (150, 230, 150)
        for c in cells:
            if LAY[c[0]] == L: a[c[1], c[2]] = (220, 0, 0)
        pics.append(Image.fromarray(a))
    o = Image.new("RGB", (sum(p.size[0] for p in pics) + 6 * len(pics), ny), "white"); xo = 0
    for p, L in zip(pics, LAY):
        o.paste(p, (xo, 0)); ImageDraw.Draw(o).text((xo + 3, 3), L, fill=(0, 0, 200)); xo += p.size[0] + 6
    o.save(O["png"]); print("lane_search: picture", O["png"])
