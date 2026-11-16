import sys, json; sys.path.insert(0, 'tools')
from rip import RML
from shapely.geometry import Point
h = RML('/home/claude/runs/rt4', 'm5')
print("I2CC_SCL join", h.join("/USB Port 2/I2CC_SCL", quiet=False, margin=6.0))
P3 = sorted([g for g, n, k, _ in h.items["In3.Cu"] if n == "3V3" and k == "pour"], key=lambda g: -g.area)
def sh(g): g = g.buffer(-0.45); return [q for q in (g.geoms if hasattr(g, "geoms") else [g]) if q.area > 0.2]
A = {"In3.Cu": sh(P3[1])}; B = {"In3.Cu": sh(P3[0])}
h.force("/USB Port 2/I2CC_SCL", "In3.Cu", [(84.9, 85.674), (84.975, 85.9245)])
r = h.rip("3V3", A, B, (85.0, 100.0), (85.0, 108.0), w=0.2, margin=16.0, depth=2, tries=8); print("3V3 P2", bool(r), r)
h.save('routes/lead5.json')
