"""er.py - team E router core: a fast maze router on the real copper of a KiCad board.

  W = World(dump_json)                 the board (edump.py output): pads, hard pours, tracks, vias, keep-outs
  W.add_routes(routes)                 earlier routed copper (rip-able)
  W.route_all(...)                     join every net's pieces, with rip-up and retry

How it works
- 0.05 mm grid over the whole board, six copper layers.
- For every cell and layer it keeps the distance to the nearest copper and to the nearest copper of a second net
  (DS: d1, n1, d2). "Is a track of net n and half width h legal here" is then one comparison:
  distance to the nearest OTHER net's copper >= clearance + h. Distances are exact for pads, tracks and vias
  (computed from the geometry) and from a distance transform for pour fills.
- Static copper (pads, hard pours, the copper plan's tracks and vias, board edge) and routed copper (rip-able) sit in
  two such stores, so pulling a route only rebuilds the routed store near it.
- A net is a set of pieces (connected copper). A search runs from one whole piece to any other piece of the net
  (Dijkstra in numba over layer, y, x); it may end on a pad, a track, a via, a pour, or by a via onto a plane.
- Rules built in: 0.15 mm clearance, 0.25 mm between HighCurrent copper (not pads) and Default-class signals,
  0.25 mm to the board edge and bare holes, via 0.45/0.3 with 0.2 mm hole to hole (0.45 to pad holes), keep-outs.
"""
import json, math, os, sys, time, heapq, fnmatch
import numpy as np
from numba import njit
from PIL import Image, ImageDraw
from scipy import ndimage

G = 0.05
LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
NL = 6
DMAX = 0.8
BIG = 9.0
CLR = 0.15
ZCLR = 0.2                           # what a pour keeps from other copper
HC_CLR = 0.25
EDGE_CLR = 0.25
VIA_D, VIA_DRILL = 0.45, 0.3
TOL_O, TOL_D = 0.031, 0.043          # raster margins: straight steps, diagonal steps
SOFTNETS = ("GND", "PACK_P", "3V3")
EDGE_NET = -2


# ------------------------------------------------------------------ distance store kernels
@njit(cache=True)
def _upd(d1, n1, d2, L, y, x, d, net):
    if net == n1[L, y, x]:
        if d < d1[L, y, x]:
            d1[L, y, x] = d
    elif d < d1[L, y, x]:
        if n1[L, y, x] != -1:
            d2[L, y, x] = d1[L, y, x]
        d1[L, y, x] = d
        n1[L, y, x] = net
    elif d < d2[L, y, x]:
        d2[L, y, x] = d


@njit(cache=True)
def ins_seg(d1, n1, d2, L, ax, ay, bx, by, r, net, X0, Y0):
    NY, NX = d1.shape[1], d1.shape[2]
    R = r + DMAX
    x0 = max(0, int(math.floor((min(ax, bx) - R - X0) / G)))
    x1 = min(NX - 1, int(math.ceil((max(ax, bx) + R - X0) / G)))
    y0 = max(0, int(math.floor((min(ay, by) - R - Y0) / G)))
    y1 = min(NY - 1, int(math.ceil((max(ay, by) + R - Y0) / G)))
    dx = bx - ax
    dy = by - ay
    LL = dx * dx + dy * dy
    for y in range(y0, y1 + 1):
        py = Y0 + y * G
        for x in range(x0, x1 + 1):
            px = X0 + x * G
            t = 0.0
            if LL > 0:
                t = ((px - ax) * dx + (py - ay) * dy) / LL
                if t < 0:
                    t = 0.0
                elif t > 1:
                    t = 1.0
            ex = px - (ax + t * dx)
            ey = py - (ay + t * dy)
            d = math.sqrt(ex * ex + ey * ey) - r
            if d < 0:
                d = 0.0
            if d < DMAX:
                _upd(d1, n1, d2, L, y, x, d, net)


@njit(cache=True)
def _poly_dist(px, py, xs, ys):
    n = len(xs)
    inside = False
    best = 1e18
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = xs[i], ys[i], xs[j], ys[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
        dx = xj - xi
        dy = yj - yi
        LL = dx * dx + dy * dy
        t = 0.0
        if LL > 0:
            t = ((px - xi) * dx + (py - yi) * dy) / LL
            if t < 0:
                t = 0.0
            elif t > 1:
                t = 1.0
        ex = px - (xi + t * dx)
        ey = py - (yi + t * dy)
        d = ex * ex + ey * ey
        if d < best:
            best = d
        j = i
    if inside:
        return 0.0
    return math.sqrt(best)


@njit(cache=True)
def ins_poly(d1, n1, d2, L, xs, ys, net, X0, Y0, grow):
    NY, NX = d1.shape[1], d1.shape[2]
    R = DMAX + grow
    x0 = max(0, int(math.floor((xs.min() - R - X0) / G)))
    x1 = min(NX - 1, int(math.ceil((xs.max() + R - X0) / G)))
    y0 = max(0, int(math.floor((ys.min() - R - Y0) / G)))
    y1 = min(NY - 1, int(math.ceil((ys.max() + R - Y0) / G)))
    for y in range(y0, y1 + 1):
        py = Y0 + y * G
        for x in range(x0, x1 + 1):
            px = X0 + x * G
            d = _poly_dist(px, py, xs, ys) - grow
            if d < 0:
                d = 0.0
            if d < DMAX:
                _upd(d1, n1, d2, L, y, x, d, net)


@njit(cache=True)
def ins_dist(d1, n1, d2, L, y0, x0, dist, net):
    h, w = dist.shape
    for y in range(h):
        for x in range(w):
            d = dist[y, x]
            if d < DMAX:
                _upd(d1, n1, d2, L, y0 + y, x0 + x, d, net)


@njit(cache=True)
def ins_min_disc(arr, cx, cy, r, X0, Y0):
    """arr[y, x] = min(arr, distance to the disc)"""
    NY, NX = arr.shape
    R = r + DMAX
    x0 = max(0, int(math.floor((cx - R - X0) / G)))
    x1 = min(NX - 1, int(math.ceil((cx + R - X0) / G)))
    y0 = max(0, int(math.floor((cy - R - Y0) / G)))
    y1 = min(NY - 1, int(math.ceil((cy + R - Y0) / G)))
    for y in range(y0, y1 + 1):
        py = Y0 + y * G
        for x in range(x0, x1 + 1):
            px = X0 + x * G
            d = math.sqrt((px - cx) ** 2 + (py - cy) ** 2) - r
            if d < 0:
                d = 0.0
            if d < arr[y, x]:
                arr[y, x] = d


@njit(cache=True)
def paint_seg(mask, ax, ay, bx, by, r, X0, Y0, val):
    """mask[y, x] = val for cells whose centre is within r of the segment"""
    NY, NX = mask.shape
    x0 = max(0, int(math.floor((min(ax, bx) - r - X0) / G)))
    x1 = min(NX - 1, int(math.ceil((max(ax, bx) + r - X0) / G)))
    y0 = max(0, int(math.floor((min(ay, by) - r - Y0) / G)))
    y1 = min(NY - 1, int(math.ceil((max(ay, by) + r - Y0) / G)))
    dx = bx - ax
    dy = by - ay
    LL = dx * dx + dy * dy
    rr = r * r + 1e-12
    for y in range(y0, y1 + 1):
        py = Y0 + y * G
        for x in range(x0, x1 + 1):
            px = X0 + x * G
            t = 0.0
            if LL > 0:
                t = ((px - ax) * dx + (py - ay) * dy) / LL
                if t < 0:
                    t = 0.0
                elif t > 1:
                    t = 1.0
            ex = px - (ax + t * dx)
            ey = py - (ay + t * dy)
            if ex * ex + ey * ey <= rr:
                mask[y, x] = val


@njit(cache=True)
def dijkstra(free, freed, vfree, tgt, through, pen, vpen, src, routable, pref, lcost, via_cost, bend, gap, maxn):
    """free/freed/tgt/pen: [NL, h, w]; vfree/through/vpen: [h, w]; src: node indices. Returns the path (node indices,
    source first) or an empty array. A node is L * h * w + y * w + x."""
    nl, h, w = free.shape
    A = h * w
    N = nl * A
    dist = np.full(N, np.inf, dtype=np.float32)
    par = np.full(N, -1, dtype=np.int32)
    pdir = np.full(N, -1, dtype=np.int8)
    sv = np.zeros(N, dtype=np.int16)
    heap = [(np.float32(0.0), np.int64(-1))]
    heap.pop()
    for s in src:
        dist[s] = 0.0
        sv[s] = gap
        heapq.heappush(heap, (np.float32(0.0), np.int64(s)))
    DX = np.array([1, -1, 0, 0, 1, 1, -1, -1])
    DY = np.array([0, 0, 1, -1, 1, -1, 1, -1])
    goal = -1
    seen = 0
    while len(heap) > 0:
        g, idx = heapq.heappop(heap)
        if g > dist[idx] + 1e-6:
            continue
        L = idx // A
        r = idx - L * A
        y = r // w
        x = r - y * w
        if tgt[L, y, x] and g > 0:
            goal = idx
            break
        seen += 1
        if seen > maxn:
            break
        if routable[L]:
            lc = lcost[L]
            pd = pdir[idx]
            for k in range(8):
                X = x + DX[k]
                Y = y + DY[k]
                if X < 0 or Y < 0 or X >= w or Y >= h:
                    continue
                if not free[L, Y, X]:
                    if not tgt[L, Y, X]:
                        continue
                if k >= 4:
                    if not (freed[L, y, x] and (freed[L, Y, X] or tgt[L, Y, X])):
                        continue
                    c = 1.4142
                else:
                    c = 1.0
                if pref[L] == 1 and DX[k] != 0:
                    c *= 1.7
                elif pref[L] == 2 and DY[k] != 0:
                    c *= 1.7
                c = c * lc + pen[L, Y, X]
                if pd != -1 and pd != k:
                    c += bend
                ng = g + c
                ni = L * A + Y * w + X
                if ng < dist[ni]:
                    dist[ni] = ng
                    par[ni] = idx
                    pdir[ni] = k
                    s2 = sv[idx] + 1
                    if s2 > gap:
                        s2 = gap
                    sv[ni] = s2
                    heapq.heappush(heap, (np.float32(ng), np.int64(ni)))
        th = through[y, x]
        if th or (vfree[y, x] and sv[idx] >= gap and (free[L, y, x] or g == 0)):
            vc = 0.0 if th else via_cost + vpen[y, x]
            for L2 in range(nl):
                if L2 == L:
                    continue
                if not (tgt[L2, y, x] or (routable[L2] and free[L2, y, x])):
                    continue
                ng = g + vc
                ni = L2 * A + r
                if ng < dist[ni]:
                    dist[ni] = ng
                    par[ni] = idx
                    pdir[ni] = -1
                    sv[ni] = 0 if not th else sv[idx]
                    heapq.heappush(heap, (np.float32(ng), np.int64(ni)))
    if goal < 0:
        return np.zeros(0, dtype=np.int64)
    out = [goal]
    cur = goal
    while par[cur] != -1:
        cur = par[cur]
        out.append(cur)
    res = np.zeros(len(out), dtype=np.int64)
    for i in range(len(out)):
        res[i] = out[len(out) - 1 - i]
    return res


class DS:
    def __init__(self, NY, NX):
        self.d1 = np.full((NL, NY, NX), BIG, np.float32)
        self.n1 = np.full((NL, NY, NX), -1, np.int32)
        self.d2 = np.full((NL, NY, NX), BIG, np.float32)

    def other(self, n, y0, y1, x0, x1):
        return np.where(self.n1[:, y0:y1, x0:x1] == n, self.d2[:, y0:y1, x0:x1], self.d1[:, y0:y1, x0:x1])

    def clear(self, y0, y1, x0, x1):
        self.d1[:, y0:y1, x0:x1] = BIG
        self.n1[:, y0:y1, x0:x1] = -1
        self.d2[:, y0:y1, x0:x1] = BIG


class World:
    def __init__(self, dump, pro=None, soft_inner=True, verbose=True, all_soft=False, hard_pours=False):
        t0 = time.time()
        D = json.load(open(dump)) if isinstance(dump, str) else dump
        self.D = D
        xs = [p[0] for o in D["outline"] for p in o["ring"]]
        ys = [p[1] for o in D["outline"] for p in o["ring"]]
        self.X0, self.Y0 = min(xs) - 0.5, min(ys) - 0.5
        self.NX = int((max(xs) - min(xs) + 1.0) / G) + 2
        self.NY = int((max(ys) - min(ys) + 1.0) / G) + 2
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.netid = {"": -1}
        self.netname = {}
        for nm in sorted(D["netclass"]):
            if nm == "":
                continue
            self.netid[nm] = len(self.netname) + 1
            self.netname[self.netid[nm]] = nm
        self.cls = {self.netid[nm]: c for nm, c in D["netclass"].items() if nm}
        self.hc = {n for n, c in self.cls.items() if "HighCurrent" in c}
        self.small = {n for n, c in self.cls.items() if not any(k in c for k in ("HighCurrent", "Power", "GND", "GateDrive", "Kelvin"))}
        self.soft_ids = {self.netid[n] for n in SOFTNETS if n in self.netid}
        NY, NX = self.NY, self.NX
        self.As, self.Hs, self.Ss = DS(NY, NX), DS(NY, NX), DS(NY, NX)       # static: all copper / HighCurrent non-pad / small-signal non-pad
        self.Ad, self.Hd, self.Sd = DS(NY, NX), DS(NY, NX), DS(NY, NX)       # routed (rip-able)
        self.hole_s = np.full((NY, NX), BIG, np.float32)
        self.hole_d = np.full((NY, NX), BIG, np.float32)
        self.ko_trk = np.zeros((NL, NY, NX), bool)
        self.ko_via = np.zeros((NY, NX), bool)
        self.smd = np.zeros((NY, NX), np.int32)                              # net id + 1 of an SMD pad a via would touch (0 none)
        self.net_items = {}            # net id -> list of static copper items for connectivity
        self.dyn = {}                  # route id -> dict(net, items)
        self.rid = 0
        self.fill_override = None
        self._nonet = 100000
        self.pad_cells = {}
        self.znet = np.full((NL, NY, NX), -1, np.int32)                       # hard pour at this cell: its net (pours give way to tracks)
        self.zdepth = np.zeros((NL, NY, NX), np.float32)                      # how deep inside that pour (mm from its edge)
        self.padnet = np.full((NL, NY, NX), -1, np.int32)                     # pad copper at this cell: its net
        self.hard_nets = set()                                                # nets whose pours may not be crossed at all
        # ---- board edge and outside (as copper of net EDGE_NET, grown so the 0.15 test gives 0.25)
        im = Image.new("1", (NX, NY), 1)
        dr = ImageDraw.Draw(im)
        for o in D["outline"]:
            dr.polygon([self.pix(x, y) for x, y in o["ring"]], fill=0)
            for hh in o["holes"]:
                dr.polygon([self.pix(x, y) for x, y in hh], fill=1)
        outside = np.array(im, dtype=bool)
        self.outside = outside
        dist = ndimage.distance_transform_edt(~outside).astype(np.float32) * G - (EDGE_CLR - CLR) - 0.035
        np.maximum(dist, 0, out=dist)
        for L in range(NL):
            ins_dist(self.As.d1, self.As.n1, self.As.d2, L, 0, 0, dist, EDGE_NET)
        # ---- pads
        for p in D["pads"]:
            n = self.netid.get(p["net"], -1)
            if n == -1:
                self._nonet += 1
                n = self._nonet
            p["_n"] = n
            drill = max(p["drill"])
            lays = range(NL) if drill > 0 else [LAYERS.index(l) for l in p["shapes"]]
            if p["npth"]:
                r = drill / 2 + (EDGE_CLR - CLR)
                for L in range(NL):
                    ins_seg(self.As.d1, self.As.n1, self.As.d2, L, p["x"], p["y"], p["x"], p["y"], r, EDGE_NET, self.X0, self.Y0)
                ins_min_disc(self.hole_s, p["x"], p["y"], drill / 2 + 0.25, self.X0, self.Y0)
                continue
            any_shape = None
            for lname, recs in p["shapes"].items():
                any_shape = recs
            for L in lays:
                recs = p["shapes"].get(LAYERS[L], any_shape if drill > 0 else None)
                if not recs:
                    continue
                for rec in recs:
                    xs_ = np.array([q[0] for q in rec["ring"]], dtype=np.float64)
                    ys_ = np.array([q[1] for q in rec["ring"]], dtype=np.float64)
                    if len(xs_) >= 3:
                        ins_poly(self.As.d1, self.As.n1, self.As.d2, L, xs_, ys_, n, self.X0, self.Y0, 0.0)
                        bx0, by0 = self.cell(xs_.min(), ys_.min()); bx1, by1 = self.cell(xs_.max(), ys_.max())
                        bx0 = max(bx0 - 1, 0); by0 = max(by0 - 1, 0); bx1 = min(bx1 + 2, NX); by1 = min(by1 + 2, NY)
                        if bx1 > bx0 and by1 > by0:
                            pm = self._fill_mask([dict(ring=list(zip(xs_, ys_)), holes=[])], bx0, by0, bx1 - bx0, by1 - by0)
                            self.padnet[L, by0:by1, bx0:bx1][pm] = n
                        self.net_items.setdefault(n, []).append(("P", L, xs_, ys_, p["ref"], p["num"]))
            if drill > 0:
                ins_min_disc(self.hole_s, p["x"], p["y"], drill / 2 + (0.25 if drill >= 0.5 else 0.0), self.X0, self.Y0)
                self.net_items.setdefault(n, []).append(("H", -1, p["x"], p["y"], drill, p["ref"], p["num"]))
            else:
                b = p["box"]
                if min(b[2] - b[0], b[3] - b[1]) <= 1.6:
                    m = VIA_D / 2 + 0.02
                    cx0, cy0 = self.cell(b[0] - m, b[1] - m)
                    cx1, cy1 = self.cell(b[2] + m, b[3] + m)
                    self.smd[max(cy0, 0):cy1 + 1, max(cx0, 0):cx1 + 1] = n + 1
        # ---- zones
        self.soft_fill = {}            # net id -> [(L, polys)] soft pours (not obstacles; reached by via / track end)
        for z in D["zones"]:
            n = self.netid.get(z["net"], -1)
            L = LAYERS.index(z["layer"])
            soft = z["net"] in SOFTNETS and ((soft_inner and 0 < L < NL - 1) or z["prio"] == 0 or z["name"].startswith("plane_"))
            z["_soft"] = soft
            if soft or all_soft:
                self.soft_fill.setdefault(n, []).append((L, z["fill"]))
                continue
            self.net_items.setdefault(n, []).append(("Z", L, z["fill"]))
            if hard_pours:
                self._ins_fill(self.As, L, z["fill"], n)
                if n in self.hc:
                    self._ins_fill(self.Hs, L, z["fill"], n)
            else:
                bb = self._poly_bbox(z["fill"], 0.1)
                if bb is not None:
                    zx0, zy0, zx1, zy1 = bb
                    m = self._fill_mask(z["fill"], zx0, zy0, zx1 - zx0, zy1 - zy0)
                    if m.any():
                        dep = ndimage.distance_transform_edt(m).astype(np.float32) * G
                        self.znet[L, zy0:zy1, zx0:zx1][m] = n
                        zd = self.zdepth[L, zy0:zy1, zx0:zx1]
                        zd[m] = dep[m]
        # ---- keep-outs
        for k in D["keepouts"]:
            if not (k["no_tracks"] or k["no_vias"]):
                continue
            im = Image.new("1", (NX, NY), 0)
            dr = ImageDraw.Draw(im)
            for pl in k["poly"]:
                dr.polygon([self.pix(x, y) for x, y in pl["ring"]], fill=1)
            m = np.array(im, dtype=bool)
            mt = ndimage.binary_dilation(m, iterations=4)          # 0.2 mm: track half width + margin
            mv = ndimage.binary_dilation(m, iterations=6)
            for lname in k["layers"]:
                if k["no_tracks"]:
                    self.ko_trk[LAYERS.index(lname)] |= mt
            if k["no_vias"]:
                self.ko_via |= mv
        # ---- static tracks and vias (the copper plan's)
        for t in D["tracks"]:
            if t["layer"] not in LAYERS:
                continue
            self._ins_track(self.netid.get(t["net"], -1), LAYERS.index(t["layer"]), t["a"], t["b"], t["w"], static=True)
        for v in D["vias"]:
            self._ins_via(self.netid.get(v["net"], -1), v["x"], v["y"], v["size"], v["drill"], static=True)
        if verbose:
            print("world: %d x %d cells, %d nets, built in %.1f s" % (NX, NY, len(self.netname), time.time() - t0), flush=True)

    # ---------------------------------------------------------------- helpers
    def pix(self, x, y):
        return ((x - self.X0) / G + 0.5, (y - self.Y0) / G + 0.5)

    def cell(self, x, y):
        return int(round((x - self.X0) / G)), int(round((y - self.Y0) / G))

    def xy(self, cx, cy):
        return round(self.X0 + cx * G, 4), round(self.Y0 + cy * G, 4)

    def _fill_mask(self, polys, x0, y0, w, h):
        im = Image.new("1", (w, h), 0)
        dr = ImageDraw.Draw(im)
        for pl in polys:
            if len(pl["ring"]) >= 3:
                dr.polygon([((x - self.X0) / G + 0.5 - x0, (y - self.Y0) / G + 0.5 - y0) for x, y in pl["ring"]], fill=1)
            for hh in pl["holes"]:
                if len(hh) >= 3:
                    dr.polygon([((x - self.X0) / G + 0.5 - x0, (y - self.Y0) / G + 0.5 - y0) for x, y in hh], fill=0)
        return np.array(im, dtype=bool)

    def _poly_bbox(self, polys, margin):
        xs = [q[0] for pl in polys for q in pl["ring"]]
        ys = [q[1] for pl in polys for q in pl["ring"]]
        if not xs:
            return None
        cx0, cy0 = self.cell(min(xs) - margin, min(ys) - margin)
        cx1, cy1 = self.cell(max(xs) + margin, max(ys) + margin)
        return max(cx0, 0), max(cy0, 0), min(cx1 + 1, self.NX), min(cy1 + 1, self.NY)

    def _ins_fill(self, ds, L, polys, n):
        bb = self._poly_bbox(polys, DMAX + 0.1)
        if bb is None:
            return
        x0, y0, x1, y1 = bb
        m = self._fill_mask(polys, x0, y0, x1 - x0, y1 - y0)
        if not m.any():
            return
        dist = ndimage.distance_transform_edt(~m).astype(np.float32) * G - 0.035
        np.maximum(dist, 0, out=dist)
        ins_dist(ds.d1, ds.n1, ds.d2, L, y0, x0, dist, n)

    def _ins_track(self, n, L, a, b, w, static=False, rid=None):
        A, H, S = (self.As, self.Hs, self.Ss) if static else (self.Ad, self.Hd, self.Sd)
        ins_seg(A.d1, A.n1, A.d2, L, a[0], a[1], b[0], b[1], w / 2, n, self.X0, self.Y0)
        if n in self.hc:
            ins_seg(H.d1, H.n1, H.d2, L, a[0], a[1], b[0], b[1], w / 2, n, self.X0, self.Y0)
        elif n in self.small:
            ins_seg(S.d1, S.n1, S.d2, L, a[0], a[1], b[0], b[1], w / 2, n, self.X0, self.Y0)
        it = ("T", L, a[0], a[1], b[0], b[1], w)
        if static:
            self.net_items.setdefault(n, []).append(it)
        return it

    def _ins_via(self, n, x, y, size, drill, static=False):
        A, H, S = (self.As, self.Hs, self.Ss) if static else (self.Ad, self.Hd, self.Sd)
        for L in range(NL):
            ins_seg(A.d1, A.n1, A.d2, L, x, y, x, y, size / 2, n, self.X0, self.Y0)
            if n in self.hc:
                ins_seg(H.d1, H.n1, H.d2, L, x, y, x, y, size / 2, n, self.X0, self.Y0)
            elif n in self.small:
                ins_seg(S.d1, S.n1, S.d2, L, x, y, x, y, size / 2, n, self.X0, self.Y0)
        ins_min_disc(self.hole_s if static else self.hole_d, x, y, drill / 2, self.X0, self.Y0)
        it = ("V", -1, x, y, size, drill)
        if static:
            self.net_items.setdefault(n, []).append(it)
        return it

    # ---------------------------------------------------------------- routed copper
    def add_route(self, n, items, meta=None):
        """items: ("T", L, ax, ay, bx, by, w) / ("V", -1, x, y, size, drill). Returns the route id."""
        self.rid += 1
        for it in items:
            if it[0] == "T":
                self._ins_track(n, it[1], (it[2], it[3]), (it[4], it[5]), it[6])
            else:
                self._ins_via(n, it[2], it[3], it[4], it[5])
        self.dyn[self.rid] = dict(net=n, items=list(items), meta=meta or {})
        return self.rid

    def snapshot(self):
        return dict(self.dyn)

    def restore(self, snap):
        """Put the routed copper back to a snapshot."""
        self.rip([r for r in self.dyn if r not in snap or self.dyn[r] is not snap[r]])
        for r, rec in snap.items():
            if r not in self.dyn:
                for it in rec["items"]:
                    if it[0] == "T":
                        self._ins_track(rec["net"], it[1], (it[2], it[3]), (it[4], it[5]), it[6])
                    else:
                        self._ins_via(rec["net"], it[2], it[3], it[4], it[5])
                self.dyn[r] = rec

    def _items_bbox(self, items, margin):
        xs, ys = [], []
        for it in items:
            if it[0] == "T":
                xs += [it[2], it[4]]; ys += [it[3], it[5]]
            else:
                xs.append(it[2]); ys.append(it[3])
        cx0, cy0 = self.cell(min(xs) - margin, min(ys) - margin)
        cx1, cy1 = self.cell(max(xs) + margin, max(ys) + margin)
        return max(cx0, 0), max(cy0, 0), min(cx1 + 1, self.NX), min(cy1 + 1, self.NY)

    def rip(self, rids):
        """Remove routes; rebuild the routed stores in the area they touched."""
        gone = [self.dyn.pop(r) for r in rids if r in self.dyn]
        if not gone:
            return
        boxes = [self._items_bbox(g["items"], DMAX + 0.4) for g in gone]
        for (x0, y0, x1, y1) in boxes:
            for ds in (self.Ad, self.Hd, self.Sd):
                ds.clear(y0, y1, x0, x1)
            self.hole_d[y0:y1, x0:x1] = BIG
        # re-insert every remaining routed item that reaches into a cleared box (inserting twice is harmless: min)
        for r, rec in self.dyn.items():
            bb = self._items_bbox(rec["items"], DMAX + 0.4)
            if not any(bb[0] < b[2] and bb[2] > b[0] and bb[1] < b[3] and bb[3] > b[1] for b in boxes):
                continue
            for it in rec["items"]:
                if it[0] == "T":
                    self._ins_track(rec["net"], it[1], (it[2], it[3]), (it[4], it[5]), it[6])
                else:
                    self._ins_via(rec["net"], it[2], it[3], it[4], it[5])

    # ---------------------------------------------------------------- connectivity
    def net_window(self, n, margin=3.0):
        xs, ys = [], []
        for it in self.all_items(n):
            if it[0] == "P":
                xs += [it[2].min(), it[2].max()]; ys += [it[3].min(), it[3].max()]
            elif it[0] == "T":
                xs += [it[2], it[4]]; ys += [it[3], it[5]]
            elif it[0] in ("V", "H"):
                xs.append(it[2]); ys.append(it[3])
            elif it[0] == "Z":
                for pl in it[2]:
                    xs += [q[0] for q in pl["ring"]]; ys += [q[1] for q in pl["ring"]]
        if not xs:
            return None
        cx0, cy0 = self.cell(min(xs) - margin, min(ys) - margin)
        cx1, cy1 = self.cell(max(xs) + margin, max(ys) + margin)
        return max(cx0, 0), max(cy0, 0), min(cx1 + 1, self.NX), min(cy1 + 1, self.NY)

    def all_items(self, n, with_soft=True):
        out = list(self.net_items.get(n, []))
        for rec in self.dyn.values():
            if rec["net"] == n:
                out += rec["items"]
        if with_soft:
            src = self.fill_override if self.fill_override is not None else self.soft_fill
            for L, polys in src.get(n, []):
                out.append(("Z", L, polys))
        return out

    def net_copper(self, n, win):
        """Boolean copper of net n in the window: [NL, h, w], plus the list of through points (vias, plated holes)."""
        x0, y0, x1, y1 = win
        w, h = x1 - x0, y1 - y0
        cu = np.zeros((NL, h, w), np.uint8)
        zcu = np.zeros((NL, h, w), np.uint8)
        thr = []
        X0w, Y0w = self.X0 + x0 * G, self.Y0 + y0 * G
        for it in self.all_items(n):
            if it[0] == "P":
                im = Image.new("1", (w, h), 0)
                ImageDraw.Draw(im).polygon([((x - X0w) / G + 0.5, (y - Y0w) / G + 0.5) for x, y in zip(it[2], it[3])], fill=1)
                cu[it[1]] |= np.array(im, dtype=np.uint8)
            elif it[0] == "T":
                paint_seg(cu[it[1]], it[2], it[3], it[4], it[5], max(it[6] / 2 - 0.02, 0.03), X0w, Y0w, 1)
            elif it[0] == "V":
                for L in range(NL):
                    paint_seg(cu[L], it[2], it[3], it[2], it[3], it[4] / 2 - 0.02, X0w, Y0w, 1)
                thr.append((it[2], it[3]))
            elif it[0] == "H":
                thr.append((it[2], it[3]))
            elif it[0] == "Z":
                zm = self._fill_mask(it[2], x0, y0, w, h)
                zm &= self.zone_ok(n, it[1], win)
                zcu[it[1]] |= zm.astype(np.uint8)
        self._zonly = zcu & ~cu                       # cells that are copper only by a pour
        self._zall = zcu
        cu |= zcu
        return cu, thr

    def zone_ok(self, n, L, win):
        """Cells of layer L where a pour of net n survives next to the routed copper of other nets."""
        x0, y0, x1, y1 = win
        ok = np.where(self.Ad.n1[L, y0:y1, x0:x1] == n, self.Ad.d2[L, y0:y1, x0:x1], self.Ad.d1[L, y0:y1, x0:x1]) >= ZCLR + 0.02
        if n in self.hc:
            ok &= np.where(self.Sd.n1[L, y0:y1, x0:x1] == n, self.Sd.d2[L, y0:y1, x0:x1], self.Sd.d1[L, y0:y1, x0:x1]) >= HC_CLR + 0.02
        return ok

    def pieces(self, n, win=None):
        """Label the connected pieces of net n. Returns (win, lab[NL, h, w] int32 (0 none), number of pieces, cu, thr)."""
        win = win or self.net_window(n)
        cu, thr = self.net_copper(n, win)
        x0, y0, x1, y1 = win
        lab = np.zeros(cu.shape, np.int32)
        base = 0
        st = np.ones((3, 3), int)
        for L in range(NL):
            l, k = ndimage.label(cu[L], structure=st)
            l[l > 0] += base
            lab[L] = l
            base += k
        parent = list(range(base + 1))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for (vx, vy) in thr:
            cx, cy = self.cell(vx, vy)
            cx -= x0; cy -= y0
            if not (0 <= cx < x1 - x0 and 0 <= cy < y1 - y0):
                continue
            ls = [lab[L, cy, cx] for L in range(NL) if lab[L, cy, cx] > 0]
            for a in ls[1:]:
                ra, rb = find(ls[0]), find(a)
                if ra != rb:
                    parent[ra] = rb
        roots = {}
        remap = np.zeros(base + 1, np.int32)
        for a in range(1, base + 1):
            r = find(a)
            if r not in roots:
                roots[r] = len(roots) + 1
            remap[a] = roots[r]
        lab = remap[lab]
        # a piece made of pour alone is an island the fill drops: not a piece
        k = len(roots)
        real = np.zeros(k + 1, bool)
        real[np.unique(lab[(cu > 0) & (self._zonly == 0)])] = True
        real[0] = True
        if not real.all():
            newid = np.cumsum(real) - 1
            newid[~real] = 0
            lab = newid.astype(np.int32)[lab]
            cu = cu * (lab > 0)
            self._zonly = self._zonly * (lab > 0)
            self._zall = self._zall * (lab > 0)
            k = int(real.sum()) - 1
        return win, lab, k, cu, thr

    # ---------------------------------------------------------------- legality masks
    def masks(self, n, win, hw, ghost=False):
        """free (straight), freed (diagonal) for a track of half width hw; vfree for a new via. With ghost=True the
        routed copper is ignored and returned separately as blocked-by-routes masks."""
        x0, y0, x1, y1 = win
        os_ = self.As.other(n, y0, y1, x0, x1)
        od = self.Ad.other(n, y0, y1, x0, x1)
        need = CLR + hw
        if n in self.small:
            hs = self.Hs.other(n, y0, y1, x0, x1) - (HC_CLR - CLR)
            hd = self.Hd.other(n, y0, y1, x0, x1) - (HC_CLR - CLR)
            os_ = np.minimum(os_, hs); od = np.minimum(od, hd)
        elif n in self.hc:
            ss = self.Ss.other(n, y0, y1, x0, x1) - (HC_CLR - CLR)
            sd = self.Sd.other(n, y0, y1, x0, x1) - (HC_CLR - CLR)
            os_ = np.minimum(os_, ss); od = np.minimum(od, sd)
        ko = self.ko_trk[:, y0:y1, x0:x1]
        fs = (os_ >= need + TOL_O) & ~ko
        fsd = (os_ >= need + TOL_D) & ~ko
        bd = od < need + TOL_O
        bdd = od < need + TOL_D
        vneed = CLR + VIA_D / 2 + TOL_O
        vs = (os_.min(axis=0) >= vneed) & ~self.ko_via[y0:y1, x0:x1] & (self.hole_s[y0:y1, x0:x1] >= 0.2 + VIA_DRILL / 2 + TOL_O)
        sm = self.smd[y0:y1, x0:x1]
        vs &= (sm == 0)
        vbd = (od.min(axis=0) < vneed) | (self.hole_d[y0:y1, x0:x1] < 0.2 + VIA_DRILL / 2 + TOL_O)
        if ghost:
            return fs, fsd, vs, bd, bdd, vbd
        return fs & ~bd, fsd & ~bdd, vs & ~vbd, None, None, None

    # ---------------------------------------------------------------- one connection
    def connect(self, n, src_piece=None, w=0.2, layers=(0, 2, 3, 5), ghost=False, margin=4.0, via_cost=60.0, bend=3.0,
                lcost=(1.25, 9, 1.0, 1.0, 9, 1.35), pref=(0, 0, 1, 2, 0, 0), hist=None, win=None, maxn=6000000, neck=0.15,
                only_target=None, allow_padvia=False, extra_pen=None, zcost=(0.5, 12.0), narrow_pen=0.6):
        """Join piece src_piece of net n (default: its smallest piece) to any other piece. Returns dict(items, cells, ...)
        or None. With ghost=True routed copper of other nets may be crossed at a price; the result lists the crossed
        route ids in 'blockers' and nothing is added."""
        win0 = self.net_window(n, margin)
        if win0 is None:
            return None
        win = win or win0
        win, lab, k, cu, thr = self.pieces(n, win)
        zonly = self._zonly
        if k < 2:
            return dict(done=True)
        x0, y0, x1, y1 = win
        h, wd = y1 - y0, x1 - x0
        # a track must end inside a pour, not on its rim: pour-only cells within 0.1 mm of the pour's edge are no ends
        zrim = np.zeros(zonly.shape, bool)
        for L in range(NL):
            if zonly[L].any():
                zrim[L] = zonly[L].astype(bool) & ~ndimage.binary_erosion(self._zall[L].astype(bool) | (cu[L] > 0), iterations=3)
        sizes = np.bincount(lab.ravel(), minlength=k + 1)
        if src_piece is None:
            src_piece = int(np.argmin(np.where(np.arange(k + 1) == 0, 10 ** 12, sizes)))
        hw_n = neck / 2
        fs, fsd, vs, bd, bdd, vbd = self.masks(n, win, hw_n, ghost)
        f2 = self.masks(n, win, w / 2, ghost)[0] if w / 2 > hw_n + 1e-9 else fs
        if allow_padvia:
            sm = self.smd[y0:y1, x0:x1]
            vs2 = self.masks(n, win, hw_n, ghost)[2]
            # a via in an own-net pad: allowed on request
            os_ = self.As.other(n, y0, y1, x0, x1)
            vneed = CLR + VIA_D / 2 + TOL_O
            own = (sm == n + 1) & (os_.min(axis=0) >= vneed) & ~self.ko_via[y0:y1, x0:x1] & (self.hole_s[y0:y1, x0:x1] >= 0.2 + VIA_DRILL / 2 + TOL_O)
            if not ghost:
                own &= ~((self.Ad.other(n, y0, y1, x0, x1).min(axis=0) < vneed) | (self.hole_d[y0:y1, x0:x1] < 0.2 + VIA_DRILL / 2 + TOL_O))
            vs = vs | own
        src_mask = (lab == src_piece)
        tgt = ((lab > 0) & ~src_mask) & ~zrim
        if only_target is not None:
            tgt &= np.isin(lab, list(only_target) if hasattr(only_target, "__iter__") else [only_target])
        # a track must end well inside a pour: targets on pours are trimmed by the raster (they are cell centres inside copper)
        routable = np.zeros(NL, np.uint8)
        for L in layers:
            routable[L] = 1
        # tracks may only end on copper that is on a routable layer, or reach any layer's copper by a via (through / new)
        through = np.zeros((h, wd), np.uint8)
        for (vx, vy) in thr:
            cx, cy = self.cell(vx, vy)
            if 0 <= cx - x0 < wd and 0 <= cy - y0 < h:
                through[cy - y0, cx - x0] = 1
        pen = np.zeros((NL, h, wd), np.float32)
        pen += np.where(f2, 0.0, narrow_pen).astype(np.float32)      # prefer room for the full width
        vpen = np.zeros((h, wd), np.float32)
        if hist is not None:
            pen += hist[:, y0:y1, x0:x1]
        if extra_pen is not None:
            pen += extra_pen[:, y0:y1, x0:x1]
        if ghost:
            pen += np.where(bd, 25.0, 0.0).astype(np.float32)
            vpen += np.where(vbd, 150.0, 0.0).astype(np.float32)
        # other nets' pours give way to a track, at a price that grows with the depth into the pour
        zn = self.znet[:, y0:y1, x0:x1]
        zo = (zn >= 0) & (zn != n)
        zd = np.minimum(self.zdepth[:, y0:y1, x0:x1], 1.2)
        zp = np.where(zo, zcost[0] + zcost[1] * zd * zd, 0.0).astype(np.float32)
        if self.hard_nets:
            zp[np.isin(zn, list(self.hard_nets)) & zo] = 5000.0
        pen += zp
        vpen += 4.0 * zp.sum(axis=0)
        free = fs.astype(np.uint8)
        freed = fsd.astype(np.uint8)
        sidx = np.flatnonzero((src_mask & ~zrim).ravel())
        if len(sidx) == 0:
            return None
        tg = tgt.astype(np.uint8)
        A = h * wd
        for attempt in range(5):
            path = dijkstra(free, freed, vs.astype(np.uint8), tg, through, pen, vpen, sidx.astype(np.int64), routable,
                            np.array(pref, np.int64), np.array(lcost, np.float64), via_cost, bend, 16, maxn)
            if len(path) == 0:
                return None
            cells = [(int(p // A), int((p % A) // wd) + y0, int((p % A) % wd) + x0) for p in path]
            if ghost:
                break
            items = self.emit(n, cells, w, neck, f2, win, through)
            cut = self.cuts_pour(n, items)
            if cut is None:
                break
            M, Lc, (bx0, by0, bx1, by1) = cut
            # that pour may not be crossed here: price it out around the cut and look again
            sub = pen[Lc, max(by0 - y0, 0):by1 - y0, max(bx0 - x0, 0):bx1 - x0]
            sub[zn[Lc, max(by0 - y0, 0):by1 - y0, max(bx0 - x0, 0):bx1 - x0] == M] += 800.0
            vsub = vpen[max(by0 - y0, 0):by1 - y0, max(bx0 - x0, 0):bx1 - x0]
            vsub[zn[Lc, max(by0 - y0, 0):by1 - y0, max(bx0 - x0, 0):bx1 - x0] == M] += 3000.0
        else:
            return None
        res = dict(cells=cells, src_piece=src_piece, pieces=k)
        if ghost:
            hit = set()
            for (L, cy, cx) in cells:
                if bd[L, cy - y0, cx - x0]:
                    hit.add((L, cy, cx))
            vias = [(cells[i][1], cells[i][2]) for i in range(1, len(cells)) if cells[i][0] != cells[i - 1][0]]
            res["blockers"] = self.routes_near(n, cells, vias, hw_n)
            return res
        res["items"] = items
        return res

    def cuts_pour(self, n, items, margin=2.0, min_cells=150):
        """Would this route split a hard pour of another net (or cut one of that net's pads off its pour)?
        Looks at each crossed pour layer by layer in a window round the route. Returns (net, layer, window) or None."""
        x0, y0, x1, y1 = self._items_bbox(items, margin)
        h, w = y1 - y0, x1 - x0
        X0w, Y0w = self.X0 + x0 * G, self.Y0 + y0 * G
        zn = self.znet[:, y0:y1, x0:x1]
        halo = np.zeros((NL, h, w), np.uint8)
        halo2 = np.zeros((NL, h, w), np.uint8)
        for it in items:
            if it[0] == "T":
                paint_seg(halo[it[1]], it[2], it[3], it[4], it[5], it[6] / 2 + ZCLR + 0.03, X0w, Y0w, 1)
                paint_seg(halo2[it[1]], it[2], it[3], it[4], it[5], it[6] / 2 + HC_CLR + 0.03, X0w, Y0w, 1)
            else:
                for L in range(NL):
                    paint_seg(halo[L], it[2], it[3], it[2], it[3], it[4] / 2 + ZCLR + 0.03, X0w, Y0w, 1)
                    paint_seg(halo2[L], it[2], it[3], it[2], it[3], it[4] / 2 + HC_CLR + 0.03, X0w, Y0w, 1)
        st = np.ones((3, 3), int)
        for L in range(NL):
            hit = zn[L][(halo2[L] > 0) & (zn[L] >= 0) & (zn[L] != n)]
            if len(hit) == 0:
                continue
            for M in np.unique(hit):
                M = int(M)
                hl = halo2[L] if (M in self.hc and n in self.small) else halo[L]
                if not ((zn[L] == M) & (hl > 0)).any():
                    continue
                pads = self.padnet[L, y0:y1, x0:x1] == M
                base = ((zn[L] == M) & self.zone_ok(M, L, (x0, y0, x1, y1))) | pads

                def count(mask):
                    lab, k = ndimage.label(mask, structure=st)
                    if k == 0:
                        return 0
                    sz = np.bincount(lab.ravel(), minlength=k + 1)
                    hasp = np.zeros(k + 1, bool)
                    hasp[np.unique(lab[pads])] = True
                    return int(((sz >= min_cells) | hasp)[1:].sum())
                if count(base & ~((hl > 0) & ~pads)) > count(base):
                    return M, L, (x0, y0, x1, y1)
        return None

    def routes_near(self, n, cells, vias, hw):
        """Route ids of other nets whose copper is closer than the clearance to this path."""
        out = set()
        pts = {}
        for (L, cy, cx) in cells:
            pts.setdefault(L, []).append((self.X0 + cx * G, self.Y0 + cy * G))
        vpts = [(self.X0 + cx * G, self.Y0 + cy * G) for cy, cx in vias]
        for rid, rec in self.dyn.items():
            if rec["net"] == n:
                continue
            extra = (HC_CLR - CLR) if ((n in self.small and rec["net"] in self.hc) or (n in self.hc and rec["net"] in self.small)) else 0.0
            bb = self._items_bbox(rec["items"], 1.0)
            near = False
            for it in rec["items"]:
                if it[0] == "T":
                    need = CLR + hw + it[6] / 2 + TOL_O + extra
                    for (px, py) in pts.get(it[1], ()):
                        if _segd(it[2], it[3], it[4], it[5], px, py) < need:
                            near = True; break
                    if not near:
                        for (px, py) in vpts:
                            if _segd(it[2], it[3], it[4], it[5], px, py) < CLR + VIA_D / 2 + it[6] / 2 + TOL_O + extra:
                                near = True; break
                else:
                    need = CLR + hw + it[4] / 2 + TOL_O + extra
                    for L2, pl in pts.items():
                        for (px, py) in pl:
                            if math.hypot(px - it[2], py - it[3]) < need:
                                near = True; break
                        if near:
                            break
                    if not near:
                        for (px, py) in vpts:
                            if math.hypot(px - it[2], py - it[3]) < max(CLR + VIA_D / 2 + it[4] / 2, 0.2 + VIA_DRILL) + TOL_O + extra:
                                near = True; break
                if near:
                    break
            if near:
                out.add(rid)
        return out

    def emit(self, n, cells, w, neck, f2, win, through):
        """Cells -> tracks (straight runs merged, one width per run) and vias."""
        x0, y0, x1, y1 = win
        items = []
        runs = []            # (L, [cells])
        cur = [cells[0]]
        for c in cells[1:]:
            if c[0] != cur[-1][0]:
                runs.append(cur)
                # layer change at this (x, y)
                if not through[c[1] - y0, c[2] - x0]:
                    if not any(it[0] == "V" and abs(it[2] - (self.X0 + c[2] * G)) < 1e-6 and abs(it[3] - (self.Y0 + c[1] * G)) < 1e-6 for it in items):
                        items.append(("V", -1, round(self.X0 + c[2] * G, 4), round(self.Y0 + c[1] * G, 4), VIA_D, VIA_DRILL))
                cur = [c]
            else:
                cur.append(c)
        runs.append(cur)
        segs = []
        for run in runs:
            if len(run) < 2:
                continue
            L = run[0][0]
            i = 0
            while i < len(run) - 1:
                dy, dx = run[i + 1][1] - run[i][1], run[i + 1][2] - run[i][2]
                j = i + 1
                while j + 1 < len(run) and (run[j + 1][1] - run[j][1], run[j + 1][2] - run[j][2]) == (dy, dx):
                    j += 1
                wide = all(f2[L, run[k][1] - y0, run[k][2] - x0] for k in range(i, j + 1))
                segs.append([L, run[i], run[j], wide, math.hypot(dy, dx) * (j - i) * G])
                i = j
        tot = sum(s[4] for s in segs) or 1.0
        narrow = sum(s[4] for s in segs if not s[3])
        allnarrow = narrow > 0.5 * tot
        for L, a, b, wide, ln in segs:
            ww = w if (wide and not allnarrow) else neck
            items.append(("T", L, round(self.X0 + a[2] * G, 4), round(self.Y0 + a[1] * G, 4), round(self.X0 + b[2] * G, 4), round(self.Y0 + b[1] * G, 4), ww))
        return items


@njit(cache=True)
def _segd(ax, ay, bx, by, px, py):
    dx = bx - ax
    dy = by - ay
    LL = dx * dx + dy * dy
    t = 0.0
    if LL > 0:
        t = ((px - ax) * dx + (py - ay) * dy) / LL
        if t < 0:
            t = 0.0
        elif t > 1:
            t = 1.0
    ex = px - (ax + t * dx)
    ey = py - (ay + t * dy)
    return math.sqrt(ex * ex + ey * ey)


@njit(cache=True)
def flood(free, freed, vfree, through, src, routable):
    """Cells a route from src can reach at all (no costs). Returns reached[NL, h, w] uint8."""
    nl, h, w = free.shape
    A = h * w
    seen = np.zeros(nl * A, np.uint8)
    stack = [np.int64(0)]
    stack.pop()
    for s in src:
        seen[s] = 1
        stack.append(np.int64(s))
    DX = np.array([1, -1, 0, 0, 1, 1, -1, -1])
    DY = np.array([0, 0, 1, -1, 1, -1, 1, -1])
    while len(stack) > 0:
        idx = stack.pop()
        L = idx // A
        r = idx - L * A
        y = r // w
        x = r - y * w
        if routable[L]:
            for k in range(8):
                X = x + DX[k]
                Y = y + DY[k]
                if X < 0 or Y < 0 or X >= w or Y >= h or not free[L, Y, X]:
                    continue
                if k >= 4 and not (freed[L, y, x] and freed[L, Y, X]):
                    continue
                ni = L * A + Y * w + X
                if not seen[ni]:
                    seen[ni] = 1
                    stack.append(np.int64(ni))
        if through[y, x] or (vfree[y, x] and free[L, y, x]):
            for L2 in range(nl):
                if L2 != L and routable[L2] and free[L2, y, x]:
                    ni = L2 * A + r
                    if not seen[ni]:
                        seen[ni] = 1
                        stack.append(np.int64(ni))
    return seen.reshape((nl, h, w))


def why(W, n, piece, layers=(0, 2, 3, 5), hw=0.075, ghost=True, margin=4.0):
    """Text diagnosis of a piece that cannot be joined: how far can a track get from it."""
    win = W.net_window(n, margin)
    win, lab, k, cu, thr = W.pieces(n, win)
    x0, y0, x1, y1 = win
    fs, fsd, vs, bd, bdd, vbd = W.masks(n, win, hw, ghost)
    routable = np.zeros(NL, np.uint8)
    for L in layers:
        routable[L] = 1
    through = np.zeros(fs.shape[1:], np.uint8)
    for (vx, vy) in thr:
        cx, cy = W.cell(vx, vy)
        if 0 <= cx - x0 < x1 - x0 and 0 <= cy - y0 < y1 - y0:
            through[cy - y0, cx - x0] = 1
    src = np.flatnonzero((lab == piece).ravel()).astype(np.int64)
    r = flood(fs.astype(np.uint8), fsd.astype(np.uint8), vs.astype(np.uint8), through, src, routable)
    out = []
    for L in layers:
        ys, xs = np.nonzero(r[L] & ~(lab[L] == piece))
        if len(xs) == 0:
            out.append("%s: stuck on its own copper" % LAYERS[L])
        else:
            a = W.xy(xs.min() + x0, ys.min() + y0)
            b = W.xy(xs.max() + x0, ys.max() + y0)
            out.append("%s: reaches %d cells, x %.1f..%.1f y %.1f..%.1f" % (LAYERS[L], len(xs), a[0], b[0], a[1], b[1]))
    sy, sx = np.nonzero((lab == piece).any(axis=0))
    return "piece %d at (%.1f, %.1f): " % (piece, *W.xy(int(sx.mean()) + x0, int(sy.mean()) + y0)) + "; ".join(out)
