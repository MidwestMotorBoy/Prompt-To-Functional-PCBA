"""pinlib.py: exact copper geometry for laying a few tracks and vias by script (team B, phase 2).
Used by pins.py (before routing, on a copper plan) and handroute.py (after routing, on a board file).

Geo(pads, tracks, vias, zones, keepouts, outline, pro) holds every copper item as shapely geometry and answers:
  check_track(net, layer, a, b, w) -> list of faults (empty = clear)
  check_via(net, x, y)             -> list of faults
  add_track / add_via              -> the new item becomes an obstacle for the next checks
  free_area(net, layer, w, box)    -> where a track centre line of width w may run (shapely), for path search
  path(net, layer, w, start, goal_geom, box) -> a short polyline from start into goal_geom, every segment checked
Rules (board.kicad_dru / .kicad_pro / the shared router):
  copper to copper 0.15 mm; 0.25 mm between a HighCurrent net and a small-signal net (Default class) unless one of
  the two is a pad; planned pour outlines of other nets are kept at the zone clearance (0.2 mm, so the fill does not
  change) or 0.25 mm for the HighCurrent pair; board edge and bare holes 0.25 mm; keep-outs that forbid tracks / vias;
  vias 0.45/0.3, at least 0.75 mm (other net) / 0.6 mm (same net) centre to centre from another via and 1.1 / 0.9 mm
  from a through-hole pad centre less the pad's radius beyond a via (the router's via rules); the antenna keep-out
  of the router (118.12..121.32, 119.88..125.28, grown 0.4 mm) is closed to tracks and vias.
Hot-loop pours (polys of a hot loop's supply or return net that touch a pad of that loop's parts, constraints.json)
are closed to other nets' tracks and vias even where the pour is soft (GND)."""
import json, math, fnmatch, re, os
from shapely.geometry import Polygon, Point, LineString, box as sbox, MultiPolygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

CU = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
VIA_D, VIA_DRILL = 0.45, 0.3
VIA_MIN_SAME, VIA_MIN_OTHER, PTH_MIN_SAME, PTH_MIN_OTHER = 0.6, 0.75, 0.9, 1.1
CLR, ZCLR, HCCLR, EDGE = 0.15, 0.2, 0.25, 0.25
EPS = -0.003                       # new copper keeps 3 um more than the rule (KiCad measures its own polygons)
ANTENNA = (118.12 - 0.4, 119.88 - 0.4, 121.32 + 0.4, 125.28 + 0.4)
SOFTNETS = ("GND", "PACK_P", "3V3")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../../.."))
PRO = os.path.join(REPO, "tools/score/template/board.kicad_pro")
CONS = os.path.join(REPO, "tools/floorplan/example/monolith/constraints.json")


def poly(r):
    return Polygon(r["ring"], r.get("holes", [])).buffer(0)


class Classes:
    def __init__(self, pro=PRO):
        ns = json.load(open(pro))["net_settings"]
        self.pat = [(p["pattern"], p["netclass"]) for p in ns.get("netclass_patterns", [])]
        self.cache = {}

    def of(self, net):
        if net not in self.cache:
            c = "Default"
            for p, k in self.pat:
                if fnmatch.fnmatchcase(net, p):
                    c = k; break
            self.cache[net] = c
        return self.cache[net]

    def hc(self, net): return self.of(net) == "HighCurrent"
    def small(self, net): return bool(net) and self.of(net) == "Default"


def hot_polys(zones, pads):
    """Indices (zone index, poly index) of hot-loop pours: polys of a loop's supply / return net on F/B that touch a
    pad of that loop's capacitors or switch parts."""
    C = json.load(open(CONS))["hot_loops"]
    out = set()
    for name, h in C.items():
        nets = {"/" + h["supply"].lstrip("/") if "/" in h["supply"] else h["supply"], h["ret"]}
        refs = set(h["caps"]) | {s.split(".")[0] for s in h["switch_pins"]}
        pg = [(p["net"], L, poly(r)) for p in pads if p["ref"] in refs for L, rs in p["shapes"].items() for r in rs]
        for zi, z in enumerate(zones):
            if z["net"] not in nets or z["layer"] not in ("F.Cu", "B.Cu"):
                continue
            for pi, g in enumerate(z["geoms"]):
                if any(n == z["net"] and L == z["layer"] and g.intersects(pg_) for n, L, pg_ in pg):
                    out.add((zi, pi))
    return out


class Geo:
    def __init__(self, pads, tracks, vias, zones, keepouts, outline, pro=PRO, zones_are_fill=False):
        """pads: cu.json pads; tracks: dicts net layer a b w; vias: dicts net x y size; zones: dicts net layer and
        either polys (spec rings) or geoms (shapely); zones_are_fill: True for filled copper of a board file (the
        clearance to them is the copper rule, not the zone clearance)."""
        self.K = Classes(pro)
        self.pads = pads
        self.zones = []
        for z in zones:
            gs = z.get("geoms") or [poly(p) for p in z["polys"]]
            self.zones.append(dict(net=z["net"], layer=z["layer"], geoms=[g for g in gs if not g.is_empty], soft=z["net"] in SOFTNETS))
        self.hot = hot_polys(self.zones, pads)
        self.fill = zones_are_fill
        self.board = unary_union([poly(o) for o in outline])
        self.edge = self.board.boundary
        self.items = {L: [] for L in CU}      # (net, kind, geom, extra) per layer; kind pad/track/via/zone/hotzone/ko/hole
        self.vias = []                         # (x, y, net)
        self.pth = []                          # (x, y, r_extra, net) through-hole pads (router's via rule)
        self.keepv = []                        # no-via geoms (all layers listed)
        for p in pads:
            for L, rs in p["shapes"].items():
                if L in CU:
                    for r in rs:
                        self.items[L].append((p["net"], "pad", poly(r), p))
            if p.get("drill", 0) > 0:
                xs = [q[0] for L, rs in p["shapes"].items() for r in rs for q in r["ring"]]
                ys = [q[1] for L, rs in p["shapes"].items() for r in rs for q in r["ring"]]
                rad = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 if xs else p["drill"] / 2
                if p.get("npth") or not p["net"]:
                    for L in CU:
                        self.items[L].append(("", "hole", Point(p["x"], p["y"]).buffer(p["drill"] / 2, 24), p))
                self.pth.append((p["x"], p["y"], max(rad - VIA_D / 2, 0.0), p["net"]))
        for t in tracks:
            self._track(t["net"], t["layer"], t["a"], t["b"], t["w"])
        for v in vias:
            self._via(v["net"], v["x"], v["y"], v.get("size", VIA_D))
        for zi, z in enumerate(self.zones):
            for pi, g in enumerate(z["geoms"]):
                self.items[z["layer"]].append((z["net"], "hotzone" if (zi, pi) in self.hot else "zone", g, z))
        for k in keepouts:
            for L in k["layers"]:
                if L not in CU: continue
                for r in k["poly"]:
                    g = poly(r)
                    if k.get("no_tracks"): self.items[L].append(("", "ko", g, k))
                    if k.get("no_vias") or k.get("no_tracks"): self.keepv.append(g)
        a = sbox(*ANTENNA)
        for L in CU: self.items[L].append(("", "ko", a, None))
        self.keepv.append(a)
        self._index()

    def _track(self, net, L, a, b, w):
        g = LineString([tuple(a), tuple(b)]).buffer(w / 2, 16) if tuple(a) != tuple(b) else Point(a).buffer(w / 2, 16)
        self.items[L].append((net, "track", g, None))
        return g

    def _via(self, net, x, y, size=VIA_D):
        g = Point(x, y).buffer(size / 2, 24)
        for L in CU:
            self.items[L].append((net, "via", g, None))
        self.vias.append((x, y, net))
        return g

    def _index(self):
        self.tree = {L: STRtree([it[2] for it in self.items[L]]) for L in CU}
        self.vtree = STRtree([Point(x, y) for x, y, n in self.vias]) if self.vias else None

    def add_track(self, net, L, a, b, w):
        self._track(net, L, a, b, w); self._index()

    def add_via(self, net, x, y, size=VIA_D):
        self._via(net, x, y, size); self._index()

    def remove_where(self, pred):
        for L in CU:
            self.items[L] = [it for it in self.items[L] if not pred(L, it)]
        self._index()

    # ---- clearance of a NEW item (net, kind 'track' / 'via') to an existing item
    def need(self, net, kind, it):
        n2, k2 = it[0], it[1]
        if k2 in ("ko",): return 0.0
        if k2 == "hole": return EDGE
        if k2 in ("zone", "hotzone"):
            hcpair = (self.K.hc(net) and self.K.small(n2)) or (self.K.small(net) and self.K.hc(n2))
            if self.fill: return HCCLR if hcpair else CLR
            return HCCLR if hcpair else ZCLR
        hcpair = (self.K.hc(net) and self.K.small(n2)) or (self.K.small(net) and self.K.hc(n2))
        if hcpair and k2 != "pad": return HCCLR
        return CLR

    def faults(self, net, L, g, kind, soft_ok=False):
        out = []
        cand = self.tree[L].query(g.buffer(HCCLR + 0.05))
        for i in cand:
            it = self.items[L][int(i)]
            n2, k2, g2 = it[0], it[1], it[2]
            if k2 == "ko":
                if g.intersects(g2): out.append((L, "keep-out", 0.0, 0.0))
                continue
            if n2 == net and k2 != "hole":
                continue
            if k2 == "zone" and soft_ok and it[3]["soft"]:
                continue
            d = g.distance(g2); nd = self.need(net, kind, it)
            if d < nd - EPS:
                out.append((L, "%s %s" % (k2, n2 or "-"), round(d, 3), nd))
        if not self.board.buffer(-EDGE + EPS).contains(g):
            out.append((L, "board edge", round(g.distance(self.edge), 3), EDGE))
        return out

    def check_track(self, net, L, a, b, w, soft_ok=False):
        g = LineString([tuple(a), tuple(b)]).buffer(w / 2, 16) if tuple(a) != tuple(b) else Point(a).buffer(w / 2, 16)
        return self.faults(net, L, g, "track", soft_ok)

    def check_via(self, net, x, y, size=VIA_D, soft_ok=False, layers=CU, inpad=False, self_ok=False, other_min=VIA_MIN_OTHER):
        g = Point(x, y).buffer(size / 2, 24); out = []
        for L in layers:
            out += [f for f in self.faults(net, L, g, "via", soft_ok)
                    if not (L in ("In1.Cu", "In4.Cu", "In2.Cu", "In3.Cu") and f[1].startswith("zone ") and f[1][5:] in SOFTNETS)]
        for vx, vy, vn in self.vias:
            d = math.hypot(vx - x, vy - y)
            if self_ok and d < 1e-6 and vn == net:
                self_ok = False; continue                 # the via itself (final checks)
            if d < (VIA_MIN_SAME if vn == net else other_min) - EPS:
                out.append(("all", "via spacing " + vn, round(d, 3), VIA_MIN_SAME if vn == net else other_min))
        for px, py, r, pn in self.pth:
            d = math.hypot(px - x, py - y) - r
            if d < (PTH_MIN_SAME if pn == net else PTH_MIN_OTHER) - EPS and not (pn == net and d < 0.05):
                out.append(("all", "through-hole pad spacing " + pn, round(d, 3), PTH_MIN_SAME if pn == net else PTH_MIN_OTHER))
        for k in self.keepv:
            if g.intersects(k): out.append(("all", "no-via area", 0.0, 0.0)); break
        if not inpad:                                      # no via in or on a small pad (the router's via-in-pad is a last resort)
            for L in ("F.Cu", "B.Cu"):
                for i in self.tree[L].query(g):
                    it = self.items[L][int(i)]
                    if it[1] == "pad" and g.intersects(it[2]):
                        b = it[2].bounds
                        if min(b[2] - b[0], b[3] - b[1]) <= 1.6:
                            out.append((L, "on pad %s.%s" % (it[3]["ref"], it[3]["num"]), 0.0, 0.0)); break
        return out

    # ---- free area for a track centre line (search help; segments are checked exactly afterwards)
    def free_area(self, net, L, w, bx, soft_ok=False):
        B = sbox(*bx); obst = []
        for i in self.tree[L].query(B.buffer(1.0)):
            it = self.items[L][int(i)]
            n2, k2, g2 = it[0], it[1], it[2]
            if k2 == "ko": obst.append(g2.buffer(w / 2)); continue
            if n2 == net and k2 != "hole": continue
            if k2 == "zone" and soft_ok and it[3]["soft"]: continue
            obst.append(g2.buffer(self.need(net, "track", it) + w / 2 + 0.005, 12))
        ok = B.intersection(self.board.buffer(-(EDGE + w / 2 + 0.005)))
        return ok.difference(unary_union(obst)) if obst else ok

    def own(self, net, L, bx):
        """Copper of the net on layer L inside the box (pads, tracks, vias, zones)."""
        B = sbox(*bx)
        return unary_union([it[2] for i in self.tree[L].query(B) for it in [self.items[L][int(i)]] if it[0] == net and it[1] != "ko"])


def path_in(free, start, goal, step=0.02):
    """Shortest 8-connected raster path inside 'free' (shapely) from start (x, y) to any point of goal (shapely),
    simplified to few straight pieces that stay inside 'free'. Returns a list of points or None."""
    import numpy as np
    from PIL import Image, ImageDraw
    import heapq
    x0, y0, x1, y1 = free.bounds
    nx, ny = int((x1 - x0) / step) + 3, int((y1 - y0) / step) + 3
    def ras(g):
        im = Image.new("1", (nx, ny), 0); d = ImageDraw.Draw(im)
        for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
            if not isinstance(q, Polygon) or q.is_empty: continue
            d.polygon([((x - x0) / step + 1, (y - y0) / step + 1) for x, y in q.exterior.coords], fill=1)
            for h in q.interiors: d.polygon([((x - x0) / step + 1, (y - y0) / step + 1) for x, y in h.coords], fill=0)
        return np.array(im, dtype=bool)
    F = ras(free.buffer(-step * 0.75))
    Gm = ras(goal.intersection(free).buffer(-step * 0.5)) & F
    if not Gm.any(): return None
    si, sj = int(round((start[0] - x0) / step + 1)), int(round((start[1] - y0) / step + 1))
    if not (0 <= si < nx and 0 <= sj < ny): return None
    # start may sit just outside free (pad centre inside the pad, which is own copper): allow it
    F[sj, si] = True
    dist = {(si, sj): 0.0}; prev = {}; q = [(0.0, si, sj)]; end = None
    D8 = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    while q:
        d, i, j = heapq.heappop(q)
        if d > dist.get((i, j), 1e9): continue
        if Gm[j, i]: end = (i, j); break
        for di, dj, c in D8:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and F[b, a]:
                nd = d + c
                if nd < dist.get((a, b), 1e9):
                    dist[(a, b)] = nd; prev[(a, b)] = (i, j); heapq.heappush(q, (nd, a, b))
    if end is None: return None
    cells = [end]
    while cells[-1] in prev: cells.append(prev[cells[-1]])
    pts = [(x0 + (i - 1) * step, y0 + (j - 1) * step) for i, j in cells[::-1]]
    pts[0] = tuple(start)
    # greedy straightening inside free
    inside = free.buffer(1e-4)
    out = [pts[0]]; k = 0
    while k < len(pts) - 1:
        j = len(pts) - 1
        while j > k + 1 and not inside.contains(LineString([pts[k], pts[j]])) and not (k == 0 and _ok_from_start(free, pts[k], pts[j])):
            j -= 1
        out.append(pts[j]); k = j
    return [(round(x, 4), round(y, 4)) for x, y in out]


def _ok_from_start(free, a, b):
    """The first piece leaves the pad centre, which is not in 'free' (own pad copper): accept it when the part of the
    line outside a small disc round the start lies in free."""
    L = LineString([a, b])
    rest = L.difference(Point(a).buffer(0.12))
    return rest.is_empty or free.buffer(1e-4).contains(rest)


def load_spec(spec_path, cu_path, pro=PRO):
    S = json.load(open(spec_path)); D = json.load(open(cu_path))
    G = Geo(D["pads"], S["tracks"], S["vias"], S["zones"], D.get("keepouts", []), D["outline"], pro)
    return S, D, G


def load_board(pcb_path, cu_path, pro=PRO):
    """A board file (tracks, vias, filled zones read from the file) and its cu.json (pads, outline, keep-outs)."""
    import sys
    sys.path.insert(0, os.path.join(REPO, "tools/copper"))
    from dc_score import load_copper
    D = json.load(open(cu_path)); Z, T, V = load_copper(pcb_path)
    zs = {}
    for z in Z:
        if len(z["pts"]) < 3: continue
        zs.setdefault((z["net"], z["layer"]), []).append(Polygon(z["pts"]).buffer(0))
    zones = [dict(net=n, layer=L, geoms=g) for (n, L), g in zs.items()]
    G = Geo(D["pads"], [dict(net=t["net"], layer=t["layer"], a=t["a"], b=t["b"], w=t["w"]) for t in T if t["layer"] in CU],
            [dict(net=v["net"], x=v["x"], y=v["y"], size=v["size"]) for v in V], zones, D.get("keepouts", []), D["outline"], pro, zones_are_fill=True)
    return D, G, (Z, T, V)


def pad_of(D, ref, num):
    ps = [p for p in D["pads"] if p["ref"] == ref and p["num"] == num and p["shapes"]]
    return ps


def fp_of(D, ref):
    return next(f for f in D["fps"] if f["ref"] == ref)


def draw(G, out, bx, L, S=60, net_hi=None, extra=(), free=None):
    """Picture of one window on one layer: other nets' copper red (hot pours purple, soft pours orange), the net
    net_hi green, pads outlined, free area for a track centre light green, extra (list of (geom, rgb)) on top."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = bx
    W_, H_ = int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1
    im = Image.new("RGB", (W_, H_), (250, 250, 248)); d = ImageDraw.Draw(im, "RGBA")
    P = lambda x, y: ((x - x0) * S, (y - y0) * S)
    def fillg(g, col, outline=None):
        for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
            if isinstance(q, Polygon) and not q.is_empty:
                d.polygon([P(*c) for c in q.exterior.coords], fill=col, outline=outline)
                for h in q.interiors: d.polygon([P(*c) for c in h.coords], fill=(250, 250, 248, 255))
            elif isinstance(q, LineString):
                d.line([P(*c) for c in q.coords], fill=col, width=2)
    B = sbox(*bx)
    order = {"zone": 0, "hotzone": 0, "track": 1, "via": 2, "pad": 3, "hole": 4, "ko": 5}
    its = sorted([G.items[L][int(i)] for i in G.tree[L].query(B)], key=lambda it: order.get(it[1], 9))
    for n, k, g, e in its:
        if k == "ko": fillg(g.boundary, (230, 140, 0, 255)); continue
        me = net_hi is not None and n == net_hi
        if k in ("zone", "hotzone"):
            col = (40, 170, 60, 110) if me else ((150, 60, 200, 110) if k == "hotzone" else ((240, 170, 60, 100) if n in SOFTNETS else (220, 80, 80, 100)))
            fillg(g.intersection(B.buffer(1)), col)
        elif k == "pad":
            fillg(g, (40, 170, 60, 200) if me else (200, 200, 200, 220), (60, 60, 60, 255))
        elif k == "hole":
            fillg(g, (0, 0, 0, 255))
        else:
            fillg(g, (40, 170, 60, 220) if me else (200, 60, 60, 200))
    if free is not None: fillg(free, (120, 230, 120, 90))
    for g, col in extra: fillg(g, col)
    for p in G.pads:
        if L in p["shapes"] and x0 - 1 < p["x"] < x1 + 1 and y0 - 1 < p["y"] < y1 + 1 and p["num"]:
            c = P(p["x"], p["y"]); d.text((c[0] - 4, c[1] - 5), p["num"], fill=(0, 0, 120, 255))
    im.save(out)
    return out


if __name__ == "__main__":
    import sys
    A = [a for a in sys.argv[1:] if not a.startswith("--")]
    O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
    if not A or A[0] != "look":
        print(__doc__ + "\nlook: pinlib.py look <spec.json | board.kicad_pcb> <cu.json> <out.png> REF.PAD|x,y@NET [--layer=F.Cu] [--w=0.2] [--r=2.5] [--px=60] [--soft]")
        sys.exit(2)
    src, cu, out, rp = A[1:5]
    if src.endswith(".kicad_pcb"): D, G, _ = load_board(src, cu)
    else: S, D, G = load_spec(src, cu)
    if "@" in rp:                                   # x,y@NET: a spot instead of a pad
        xy, nn = rp.split("@", 1); x_, y_ = map(float, xy.split(","))
        p = dict(x=x_, y=y_, net=nn, shapes={"F.Cu": []})
    else:
        ref, num = rp.split(".", 1); p = pad_of(D, ref, num)[0]
    L = O.get("layer", next(iter(p["shapes"]))); w = float(O.get("w", 0.2)); r = float(O.get("r", 2.5))
    bx = (p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
    fr = G.free_area(p["net"], L, w, bx, "soft" in O)
    draw(G, out, bx, L, float(O.get("px", 60)), p["net"], free=fr)
    print(out, p["net"], L, "free area for a %.2f mm track centre: %.2f mm2" % (w, fr.area))
