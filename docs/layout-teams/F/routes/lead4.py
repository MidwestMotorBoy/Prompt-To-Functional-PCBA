import sys, json; sys.path.insert(0, 'tools')
from rip import RML
from shapely.geometry import Point
h = RML('/home/claude/runs/rt4', 'm4'); A3 = None
def piece(C, x, y): return min(C, key=lambda c: min(g.distance(Point(x, y)) for gs in c.values() for g in gs))
def rest(C, A):
    B = {}
    for c in C:
        if c is A: continue
        for L, gs in c.items(): B.setdefault(L, []).extend(gs)
    return B
C = h.comps("SCL"); A = piece(C, 82.4, 84.53)
h.force("SCL", "F.Cu", [(82.4, 84.53), (82.4, 85.3), (82.42, 85.75)], w=0.15); print("via free", h.via_free("SCL", 82.42, 85.75)); h.via("SCL", 82.42, 85.75)
C = h.comps("SCL"); A = piece(C, 82.42, 85.75); print(len(C))
r = h.rip("SCL", A, rest(C, A), (82.42, 85.75), (100.1, 95.0), margin=22.0); print("SCL U501.9", bool(r), r)
P3 = sorted([g for g, n, k, _ in h.items["In3.Cu"] if n == "3V3" and k == "pour"], key=lambda g: -g.area)
print("3V3 In3 pour pieces", [(round(g.area, 1), [round(v, 1) for v in g.bounds]) for g in P3[:6]])
main = P3[0].buffer(-0.45); B = {"In3.Cu": [q for q in (main.geoms if hasattr(main, "geoms") else [main]) if q.area > 0.2]}
# 1. the Port 2 3V3 piece (via 79.45, 86.67 and the pour piece round it) to the main pour
C = h.comps("3V3"); A = piece(C, 79.45, 86.67)
p2 = [g for g in P3[1:] if g.buffer(0.01).contains(Point(79.45, 86.67)) or g.distance(Point(79.45, 86.67)) < 0.5]
print("P2 pour piece", [(round(g.area, 1), [round(v, 1) for v in g.bounds]) for g in p2])
A = dict(A); A.setdefault("In3.Cu", []); A["In3.Cu"] = A["In3.Cu"] + [q for g in p2 for q in ([g.buffer(-0.45)] if g.buffer(-0.45).geom_type == "Polygon" else list(g.buffer(-0.45).geoms)) if q.area > 0.2]
A3 = A
# 2. J301.1: the C313-Pad2 track down x 114.5 walls the pin's track in. C314.1 is fed from C313.2 instead (under C313.1),
#    the old track and its via go, and the 3V3 track runs on west to C302.1.
N = "Net-(C313-Pad2)"
print("pulled", h.pull(N, [114.2, 114.1, 115.5, 118.1], "F.Cu"), h.pull(N, [114.8, 114.1, 115.3, 114.7], "In2.Cu"))
h.force(N, "F.Cu", [(115.37, 117.96), (115.37, 118.3), (115.6, 118.525), (116.9, 118.525), (117.24, 118.2), (117.24, 117.96)], w=0.15)
print("C313 pieces", len(h.comps(N)))
r = h.try_route("3V3", (114.73, 116.67), (113.52, 117.36)); print("3V3 J301.1", bool(r), r)
if "--p2" in sys.argv:
    r = h.rip("3V3", A3, B, (79.45, 86.67), (85.0, 108.0), w=0.2, margin=14.0, depth=2, tries=8); print("3V3 P2 (2)", bool(r), r)
h.save('routes/lead4.json')
