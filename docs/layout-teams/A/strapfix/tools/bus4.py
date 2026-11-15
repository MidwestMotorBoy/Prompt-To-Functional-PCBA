#!/usr/bin/env python3
"""bus4.py <spec.json> <bare.json> [--net=PACK_P] [--from=In2.Cu] [--layer=In4.Cu] [--mode=copy|strip] [--w=4]
          [--join=1.5] [--prio=10] [--clip=0.6] [--box=x0,y0,x1,y1;...]
Team A strapfix copper step (after split_spec.py, before write_copper.py): a second copy of a bus net on a layer the
router never routes on (In1/In4 are the GND planes; router.py routes F, In2, In3, B only). Signal routes can cut the
soft In2 PACK_P pour into islands, but on In4 only signal VIAS pass (KiCad refill clears them), so this copper stays
joined after routing whatever the router does, and it blocks no track or via of the router at all.
  --mode=copy : the whole --from pour outline(s) of the net, as zones on --layer (priority above the GND plane)
  --mode=strip: only bands of width --w along a minimum spanning tree over the net's via groups (straight lines
                between group anchors, Kruskal), clipped to the board outline less --clip mm; one zone per polygon.
  --mode=fill: the whole board outline on --layer (use --prio=0 --soft=1 for a GND fill under hard zones).
  --box limits copy to the union of the boxes; --mode=strip+copy = the strip bands plus the copy inside --box.
Every zone added is single-outline (KiCad keeps only the first outline of a zone on re-save)."""
import sys, json, math
import numpy as np
from shapely.geometry import Polygon, LineString, Point, mapping
from shapely.ops import unary_union
a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
NET = opt.get("net", "PACK_P"); FROM = opt.get("from", "In2.Cu"); LAY = opt.get("layer", "In4.Cu"); MODE = opt.get("mode", "copy")
W = float(opt.get("w", 4)); JOIN = float(opt.get("join", 1.5)); PRIO = int(opt.get("prio", 10)); CLIP = float(opt.get("clip", 0.6))
MAXL = float(opt.get("maxlen", 40)); OUT = opt.get("out", a[0])
S = json.load(open(a[0])); D = json.load(open(a[1]))
def zpoly(p): return Polygon(p["ring"], p.get("holes", []))
board = unary_union([Polygon(o["ring"]) for o in D["outline"]]).buffer(-CLIP)
src = unary_union([zpoly(p) for z in S["zones"] if z["net"] == NET and z["layer"] == FROM for p in z["polys"]])
from shapely.geometry import box as _box
def boxes():
    bs = [_box(*[float(v) for v in b.split(",")]) for b in opt.get("box", "").split(";") if b]
    return unary_union(bs) if bs else None
if MODE == "fill":                          # the whole board on --layer (lowest priority by default; --soft=1 for GND)
    g = board
    if boxes() is not None: g = g.intersection(boxes())
elif MODE == "copy":
    g = src.intersection(board)
    if boxes() is not None: g = g.intersection(boxes())
else:
    vs = [(v["x"], v["y"]) for v in S["vias"] if v["net"] == NET] + [(p["x"], p["y"]) for p in D["pads"] if p.get("drill") and p.get("net") == NET]
    grp = list(range(len(vs)))
    def f(i):
        while grp[i] != i: grp[i] = grp[grp[i]]; i = grp[i]
        return i
    for i in range(len(vs)):
        for j in range(i + 1, len(vs)):
            if math.dist(vs[i], vs[j]) < JOIN: grp[f(i)] = f(j)
    G = {}
    for i, v in enumerate(vs): G.setdefault(f(i), []).append(v)
    A = [min(g_, key=lambda v: math.dist(v, np.mean(g_, axis=0))) for g_ in G.values()]
    comp = list(range(len(A)))
    def cf(i):
        while comp[i] != i: comp[i] = comp[comp[i]]; i = comp[i]
        return i
    lines = []
    for d, i, j in sorted((math.dist(A[i], A[j]), i, j) for i in range(len(A)) for j in range(i + 1, len(A))):
        if cf(i) != cf(j) and d <= MAXL: lines.append(LineString([A[i], A[j]])); comp[cf(i)] = cf(j)
    g = unary_union([l.buffer(W / 2, 8) for l in lines] + [Point(p).buffer(W / 2, 8) for p in A]).intersection(board)
    if MODE == "strip+copy":                # MST bands everywhere, plus the whole pour inside --box
        g = unary_union([g, src.intersection(board).intersection(boxes())])
# keep the band off other nets' hard zones on the layer (there are none on In4 by default)
oth = unary_union([zpoly(p) for z in S["zones"] if z["net"] != NET and z["layer"] == LAY and not z.get("soft") for p in z["polys"]])
if not oth.is_empty: g = g.difference(oth.buffer(0.3))
polys = [p for p in getattr(g, "geoms", [g]) if not p.is_empty and p.area > 1.0]
for p in polys:
    p = p.simplify(0.02)
    S["zones"].append(dict(net=NET, layer=LAY, priority=PRIO, soft=bool(int(opt.get("soft", 0))), kinds=["bus"], added=True,
                           polys=[dict(ring=[list(map(lambda c: round(c, 4), q)) for q in p.exterior.coords[:-1]],
                                       holes=[[list(map(lambda c: round(c, 4), q)) for q in h.coords[:-1]] for h in p.interiors])],
                           area_mm2=round(p.area, 1)))
json.dump(S, open(OUT, "w"))
print("bus4", json.dumps(dict(net=NET, layer=LAY, mode=MODE, w=W, zones=len(polys), area_mm2=round(sum(p.area for p in polys), 1))))
