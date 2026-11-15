#!/usr/bin/env python3
"""straps.py <spec.json> <bare.json (cu_dump of the placed bare board)> [--net=PACK_P] [--layer=In2.Cu] [--w=1.5,1.0,0.6]
         [--join=1.5] [--out=spec.json]
Team A (stagepwr) copper step, run after split_spec.py and before write_copper.py: STRAP TRACKS for a bus net.

Why: a bus net's inner-layer pour (PACK_P on In2) is soft: the router may route signals through it and the pour
refills around them. In2 is the router's vertical layer, so a few vertical signal tracks can cut the pour into
islands and open the power path on the routed board (team D). A strap is a hard track of the net laid on the pour
before routing, so the router has to go round it and the net's terminals stay joined whatever is routed.

How: the net's vias in the spec (the bus via arrays the planner put at every terminal) are grouped (centres within
--join mm); the groups are joined Kruskal-style (every pair, shortest first, while it joins two pieces, up to --maxlen=30 mm); a pair becomes a straight track
on --layer (or an L of two tracks, either corner) at the widest of --w that keeps the clearance from every other
net's via, plated hole and hard zone on that layer and stays inside the net's own pour outline on that layer. An
edge with no legal strap is reported and left to the pour. Tracks are appended to spec['tracks']."""
import sys, json, math
import numpy as np
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
NET = opt.get("net", "PACK_P"); LAY = opt.get("layer", "In2.Cu"); WS = [float(v) for v in opt.get("w", "1.5,1.0,0.6").split(",")]
JOIN = float(opt.get("join", 1.5)); MAXL = float(opt.get("maxlen", 30)); OUT = opt.get("out", a[0])
S = json.load(open(a[0])); D = json.load(open(a[1])); clr = max(S.get("clearance_mm", 0.2), 0.2)

def zpoly(p): return Polygon(p["ring"], p.get("holes", []))
own = unary_union([zpoly(p) for z in S["zones"] if z["net"] == NET and z["layer"] == LAY for p in z["polys"]])
if own.is_empty: sys.exit(f"straps: no {NET} zone on {LAY}")
obs = [Point(v["x"], v["y"]).buffer(v["size"] / 2, 12) for v in S["vias"] if v["net"] != NET]
obs += [zpoly(p) for z in S["zones"] if z["net"] != NET and z["layer"] == LAY and not z.get("soft") for p in z["polys"]]
obs += [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in S["tracks"] if t["layer"] == LAY and t["net"] != NET]
for p in D["pads"]:
    if p.get("drill") and p.get("net") != NET:
        obs.append(Point(p["x"], p["y"]).buffer(p["drill"] / 2 + 0.25, 12))      # plated hole: drill + annulus on inner layers
    if p.get("npth"): obs.append(Point(p["x"], p["y"]).buffer(p.get("drill", 0) / 2 + 0.3, 12))
O = unary_union(obs)

vs = [(v["x"], v["y"]) for v in S["vias"] if v["net"] == NET]
vs += [(p["x"], p["y"]) for p in D["pads"] if p.get("drill") and p.get("net") == NET]
# groups of vias (single linkage within JOIN)
grp = list(range(len(vs)))
def f(i):
    while grp[i] != i: grp[i] = grp[grp[i]]; i = grp[i]
    return i
for i in range(len(vs)):
    for j in range(i + 1, len(vs)):
        if math.dist(vs[i], vs[j]) < JOIN: grp[f(i)] = f(j)
G = {}
for i, v in enumerate(vs): G.setdefault(f(i), []).append(v)
C = [tuple(np.mean(g, axis=0)) for g in G.values()]
# snap each group's anchor to its via nearest the centroid (a strap must end on copper of the net)
A = [min(g, key=lambda v: math.dist(v, c)) for g, c in zip(G.values(), C)]
n = len(A)
n = len(A)
def legal(pts, w):
    ln = LineString(pts); g = ln.buffer(w / 2, 8)
    return g.distance(O) >= clr and own.buffer(0.01).contains(g)

tracks, rep = [], dict(net=NET, layer=LAY, groups=n, drawn=0)
# Kruskal over every pair, shortest first: a pair is joined by the first legal strap, only if it joins two pieces
comp = list(range(n))
def cf(i):
    while comp[i] != i: comp[i] = comp[comp[i]]; i = comp[i]
    return i
pairs = sorted(((math.dist(A[i], A[j]), i, j) for i in range(n) for j in range(i + 1, n)))
for d, i, j in pairs:
    if cf(i) == cf(j) or d > MAXL: continue
    p, q = A[i], A[j]; done = False
    for w in WS:
        for pts in ([p, q], [p, (q[0], p[1]), q], [p, (p[0], q[1]), q]):
            if legal(pts, w):
                for s_, t_ in zip(pts, pts[1:]):
                    if math.dist(s_, t_) > 1e-3: tracks.append(dict(net=NET, layer=LAY, a=[round(s_[0], 4), round(s_[1], 4)], b=[round(t_[0], 4), round(t_[1], 4)], w=w))
                done = True; rep["drawn"] += 1; rep.setdefault("widths", []).append(w); comp[cf(i)] = cf(j); break
        if done: break
# pieces still apart: a grid path (0.1 mm) through the room left inside the pour, simplified, checked as above
import shapely
from collections import deque
RES = 0.1; bx0, by0, bx1, by1 = own.bounds
xs = np.arange(bx0, bx1, RES); ys = np.arange(by0, by1, RES); XX, YY = np.meshgrid(xs, ys)
def freemask(w):
    m = shapely.contains_xy(own.buffer(-w / 2 - 0.02), XX, YY)
    return m & ~shapely.contains_xy(O.buffer(clr + w / 2 + 0.02), XX, YY)
def cellof(p): return int(round((p[1] - by0) / RES)), int(round((p[0] - bx0) / RES))
def bfs(m, a, b):
    H, W = m.shape; (ia, ja), (ib, jb) = cellof(a), cellof(b)
    m = m.copy()
    for (i, j) in ((ia, ja), (ib, jb)):        # the anchor vias are the net's own copper: open a small disk there
        m[max(0, i - 3):i + 4, max(0, j - 3):j + 4] = True
    prev = np.full(m.shape, -1, np.int64); prev[ia, ja] = ia * W + ja; q = deque([(ia, ja)])
    while q:
        i, j = q.popleft()
        if (i, j) == (ib, jb): break
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            u, v = i + di, j + dj
            if 0 <= u < H and 0 <= v < W and m[u, v] and prev[u, v] < 0: prev[u, v] = i * W + j; q.append((u, v))
    if prev[ib, jb] < 0: return None
    pts = [(ib, jb)]
    while pts[-1] != (ia, ja): k = prev[pts[-1]]; pts.append((k // W, k % W))
    return [a] + [(bx0 + j * RES, by0 + i * RES) for i, j in pts[::-1][1:-1]] + [b]
masks = {}
progress = True
while progress and len({cf(i) for i in range(n)}) > 1:
    progress = False
    best = {}
    for d, i, j in pairs:
        if cf(i) == cf(j) or d > MAXL: continue
        k = tuple(sorted((cf(i), cf(j))))
        if k not in best: best[k] = (d, i, j)
    for d, i, j in sorted(best.values()):
        if cf(i) == cf(j): continue
        for w in WS:
            if w not in masks: masks[w] = freemask(w)
            pth = bfs(masks[w], A[i], A[j])
            if pth is None: continue
            ln = LineString(pth).simplify(0.08); pts = list(ln.coords)
            if not legal(pts, w): pts = list(LineString(pth).simplify(0.02).coords)
            if not legal(pts, w): continue
            for s_, t_ in zip(pts, pts[1:]):
                if math.dist(s_, t_) > 1e-3: tracks.append(dict(net=NET, layer=LAY, a=[round(s_[0], 4), round(s_[1], 4)], b=[round(t_[0], 4), round(t_[1], 4)], w=w))
            rep["drawn"] += 1; rep.setdefault("widths", []).append(w); rep["grid_paths"] = rep.get("grid_paths", 0) + 1; comp[cf(i)] = cf(j); progress = True; break
rep["pieces_left"] = len({cf(i) for i in range(n)})
rep["left_apart"] = [[round(c, 2) for c in A[i]] for i in range(n) if cf(i) != cf(0)] if rep["pieces_left"] > 1 else []
S["tracks"] += tracks; json.dump(S, open(OUT, "w"))
rep["tracks"] = len(tracks); rep["length_mm"] = round(sum(math.dist(t["a"], t["b"]) for t in tracks), 1)
print("straps", json.dumps(rep))
