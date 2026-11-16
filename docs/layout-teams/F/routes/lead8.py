import sys, json; sys.path.insert(0, 'tools')
from rip import RML
from shapely.geometry import Point
h = RML('/home/claude/runs/rt4', 'm8')
C = h.comps("3V3"); A = min(C, key=lambda c: min(g.distance(Point(81.225, 81.0745)) for gs in c.values() for g in gs))
print("pieces", len(C), "island items", sum(len(v) for v in A.values()))
B = {}
for c in C:
    if c is A: continue
    if not any(g.distance(Point(x, y)) < 0.05 for gs in c.values() for g in gs for x, y in ((79.45, 86.674), (88.2, 89.325), (89.65, 90.0))): continue
    for L, gs in c.items(): B.setdefault(L, []).extend(gs)
print("goal items", sum(len(v) for v in B.values()))
r = None
for w in (0.2, 0.15):
    r = h.route("3V3", (81.225, 81.0745), (88.2, 86.0), w=w, margin=12.0, start_geoms=A, goal_geoms=B, quiet=True)
    if r: h.anchor("3V3", r); print("free", r); break
if not r:
    r = h.rip("3V3", A, B, (81.225, 81.0745), (88.2, 86.0), margin=12.0, depth=2, tries=10); print("rip", bool(r), r)
h.save('routes/lead8.json')
