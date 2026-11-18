#!/usr/bin/env python3
"""net_islands.py <board.kicad_pcb> <cu_dump.json> <net> : team A r6_merge. Lists the connected pieces of one net's copper
(filled zone polygons, tracks, vias, pads) so a KiCad 'Zone | Zone' unconnected item (which only gives zone anchors) can be found."""
import sys, json
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
from shapely.geometry import Polygon, Point, LineString
Z, T, V = load_copper(sys.argv[1]); D = json.load(open(sys.argv[2])); N = sys.argv[3]
LY = D["layers"]; it = []
for z in Z:
    if z["net"] == N and len(z["pts"]) > 2: it.append(("zone", {z["layer"]}, Polygon(z["pts"]).buffer(0)))
for t in T:
    if t["net"] == N: it.append(("track", {t["layer"]}, LineString([t["a"], t["b"]]).buffer(t["w"] / 2)))
for v in V:
    if v["net"] == N: it.append(("via", set(LY), Point(v["x"], v["y"]).buffer(0.15)))
for p in D["pads"]:
    if p["net"] == N:
        for L, sh in p["shapes"].items():
            for s in sh: it.append(("pad %s.%s" % (p["ref"], p["num"]), set(LY) if p.get("drill") else {L}, Polygon(s["ring"]).buffer(0)))
par = list(range(len(it)))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
from shapely.strtree import STRtree
tr = STRtree([g for _, _, g in it])
for i, (_, li, gi) in enumerate(it):
    for j in tr.query(gi):
        if j > i and li & it[j][1] and gi.intersects(it[j][2]): par[f(i)] = f(j)
import collections; G = collections.defaultdict(list)
for i in range(len(it)): G[f(i)].append(i)
gs = sorted(G.values(), key=lambda g: -sum(it[i][2].area for i in g))
for g in gs[1:]:
    b = [it[i][2].bounds for i in g]
    print("ISLAND %.2f mm2 bbox %.2f,%.2f..%.2f,%.2f :" % (sum(it[i][2].area for i in g), min(x[0] for x in b), min(x[1] for x in b), max(x[2] for x in b), max(x[3] for x in b)),
          ", ".join(sorted({it[i][0] + ("@" + "/".join(sorted(it[i][1])) if it[i][0] in ("zone", "track") else "") for i in g})))
print("main piece + %d islands" % (len(gs) - 1))
