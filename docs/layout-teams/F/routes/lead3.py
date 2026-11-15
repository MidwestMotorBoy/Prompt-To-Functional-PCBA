import sys, json; sys.path.insert(0, 'tools')
from rip import RML
h = RML('/home/claude/runs/rt4', 'm2')
print("before", {n: len(h.comps(n)) for n in ("SCL", "SDA", "EN_5V1")})
print("pulled", h.pull("SDA", [103.0, 119.0, 112.0, 131.0]), h.pull("EN_5V1", [99.0, 111.0, 112.0, 123.0]))
print("after pull", {n: len(h.comps(n)) for n in ("SCL", "SDA", "EN_5V1")})
P = json.load(open('routes/p1top.json'))
full = [r for r in P["routes"] if r["net"] == "SCL" and max(p[2] for p in r["path"]) > 101.7]
tail = full[0]["path"]; i = [k for k, p in enumerate(tail) if p[2] > 101.6][0]
h.lay("SCL", tail[i - 1:], 0.15)
for r in full[1:]: h.lay("SCL", r["path"], 0.15)
h.via("SCL", 107.65, 115.375)
print("SCL pieces", len(h.comps("SCL")))
from shapely.geometry import Point
for n in ("EN_5V1", "SDA"):
    ok = h.join(n, quiet=False, margin=14.0); print(n, "join", ok, len(h.comps(n)))
def ripjoin(n, prot):
    for _ in range(6):
        if h.join(n, margin=14.0): return True
        C = h.comps(n); C.sort(key=lambda c: sum(g.area for gs in c.values() for g in gs)); A = C[0]; B = {}
        for c in C[1:]:
            for L, gs in c.items(): B.setdefault(L, []).extend(gs)
        pa = list(A.values())[0][0].representative_point(); pb = min((g for gs in B.values() for g in gs), key=lambda g: g.distance(pa)).representative_point()
        if not h.rip(n, A, B, (pa.x, pa.y), (pb.x, pb.y), margin=10.0, protect=prot): return False
    return len(h.comps(n)) == 1
for n in ("EN_5V1", "SDA"): print(n, "ripjoin", ripjoin(n, ("SCL", "SDA", "EN_5V1")), len(h.comps(n)))
S = json.load(open('routes/south.json'))
for r in S["routes"]:
    if r["net"] == "EN_5V1" and all(p[0] == "F.Cu" and p[1] < 103 for p in r["path"]): h.lay("EN_5V1", r["path"], r["w"]); print("re-laid", r["path"][0], r["path"][-1])
for n in ("EN_5V1",): print(n, [[(L, round(g.centroid.x,2), round(g.centroid.y,2)) for L, gs in c.items() for g in gs][:4] for c in h.comps(n)])
h.save('routes/lead3.json')
