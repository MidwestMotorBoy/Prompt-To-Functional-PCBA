#!/usr/bin/env python3
"""via_site.py <board> <cu_dump.json> <net> <x0,y0,x1,y1> [zone layers=In3.Cu,In4.Cu] : team A r6_merge. Grid search (0.05 mm) for
legal sites of a 0.45/0.3 via of <net> inside the window: >= 0.16 mm to other-net tracks/vias (all layers) and pads, >= 0.5 mm
hole edge to hole edge for drilled pads, and inside a filled <net> zone on one of the zone layers (0.3 mm inside). Prints sites by margin."""
import sys, json
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
Z, T, V = load_copper(sys.argv[1]); D = json.load(open(sys.argv[2])); N = sys.argv[3]; w = [float(v) for v in sys.argv[4].split(",")]
ZL = (sys.argv[5] if len(sys.argv) > 5 else "In3.Cu,In4.Cu").split(",")
W = Polygon([(w[0] - 2, w[1] - 2), (w[2] + 2, w[1] - 2), (w[2] + 2, w[3] + 2), (w[0] - 2, w[3] + 2)])
ob = []; holes = []
for t in T:
    if t["net"] != N:
        g = LineString([t["a"], t["b"]]).buffer(t["w"] / 2)
        if g.intersects(W): ob.append(g)
for v in V:
    if v["net"] != N and W.contains(Point(v["x"], v["y"])): ob.append(Point(v["x"], v["y"]).buffer(v.get("size", 0.45) / 2)); holes.append(Point(v["x"], v["y"]).buffer(0.15 - 0.25))if False else None
    if W.contains(Point(v["x"], v["y"])): holes.append((Point(v["x"], v["y"]), 0.15, 0.2))
for p in D["pads"]:
    P0 = Point(p["x"], p["y"])
    if not W.contains(P0): continue
    if p.get("drill"): holes.append((P0, p["drill"] / 2 if not isinstance(p["drill"], list) else max(p["drill"]) / 2, 0.45))
    if p["net"] != N:
        for L, sh in p["shapes"].items():
            for s in sh: ob.append(Polygon(s["ring"]).buffer(0))
    if p.get("drill") and not p["shapes"]: ob.append(P0.buffer(p["drill"] / 2 + 0.15))
O = unary_union(ob)
zn = unary_union([Polygon(z["pts"]).buffer(0) for z in Z if z["net"] == N and z["layer"] in ZL and len(z["pts"]) > 2]).buffer(-0.3)
res = []
x = w[0]
while x <= w[2]:
    y = w[1]
    while y <= w[3]:
        p = Point(x, y)
        if ZL == ["any"] or zn.contains(p):
            m = O.distance(p) - 0.225 - 0.16
            for hp, hr, hc in holes: m = min(m, hp.distance(p) - hr - 0.15 - hc - 0.02)
            if m >= 0: res.append((round(m, 3), round(x, 3), round(y, 3)))
        y += 0.05
    x += 0.05
res.sort(reverse=True); print(len(res), "sites; best:", res[:12] if len(sys.argv) < 7 else sorted(res, key=lambda r: (r[1], r[2])))
