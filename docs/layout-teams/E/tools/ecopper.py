"""ecopper.py <spec.json> <bare.json>        hand copper on top of the planner's (env ECOPPER = the list file)
A copper step for sc.sh (SPEC_STEPS), run after the planner and before write_copper.py. The list file has one item
per line ('#' comments):
    zone  NET LAYER PRIO  x,y x,y x,y ...      a pour outline (KiCad fills it and keeps the clearances)
    box   NET LAYER PRIO  x0,y0,x1,y1          the same, as a rectangle
    track NET LAYER W     x,y x,y ...          a hard track
    via   NET x,y [x,y ...]                    0.45/0.3 vias
    drop  NET LAYER|*  x0,y0,x1,y1             remove the planner's tracks and vias of NET that lie in the box
                                               (zones of NET on that layer are clipped to outside the box)
    unvia NET x,y ...                          remove the planner's via of NET at each point (one that a hand via replaces)
    dropz NET LAYER|*  x0,y0,x1,y1             the same, but the vias stay
    shift dx dy                                added to every coordinate on the lines that follow (0 0 to end)
NET may be a short name (matched against the end of the board net name; NAME@1 = /USB Port 1/NAME). Planner tracks
of OTHER nets on that layer that cross a zone or box drawn here are removed and reported (hand copper wins, the
router reconnects those pads); their vias stay and the pour fills round them."""
import sys, os, json
from shapely.geometry import Polygon, LineString, Point, box as sbox
from shapely.ops import unary_union
S = json.load(open(sys.argv[1])); D = json.load(open(sys.argv[2])); F = os.environ.get("ECOPPER")
if not F or not os.path.exists(F): sys.exit(0)
nets = sorted({p["net"] for p in D["pads"] if p["net"]})
def net(n):
    if "@" in n: n = "/USB Port %s/%s" % (n.split("@")[1], n.split("@")[0])
    m = [x for x in nets if x == n or x.endswith("/" + n)]
    if len(m) != 1: sys.exit("ecopper: net %r matches %s" % (n, m))
    return m[0]
SH = [0.0, 0.0]
def pt(s):
    v = [float(q) for q in s.split(",")]
    return [round(q + SH[i % 2], 4) for i, q in enumerate(v)]
added = []; rm_t = rm_v = 0
def clear_others(poly, n, layer):
    global rm_t, rm_v
    keep = []
    for t in S["tracks"]:
        if t["net"] != n and t["layer"] == layer and LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + 0.2).intersects(poly): rm_t += 1
        else: keep.append(t)
    S["tracks"] = keep        # vias of other nets stay: the pour fills round them
for ln, line in enumerate(open(F), 1):
    a = line.split("#")[0].split()
    if not a: continue
    k = a[0]
    if k in ("zone", "box"):
        n = net(a[1]); L = a[2]; pr = int(a[3])
        ring = [pt(s) for s in a[4:]] if k == "zone" else (lambda b: [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]])(pt(a[4]))
        S["zones"].append(dict(net=n, layer=L, priority=pr, soft=False, kinds=["hand"], polys=[dict(ring=ring, holes=[])]))
        clear_others(Polygon(ring), n, L); added.append("%s %s %s" % (k, a[1], L))
    elif k == "track":
        n = net(a[1]); L = a[2]; w = float(a[3]); pts = [pt(s) for s in a[4:]]
        for p, q in zip(pts, pts[1:]): S["tracks"].append(dict(net=n, layer=L, a=p, b=q, w=w))
        added.append("track %s %s" % (a[1], L))
    elif k == "via":
        n = net(a[1])
        for s in a[2:]: x, y = pt(s); S["vias"].append(dict(net=n, x=x, y=y, size=0.45, drill=0.3))
        added.append("via %s x%d" % (a[1], len(a) - 2))
    elif k in ("drop", "dropz"):
        n = net(a[1]); L = a[2]; b = sbox(*pt(a[3])); t0, v0 = len(S["tracks"]), len(S["vias"])
        S["tracks"] = [t for t in S["tracks"] if not (t["net"] == n and (L == "*" or t["layer"] == L) and LineString([t["a"], t["b"]]).intersects(b))]
        if k == "drop": S["vias"] = [v for v in S["vias"] if not (v["net"] == n and b.contains(Point(v["x"], v["y"])))]
        nz = []
        for z in S["zones"]:
            if z["net"] != n or not (L == "*" or z["layer"] == L): nz.append(z); continue
            for p in z["polys"]:
                g = Polygon(p["ring"], p.get("holes", [])).buffer(0).difference(b)
                for q in (g.geoms if hasattr(g, "geoms") else [g]):
                    if q.is_empty or q.area < 0.2: continue
                    nz.append(dict(z, polys=[dict(ring=[list(c) for c in q.exterior.coords[:-1]], holes=[[list(c) for c in h.coords[:-1]] for h in q.interiors])]))
        S["zones"] = nz; added.append("drop %s: %d tracks, %d vias" % (a[1], t0 - len(S["tracks"]), v0 - len(S["vias"])))
    elif k == "unvia":
        n = net(a[1]); v0 = len(S["vias"])
        for q in a[2:]:
            x, y = pt(q); S["vias"] = [v for v in S["vias"] if not (v["net"] == n and abs(v["x"] - x) < 0.06 and abs(v["y"] - y) < 0.06)]
        added.append("unvia %s: %d vias" % (a[1], v0 - len(S["vias"])))
    elif k == "shift": SH[0], SH[1] = float(a[1]), float(a[2])
    else: sys.exit("ecopper line %d: %s?" % (ln, k))
json.dump(S, open(sys.argv[1], "w"))
print("ecopper", json.dumps(dict(added=added, removed_other_tracks=rm_t, removed_other_vias=rm_v)))
