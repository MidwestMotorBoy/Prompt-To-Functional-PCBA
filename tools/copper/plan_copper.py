"""plan_copper.py <cu_dump.json of the placed bare board> <constraints.json> <out spec.json> [intent.json] [--escape=0.4] [--mirror=3] [--grow=1.5]
Power copper for a placed board, generated from the circuit code: no coordinates typed by hand, the same rules on
every placement. Writes a spec (zones, vias, tracks) that write_copper.py puts into the board.

What it draws, in this order (each step sees the copper of the steps before as obstacles):
 1. Return planes: the return net (the hot loops' ret, GND) as a solid pour on the two layers next to the outer
    layers, over the whole outline. The router may cut through them (soft), KiCad refills around its tracks.
 2. Hot loops, then switch nodes (power nets of kind switching): for each declared hot loop, on the switch part's layer, a supply pour and a return pour over the
    loop's pads (the rule copper the floorplan stage scored, stage_copper.py), cut back from other nets' pads; return
    vias at every capacitor and at the switch's return pads.
 3. Power nets, highest current first. Terminals and currents come from roles.py.
      local net  (its terminals within BUS_SPAN_MM): a copper tree on the outer layer that holds most of its
                 terminal current. Terminals are joined one at a time, nearest first, by a shortest path on a
                 0.1 mm grid. The path is as wide as the current needs (roles.width_mm) where there is room, and
                 narrows where there is not (a pin of a fine-pitch IC). Terminals on the other outer layer get a via
                 array (1 A per via) and join the tree through it. A terminal with no path on the tree's layer
                 gets a detour: vias at the pad, a corridor on the other outer layer, vias down into the tree.
      bus net    (terminals spread wider): a pour on the next free inner layer over the terminals' hull, and a via
                 array plus a short pour at every terminal. Soft, like the planes.
 4. Return pads: every pad of the return net that no pour already serves gets vias (1 A each, at least one) and a
    short track to them.
 5. --mirror=A: every non-switching power net of at least A amps gets a copy of its outer-layer copper on the other
    outer layer wherever that is free, stitched by vias next to each terminal it reaches (the layers share the
    current; on the Monolith hand placement this halves CELL_P's drop). Switch nodes are left out: their area is
    the noise antenna.
 6. --grow=MM: all power copper on the outer layers grows into the room that is left, in 0.5 mm rounds so that
    neighbouring nets share it, keeping the escape room at signal pads and out of keep-outs and lanes.

Escape room: power copper on an outer layer keeps ESCAPE mm more than the clearance from every pad of a signal
net, so a 0.2 mm track can still leave that pad (spike 4: 20 of 23 router failures were pads walled in by pours).
Within NEAR_TERM_MM of the net's own terminal pads only the clearance applies, or a fine-pitch power pin could not
be reached at all. Lanes declared in the intent file (intent["lanes"]: layers, points, width_mm) are kept free of
power copper.

What it does not do yet: grow copper where the DC solver shows crowding (SPROUT: --grow is blind to where the
current flows), Kelvin taps (left to the router,
which must land them on the resistor pads), gate-drive geometry, thermal relief choices (all pads connect solid)."""
import sys, os, json, math, heapq, time
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, mapping
from shapely.ops import unary_union
from shapely import affinity
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles import Design, poly, width_mm, vias_for
try:
    from numba import njit
except ImportError:
    njit = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))

RES = 0.1            # mm, planning grid
EDGE_MM = 0.3        # copper to board edge (JLCPCB minimum, pcb-layout skill references/dfm-jlcpcb.md)
VIA_D, VIA_DRILL = 0.45, 0.3     # the via the Monolith rules allow and the floorplan stage used
VIA_PITCH = 0.75     # centre to centre within an array: 0.3 mm of copper between pads
MIN_W = 0.3          # narrowest power path
FINE_PAD_MM = 0.7    # a pad this narrow or less may be left along its own axis at the pins' own spacing
MIN_CLR = 0.15       # never closer than this (the Monolith rules' and JLC's minimum clearance)
SPINE_W = 0.25       # the track laid along every path (see spine())
BUS_SPAN_MM = 25.0   # a net whose terminals spread wider than this, with at least BUS_MIN_TERMINALS of them,
BUS_MIN_TERMINALS = 6   # gets an inner-layer pour
NEAR_TERM_MM = 1.0
HOLE_GAP = 0.25      # drill edge to drill edge (KiCad's default hole-to-hole)
PAD_HOLE_GAP = 0.45  # to a plated pad hole of 0.5 mm or more (Monolith's 'Pad hole spacing' rule)
RAST_MM = 0.1        # margin for the planning raster on via and track clearances
WIDE_COST = 3.0      # extra path cost, per cell, for running narrower than the target width
ROUTER_A = 1.0       # a power net under this current gets no outer-layer copper tree unless it is a bus: a router track
                     # carries it, and a tree would take a strip of the outer layer the length of the net (3V3, 0.5 A,
                     # ran 60 mm along Monolith's edge)
EXIT_MM = 1.2        # exit lane kept for a power pin of an IC with pins of two or more power nets (exits())
DETOUR_MAX_MM = 10.0 # a detour on the other outer layer longer than this is not drawn (it would take the layer). The
                     # hand board takes Port 2's switch node from the half-bridge's enclosed SW pad to the inductor this
                     # way, about 7 mm on B.Cu and In2; seed 9's 20 mm switch-node strips were what Logan rejected
WIND_MAX = 1.5       # a path longer than WIND_MAX x the straight distance + WIND_SLACK_MM is not drawn: the parts are
WIND_SLACK_MM = 3.0  # too far apart or walled in, which is a placement failure, reported, not something to snake around

def rings(g):
    """shapely (Multi)Polygon -> [{'ring','holes'}]"""
    if g.is_empty: return []
    gs = [g] if isinstance(g, Polygon) else [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon)]
    return [dict(ring=[(round(x, 4), round(y, 4)) for x, y in q.exterior.coords[:-1]], holes=[[(round(x, 4), round(y, 4)) for x, y in h.coords[:-1]] for h in q.interiors]) for q in gs if q.area > 0.01]

@njit(cache=True)
def dijkstra(cost, start, goal):
    """8-connected shortest path on a cost grid (inf = blocked), from any start cell to the nearest goal cell."""
    H, W = cost.shape; dist = np.full((H, W), np.inf); prev = np.full((H, W), -1, np.int64)
    hp = [(0.0, np.int64(0))]; hp.pop()
    for i in range(H):
        for j in range(W):
            if start[i, j] and cost[i, j] < np.inf: dist[i, j] = 0.0; hp.append((0.0, np.int64(i * W + j)))
    heapq.heapify(hp)
    di = np.array([-1, 1, 0, 0, -1, -1, 1, 1]); dj = np.array([0, 0, -1, 1, -1, 1, -1, 1]); dl = np.array([1.0, 1.0, 1.0, 1.0, 1.4142, 1.4142, 1.4142, 1.4142])
    end = -1
    while hp:
        d, k = heapq.heappop(hp); i = k // W; j = k % W
        if d > dist[i, j]: continue
        if goal[i, j]: end = k; break
        for t in range(8):
            a = i + di[t]; b = j + dj[t]
            if a < 0 or b < 0 or a >= H or b >= W: continue
            c = cost[a, b]
            if c == np.inf: continue
            nd = d + dl[t] * 0.5 * (c + cost[i, j])
            if nd < dist[a, b]: dist[a, b] = nd; prev[a, b] = k; heapq.heappush(hp, (nd, np.int64(a * W + b)))
    path = []
    while end >= 0: path.append(end); end = prev[end // W, end % W]
    return path

class Planner:
    def __init__(self, dump, cons, intent=None, escape=0.4, grow=0.0, mirror=0.0):
        self.d = Design(dump, cons); D = self.d.D; self.escape = escape; self.grow = grow; self.mirror = mirror
        self.layers = D["layers"]; self.outer = [self.layers[0], self.layers[-1]]
        self.planes = [self.layers[1], self.layers[-2]] if len(self.layers) >= 4 else []
        self.inner_free = [l for l in self.layers[1:-1] if l not in self.planes]
        self.clr = D["clearance_mm"]; st = {s["layer"]: s for s in D["stackup"]}; self.t = {l: st.get(l, {}).get("t_mm", 0.035) for l in self.layers}
        self.board = unary_union([poly(r) for r in D["outline"]]); self.inside = self.board.buffer(-EDGE_MM)
        x0, y0, x1, y1 = self.board.bounds; self.x0, self.y0 = x0 - 1, y0 - 1
        self.W = int((x1 + 1 - self.x0) / RES) + 1; self.H = int((y1 + 1 - self.y0) / RES) + 1
        self.lanes = [(l, LineString(ln["points"]).buffer(ln.get("width_mm", 1.0) / 2)) for ln in (intent or {}).get("lanes", []) for l in ln.get("layers", self.layers)]
        self.zones = {}; self.vias = []; self.tracks = []; self.notes = []; self.report = {}
        self.netid = {n: i for i, n in enumerate(self.d.board_nets)}
        # per-layer obstacle rasters
        self.padnet = {L: np.full((self.H, self.W), -1, np.int32) for L in self.layers}
        self.padpoly = {L: [] for L in self.layers}
        for p in self.d.pads:
            for L, recs in p["shapes"].items():
                if L not in self.padnet: continue
                for r in recs: self.fill(self.padnet[L], Polygon(r["ring"]), self.netid[p["net"]])
                self.padpoly[L].append((p, self.d.pad_poly(p, L)))
        self.npth = [Point(p["x"], p["y"]).buffer(p.get("drill", 0) / 2 + EDGE_MM) for p in D["pads"] if p.get("npth")]      # a hole is an edge
        self.block = {L: ~self.raster(self.inside) for L in self.layers}
        self.novia = np.zeros((self.H, self.W), bool)
        for k in D["keepouts"]:
            g = unary_union([poly(r) for r in k["poly"]])
            if k["no_vias"]: self.novia |= self.raster(g.buffer(VIA_D / 2 + RAST_MM))
            if not (k["no_pours"] or k["no_tracks"]): continue
            for L in k["layers"]:
                if L in self.block: self.block[L] |= self.raster(g)
        self.blockgeom = {L: [g for l2, g in self.lanes if l2 == L] for L in self.layers}
        for k in D["keepouts"]:
            if k["no_pours"] or k["no_tracks"]:
                for L in k["layers"]:
                    if L in self.blockgeom: self.blockgeom[L].append(unary_union([poly(r) for r in k["poly"]]))
        for L, g in self.lanes: self.block[L] |= self.raster(g)
        for h in self.npth:
            for L in self.layers: self.block[L] |= self.raster(h)
        self.cu = {L: np.full((self.H, self.W), -1, np.int32) for L in self.layers}     # generated copper by net
        self.drilled = [(p["x"], p["y"], p["drill"]) for p in D["pads"] if p.get("drill")]
        self.viamap = np.full((self.H, self.W), -1, np.int32)
        self.signal = np.array([self.d.role(n) == "signal" for n in self.d.board_nets])
        self.exits()

    def exits(self):
        """Exit lanes at ICs with pins of two or more power nets: from each such pin on the package edge, a strip
        EXIT_MM outward, kept for that pin's net. Without them the first net's pour can wrap round the IC and wall
        the other off (Monolith round 2: PPHV round the PD chip U401 closed in its VBUS and PP5V pins)."""
        self.reserve = {L: np.full((self.H, self.W), -1, np.int32) for L in self.layers}; n = 0
        by = {}
        for p in self.d.pads:
            if p["ref"].startswith("U"): by.setdefault(p["ref"], []).append(p)
        for ref, ps in by.items():
            pw = {p["net"] for p in ps if p["net"] in self.d.power and self.d.current(p["net"]) >= 1.0 and self.d.role(p["net"]) != "return" and p["net"] not in self.d.ret}
            if len(pw) < 2: continue
            for L in self.outer:
                pp = [(p, self.d.pad_poly(p, L)) for p in ps if L in p["shapes"]]
                if not pp: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp]).bounds
                for p, g in pp:
                    if p["net"] not in pw: continue
                    a0, b0, a1, b1 = g.bounds; e = EXIT_MM
                    for hit, box in ((a0 - x0 < 0.3, (a0 - e, b0, a0, b1)), (x1 - a1 < 0.3, (a1, b0, a1 + e, b1)),
                                     (b0 - y0 < 0.3, (a0, b0 - e, a1, b0)), (y1 - b1 < 0.3, (a0, b1, a1, b1 + e))):
                        if hit:
                            m = self.raster(Polygon([(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])])) & (self.padnet[L] < 0)
                            self.reserve[L][m] = self.netid[p["net"]]; n += 1
        self.report["exit_lanes"] = n

    # raster helpers
    def P(self, x, y): return ((x - self.x0) / RES, (y - self.y0) / RES)
    def raster(self, g):
        im = Image.new("L", (self.W, self.H), 0); dr = ImageDraw.Draw(im)
        for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
            if not isinstance(q, Polygon) or q.is_empty: continue
            dr.polygon([self.P(*c) for c in q.exterior.coords], fill=1)
            for h in q.interiors: dr.polygon([self.P(*c) for c in h.coords], fill=0)
        return np.array(im, dtype=bool)
    def fill(self, arr, g, v): arr[self.raster(g)] = v
    def xy(self, i, j): return (self.x0 + (j + 0.5) * RES, self.y0 + (i + 0.5) * RES)

    def room(self, net, L, loose=False):
        """Distance in mm from each cell to the nearest thing this net's copper must keep away from, less the
        clearance: copper of radius r fits at a cell where room >= r."""
        nid = self.netid[net]; pn = self.padnet[L]
        other = ((pn >= 0) & (pn != nid)) | self.block[L] | ((self.cu[L] >= 0) & (self.cu[L] != nid))
        other |= (self.viamap >= 0) & (self.viamap != nid)
        other |= (self.reserve[L] >= 0) & (self.reserve[L] != nid)
        dist = ndimage.distance_transform_edt(~other) * RES - self.clr
        if loose or self.escape <= 0: return dist
        sig = (pn >= 0) & (pn != nid) & self.signal[np.maximum(pn, 0)]
        ds = ndimage.distance_transform_edt(~sig) * RES - self.clr - self.escape
        return np.minimum(dist, ds)

    def disk(self, x, y, r):
        m = np.zeros((self.H, self.W), bool); ci, cj = (y - self.y0) / RES - 0.5, (x - self.x0) / RES - 0.5; k = int(r / RES) + 2
        i0, i1, j0, j1 = max(0, int(ci) - k), min(self.H, int(ci) + k + 1), max(0, int(cj) - k), min(self.W, int(cj) + k + 1)
        ii, jj = np.mgrid[i0:i1, j0:j1]; m[i0:i1, j0:j1] = (ii - ci) ** 2 + (jj - cj) ** 2 <= (r / RES) ** 2; return m

    def add_zone(self, net, L, g, prio, soft=False, kind=""):
        g = g.intersection(self.inside)
        if g.is_empty: return
        z = self.zones.setdefault((net, L), dict(net=net, layer=L, geom=g, priority=prio, soft=soft, kinds={kind}))
        if z["geom"] is not g: z["geom"] = unary_union([z["geom"], g]); z["priority"] = max(z["priority"], prio); z["kinds"].add(kind)
        if not soft: self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]

    def clip_others(self, net, L, g, loose_near=None):
        """Cut back from other nets' pads by the clearance (plus escape room for signal pads, except near loose_near)."""
        cut = []
        for p, pg in self.padpoly[L]:
            if p["net"] == net or pg is None: continue
            extra = self.escape if self.d.role(p["net"]) == "signal" and (loose_near is None or pg.distance(loose_near) > NEAR_TERM_MM) else 0.0
            cut.append(pg.buffer(self.clr + extra, 4))
        for (n2, L2), z in self.zones.items():
            if L2 == L and n2 != net and not z["soft"]: cut.append(z["geom"].buffer(self.clr, 4))
        for v in self.vias:
            if v["net"] != net: cut.append(Point(v["x"], v["y"]).buffer(VIA_D / 2 + self.clr, 8))
        return g.difference(unary_union(cut)) if cut else g

    def place_vias(self, net, near, count, layers_ok=None, inside=None, toward=None, link=None, link_w=0.4):
        """Up to count vias of net as close as possible to the shape near, legal on both outer layers (RAST_MM more
        room than the via needs, for the raster), VIA_PITCH from every other via and plated hole. With link=(layer,
        pad shape): only vias that a straight link_w track from that pad can reach without coming near another net.
        Returns the vias placed, each with the link track's start point when one is needed."""
        r = VIA_D / 2; ok = np.ones((self.H, self.W), bool)
        ok &= ~self.novia
        for L in self.outer: ok &= (self.room(net, L, loose=True) >= r + RAST_MM) & ~self.block[L]
        if inside is not None: ok &= self.raster(inside.buffer(-r))
        lroom = self.room(net, link[0], loose=True) if link else None
        c = near.centroid if toward is None else Point(toward)
        x0, y0, x1, y1 = near.buffer(2.5).bounds
        i0, i1 = max(0, int((y0 - self.y0) / RES)), min(self.H, int((y1 - self.y0) / RES) + 1); j0, j1 = max(0, int((x0 - self.x0) / RES)), min(self.W, int((x1 - self.x0) / RES) + 1)
        cand = []
        for i in range(i0, i1, 2):
            for j in range(j0, j1, 2):
                if not ok[i, j]: continue
                x, y = self.xy(i, j); dn = near.distance(Point(x, y))
                if dn > 2.0 or (dn < r + 0.05 and not near.contains(Point(x, y))): continue
                cand.append((dn + 0.15 * math.hypot(x - c.x, y - c.y), x, y))
        cand.sort(); out = []
        holes = [(v["x"], v["y"], VIA_DRILL) for v in self.vias] + self.drilled
        gap = lambda d: PAD_HOLE_GAP if d >= 0.5 else HOLE_GAP
        for _, x, y in cand:
            if len(out) >= count: break
            if any(math.hypot(x - a, y - b) < max(VIA_PITCH, (d + VIA_DRILL) / 2 + gap(d)) for a, b, d in holes): continue
            if any(LineString([t["a"], t["b"]]).distance(Point(x, y)) < r + t["w"] / 2 + self.clr for t in self.tracks if t["net"] != net): continue   # tracks are not on the raster
            v = dict(net=net, x=round(x, 3), y=round(y, 3), size=VIA_D, drill=VIA_DRILL)
            if link:
                L, pg = link; q = pg.exterior.interpolate(pg.exterior.project(Point(x, y))) if isinstance(pg, Polygon) else pg.centroid
                q = LineString([(q.x, q.y), pg.centroid.coords[0]]).interpolate(min(0.1, q.distance(pg.centroid)))     # just inside the pad
                seg = LineString([(q.x, q.y), (x, y)]); clear = True
                for k in range(int(seg.length / 0.05) + 1):
                    pt = seg.interpolate(k * 0.05)
                    if pg.contains(pt): continue
                    ii, jj = int((pt.y - self.y0) / RES), int((pt.x - self.x0) / RES)
                    if lroom[ii, jj] < link_w / 2 + RAST_MM: clear = False; break
                if not clear: continue
                if pg.distance(Point(x, y)) > 0.01: v["link"] = (link[0], round(q.x, 4), round(q.y, 4))
            out.append(v); self.vias.append(v); holes.append((x, y, VIA_DRILL))
            self.viamap[self.disk(x, y, VIA_D / 2) & (self.viamap < 0)] = self.netid[net]
        return out

    def stub(self, net, L, gp, vs, w=0.5):
        """Copper from a pad to its vias: the pad, the via pads, the checked straight links, and whatever of their
        hull is clear of other nets; only the piece that holds the pad is kept."""
        parts = [gp] + [Point(v["x"], v["y"]).buffer(VIA_D / 2 + 0.05, 8) for v in vs]
        parts += [LineString([v["link"][1:], (v["x"], v["y"])]).buffer(w / 2, 4) for v in vs if v.get("link")]
        core = unary_union(parts); hull = self.clip_others(net, L, core.convex_hull, loose_near=gp)
        g = unary_union([core, hull]); return unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(gp)])

    def component(self, net, L, seed):
        """The piece of the net's planned copper on L that holds the seed cells. Pieces count as joined only where
        they overlap by more than a cell, so two pours that merely touch on the raster are not taken as connected."""
        m = self.cu[L] == self.netid[net]
        if not seed.any() or not m.any(): return m & seed
        e = ndimage.binary_erosion(m) | (m & seed); lab, _ = ndimage.label(e)
        ids = np.unique(lab[seed & e]); ids = ids[ids > 0]
        return ndimage.binary_dilation(np.isin(lab, ids)) & m

    def spine(self, net, L, pth):
        """The path's centre line as a SPINE_W track: the corridor pour joins the tree and the terminal through it even
        where KiCad's fill leaves a neck open (a pour that only touches another piece of the same net at a corner)."""
        if len(pth) < 2: return
        line = LineString([self.xy(i, j) for i, j in pth]).simplify(0.04)
        c = list(line.coords); obs = self.obstacles(net, L)
        for a, b in zip(c, c[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-3 and LineString([a, b]).buffer(SPINE_W / 2, 4).distance(obs) >= self.clr: self.tracks.append(dict(net=net, layer=L, a=(round(a[0], 4), round(a[1], 4)), b=(round(b[0], 4), round(b[1], 4)), w=SPINE_W))

    def obstacles(self, net, L):
        """Exact shapes on L that copper of net must keep the clearance from: other nets' pads, planned copper,
        vias and tracks."""
        g = [pg for p, pg in self.padpoly[L] if p["net"] != net and pg is not None]
        g += [z["geom"] for (n2, L2), z in self.zones.items() if L2 == L and n2 != net and not z["soft"]]
        g += [Point(v["x"], v["y"]).buffer(VIA_D / 2, 8) for v in self.vias if v["net"] != net]
        g += [LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 4) for t in self.tracks if t["layer"] == L and t["net"] != net]
        g += [h for h in self.npth]
        return unary_union(g)

    def anchor(self, net, L, pads, cu):
        """A short track from each terminal pad into the net's copper on L. A pour that only grazes a fine-pitch pad
        may not fill up to it (clearance to the pins beside it, minimum width); a track always connects.
        Tried in order, checked on exact shapes: straight from the pad centre to the nearest copper; out along the
        pad's long axis as wide as the pad (it then keeps the spacing the pins already have) and on to the copper."""
        far = cu.difference(unary_union([self.d.pad_poly(p, L).buffer(0.25) for p in pads]))
        if far.is_empty: return 0
        obs = self.obstacles(net, L); n = 0; inner = far.buffer(-0.1)
        if inner.is_empty: inner = far
        for p in pads:
            pg = self.d.pad_poly(p, L); c = pg.centroid
            if pg.buffer(0.05).intersects(inner): continue      # the pour already covers part of the pad
            gap = obs.distance(pg)                         # what the pad itself keeps from its neighbours
            rect = pg.minimum_rotated_rectangle; xy = list(rect.exterior.coords)[:4]
            e1 = (xy[1][0] - xy[0][0], xy[1][1] - xy[0][1]); e2 = (xy[2][0] - xy[1][0], xy[2][1] - xy[1][1])
            l1, l2 = math.hypot(*e1), math.hypot(*e2); u, half, s = ((e1[0] / l1, e1[1] / l1), l1 / 2, l2) if l1 >= l2 else ((e2[0] / l2, e2[1] / l2), l2 / 2, l1)
            def to_cu(pt, w, clr):
                q = inner.boundary.interpolate(inner.boundary.project(pt)); dx, dy = q.x - pt.x, q.y - pt.y; dl = math.hypot(dx, dy)
                if dl > 1e-6: q = Point(q.x + dx / dl * 0.1, q.y + dy / dl * 0.1)
                seg = LineString([(pt.x, pt.y), (q.x, q.y)])
                return seg if seg.length < 3.0 and seg.buffer(w / 2, 4).difference(pg).distance(obs) >= clr else None
            best = None
            w0 = min(0.5, 0.8 * s); sg = to_cu(c, w0, self.clr)
            if sg: best = [(sg, w0)]
            for sign in ((1, -1) if s <= FINE_PAD_MM else ()):
                if best: break
                for ext in (0.3, 0.6, 1.0, 1.5):
                    p1 = Point(c.x + u[0] * sign * (half + ext), c.y + u[1] * sign * (half + ext)); s1 = LineString([(c.x, c.y), (p1.x, p1.y)])
                    if s1.buffer(s / 2, cap_style=2).difference(pg).distance(obs) < max(MIN_CLR, min(self.clr, gap)) - 1e-3: break
                    if inner.contains(p1): best = [(s1, s)]; break
                    s2 = to_cu(p1, min(s, 0.4), self.clr)
                    if s2: best = [(s1, s), (s2, min(s, 0.4))]; break
            for sg, w in best or []:
                (ax, ay), (bx, by) = sg.coords[0], sg.coords[-1]
                self.tracks.append(dict(net=net, layer=L, a=(round(ax, 4), round(ay, 4)), b=(round(bx, 4), round(by, 4)), w=round(w, 3)))
            n += bool(best)
        return n

    # 1. planes
    def planes_step(self):
        for net in sorted(self.d.ret):
            for L in self.planes: self.add_zone(net, L, self.inside, 0, soft=True, kind="plane")
        self.report["planes"] = {L: sorted(self.d.ret) for L in self.planes}

    # 2. hot loops (the stage rule copper)
    def hot_loops_step(self):
        C = self.d.C; rep = {}
        for name, hl in sorted(C.get("hot_loops", {}).items()):
            P, G = self.d.board(hl["supply"]), self.d.board(hl["ret"]); ref = hl["switch_pins"][0].split(".")[0]; L = self.d.fp[ref]["layer"]
            sw = [p for p in self.d.by_ref[ref] if p["key"] in self.d.switch_pins]
            caps = [c for c in hl["caps"] if c in self.d.by_ref]
            pp = [p for p in sw if p["net"] == P] + [p for c in caps for p in self.d.by_ref[c] if p["net"] == P and L in p["shapes"]]
            gp = [p for p in sw if p["net"] == G] + [p for c in caps for p in self.d.by_ref[c] if p["net"] == G and L in p["shapes"]]
            if not pp or not gp: self.notes.append(f"{name}: switch or capacitor pads not on {L}"); continue
            near = unary_union([self.d.pad_poly(p, L) for p in pp + gp])
            sup, ret, how = self.loop_pours(P, G, L, sw, pp, gp, near, caps)
            self.add_zone(P, L, sup, 30, kind="hot loop " + name)
            self.add_zone(G, L, ret, 25, kind="hot loop " + name)
            nv = 0
            for c in caps:
                for p in self.d.by_ref[c]:
                    if p["net"] == G and L in p["shapes"]: nv += len(self.place_vias(G, self.d.pad_poly(p, L), 2, inside=ret, toward=near.centroid))
            swg = [p for p in sw if p["net"] == G]
            if swg: nv += len(self.place_vias(G, unary_union([self.d.pad_poly(p, L) for p in swg]), 3, inside=ret))
            rep[name] = dict(shape=how, layer=L, supply_mm2=round(sup.area, 1), return_mm2=round(ret.area, 1), return_vias=nv)
        self.report["hot_loops"] = rep

    def loop_pours(self, P, G, L, sw, pp, gp, near, caps):
        """Supply and return pours of one hot loop. Candidates: the convex hull of each net's pads (widest, least
        inductance) or pair hulls, each capacitor pad to the nearest switch pad of its net (for a placement where
        one net's hull would cut the other's pads apart), grown 0.3 mm or not at all (pins 0.5 mm apart); each with
        the supply cut first or the return cut first.
        The one that closes the most capacitors on the layer wins, in the circuit code's capacitor order (the first,
        the high-frequency one, matters most): supply pad to the switch's supply pad and return pad to the switch's
        return pad, each in one piece of pour. Then the fewest pieces, the supply counting ten times (a split return
        still closes through its vias and the plane under it; a split supply does not), then the earlier candidate."""
        pad = lambda p: self.d.pad_poly(p, L)
        def keep(g, pads):
            u = unary_union([pad(p) for p in pads]); return unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(u)] or [g])
        def pieces(g, pads):
            g = g.buffer(-0.1, 4).buffer(0.1, 4)       # as KiCad fills it: a neck under 0.15 mm does not join
            return sum(1 for q in getattr(g, "geoms", [g]) if any(q.intersects(pad(p)) for p in pads)) + sum(1 for p in pads if not g.intersects(pad(p)))
        def pairs(ps, b=0.3):
            s_ = [p for p in ps if p["key"] in self.d.switch_pins] or ps[:1]; hs = [unary_union([pad(p).buffer(b, 4) for p in s_]).convex_hull]
            for p in ps:
                if p in s_: continue
                q = min(s_, key=lambda q: pad(q).distance(pad(p))); hs.append(unary_union([pad(p).buffer(b, 4), pad(q).buffer(b, 4)]).convex_hull)
            return unary_union(hs)
        thin = lambda ps: pairs(ps, 0.0)       # as wide as the pads: for a fine-pitch switch whose pins are 0.5 mm apart
        full = lambda ps: unary_union([pad(p).buffer(0.3, 4) for p in ps]).convex_hull
        best = None
        for how, shape, sup_first in [("hull, supply first", full, True), ("hull, return first", full, False), ("pairs, supply first", pairs, True), ("pairs, return first", pairs, False), ("thin pairs, supply first", thin, True), ("thin pairs, return first", thin, False)]:
            hP, hG = shape(pp), shape(gp)
            if sup_first:
                sup = keep(self.clip_others(P, L, hP, loose_near=near), pp); ret = keep(self.clip_others(G, L, hG.difference(sup.buffer(self.clr, 4)), loose_near=near), gp)
            else:
                ret = keep(self.clip_others(G, L, hG, loose_near=near), gp); sup = keep(self.clip_others(P, L, hP.difference(ret.buffer(self.clr, 4)), loose_near=near), pp)
            so, ro = sup.buffer(-0.1, 4).buffer(0.1, 4), ret.buffer(-0.1, 4).buffer(0.1, 4)
            def one(g, a, b): return any(q.intersects(pad(a)) and q.intersects(pad(b)) for q in getattr(g, "geoms", [g]))
            swP = [p for p in sw if p["net"] == P]; swG = [p for p in sw if p["net"] == G]
            closed = tuple(-int(all(one(so, a, b) for a in swP for b in self.d.by_ref[c] if b["net"] == P and L in b["shapes"]) and
                                all(one(ro, a, b) for a in swG for b in self.d.by_ref[c] if b["net"] == G and L in b["shapes"])) for c in caps)
            sc = (closed, 10 * pieces(sup, pp) + pieces(ret, gp))
            if best is None or sc < best[0]: best = (sc, sup, ret, f"{how}, closes {[c for c, k in zip(caps, closed) if k]}, {pieces(sup, pp)} supply and {pieces(ret, gp)} return pieces")
        return best[1], best[2], best[3]

    # 3. power nets
    def path(self, net, L, start_mask, goal_mask, w, near_mask, tight=False):
        """Shortest path from the tree to a terminal. Escape room is kept except near the net's own terminal
        pads (near_mask); with tight=True only the clearance is kept anywhere (a last try, reported)."""
        rm = self.room(net, L, loose=True) if tight else np.where(near_mask, self.room(net, L, loose=True), self.room(net, L))
        rr = np.minimum(rm, w / 2)
        cost = np.where(rm >= MIN_W / 2, 1.0 + WIDE_COST * (1.0 - rr / (w / 2)), np.inf)
        cost[goal_mask | start_mask] = np.minimum(cost[goal_mask | start_mask], 1.0)      # own pads are always passable
        cells = np.argwhere(start_mask | goal_mask)
        if len(cells) == 0: return None, None
        i0, j0 = cells.min(0); i1, j1 = cells.max(0); m = int(8 / RES)
        i0, j0 = max(0, i0 - m), max(0, j0 - m); i1, j1 = min(self.H, i1 + m + 1), min(self.W, j1 + m + 1)
        sub = np.ascontiguousarray(cost[i0:i1, j0:j1]); pth = dijkstra(sub, start_mask[i0:i1, j0:j1], goal_mask[i0:i1, j0:j1])
        if not pth: return None, None
        Wd = j1 - j0; pts = [(i0 + k // Wd, j0 + k % Wd) for k in pth]
        return pts, rr

    def corridor(self, pts, rr, w):
        """Copper along a grid path: a disk at every few cells, as wide as the room allows up to the target."""
        shapes = []
        for k, (i, j) in enumerate(pts):
            if k % 2 and k != len(pts) - 1: continue
            r = float(min(rr[i, j], w / 2))
            if r >= MIN_W / 2 - 1e-6: x, y = self.xy(i, j); shapes.append(Point(x, y).buffer(r, 6))
        line = [self.xy(i, j) for i, j in pts]
        if len(line) > 1: shapes.append(LineString(line).buffer(MIN_W / 2, 4))
        return unary_union(shapes)

    def unvia(self, vs):
        for v in vs:
            self.vias.remove(v); self.viamap[self.disk(v["x"], v["y"], VIA_D / 2) & (self.viamap == self.netid[v["net"]])] = -1

    def plen(self, pth):
        return sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(pth, pth[1:])) * RES

    def winding(self, net, pth, ref, rep):
        """True (and reported as a placement failure) when the path winds: much longer than the straight line."""
        L = self.plen(pth); (i0, j0), (i1, j1) = pth[0], pth[-1]; d = math.hypot(i1 - i0, j1 - j0) * RES
        if L <= WIND_MAX * d + WIND_SLACK_MM: return False
        rep.setdefault("placement_failures", []).append(f"{ref}: path {L:.0f} mm for {d:.0f} mm straight")
        return True

    def detour(self, net, L, gp, w, I, tree):
        """A terminal on L with no path to the tree on L: vias at the terminal, a corridor on the other outer layer
        to a point over the tree, and vias down into the tree there. True if it was drawn."""
        Lo = [l for l in self.outer if l != L][0]; n = vias_for(I); r = VIA_D / 2
        vs = self.place_vias(net, gp, n, link=(L, gp))
        if not vs: return False
        vg = unary_union([Point(v["x"], v["y"]).buffer(r, 8) for v in vs]); start = self.raster(vg)
        ok = tree & ~self.novia & ~ndimage.binary_dilation(start, iterations=int(1.5 / RES))
        for l in self.outer: ok &= self.room(net, l, loose=True) >= r + RAST_MM
        ok = ndimage.binary_erosion(ok, iterations=2)
        if not ok.any(): self.unvia(vs); return False
        near = ndimage.binary_dilation(start | ok, iterations=int(NEAR_TERM_MM / RES))
        pth, rr = self.path(net, Lo, start, ok, w, near)
        if pth is None: pth, rr = self.path(net, Lo, start, ok, w, near, tight=True)
        if pth is None or self.plen(pth) > DETOUR_MAX_MM: self.unvia(vs); return False
        if not start[pth[0]]: pth = pth[::-1]
        ex, ey = self.xy(*pth[-1]); zl = self.zones[(net, L)]["geom"]
        ve = self.place_vias(net, Point(ex, ey).buffer(0.3), n, inside=zl, toward=(ex, ey))
        if not ve: self.unvia(vs); return False
        self.add_zone(net, L, self.stub(net, L, gp, vs), 15, kind="detour stub")
        ends = unary_union([vg] + [Point(v["x"], v["y"]).buffer(r, 8) for v in ve]).buffer(0.1)
        self.add_zone(net, Lo, self.clip_others(net, Lo, unary_union([self.corridor(pth, rr, w), ends]), loose_near=ends), 18, kind="detour")
        self.spine(net, Lo, pth); return True

    def net_step(self, net):
        T = self.d.terminals(net); I = self.d.current(net)
        if not T: return
        if I < ROUTER_A and net not in self.bus_nets:
            self.report.setdefault("nets", {})[net] = dict(current_a=I, terminals=len(T), span_mm=0, joined=[], left_to_router=[f"all ({I} A, under {ROUTER_A} A)"], vias=0); return
        pts = [Point(p["x"], p["y"]) for g in T for p in g["pads"]]; span = math.hypot(*(np.ptp([[q.x, q.y] for q in pts], axis=0))) if len(pts) > 1 else 0
        rep = dict(current_a=I, terminals=len(T), span_mm=round(span, 1), joined=[], left_to_router=[], vias=0)
        layer_I = {L: 0.0 for L in self.outer}
        for g in T:
            for L in self.outer:
                if any(L in p["shapes"] for p in g["pads"]): layer_I[L] += g["current_a"]
        main = max(self.outer, key=lambda L: (layer_I[L], L == self.outer[0]))
        bus = bool(net in self.bus_nets and self.inner_free)
        nearT = {L: ndimage.binary_dilation(self.raster(unary_union([self.d.pad_poly(p, L) for g in T for p in g["pads"] if L in p["shapes"]] or [Polygon()])), iterations=int(NEAR_TERM_MM / RES)) for L in self.outer}
        if bus:
            Li = self.inner_free.pop(0); rep["inner_layer"] = Li
            hull = unary_union([q.buffer(2.0) for q in pts]).convex_hull
            self.add_zone(net, Li, hull, 10, soft=True, kind="bus")
        T.sort(key=lambda g: (-g["current_a"], g["ref"]))
        tree = {L: (self.cu[L] == self.netid[net]) for L in self.outer}
        for L in self.outer:
            if tree[L].any(): rep["joined"].append("existing copper on " + L)
        todo = list(T); seed = np.zeros((self.H, self.W), bool)
        g = next((g for g in todo if any(main in p["shapes"] for p in g["pads"])), None)
        if g is not None:      # the tree grows from the highest-current terminal on main, as one connected piece
            todo.remove(g); gp = unary_union([self.d.pad_poly(p, main) for p in g["pads"] if main in p["shapes"]])
            self.add_zone(net, main, gp, 20, kind="tree"); seed = self.raster(gp); rep["joined"].append(g["ref"])
        tree[main] = self.component(net, main, seed)
        while todo:
            # nearest terminal to the tree on main first
            def dist(g):
                tc = np.argwhere(tree[main])
                if len(tc) == 0: return 0
                c = np.array([[(p["y"] - self.y0) / RES, (p["x"] - self.x0) / RES] for p in g["pads"]])
                return float(np.min(np.abs(tc[None, :, :] - c[:, None, :]).sum(-1))) if len(tc) < 20000 else float(np.min(np.abs(tc[::10][None] - c[:, None]).sum(-1)))
            g = min(todo, key=dist); todo.remove(g)
            w = max(MIN_W, width_mm(g["current_a"], self.t[main]))
            if bus: w = max(MIN_W, min(w, width_mm(g["current_a"], self.t[main])))
            on_main = [p for p in g["pads"] if main in p["shapes"]]
            if on_main:
                gp = unary_union([self.d.pad_poly(p, main) for p in on_main])
                if bus and any(p.get("drill") for p in g["pads"]):      # a plated hole reaches the inner pour itself
                    rep["joined"].append(g["ref"] + " (plated hole)"); continue
                if bus:      # bus terminal: vias to the inner pour, plus a stub on the pad layer
                    vs = self.place_vias(net, gp, vias_for(g["current_a"]), link=(main, gp)); rep["vias"] += len(vs)
                    if vs:
                        self.add_zone(net, main, self.stub(net, main, gp, vs), 15, kind="bus stub"); rep["joined"].append(g["ref"])
                    else: rep["left_to_router"].append(g["ref"] + " (no room for a via)")
                    continue
                goal = self.raster(gp); near = ndimage.binary_dilation(goal | tree[main], iterations=int(NEAR_TERM_MM / RES)) & ~ndimage.binary_dilation(tree[main], iterations=int(NEAR_TERM_MM / RES)) | goal
                pth, rr = self.path(net, main, tree[main], goal, w, nearT[main])
                if pth is None:
                    pth, rr = self.path(net, main, tree[main], goal, w, nearT[main], tight=True)
                    if pth is not None: rep.setdefault("tight", []).append(g["ref"])
                if pth is not None and self.winding(net, pth, g["ref"], rep): pth = None; why = " (path winds)"
                else: why = " (no path on " + main + ")"
                if pth is None and tree[main].any() and self.detour(net, main, gp, w, g["current_a"], tree[main]):
                    rep.setdefault("detour", []).append(g["ref"]); rep["joined"].append(g["ref"] + " (detour)"); continue
                if pth is None:
                    rep["left_to_router"].append(g["ref"] + why); continue
                cor = self.clip_others(net, main, unary_union([self.corridor(pth, rr, w), gp]), loose_near=unary_union([gp, Point(self.xy(*pth[-1])).buffer(NEAR_TERM_MM)]))
                self.spine(net, main, pth)
                self.add_zone(net, main, cor, 20, kind="tree"); tree[main] = self.component(net, main, seed); rep["joined"].append(g["ref"])
            else:            # terminal on the other outer layer: via array next to it, then join the tree on main
                Lo = [L for L in self.outer if L != main][0]
                gp = unary_union([self.d.pad_poly(p, Lo) for p in g["pads"] if Lo in p["shapes"]])
                if gp.is_empty: continue
                vs = self.place_vias(net, gp, vias_for(g["current_a"]), link=(Lo, gp)); rep["vias"] += len(vs)
                if not vs: rep["left_to_router"].append(g["ref"] + " (no room for a via)"); continue
                self.add_zone(net, Lo, self.stub(net, Lo, gp, vs), 15, kind="via stub")
                if bus: rep["joined"].append(g["ref"]); continue
                vg = unary_union([Point(v["x"], v["y"]).buffer(VIA_D / 2, 8) for v in vs])
                if not tree[main].any(): self.add_zone(net, main, vg.buffer(0.15), 20, kind="tree"); seed = self.raster(vg); tree[main] = self.component(net, main, seed); rep["joined"].append(g["ref"]); continue
                goal = self.raster(vg); near = nearT[main] | ndimage.binary_dilation(goal, iterations=int(NEAR_TERM_MM / RES))
                pth, rr = self.path(net, main, tree[main], goal, w, near)
                if pth is None:
                    pth, rr = self.path(net, main, tree[main], goal, w, near, tight=True)
                    if pth is not None: rep.setdefault("tight", []).append(g["ref"] + " (vias)")
                if pth is None: rep["left_to_router"].append(g["ref"] + " (via array has no path on " + main + ")"); continue
                if self.winding(net, pth, g["ref"] + " (vias)", rep): rep["left_to_router"].append(g["ref"] + " (via array path winds)"); continue
                self.add_zone(net, main, self.clip_others(net, main, unary_union([self.corridor(pth, rr, w), vg.buffer(0.1)]), loose_near=unary_union([vg, Point(self.xy(*pth[-1])).buffer(NEAR_TERM_MM)])), 20, kind="tree")
                self.spine(net, main, pth)
                tree[main] = self.component(net, main, seed); rep["joined"].append(g["ref"] + " (vias)")
        if (net, main) in self.zones and not bus:      # tracks from every terminal pad on main into the copper
            rep["anchors"] = self.anchor(net, main, [p for g in T for p in g["pads"] if main in p["shapes"] and not p.get("drill")], self.zones[(net, main)]["geom"])
        rep["main_layer"] = main; self.report.setdefault("nets", {})[net] = rep

    # 4. return pads
    def return_step(self):
        rep = dict(vias=0, pads=0, left_to_router=[])
        for net in sorted(self.d.ret):
            Tm = {g["ref"]: g for g in self.d.terminals(net)}
            for ref, pads in sorted(self.d.by_ref.items()):
                gp = [p for p in pads if p["net"] == net and not p.get("drill")]
                for L in self.outer:
                    pl = [p for p in gp if L in p["shapes"]]
                    if not pl: continue
                    n = vias_for(Tm[ref]["current_a"]) if ref in Tm else 1
                    for p in sorted(pl, key=lambda p: -self.d.area(p)):
                        sh = self.d.pad_poly(p, L); rep["pads"] += 1
                        z = self.zones.get((net, L)); zg = z["geom"].buffer(-0.1, 4).buffer(0.1, 4) if z else None     # a neck under KiCad's 0.15 mm fill width does not join
                        pieces = [q for q in getattr(zg, "geoms", [zg]) if q.intersects(sh.buffer(0.15))] if z else []
                        if pieces:     # the pad sits in a return pour: served if that piece of pour holds a via
                            pc = unary_union(pieces)
                            if not any(pc.contains(Point(v["x"], v["y"])) for v in self.vias if v["net"] == net):
                                rep["vias"] += len(self.place_vias(net, pc, 2, inside=pc))
                            if any(pc.contains(Point(v["x"], v["y"])) for v in self.vias if v["net"] == net):
                                rep["anchored"] = rep.get("anchored", 0) + self.anchor(net, L, [p], pc); continue
                        vs = self.place_vias(net, sh, n, link=(L, sh), link_w=0.3); n = 1    # the part's current through its largest pad
                        if not vs and self.return_join(net, L, unary_union([sh] + pieces)): rep.setdefault("joined_on_layer", []).append(f"{ref}.{p['num']}"); continue
                        if not vs: rep["left_to_router"].append(f"{ref}.{p['num']}"); continue
                        rep["vias"] += len(vs)
                        for v in vs:
                            if v.get("link"): self.tracks.append(dict(net=net, layer=v["link"][0], a=v["link"][1:], b=(v["x"], v["y"]), w=0.3))
        self.report["return_pads"] = rep

    # 5. second layer: copy each high-current net's copper onto the other outer layer where it is free, stitched
    def mirror_step(self, min_a):
        """For every power net of at least min_a: its outer-layer copper copied to the other outer layer wherever
        that layer is free (pieces under 2 mm2 dropped), joined by vias next to each terminal the piece reaches, so
        the two layers share the current."""
        rep = {}
        for net in sorted(self.d.power, key=lambda n: (-self.d.current(n), n)):
            if self.d.current(net) < min_a or self.d.power[net]["kind"] == "switching": continue    # a switch node stays small
            T = [t for t in self.d.terminals(net) if not any(p.get("drill") for p in t["pads"])]    # a plated hole joins the layers itself
            for L in self.outer:
                z = self.zones.get((net, L)); Lo = [l for l in self.outer if l != L][0]
                if not z or z["soft"] or "mirror" in z["kinds"]: continue
                g = self.clip_others(net, Lo, z["geom"])
                tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + self.clr, 4) for t in self.tracks if t["layer"] == Lo and t["net"] != net]
                bl = [b.buffer(self.clr, 4) for b in self.blockgeom[Lo]] + self.npth
                if tr or bl: g = g.difference(unary_union(tr + bl))
                g = g.buffer(-0.15, 4).buffer(0.15, 4)          # no necks narrower than 0.3 mm
                pieces = [q for q in getattr(g, "geoms", [g]) if q.area >= 2.0]
                nv = 0; kept = []
                for pc in pieces:
                    self.add_zone(net, Lo, pc, 12, kind="mirror"); vs = []
                    both = pc.intersection(z["geom"])
                    for t in T:
                        pg = unary_union([self.d.pad_poly(p, L) for p in t["pads"] if L in p["shapes"]] or [Polygon()])
                        if pg.is_empty or pg.distance(pc) > 1.0: continue
                        vs += self.place_vias(net, pg, max(2, vias_for(t["current_a"]) // 2), inside=both)
                    if len(vs) < 2: vs += self.place_vias(net, both, 2 - len(vs), inside=both)
                    nv += len(vs); kept.append(pc)
                    if not vs:          # an unstitched copy carries nothing: take it back
                        zz = self.zones[(net, Lo)]; zz["geom"] = zz["geom"].difference(pc.buffer(0.01))
                        self.cu[Lo][self.raster(pc) & (self.cu[Lo] == self.netid[net])] = -1; kept.pop()
                if kept: rep[f"{net} {Lo}"] = dict(mm2=round(sum(p.area for p in kept), 1), vias=nv)
        self.report["mirror"] = rep

    # 5b. spread: widen the power copper into the room left once every net and return pad has what it needs
    def grow_step(self, step=0.5):
        """In rounds of step mm, every power net's copper on the outer layers grows into free room (clear of other
        nets' pads, copper, vias and tracks, with escape room at signal pads, and out of keep-outs and lanes), so
        neighbouring nets share the room instead of the first one taking it. Only pieces that touch the net's
        existing copper are kept."""
        rep = {}; nets = sorted(self.d.power, key=lambda n: (-self.d.current(n), n)); left = self.grow
        while left > 1e-6:
            d = min(step, left); left -= d
            for net in nets:
                for L in self.outer:
                    z = self.zones.get((net, L))
                    if not z or z["soft"] or "mirror" in z["kinds"]: continue      # the copy stays a copy: the other side is for routing
                    g = z["geom"].buffer(d, 4).intersection(self.inside)
                    g = self.clip_others(net, L, g)
                    tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + self.clr, 4) for t in self.tracks if t["layer"] == L and t["net"] != net]
                    bl = [b.buffer(self.clr, 4) for b in self.blockgeom[L]] + self.npth
                    if tr or bl: g = g.difference(unary_union(tr + bl))
                    g = unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(z["geom"]) and q.intersection(z["geom"]).area > 0.05])
                    if g.is_empty: continue
                    a0 = z["geom"].area; z["geom"] = unary_union([z["geom"], g]); self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]
                    rep[f"{net} {L}"] = round(rep.get(f"{net} {L}", 0) + z["geom"].area - a0, 1)
        self.report["grown_mm2"] = rep

    def usage(self):
        """Power copper area per outer layer against the board area: how much routing room the copper takes."""
        a = self.inside.area; out = {}
        for L in self.outer:
            u = unary_union([z["geom"] for (n, l), z in self.zones.items() if l == L and not z["soft"] and self.d.role(n) == "power"] or [Polygon()])
            out[L] = dict(power_mm2=round(u.area), board_pct=round(100 * u.area / a, 1))
        self.report["outer_layer_use"] = out

    def return_join(self, net, L, sh):
        """A return pad (with the pour piece it sits in) where no via fits: a narrow path on its own layer to the
        nearest piece of the net's copper there that holds a via. True if drawn."""
        z = self.zones.get((net, L)); start = self.raster(sh)
        if z is None: return False
        m = self.raster(z["geom"].buffer(-0.1, 4).buffer(0.1, 4))       # pieces as KiCad will fill them
        lab, _ = ndimage.label(m | start)
        ids = {lab[int((v["y"] - self.y0) / RES), int((v["x"] - self.x0) / RES)] for v in self.vias if v["net"] == net}
        ids -= {0} | set(np.unique(lab[start]).tolist())
        if not ids: return False
        goal = np.isin(lab, list(ids))
        pth, rr = self.path(net, L, start, goal, MIN_W, ndimage.binary_dilation(start | goal, iterations=int(NEAR_TERM_MM / RES)), tight=True)
        if pth is None or len(pth) > 6 / RES: return False
        cor = self.clip_others(net, L, unary_union([self.corridor(pth, rr, MIN_W), sh]), loose_near=sh.buffer(NEAR_TERM_MM))
        self.add_zone(net, L, cor, 22, kind="return join"); self.spine(net, L, pth); return True

    def run(self):
        t0 = time.time()
        self.planes_step()
        # buses: nets spread wider than BUS_SPAN_MM with at least BUS_MIN_TERMINALS terminals; the free inner layers
        # go to those with the most terminals (a rail that feeds many loads), one layer each
        cand = []
        for n in self.d.power:
            T = self.d.terminals(n); xy = np.array([[p["x"], p["y"]] for g in T for p in g["pads"]])
            if len(T) >= BUS_MIN_TERMINALS and len(xy) > 1 and math.hypot(*np.ptp(xy, axis=0)) > BUS_SPAN_MM: cand.append((-len(T), -self.d.current(n), n))
        self.bus_nets = [n for _, _, n in sorted(cand)[:len(self.inner_free)]]; self.report["buses"] = self.bus_nets
        # then switch nodes: short; their pads keep the clearance inside the loop pours, and near their own pads only the clearance applies
        sw = [n for n in self.d.power if self.d.power[n]["kind"] == "switching"]
        self.hot_loops_step()     # loops first: switch-node copper drawn first cut the FETs' return pins off (seed 9, all six USB loops open)
        for net in sorted(sw, key=lambda n: (-self.d.current(n), n)): self.net_step(net)
        for net in sorted(set(self.d.power) - set(sw), key=lambda n: (-self.d.current(n), n)): self.net_step(net)
        self.return_step()
        if self.mirror > 0: self.mirror_step(self.mirror)
        if self.grow > 0: self.grow_step()
        self.usage()
        self.report["seconds"] = round(time.time() - t0, 1); self.report["notes"] = self.notes
        zs = []
        for (net, L), z in sorted(self.zones.items(), key=lambda kv: (-kv[1]["priority"], kv[0])):
            zs.append(dict(net=net, layer=L, priority=z["priority"], soft=z["soft"], kinds=sorted(z["kinds"]), polys=rings(z["geom"]), area_mm2=round(z["geom"].area, 1)))
        return dict(zones=zs, vias=self.vias, tracks=self.tracks, report=self.report, clearance_mm=self.clr)

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = Planner(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")
