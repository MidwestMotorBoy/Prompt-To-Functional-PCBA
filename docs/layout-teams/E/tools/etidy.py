"""etidy.py <base.e.json> <routed.e.json> <routes.json> <out.routes.json>
Trims what rip-up leaves behind: a routed track whose end touches no other copper of its net is cut back to the last
point where something does (or dropped if nothing does), a track up to 0.3 mm long that touches one
thing only (it lies inside a via) is dropped, and a routed via that joins fewer than two layers is dropped.
Repeats until nothing changes. Pads, hand copper and the planner's copper come from the base dump, the pours as KiCad
filled them from the routed dump; only items of routes.json are changed. Check the result with eapply.sh (DRC)."""
import sys, json, math
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

B = json.load(open(sys.argv[1])); F = json.load(open(sys.argv[2])); R = json.load(open(sys.argv[3]))
LAY = B["layers"]; NL = len(LAY)
SKIP = {"GND", "PACK_P", "3V3"}             # plane nets: their route ends land in pours, and their fills are too big to test
nets = {r["net"] for r in R["routes"]} - SKIP
stat = {}                                    # (net, layer index) -> [geometry]
def add(net, L, g):
    if net in nets and not g.is_empty: stat.setdefault((net, L), []).append(g)
def poly(p):
    g = Polygon(p["ring"], p.get("holes", []))
    return g if g.is_valid else g.buffer(0)
for p in B["pads"]:
    for ln, shapes in p["shapes"].items():
        if ln in LAY:
            for s in shapes: add(p["net"], LAY.index(ln), poly(s))
for t in B["tracks"]:
    if t["layer"] in LAY: add(t["net"], LAY.index(t["layer"]), LineString([t["a"], t["b"]]).buffer(t["w"] / 2))
for v in B["vias"]:
    for L in range(NL): add(v["net"], L, Point(v["x"], v["y"]).buffer(v["size"] / 2))
for z in F["zones"]:
    if z["layer"] in LAY:
        for s in z["fill"]: add(z["net"], LAY.index(z["layer"]), poly(s))
TR = {k: STRtree(v) for k, v in stat.items()}       # no union: the ground pours are far too big for one

items = []                                   # mutable routed items: dict(net, kind, L, a, b, w, route, idx, alive)
for ri, r in enumerate(R["routes"]):
    if r["net"] in SKIP: continue
    for it in r["items"]:
        if it[0] == "T": items.append(dict(net=r["net"], kind="T", L=it[1], a=(it[2], it[3]), b=(it[4], it[5]), w=it[6], it=it, alive=True, fixed=bool(r.get("meta", {}).get("tap"))))
        else: items.append(dict(net=r["net"], kind="V", x=it[2], y=it[3], r=it[4] / 2, it=it, alive=True, fixed=bool(r.get("meta", {}).get("tap"))))
by_net = {}
for i in items: by_net.setdefault(i["net"], []).append(i)

def copper(i, L):
    if i["kind"] == "T" and (i["L"] != L or i["a"] == i["b"]): return None
    if "g" not in i:
        i["g"] = Point(i["x"], i["y"]).buffer(i["r"]) if i["kind"] == "V" else LineString([i["a"], i["b"]]).buffer(i["w"] / 2)
    return i["g"]
def touches(net, L, pt, me):
    P = Point(pt).buffer(max(me.get("w", 0.2) / 2 - 0.01, 0.02), 4)      # the end cap: the router ends a track on a pad's edge
    if (net, L) in TR and len(TR[(net, L)].query(P, predicate="intersects")): return True
    for o in by_net[net]:
        if o is me or not o["alive"]: continue
        g = copper(o, L)
        if g is not None and g.intersects(P): return True
    return False

def touch_set(net, L, pt, me):
    P = Point(pt).buffer(max(me.get("w", 0.2) / 2 - 0.01, 0.02), 4); out = set()
    if (net, L) in TR: out |= {("s", int(j)) for j in TR[(net, L)].query(P, predicate="intersects")}
    for o in by_net[net]:
        if o is me or not o["alive"]: continue
        g = copper(o, L)
        if g is not None and g.intersects(P): out.add(("d", id(o)))
    return out

cut = dropped = vdropped = 0
changed = True
while changed:
    changed = False
    for i in items:
        if not i["alive"] or i["fixed"]: continue
        if i["kind"] == "V":
            n = sum(1 for L in range(NL) if touches(i["net"], L, (i["x"], i["y"]), i))
            if n < 2: i["alive"] = False; vdropped += 1; changed = True
            continue
        if i["a"] == i["b"]: i["alive"] = False; continue
        ea = i.get("fa") or touches(i["net"], i["L"], i["a"], i); eb = i.get("fb") or touches(i["net"], i["L"], i["b"], i)
        if ea and eb:
            if math.dist(i["a"], i["b"]) <= 0.3:            # a short track that touches one thing only (it lies inside a via)
                if len(touch_set(i["net"], i["L"], i["a"], i) | touch_set(i["net"], i["L"], i["b"], i)) <= 1:
                    i["alive"] = False; dropped += 1; changed = True
            continue
        line = LineString([i["a"], i["b"]]); ln = line.length
        k = (i["net"], i["L"])
        oth = [stat[k][j] for j in TR[k].query(line, predicate="intersects")] if k in TR else []
        oth += [g for g in (copper(o, i["L"]) for o in by_net[i["net"]] if o is not i and o["alive"]) if g is not None]
        hit = line.intersection(unary_union(oth)) if oth else None
        if hit is None or hit.is_empty: i["alive"] = False; dropped += 1; changed = True; continue
        ss = []
        for g in (hit.geoms if hasattr(hit, "geoms") else [hit]):
            ss += [line.project(Point(c)) for c in g.coords]
        s0, s1 = (0.0 if ea else min(ss)), (ln if eb else max(ss))
        if s1 - s0 < 0.02: i["alive"] = False; dropped += 1; changed = True; continue
        if s0 > 1e-6 or s1 < ln - 1e-6:
            pa, pb = line.interpolate(s0), line.interpolate(s1)
            i["a"], i["b"] = (round(pa.x, 4), round(pa.y, 4)), (round(pb.x, 4), round(pb.y, 4)); i.pop("g", None); cut += 1; changed = True
        i["fa"] = i["fb"] = True              # a cut end lies on the edge of what it touches: settled
for i in items:
    if i["kind"] == "T": i["it"][2:6] = [i["a"][0], i["a"][1], i["b"][0], i["b"][1]]
live = {id(i["it"]) for i in items if i["alive"]}
for r in R["routes"]:
    if r["net"] not in SKIP: r["items"] = [it for it in r["items"] if id(it) in live]
json.dump(R, open(sys.argv[4], "w"))
print("etidy: %d track ends cut back, %d tracks dropped, %d vias dropped" % (cut, dropped, vdropped))
