"""links.py <spec.json> <bare.json or cu.json> <out spec.json> --link="NET|LAYER|W|x1,y1/x2,y2/..." [--link=...] [--via="NET|x,y"]
Explicit power links in the copper plan: short hard tracks (and through vias) that join a pour piece or a pad the
planner left apart, given by coordinates, each checked exactly (shapely) before it is written.

Why: on the r4 copper board KiCad lists power items in pieces that no router edge joins (the router does not route
a pour to itself, and sealed Kelvin pads are never a route end), e.g. Port 2 BAT_SNS_P: the pour's neck to R528.1
(Kelvin tap) is thinner than the fill's minimum, so R528.1 sits on its own island. A link is the planner's copper,
not a route: it goes in before routing and the router treats it as hard.

Each --link is NET|LAYER|width mm|points (write a space in a net name as '~', so the option survives final_route.sh's
--filters string: --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.0) (x,y separated by '/'), each --via is NET|x,y (0.45/0.3 mm through via).
Checks: every link track and via keeps --clr mm (default 0.2; 0.25 to small-signal tracks is the board rule for
HighCurrent nets, use --clr=0.25 for those) from every other net's pad on its layer (and through-hole pads), the
plan's tracks and vias of other nets on the layer, and 0.25 mm from the board edge (other nets' planned pours are
refilled round the link by KiCad, so they are not obstacles: the area a link takes from them is printed; --zones_hard
makes them obstacles); a via is checked on F.Cu,
In2.Cu, In3.Cu and B.Cu against pads, tracks and non-GND pours of other nets, and 0.2 mm hole to hole.
Prints each link with its least clearance; exit 1 (nothing written) on any fault, so a bad link never reaches a board.
Options: --clr=0.2 --png=<file> --win=x0,y0,x1,y1"""
import sys, json, math
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

A = [a for a in sys.argv[1:] if not a.startswith("--")]
OPTS = [a[2:].replace("~", " ").split("=", 1) for a in sys.argv[1:] if a.startswith("--")]   # '~' = space (net names in a --filters string)
O = {k: v for k, v in OPTS}
if len(A) < 3: print(__doc__); sys.exit(2)
CLR = float(O.get("clr", 0.2))
S = json.load(open(A[0])); D = json.load(open(A[1]))
def poly(r): return Polygon(r["ring"], r.get("holes", [])).buffer(0)
BOARD = unary_union([poly(o) for o in D["outline"]])
def obstacles(net, layer, gnd_ok=False):
    o = []
    for p in D["pads"]:
        if p["net"] == net and p["net"]: continue
        if layer in p["shapes"] or p.get("drill", 0) > 0: o += [poly(r) for r in p["shapes"].get(layer, [])]
        if p.get("drill", 0) > 0: o.append(Point(p["x"], p["y"]).buffer(p["drill"] / 2 + 0.1))
    o += [LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 8) for t in S["tracks"] if t["layer"] == layer and t["net"] != net]
    o += [Point(v["x"], v["y"]).buffer(v["size"] / 2, 16) for v in S["vias"] if v["net"] != net]
    if "zones_hard" in O:
        o += [poly(p) for z in S["zones"] if z["layer"] == layer and z["net"] != net and not (gnd_ok and z["net"] == "GND") for p in z["polys"]]
    return unary_union(o)
def zone_overlap(net, layer, g):                    # area of other nets' planned pours the link takes (their fill clears it)
    return sum(g.buffer(CLR).intersection(poly(p)).area for z in S["zones"] if z["layer"] == layer and z["net"] != net for p in z["polys"])
new_t, new_v, faults = [], [], []
for k, v in OPTS:
    if k == "link":
        net, L, w, pts = v.split("|"); w = float(w); pts = [tuple(map(float, p.split(","))) for p in pts.split("/")]
        ob = obstacles(net, L)
        for a, b in zip(pts, pts[1:]):
            g = LineString([a, b]).buffer(w / 2, 16); d = g.distance(ob); de = BOARD.exterior.distance(g) if BOARD.contains(g) else -1
            print(f"  link {net} {L} {w} mm {a} -> {b}: clearance {d:.3f} mm, edge {de:.2f} mm, takes {zone_overlap(net, L, g):.2f} mm2 of other nets' pours")
            if d < CLR - 0.002 or de < 0.25: faults.append(("link", net, L, a, b, round(d, 3)))
            new_t.append(dict(net=net, layer=L, a=list(a), b=list(b), w=w))
    elif k == "via":
        net, xy = v.split("|"); x, y = map(float, xy.split(",")); disc = Point(x, y).buffer(0.225, 16)
        dm = min(disc.distance(obstacles(net, L, gnd_ok=True)) for L in ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu"))
        hh = min([math.dist((x, y), (q["x"], q["y"])) - 0.15 - q["drill"] / 2 for q in S["vias"]] +
                 [math.dist((x, y), (p["x"], p["y"])) - 0.15 - p["drill"] / 2 for p in D["pads"] if p.get("drill", 0) > 0] + [9])
        print(f"  via {net} at {x},{y}: clearance {dm:.3f} mm, hole to hole {hh:.3f} mm")
        if dm < CLR - 0.002 or hh < 0.2: faults.append(("via", net, x, y, round(dm, 3), round(hh, 3)))
        new_v.append(dict(net=net, x=x, y=y, size=0.45, drill=0.3))
if faults:
    for f in faults: print("  FAULT", f)
    print(f"links: {len(faults)} faults, nothing written"); sys.exit(1)
S["tracks"] = S["tracks"] + new_t; S["vias"] = S["vias"] + new_v
S.setdefault("links", []).extend([dict(kind="track", **t) for t in new_t] + [dict(kind="via", **q) for q in new_v])
json.dump(S, open(A[2], "w"), indent=1)
print(f"links: {len(new_t)} tracks, {len(new_v)} vias added, 0 faults")
