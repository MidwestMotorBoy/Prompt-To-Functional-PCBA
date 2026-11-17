#!/usr/bin/env python3
"""specfix.py <spec.json> <fix.json>[,<fix2.json>...] : round-6 copper escape rules applied to a planned spec (in place).
fix.json = {"cuts":   [{"layers": ["F.Cu", ...], "net": "<regex, optional>", "circle": [x, y, r] | "rect": [x0, y0, x1, y1]
                        | "seg": [[xa, ya], [xb, yb], half_width]}],
            "tracks": [{"net", "layer", "a": [x, y], "b": [x, y], "w"}],
            "vias":   [{"net", "x", "y", "size", "drill"}]}
Cuts subtract the shape from every matching zone outline (pieces under 0.05 mm2 dropped, one zone per piece, as
split_spec.py). Tracks and vias are added to the spec as fixed copper (the router treats them as part of their net).
Spec vias/tracks of OTHER nets that overlap a cut are reported, not moved."""
import json, re, sys
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union

spec = json.load(open(sys.argv[1]))
fixes = [json.load(open(f)) for f in sys.argv[2].split(",") if f]


def shape(c):
    if "circle" in c:
        x, y, r = c["circle"]; return Point(x, y).buffer(r, 32)
    if "rect" in c:
        return box(*c["rect"])
    if "seg" in c:
        a, b, h = c["seg"]; return LineString([a, b]).buffer(h, 16)
    if "poly" in c:
        return Polygon(c["poly"])
    raise SystemExit("bad cut %r" % c)


def to_poly(p):
    return Polygon(p["ring"], p.get("holes", []))


def from_geom(g):
    out = []
    for q in (getattr(g, "geoms", None) or [g]):
        if q.geom_type != "Polygon" or q.area < 0.05:
            continue
        q = q.simplify(0.002)
        out.append({"ring": [list(map(lambda v: round(v, 4), c)) for c in q.exterior.coords[:-1]],
                    "holes": [[list(map(lambda v: round(v, 4), c)) for c in h.coords[:-1]] for h in q.interiors]})
    return out


ncut = 0
for fx in fixes:
    for c in fx.get("cuts", []):
        sh = shape(c); rx = re.compile(c["net"]) if c.get("net") else None
        new = []
        for z in spec["zones"]:
            if z["layer"] not in c["layers"] or (rx and not rx.search(z["net"])):
                new.append(z); continue
            hit = False; polys = []
            for p in z["polys"]:
                g = to_poly(p).buffer(0)
                if g.intersects(sh):
                    hit = True; polys += from_geom(g.difference(sh))
                else:
                    polys.append(p)
            if not hit:
                new.append(z); continue
            ncut += 1
            for p in polys:
                y = dict(z); y["polys"] = [p]; new.append(y)
        spec["zones"] = new
        for v in spec["vias"]:
            if sh.distance(Point(v["x"], v["y"])) < v["size"] / 2 and (not rx or rx.search(v["net"])):
                print("specfix: WARNING cut %r overlaps via %s at %.2f,%.2f" % (c, v["net"], v["x"], v["y"]))
    for t in fx.get("tracks", []):
        spec["tracks"].append({k: t[k] for k in ("net", "layer", "a", "b", "w")})
    for v in fx.get("vias", []):
        spec["vias"].append({"net": v["net"], "x": v["x"], "y": v["y"], "size": v.get("size", 0.45), "drill": v.get("drill", 0.3)})
    print("specfix: %d cuts (%d zone hits), %d tracks, %d vias" % (len(fx.get("cuts", [])), ncut, len(fx.get("tracks", [])), len(fx.get("vias", []))))
json.dump(spec, open(sys.argv[1], "w"))
