import sys, json; sys.path.insert(0, 'tools')
from rip import RML
from shapely.geometry import Point
h = RML('/home/claude/runs/rt4', 'm7')
def hard(a, b, label, m=6.0):
    r = h.try_route("3V3", a, b)
    if r: print(label, "free", r); return r
    C = h.comps("3V3"); pc = lambda p: min(C, key=lambda c: min(g.distance(Point(p)) for gs in c.values() for g in gs))
    A, B = pc(a), pc(b)
    if A is B: print(label, "same piece already"); return None
    r = h.rip("3V3", A, B, a, b, margin=m, depth=2); print(label, "rip", bool(r), r); return r
for a in ((79.0, 80.025), (81.225, 81.0745)):
    if hard(a, (79.45, 86.674), "U501.38 island -> via 79.45/86.67 from %s" % (a,)): break
hard((84.8, 107.97), (88.025, 117.0745), "south end -> via 88.03/117.07", m=8.0)
h.save('routes/lead7.json')
