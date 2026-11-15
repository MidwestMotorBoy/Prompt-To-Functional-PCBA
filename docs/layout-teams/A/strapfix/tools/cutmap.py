#!/usr/bin/env python3
"""cutmap.py <cu.kicad_pcb (before routing, filled)> <routed.kicad_pcb> <cu.json dump> <out_prefix> [net=PACK_P] [layer=In2.Cu]
Team A strapfix: where routing cut a power pour. Per power-zone net and layer: filled area before/after, number of
filled pieces before/after, and the foreign tracks and vias of the routed board that lie in the pour as it was
before routing (the cutters). Writes <out_prefix>.json and <out_prefix>_<layer>.png (before pour light, after
pour dark, cutting tracks red, cutting vias blue, pieces numbered)."""
import sys, os, json
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from PIL import Image, ImageDraw
a = sys.argv[1:]; cu, rt, dump, out = a[:4]; NET = a[4] if len(a) > 4 else "PACK_P"; LAY = a[5] if len(a) > 5 else "In2.Cu"
Zb, Tb, Vb = load_copper(cu); Za, Ta, Va = load_copper(rt)
def U(Z, n, L): return unary_union([Polygon(z["pts"]).buffer(0) for z in Z if z["net"] == n and z["layer"] == L and len(z["pts"]) > 2])
rep = {}
for n, L in sorted({(z["net"], z["layer"]) for z in Zb}):
    b, af = U(Zb, n, L), U(Za, n, L)
    pb = len(getattr(b, "geoms", [b])) if not b.is_empty else 0; pa = len(getattr(af, "geoms", [af])) if not af.is_empty else 0
    rep[f"{n}@{L}"] = dict(area_before=round(b.area, 1), area_after=round(af.area, 1), pieces_before=pb, pieces_after=pa)
b = U(Zb, NET, LAY); af = U(Za, NET, LAY)
newT = [t for t in Ta if t["layer"] == LAY and t["net"] != NET and LineString([t["a"], t["b"]]).buffer(t["w"] / 2).intersects(b)]
newV = [v for v in Va if v["net"] != NET and Point(v["x"], v["y"]).intersects(b)]
oldV = {(round(v["x"], 3), round(v["y"], 3)) for v in Vb}
newV = [v for v in newV if (round(v["x"], 3), round(v["y"], 3)) not in oldV]
cut = {}
for t in newT: cut.setdefault(t["net"], [0, 0.0])[0] += 1; cut[t["net"]][1] += LineString([t["a"], t["b"]]).intersection(b).length
rep["cutters"] = {k: dict(segments=v[0], mm_in_pour=round(v[1], 1)) for k, v in sorted(cut.items(), key=lambda kv: -kv[1][1])}
vc = {}
for v in newV: vc[v["net"]] = vc.get(v["net"], 0) + 1
rep["cut_vias"] = vc
pcs = list(getattr(af, "geoms", [af]))
rep["pieces_after"] = [dict(area=round(p.area, 1), centroid=[round(p.centroid.x, 1), round(p.centroid.y, 1)]) for p in sorted(pcs, key=lambda p: -p.area)]
json.dump(rep, open(out + ".json", "w"), indent=1)
D = json.load(open(dump)); xs = [x for o in D["outline"] for x, _ in o["ring"]]; ys = [y for o in D["outline"] for _, y in o["ring"]]
x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys); S = 12
im = Image.new("RGB", (int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1), (250, 250, 248)); d = ImageDraw.Draw(im, "RGBA")
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
for o in D["outline"]: d.line([P(*q) for q in o["ring"] + o["ring"][:1]], fill=(0, 0, 0), width=2)
def poly(g, fill):
    for p in getattr(g, "geoms", [g]):
        if p.is_empty: continue
        d.polygon([P(*q) for q in p.exterior.coords], fill=fill)
        for h in p.interiors: d.polygon([P(*q) for q in h.coords], fill=(250, 250, 248, 255))
poly(b, (255, 200, 120, 255)); poly(af, (200, 120, 20, 200))
for t in Ta:
    if t["layer"] == LAY and t["net"] == NET: d.line([P(*t["a"]), P(*t["b"])], fill=(120, 60, 0, 255), width=max(1, int(t["w"] * S)))
for t in Ta:
    if t["layer"] == LAY and t["net"] != NET: d.line([P(*t["a"]), P(*t["b"])], fill=(220, 0, 0, 255) if t in newT else (150, 150, 150, 160), width=max(1, int(t["w"] * S)))
for v in Va:
    c = P(v["x"], v["y"]); r = v["size"] / 2 * S
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(0, 0, 220, 255) if v in newV else (90, 90, 90, 120), width=2 if v in newV else 1)
for p in D["pads"]:
    for r_ in p["shapes"].get(LAY, []): d.polygon([P(*q) for q in r_["ring"]], outline=(60, 60, 60, 255))
for i, p in enumerate(sorted(pcs, key=lambda p: -p.area)):
    c = p.representative_point(); d.text(P(c.x, c.y), str(i), fill=(0, 0, 0, 255))
im.save(f"{out}_{LAY.split('.')[0]}.png")
print(json.dumps({k: v for k, v in rep.items() if k in ("cutters", "cut_vias")})[:3000]); print("pieces", len(pcs), rep["pieces_after"][:12])
