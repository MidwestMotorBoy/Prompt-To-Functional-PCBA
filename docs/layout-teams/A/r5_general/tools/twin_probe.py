import json, sys, math
from shapely.geometry import Polygon
from shapely.ops import unary_union
def load(f):
    d = json.load(open(f)); fps = {x["ref"]: x for x in d["fps"]}; pads = {}
    for p in d["pads"]:
        for L, sh in p["shapes"].items():
            for s in sh: pads.setdefault(p["ref"], []).append(Polygon(s["ring"]))
    return fps, {r: unary_union(v) for r, v in pads.items()}
def nb(fps, geo, ref, D):
    g = geo[ref].buffer(D); a = fps[ref]
    return [(fps[r]["fp"], round(fps[r]["rot"] % 360), fps[r]["layer"], fps[r]["x"] - a["x"], fps[r]["y"] - a["y"], r) for r in geo if r != ref and r in fps and geo[r].intersects(g)]
def twin(fps, geo, A, B, D=3.0, tol=0.15):
    if (fps[A]["fp"], round(fps[A]["rot"] % 360), fps[A]["layer"]) != (fps[B]["fp"], round(fps[B]["rot"] % 360), fps[B]["layer"]): return False, "pose"
    na, nbb = nb(fps, geo, A, D), nb(fps, geo, B, D); miss = []
    for X, Y, lab in ((na, nbb, "A"), (nbb, na, "B")):
        for f, r, l, dx, dy, ref in X:
            if not any(f == f2 and r == r2 and l == l2 and math.hypot(dx - dx2, dy - dy2) <= tol for f2, r2, l2, dx2, dy2, _ in Y): miss.append(lab + ":" + ref)
    return not miss, miss
fps, geo = load(sys.argv[1])
for A, B in [x.split(",") for x in sys.argv[2:]]:
    print(A, B, twin(fps, geo, A, B))
