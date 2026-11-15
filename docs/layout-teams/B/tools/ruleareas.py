"""ruleareas.py <spec.json> <bare.json or cu.json> <out spec.json> [options]
KiCad rule areas in the copper plan (spec["rule_areas"], written by tools/write_copper_split.py), so that the full
trial route keeps signals out of chosen copper. The router obeys rule areas (tools/score/router.py mark_ko): a
"no tracks" area closes its layers to tracks AND vias, a "no vias" area only to vias. Pours stay allowed.

Three kinds (each optional, any may be given):
  --protect=3V3:F.Cu,PACK_P:F.Cu  every planned pour of that net on that layer: no tracks. For SOFT nets (the score
                 routes with --softnets=GND,PACK_P,3V3): the router may cut their pours, and its last refill then
                 leaves pads and stubs on pieces (r4 baseline route: J301.1 cut off the 3V3 F.Cu pour at C303, so
                 3V3 at L201 reads open on the routed board although the In3 3V3 straps hold).
  --hot          on F.Cu, over the hot loops' GND return pours (the planner's priority-25 'return join' zones):
                 no tracks (so no signal track or via cuts the loop's return copper; on r3/r4 signal vias there raised
                 Port 1 and Port 2 HL_IN by 0.01 nH each). --hot_mode=vias: no vias only (tracks may still cross). --hot_supply adds the soft supply pours of the loops
                 (PACK_P F.Cu zones that hold a hot-loop capacitor pad: HL_3V3, HL_5V).
  --corridor="In2.Cu:2.5:x1,y1/x2,y2/..."  a no-signal corridor of that width along that polyline on that layer
                 (several separated by ';'). --corridor_vias=1 makes it no-vias only instead of no-tracks.
Every area is cut back from:
  - every track and via of the plan on its layers (KiCad DRC flags ANY net's track inside a "no tracks" area,
    the plan's straps and trunks included), by --gap mm;
  - every pad of another net on its layers by --esc mm (the pad keeps its escape), and every through-hole pad;
  - pieces under --min_area mm2 are dropped.
Options: --gap=0.05 --esc=0.5 --min_area=0.3 --png=<file> --win=x0,y0,x1,y1 (picture window)
Prints each area's layer, kind and area; the plan gets spec["rule_areas"] (appended) and a record in
spec["rule_area_report"]."""
import sys, json
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 3: print(__doc__); sys.exit(2)
GAP, ESC, MINA = float(O.get("gap", 0.05)), float(O.get("esc", 0.5)), float(O.get("min_area", 0.3))
S = json.load(open(A[0])); D = json.load(open(A[1]))
def poly(r): return Polygon(r["ring"], r.get("holes", [])).buffer(0)
def parts(g): return [g] if isinstance(g, Polygon) else [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon)]
def ring(q): return dict(ring=[[round(x, 4), round(y, 4)] for x, y in q.exterior.coords[:-1]],
                         holes=[[[round(x, 4), round(y, 4)] for x, y in h.coords[:-1]] for h in q.interiors])

def cutback(g, layer, net_ok=()):
    """g minus the plan's tracks and vias on the layer, other nets' pads, through-hole pads"""
    cut = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + GAP, 8) for t in S["tracks"] if t["layer"] == layer]
    cut += [Point(v["x"], v["y"]).buffer(v["size"] / 2 + GAP, 12) for v in S["vias"]]
    for p in D["pads"]:
        if p.get("drill", 0) > 0: cut += [poly(r).buffer(GAP) for r in p["shapes"].get(layer, [])] or [Point(p["x"], p["y"]).buffer(p["drill"] / 2 + GAP)]
        elif layer in p["shapes"] and p["net"] not in net_ok: cut += [poly(r).buffer(ESC) for r in p["shapes"][layer]]
    return g.difference(unary_union(cut)) if cut else g

areas, rep = [], []
if "hot" in O:
    caps = set()
    C = json.load(open(O.get("constraints", sys.path[0] + "/../../../../tools/floorplan/example/monolith/constraints.json")))
    for h in C["hot_loops"].values(): caps |= set(h["caps"])
    capg = unary_union([poly(r) for p in D["pads"] if p["ref"] in caps for r in p["shapes"].get("F.Cu", [])])
    sel = []
    for z in S["zones"]:
        if z["layer"] != "F.Cu": continue
        if z["net"] == "GND" and "return join" in z["kinds"]: sel += [("GND", poly(p)) for p in z["polys"]]
        elif "hot_supply" in O and z["net"] == "PACK_P":
            sel += [("PACK_P", poly(p)) for p in z["polys"] if poly(p).intersects(capg)]
    for net, g in sel:
        g = cutback(g, "F.Cu", net_ok=(net,))
        for q in parts(g.buffer(0)):
            if q.area >= MINA:
                hv = O.get("hot_mode", "tracks") == "vias"
                areas.append(dict(name=f"ra_hot_{net}", layers=["F.Cu"], polys=[ring(q)], no_tracks=not hv, no_vias=hv))
                rep.append(dict(kind=f"hot {net}", layer="F.Cu", area_mm2=round(q.area, 2), at=[round(q.centroid.x, 2), round(q.centroid.y, 2)]))
for pr in [c for c in O.get("protect", "").split(",") if c]:
    net, L = pr.rsplit(":", 1)
    for z in S["zones"]:
        if z["net"] != net or z["layer"] != L: continue
        for p in z["polys"]:
            for q in parts(cutback(poly(p), L, net_ok=(net,)).buffer(0)):
                if q.area >= MINA:
                    areas.append(dict(name=f"ra_protect_{net}", layers=[L], polys=[ring(q)], no_tracks=True, no_vias=False))
                    rep.append(dict(kind=f"protect {net}", layer=L, area_mm2=round(q.area, 2), at=[round(q.centroid.x, 2), round(q.centroid.y, 2)]))
for c in [c for c in O.get("corridor", "").split(";") if c]:
    L, w, pts = c.split(":"); w = float(w); pts = [tuple(map(float, p.split(","))) for p in pts.split("/")]
    g = LineString(pts).buffer(w / 2, 16, cap_style=2) if len(pts) > 1 else Point(pts[0]).buffer(w / 2)
    own = {z["net"] for z in S["zones"] if z["layer"] == L and z.get("soft")}
    g = cutback(g, L, net_ok=own)
    nv = O.get("corridor_vias") == "1"
    for q in parts(g.buffer(0)):
        if q.area >= MINA:
            areas.append(dict(name="ra_corridor", layers=[L], polys=[ring(q)], no_tracks=not nv, no_vias=nv))
            rep.append(dict(kind="corridor " + ("no vias" if nv else "no tracks"), layer=L, area_mm2=round(q.area, 2), at=[round(q.centroid.x, 2), round(q.centroid.y, 2)]))
S["rule_areas"] = S.get("rule_areas", []) + areas
S.setdefault("rule_area_report", []).extend(rep)
json.dump(S, open(A[2], "w"), indent=1)
tot = sum(r["area_mm2"] for r in rep)
for r in rep: print("  ", r["kind"], r["layer"], r["area_mm2"], "mm2 at", r["at"])
print(f"rule areas: {len(areas)} added ({', '.join(sorted({r['kind'] for r in rep}))}), {tot:.1f} mm2")

if "png" in O:
    x0, y0, x1, y1 = map(float, O.get("win", "78,60,124,140").split(",")); k = 20
    im = Image.new("RGB", (int((x1 - x0) * k), int((y1 - y0) * k)), "white"); dr = ImageDraw.Draw(im, "RGBA")
    P = lambda x, y: ((x - x0) * k, (y - y0) * k)
    for z in S["zones"]:
        if z["layer"] == "F.Cu":
            for p in z["polys"]: dr.polygon([P(*c) for c in p["ring"]], fill=(90, 90, 90, 60) if z["net"] == "GND" else (200, 120, 200, 60))
    for p in D["pads"]:
        for r in p["shapes"].get("F.Cu", []): dr.polygon([P(*c) for c in r["ring"]], outline=(0, 0, 0, 255))
    for a in areas:
        for p in a["polys"]:
            dr.polygon([P(*c) for c in p["ring"]], fill=(230, 60, 60, 110), outline=(200, 0, 0, 255))
            for h in p["holes"]: dr.polygon([P(*c) for c in h], fill=(255, 255, 255, 200))
    im.save(O["png"])
