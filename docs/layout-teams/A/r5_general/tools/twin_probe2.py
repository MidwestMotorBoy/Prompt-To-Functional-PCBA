import sys, json, math
sys.path.insert(0,'/home/claude/repo/tools/copper')
from roles import Design
from shapely.ops import unary_union
from shapely.geometry import Polygon
D = Design(sys.argv[1], '/home/claude/repo/tools/floorplan/example/monolith/constraints.json')
PINS = ['1','17','18','19','28','29','30','37']; R = float(sys.argv[2]) if len(sys.argv) > 2 else 3
geo = {r: unary_union([D.pad_poly(p, L) for p in ps for L in p["shapes"] if not p.get("drill")] or [Polygon()]) for r, ps in D.by_ref.items()}
def pose(r): f = D.fp[r]; return (f["fp"], round(f["rot"] % 360), f["layer"])
def hood(r):
    nets = {p["net"] for p in D.by_ref[r] if p["num"] in PINS}; a = D.fp[r]
    g = unary_union([D.pad_poly(p, L) for p in D.by_ref[r] if p["num"] in PINS for L in p["shapes"]]).buffer(R)
    return [pose(q) + (round(D.fp[q]["x"] - a["x"],2), round(D.fp[q]["y"] - a["y"],2), q) for q, ps in D.by_ref.items() if q != r and any(x["net"] in nets for x in ps) and geo[q].intersects(g)]
def same(X, Y): return all(any(x[:3] == y[:3] and math.hypot(x[3] - y[3], x[4] - y[4]) <= 0.15 for y in Y) for x in X)
a, b = hood('U501'), hood('U401')
print(sys.argv[1], R, len(a), len(b), same(a,b) and same(b,a), sorted(x[5] for x in a), sorted(x[5] for x in b))
