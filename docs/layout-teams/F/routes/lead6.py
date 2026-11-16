import sys, json; sys.path.insert(0, 'tools')
from rip import RML
from shapely.geometry import Point
h = RML('/home/claude/runs/rt4', 'm6')
P3 = sorted([g for g, n, k, _ in h.items["In3.Cu"] if n == "3V3" and k == "pour"], key=lambda g: -g.area)
def sh(g, d=0.5): g = g.buffer(-d); return [q for q in (g.geoms if hasattr(g, "geoms") else [g]) if q.area > 0.2]
def ext(a, tgt, label, m=6.0):
    A = {"In3.Cu": [Point(a).buffer(0.08)]}; B = {"In3.Cu": sh(tgt)}
    for w in (0.2, 0.15):
        r = h.route("3V3", a, a, w=w, margin=m, start_geoms=A, goal_geoms=B, quiet=True)
        if r: print(label, "free", r); return r
    r = h.rip("3V3", A, B, a, a, margin=m, depth=2); print(label, "rip", bool(r), r); return r
ext((84.8, 107.924), P3[1], "south end -> main pour")
ext((83.8, 83.14), P3[0], "U501.38 scrap -> north pour")
h.save('routes/lead6.json')
