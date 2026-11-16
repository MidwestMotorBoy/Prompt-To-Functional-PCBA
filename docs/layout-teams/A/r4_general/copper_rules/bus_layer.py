#!/usr/bin/env python3
"""bus_layer.py <spec.json> <bare.json> <constraints.json> [--rules=<rules.json>] [--router=<router.py>] [step options]
Copper step after split_zones.py and before write_copper.py (generalised from team A strapfix/tools/bus4.py).

Rule (protected bus copy): the router may cut the soft inner pour of a high-current bus net into islands (its
signal tracks run through it and KiCad refills around them). A second copy of that bus on a copper layer the router
never routes on can be pierced by signal vias but never cut by a track, so the bus stays joined after routing, and it
costs the router nothing. A soft fill of the return net on the outer layer away from the hot loops then gives the
return net back the plane area the copy took.

Each step is one dict (rules.json "bus_layer": [step, ...], or one step from the command line). Fields, with the
'auto' derivation that is used when a field is missing or "auto":
  net     auto = every bus net of the plan (spec report 'buses': nets the stock planner gave an inner pour, i.e. 6+
          terminals spread over 25 mm) carrying at least min_a amps (default 3 A, the stock planner's mirror limit);
          "auto:return" = the hot loops' return net.
  from    auto = the inner layer that holds the net's soft bus pour in the plan.
  layer   auto = a copper layer the router never routes on (stack layers minus the router's LAYERS list, read from
          router.py or rules.json "router"."layers"), the inner one farthest in the stack from the layer of the hot-loop
          switch parts (the plane next to the hot loops stays a solid return plane); "auto:far_outer" = the outer layer
          away from the hot-loop parts.
  mode    copy (the whole from-pour), strip (bands of width w along a minimum spanning tree over the net's via groups:
          vias closer than join mm are one group), strip+copy (bands + the pour inside box), fill (the whole outline).
  w       band width, default 3.0 mm (team A strapfix screens: 3 mm bands + copy inside the high-current box gave the
          lowest routed loss of w = 3, 4, 6, 10 and of whole-pour copies).
  box     region of the strip+copy copy: "x0,y0,x1,y1;..." or auto = bounding box of the pads of the net's series
          terminals carrying at least hi_frac (default 0.5) of the net current, grown by w.
  prio (10), soft (0), clip (0.6 mm from the outline), join (1.5), maxlen (40 mm), min_a (3), hi_frac (0.5).
Every zone written is single-outline. The step never touches other nets' hard zones on the layer (kept 0.3 mm off)."""
import sys, os, json, math, re
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box as _box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DEF = dict(net="auto", frm="auto", layer="auto", mode="strip+copy", w=3.0, join=1.5, prio=10, clip=0.6, maxlen=40.0, box="auto",
           soft=0, min_a=3.0, hi_frac=0.5)


def _stock_dir():
    d = os.environ.get("PLAN_COPPER_DIR")
    if d: return d
    p = HERE
    while p != "/":
        if os.path.exists(os.path.join(p, "tools", "copper", "roles.py")): return os.path.join(p, "tools", "copper")
        p = os.path.dirname(p)
    raise SystemExit("bus_layer: tools/copper not found")


def router_layers(cfg, router):
    if cfg.get("router", {}).get("layers"): return list(cfg["router"]["layers"])
    src = open(router).read(); m = re.search(r"^LAYERS\s*=\s*\[([^\]]*)\]", src, re.M)
    if not m: raise SystemExit("bus_layer: no LAYERS list in " + router)
    out = []
    for t in re.findall(r"pcbnew\.(\w+)", m.group(1)):
        a, b = t.rsplit("_", 1); out.append(f"{a}.{b}")
    return out


def zpoly(p): return Polygon(p["ring"], p.get("holes", []))


def derive(st, S, D, des, cfg, router, log):
    """Fill the 'auto' fields of one step from the plan, the board and the constraints. Returns a list of steps."""
    st = dict(DEF, **{("frm" if k == "from" else k): v for k, v in st.items()})
    layers = D["layers"]; outer = [layers[0], layers[-1]]
    sw_layers = [des.fp[t.split(".")[0]]["layer"] for hl in des.C.get("hot_loops", {}).values() for t in hl["switch_pins"][:1] if t.split(".")[0] in des.fp]
    hot = max(set(sw_layers), key=sw_layers.count) if sw_layers else outer[0]
    if st["net"] == "auto":
        nets = [n for n in S.get("report", {}).get("buses", []) if des.current(n) >= float(st["min_a"])]
        log(f"bus_layer: auto net -> {nets} (plan buses {S.get('report', {}).get('buses')}, >= {st['min_a']} A)")
        return [s for n in nets for s in derive(dict(st, net=n), S, D, des, cfg, router, log)]
    if st["net"] == "auto:return": st["net"] = sorted(des.ret)[0]
    if st["frm"] == "auto":
        fl = [z["layer"] for z in S["zones"] if z["net"] == st["net"] and z["layer"] not in outer and "bus" in z.get("kinds", []) and z.get("soft")]
        st["frm"] = fl[0] if fl else None
    if st["layer"] == "auto":
        rl = router_layers(cfg, router); free = [l for l in layers[1:-1] if l not in rl]
        if not free: raise SystemExit("bus_layer: every inner layer is routed; no protected layer")
        st["layer"] = max(free, key=lambda l: (abs(layers.index(l) - layers.index(hot)), layers.index(l)))
        log(f"bus_layer: router layers {rl}; layers it never routes {free}; hot-loop parts on {hot} -> {st['layer']}")
    elif st["layer"] == "auto:far_outer":
        st["layer"] = [l for l in outer if l != hot][0]
    if st["mode"] == "strip+copy" and st["box"] == "auto":
        I = des.current(st["net"]); pads = []
        for g in des.terminals(st["net"]):
            if g["kind"] == "series" and g["current_a"] >= float(st["hi_frac"]) * I:
                pads += [des.pad_poly(p, L) for p in g["pads"] for L in p["shapes"]]
        b = unary_union(pads).bounds; w = float(st["w"])
        st["box"] = ",".join(str(round(v, 2)) for v in (b[0] - w, b[1] - w, b[2] + w, b[3] + w))
        log(f"bus_layer: auto box for {st['net']}: terminals >= {st['hi_frac']} x {I} A -> {st['box']}")
    return [st]


def step(S, D, st):
    NET, FROM, LAY, MODE = st["net"], st["frm"], st["layer"], st["mode"]
    W, JOIN, PRIO, CLIP, MAXL = float(st["w"]), float(st["join"]), int(st["prio"]), float(st["clip"]), float(st["maxlen"])
    board = unary_union([Polygon(o["ring"]) for o in D["outline"]]).buffer(-CLIP)
    src = unary_union([zpoly(p) for z in S["zones"] if z["net"] == NET and z["layer"] == FROM for p in z["polys"]])
    bs = [_box(*[float(v) for v in b.split(",")]) for b in str(st.get("box") or "").split(";") if b and b != "auto"]
    boxes = unary_union(bs) if bs else None
    if MODE == "fill":
        g = board
        if boxes is not None: g = g.intersection(boxes)
    elif MODE == "copy":
        g = src.intersection(board)
        if boxes is not None: g = g.intersection(boxes)
    else:
        vs = [(v["x"], v["y"]) for v in S["vias"] if v["net"] == NET] + [(p["x"], p["y"]) for p in D["pads"] if p.get("drill") and p.get("net") == NET]
        grp = list(range(len(vs)))
        def f(i):
            while grp[i] != i: grp[i] = grp[grp[i]]; i = grp[i]
            return i
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                if math.dist(vs[i], vs[j]) < JOIN: grp[f(i)] = f(j)
        G = {}
        for i, v in enumerate(vs): G.setdefault(f(i), []).append(v)
        A = [min(g_, key=lambda v: math.dist(v, np.mean(g_, axis=0))) for g_ in G.values()]
        comp = list(range(len(A)))
        def cf(i):
            while comp[i] != i: comp[i] = comp[comp[i]]; i = comp[i]
            return i
        lines = []
        for d, i, j in sorted((math.dist(A[i], A[j]), i, j) for i in range(len(A)) for j in range(i + 1, len(A))):
            if cf(i) != cf(j) and d <= MAXL: lines.append(LineString([A[i], A[j]])); comp[cf(i)] = cf(j)
        g = unary_union([l.buffer(W / 2, 8) for l in lines] + [Point(p).buffer(W / 2, 8) for p in A]).intersection(board)
        if MODE == "strip+copy":
            g = unary_union([g, src.intersection(board).intersection(boxes)])
    oth = unary_union([zpoly(p) for z in S["zones"] if z["net"] != NET and z["layer"] == LAY and not z.get("soft") for p in z["polys"]])
    if not oth.is_empty: g = g.difference(oth.buffer(0.3))
    polys = [p for p in getattr(g, "geoms", [g]) if not p.is_empty and p.area > 1.0]
    for p in polys:
        p = p.simplify(0.02)
        S["zones"].append(dict(net=NET, layer=LAY, priority=PRIO, soft=bool(int(st.get("soft", 0))), kinds=["bus"], added=True,
                               polys=[dict(ring=[list(map(lambda c: round(c, 4), q)) for q in p.exterior.coords[:-1]],
                                           holes=[[list(map(lambda c: round(c, 4), q)) for q in h.coords[:-1]] for h in p.interiors])],
                               area_mm2=round(p.area, 1)))
    return dict(net=NET, layer=LAY, mode=MODE, w=W, box=st.get("box"), zones=len(polys), area_mm2=round(sum(p.area for p in polys), 1))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
    sys.path.insert(0, _stock_dir()); from roles import Design
    cfg = json.load(open(opt.pop("rules"))) if "rules" in opt else {}
    router = opt.pop("router", os.path.join(os.path.dirname(_stock_dir()), "score", "router.py"))
    out = opt.pop("out", a[0])
    S = json.load(open(a[0])); D = json.load(open(a[1])); des = Design(a[1], a[2])
    steps = [dict(opt)] if opt else cfg.get("bus_layer", [])
    for st in steps:
        for s in derive(st, S, D, des, cfg, router, print):
            print("bus4", json.dumps(step(S, D, s)))
    json.dump(S, open(out, "w"))


if __name__ == "__main__":
    main()
