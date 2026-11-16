#!/usr/bin/env python3
# r5_merge copy of r4_general/tools/spec_diff.py: invalid zone rings are repaired with buffer(0) for the area check (the ring check is unchanged)
"""spec_diff.py <a/spec.json> <b/spec.json> [--tol=0.01] [--quiet]
Compares two copper specs (the planner output that write_copper.py puts into the board), per net and layer:
zones (count, area, bounding box, priority, soft, kinds), tracks (count, length, set of segments) and vias (count,
set of positions). Then a geometric check per net and layer: area of the symmetric difference of the zone unions.
Prints one line per (net, layer) that differs and a verdict line:
  IDENTICAL            every zone ring, track and via is the same (after rounding to 1e-4 mm)
  GEOMETRIC-IDENTICAL  same copper (sym. difference < tol mm2 per net/layer, same tracks and vias), rings may be
                       written in another order or start point
  DIFFERENT            anything else (exit code 1)"""
import sys, json, math
from collections import defaultdict, Counter
from shapely.geometry import Polygon
from shapely.ops import unary_union

a = [x for x in sys.argv[1:] if not x.startswith("--")]
opt = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
TOL = float(opt.get("tol", 0.01)); QUIET = "quiet" in opt
A, B = (json.load(open(f)) for f in a[:2])


def zp(p):
    g = Polygon(p["ring"], p.get("holes") or [])
    return g if g.is_valid else g.buffer(0)


def r4(v): return round(float(v), 4)


def zones(S):
    out = defaultdict(list)
    for z in S["zones"]:
        for p in z["polys"]:
            out[(z["net"], z["layer"])].append(dict(prio=z["priority"], soft=bool(z["soft"]), kinds=tuple(sorted(z.get("kinds", []))), poly=zp(p),
                                                    ring=tuple(tuple(map(r4, c)) for c in p["ring"])))
    return out


def tracks(S):
    out = defaultdict(Counter)
    for t in S["tracks"]:
        e = tuple(sorted([tuple(map(r4, t["a"])), tuple(map(r4, t["b"]))]))
        out[(t["net"], t["layer"])][(e, r4(t["w"]))] += 1
    return out


def vias(S):
    out = defaultdict(Counter)
    for v in S["vias"]: out[v["net"]][(r4(v["x"]), r4(v["y"]), r4(v["size"]), r4(v["drill"]))] += 1
    return out


za, zb = zones(A), zones(B); ta, tb = tracks(A), tracks(B); va, vb = vias(A), vias(B)
exact = True; geo = True; lines = []
for k in sorted(set(za) | set(zb)):
    A_, B_ = za.get(k, []), zb.get(k, [])
    ga = unary_union([z["poly"] for z in A_]) if A_ else Polygon(); gb = unary_union([z["poly"] for z in B_]) if B_ else Polygon()
    sd = ga.symmetric_difference(gb).area
    ra = sorted((z["ring"], z["prio"], z["soft"], z["kinds"]) for z in A_); rb = sorted((z["ring"], z["prio"], z["soft"], z["kinds"]) for z in B_)
    meta_a = sorted((z["prio"], z["soft"], z["kinds"]) for z in A_); meta_b = sorted((z["prio"], z["soft"], z["kinds"]) for z in B_)
    if ra != rb: exact = False
    if sd >= TOL or meta_a != meta_b: geo = False
    if ra != rb or sd >= TOL:
        bb = lambda g: [round(v, 2) for v in g.bounds] if not g.is_empty else []
        lines.append(f"ZONE {k[0]} {k[1]}: n {len(A_)} vs {len(B_)}, area {ga.area:.2f} vs {gb.area:.2f} mm2, sym.diff {sd:.3f} mm2, bbox {bb(ga)} vs {bb(gb)}"
                     + ("" if meta_a == meta_b else f", prio/soft/kinds {meta_a} vs {meta_b}"))
for k in sorted(set(ta) | set(tb)):
    if ta.get(k, Counter()) != tb.get(k, Counter()):
        exact = geo = False
        la = sum(math.dist(*e) * c for (e, w), c in ta.get(k, Counter()).items()); lb = sum(math.dist(*e) * c for (e, w), c in tb.get(k, Counter()).items())
        only_a = sorted((ta.get(k, Counter()) - tb.get(k, Counter())).elements())[:4]; only_b = sorted((tb.get(k, Counter()) - ta.get(k, Counter())).elements())[:4]
        lines.append(f"TRACK {k[0]} {k[1]}: n {sum(ta.get(k, Counter()).values())} vs {sum(tb.get(k, Counter()).values())}, length {la:.2f} vs {lb:.2f} mm; only in a {only_a}; only in b {only_b}")
for n in sorted(set(va) | set(vb)):
    if va.get(n, Counter()) != vb.get(n, Counter()):
        exact = geo = False
        lines.append(f"VIA {n}: n {sum(va.get(n, Counter()).values())} vs {sum(vb.get(n, Counter()).values())}; only in a {sorted((va.get(n, Counter()) - vb.get(n, Counter())).elements())[:4]}; only in b {sorted((vb.get(n, Counter()) - va.get(n, Counter())).elements())[:4]}")
tot = lambda Z, T, V: (sum(len(v) for v in Z.values()), sum(sum(v.values()) for v in T.values()), sum(sum(v.values()) for v in V.values()))
print(f"a: {a[0]}: zones/tracks/vias {tot(za, ta, va)}; b: {a[1]}: {tot(zb, tb, vb)}")
if not QUIET or not geo:
    for l in lines: print(l)
v = "IDENTICAL" if exact else "GEOMETRIC-IDENTICAL" if geo else "DIFFERENT"
print(f"{v}: {len(lines)} differing (net, layer) entries")
sys.exit(0 if geo else 1)
