"""win_items.py <spec.json> <cu.json> x0,y0,x1,y1 [--layers=F.Cu,B.Cu]   (team B phase 2, worker A)
Lists every pad, plan track, plan via and pour piece (bounds) of a copper plan inside a window, with nets: the numbers
behind a pinlib.py look picture, for designing a table entry or a link by coordinates."""
import sys, json
from shapely.geometry import box, Polygon
A = [a for a in sys.argv[1:] if not a.startswith("--")]; O = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
S = json.load(open(A[0])); D = json.load(open(A[1])); x0, y0, x1, y1 = map(float, A[2].split(",")); B = box(x0, y0, x1, y1)
LY = O.get("layers", "F.Cu,B.Cu").split(",")
for p in D["pads"]:
    for L, rs in p["shapes"].items():
        if L not in LY: continue
        for r in rs:
            g = Polygon(r["ring"])
            if g.intersects(B): print("pad  %-6s %-4s %-6s %-28s c %.3f,%.3f  bounds %s" % (p["ref"], p["num"], L, p["net"][:28], p["x"], p["y"], tuple(round(v, 3) for v in g.bounds)))
for t in S["tracks"]:
    if t["layer"] in LY and B.intersects(box(min(t["a"][0], t["b"][0]), min(t["a"][1], t["b"][1]), max(t["a"][0], t["b"][0]) + 1e-6, max(t["a"][1], t["b"][1]) + 1e-6)):
        print("trk  %-6s %-28s %s -> %s w %.2f %s" % (t["layer"], t["net"][:28], t["a"], t["b"], t["w"], t.get("pins", "")))
for v in S["vias"]:
    if B.contains(box(v["x"], v["y"], v["x"] + 1e-6, v["y"] + 1e-6)): print("via  %-28s %.3f,%.3f %s" % (v["net"][:28], v["x"], v["y"], v.get("pins", "")))
for z in S["zones"]:
    if z["layer"] not in LY: continue
    for pr in z["polys"]:
        g = Polygon(pr["ring"], pr.get("holes", [])).buffer(0)
        if g.intersects(B): print("zone %-6s %-28s bounds %s area %.2f (in window %.2f)" % (z["layer"], z["net"][:28], tuple(round(v, 2) for v in g.bounds), g.area, g.intersection(B).area))
for k in S.get("rule_areas", []):
    print("rule area", {kk: vv for kk, vv in k.items() if kk not in ("poly", "polys", "ring")}) if any(Polygon(r["ring"] if isinstance(r, dict) else r).intersects(B) for r in (k.get("polys") or k.get("poly") or [])) else None
