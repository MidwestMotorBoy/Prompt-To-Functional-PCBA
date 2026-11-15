"""mroute.py: a multi-layer path search for hand routing, with the board's real rules.
    from mroute import MR
    m = MR(dir, board)                       # like obst.HR (same save / load / via / seg / drop)
    m.route(net, (x, y), (x, y), w=0.2)      # A* over F, In2, In3, B with through vias; adds the tracks and vias and
                                             # returns the path [(layer, x, y), ...] or None
    m.route(net, a, b, layers=('In3.Cu', 'B.Cu'), margin=6, via_cost=2.0, avoid=[(x0, y0, x1, y1), ...])
Rules used (from the project's .kicad_pro / .kicad_dru): 0.15 mm copper clearance; 0.25 mm between HighCurrent copper
and Default-class signal copper (pads exempt); 0.3 mm to the board edge; via 0.45 / 0.3, 0.6 mm between via centres.
Pours of GND anywhere and of PACK_P / 3V3 on In2 / In3 refill round new copper and are not obstacles; every other
pour is a power path and is kept whole. Tracks may enter no-via areas; vias may not."""
import sys, os, json, math, heapq, fnmatch
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point, LineString, Polygon, box as sbox
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from obst import HR, SIG

class MR(HR):
    def __init__(self, d, board):
        super().__init__(d, board)
        d = os.path.abspath(d); P = json.load(open("%s/%s.kicad_pro" % (d, board)))["net_settings"]
        self.pat = [(p["pattern"], p["netclass"]) for p in P.get("netclass_patterns") or []]
        D = json.load(open("%s/%s.json" % (d, board))); self.ko_t, self.ko_v = [], []
        for k in D.get("keepouts", []):
            for pl in k["poly"]:
                g = Polygon(pl["ring"]).buffer(0)
                for L in k["layers"]:
                    if k.get("no_tracks"): self.ko_t.append((L, g))
                    if k.get("no_vias"): self.ko_v.append(g)
        self._cls = {}
    def cls(self, net):
        if net not in self._cls:
            c = "GND" if net == "GND" else "Default"
            for p, k in self.pat:
                if fnmatch.fnmatchcase(net, p): c = k; break
            self._cls[net] = c
        return self._cls[net]
    def clr(self, net, onet, kind):
        a, b = self.cls(net), self.cls(onet)
        if kind not in ("pad", "hole") and ((a == "HighCurrent" and b == "Default") or (b == "HighCurrent" and a == "Default")): return 0.25
        return 0.15
    def soft_pour(self, n, L): return n == "GND" or (n in ("PACK_P", "3V3") and L in ("In2.Cu", "In3.Cu"))

    def clusters(self, net):
        """Copper of one net grouped into electrically joined pieces, largest first: [{layer: [geom, ...]}, ...]."""
        it = [(L, geo) for L in SIG for geo, n, kind, name in self.items[L] if n == net and kind != "keepout"]
        par = list(range(len(it)))
        def find(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        from shapely.strtree import STRtree
        for L in SIG:
            idx = [i for i, (l, g_) in enumerate(it) if l == L]
            if not idx: continue
            tr = STRtree([it[i][1] for i in idx])
            for a_, i in enumerate(idx):
                for b_ in tr.query(it[i][1].buffer(0.005)):
                    j = idx[int(b_)]
                    if j > i and it[i][1].distance(it[j][1]) < 0.005: par[find(i)] = find(j)
        # vias and through pads join the layers: same position on several layers
        pos = {}
        for i, (L, g_) in enumerate(it):
            if g_.area < 4.0:
                c = g_.centroid; k = (round(c.x, 2), round(c.y, 2), round(g_.area, 3))
                if k in pos: par[find(i)] = find(pos[k])
                else: pos[k] = i
        cl = {}
        for i, (L, g_) in enumerate(it): cl.setdefault(find(i), {}).setdefault(L, []).append(g_)
        return sorted(cl.values(), key=lambda c: -sum(g_.area for gs in c.values() for g_ in gs))
    def join(self, net, cl, main, w=0.2, margin=5.0, **kw):
        """Route from one copper piece of a net (a cluster from clusters()) to another; the search starts anywhere on
        the first and ends anywhere on the second."""
        from shapely.ops import unary_union, nearest_points
        ua = unary_union([g_ for gs in cl.values() for g_ in gs]); ub = unary_union([g_ for gs in main.values() for g_ in gs])
        p, q = nearest_points(ua, ub)
        return self._search(net, (min(p.x, q.x) - margin, min(p.y, q.y) - margin, max(p.x, q.x) + margin, max(p.y, q.y) + margin), cl, main, w, **kw)
    def route(self, net, a, b, w=0.2, margin=4.0, la=None, lb=None, **kw):
        def at(p, pref):
            c = {}
            for L in SIG:
                if pref and L not in pref: continue
                gs = [geo for geo, n, kind, name in self.items[L] if n == net and kind != "keepout" and geo.distance(Point(p)) < 0.03]
                if gs: c[L] = gs
            return c
        ca, cb = at(a, la), at(b, lb)
        if not ca or not cb:
            print("  route %s: %s (%.2f, %.2f) is not on copper of this net" % (net, "start" if not ca else "end", *(a if not ca else b))); self.ok = False; return None
        # grow each end to the whole joined piece it belongs to
        for cl in self.clusters(net):
            for c in (ca, cb):
                if any(any(g1.equals(g2) for g2 in cl.get(L, [])) for L, gs in c.items() for g1 in gs[:1]):
                    for L, gs in cl.items(): c[L] = gs
        if ca is cb or all(ca.get(L) == cb.get(L) for L in SIG): print("  route %s: both ends are already joined" % net); return []
        return self._search(net, (min(a[0], b[0]) - margin, min(a[1], b[1]) - margin, max(a[0], b[0]) + margin, max(a[1], b[1]) + margin), ca, cb, w, **kw)

    def _search(self, net, bb, SRC, DST, w=0.2, layers=SIG, g=0.05, via_cost=1.5, avoid=(), quiet=False, max_cells=8000000, ghost=None):
        x0, y0, x1, y1 = bb
        W, H = int((x1 - x0) / g) + 1, int((y1 - y0) / g) + 1; win = sbox(x0, y0, x1, y1)
        PX = lambda x, y: ((x - x0) / g, (y - y0) / g)
        def draw(d, geo, fill=1):
            for q in (geo.geoms if hasattr(geo, "geoms") else [geo]):
                if q.is_empty or q.geom_type != "Polygon": continue
                d.polygon([PX(x, y) for x, y in q.exterior.coords], fill=fill)
                for hole in q.interiors: d.polygon([PX(x, y) for x, y in hole.coords], fill=1 - fill)
        tm = {}; vim = Image.new("L", (W, H), 0); vd = ImageDraw.Draw(vim); src = {}; dst = {}
        gn = sorted(ghost) if ghost else []; gi = {n: i + 1 for i, n in enumerate(gn)}; labt = {}; lvi = Image.new("I", (W, H), 0); lvd = ImageDraw.Draw(lvi)
        edge_t = self.outline.buffer(-(0.3 + w / 2)); edge_v = self.outline.buffer(-0.55)
        for L in SIG:
            im = Image.new("L", (W, H), 1); d = ImageDraw.Draw(im); draw(d, edge_t, 0)        # outside the board: blocked
            lim = Image.new("I", (W, H), 0); ld = ImageDraw.Draw(lim)
            for i in self.tree[L].query(win):
                geo, n, kind, name = self.items[L][int(i)]
                if kind == "keepout" or n == net: continue
                if kind == "pour" and self.soft_pour(n, L): continue
                c = self.clr(net, n, kind) + 0.03
                if n in gi and kind in ("track", "via"):               # a route that may be pulled: passable at a price
                    draw(ld, geo.buffer(c + w / 2), gi[n]); draw(lvd, geo.buffer(c + 0.225), gi[n]); continue
                draw(d, geo.buffer(c + w / 2)); draw(vd, geo.buffer(c + 0.225))
            for KL, kg in self.ko_t:
                if KL == L: draw(d, kg.buffer(w / 2))
            for bx in avoid: draw(d, sbox(*bx))
            tm[L] = np.array(im, dtype=bool); labt[L] = np.array(lim, dtype=np.int32)
            for C_, out in ((SRC, src), (DST, dst)):
                om = Image.new("L", (W, H), 0); od = ImageDraw.Draw(om)
                for geo in C_.get(L, []):
                    if not geo.intersects(win): continue
                    e = geo.buffer(-max(0.02, w / 2 - 0.01))                 # the new track must lie inside its own copper there
                    draw(od, e if not e.is_empty else geo.centroid.buffer(0.04))
                out[L] = np.array(om, dtype=bool)
        for kg in self.ko_v: draw(vd, kg.buffer(0.225))
        em = Image.new("L", (W, H), 1); draw(ImageDraw.Draw(em), edge_v, 0)
        for vx, vy, s_, n in self.vias:
            if x0 - 1 < vx < x1 + 1 and y0 - 1 < vy < y1 + 1:
                if n in gi: lvd.ellipse([PX(vx - 0.6, vy - 0.6), PX(vx + 0.6, vy + 0.6)], fill=gi[n])
                else: vd.ellipse([PX(vx - 0.6, vy - 0.6), PX(vx + 0.6, vy + 0.6)], fill=1)
        vb = np.array(vim, dtype=bool) | np.array(em, dtype=bool); labv = np.array(lvi, dtype=np.int32); lt = [labt[L] for L in SIG]; PEN = 12.0
        free = {L: src[L] | dst[L] for L in SIG}
        blk = [tm[L] & ~free[L] for L in SIG]; gl = [dst[L] for L in SIG]; fr = [free[L] for L in SIG]
        ok_layer = [L in layers for L in SIG]; lc = [1.15, 1.0, 1.0, 1.15]; VC = via_cost / g
        gy, gx = np.nonzero(np.any(np.stack(gl), axis=0))
        if len(gx) == 0 or not any(src[L].any() for L in SIG):
            if not quiet: print("  route %s: an end has no copper inside the search window" % net)
            self.ok = False; return None
        tx, ty = float(gx.mean()), float(gy.mean()); rad = float(np.hypot(gx - tx, gy - ty).max())      # heuristic: distance to the goal's disc
        def hh(x, y):
            dxy = math.hypot(x - tx, y - ty) - rad
            return 1.2 * dxy if dxy > 0 else 0.0
        D8 = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142))
        best = {}; par = {}; pq = []
        from scipy import ndimage
        for l, L in enumerate(SIG):                            # start from the rim of the source copper
            rim = src[L] & ~ndimage.binary_erosion(src[L], border_value=1)
            for y, x in zip(*np.nonzero(rim)):
                k = (l, int(y), int(x)); best[k] = 0.0; par[k] = None; heapq.heappush(pq, (hh(x, y), k))
        found = None; n_exp = 0
        while pq:
            f, k = heapq.heappop(pq); l, y, x = k; gk = best[k]
            if f > gk + hh(x, y) + 1e-6: continue
            if gl[l][y, x]: found = k; break
            n_exp += 1
            if n_exp > max_cells: break
            pk = par[k]
            for dx, dy, cst in D8:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < W and 0 <= ny < H) or blk[l][ny, nx]: continue
                if not ok_layer[l] and not fr[l][ny, nx]: continue
                nk = (l, ny, nx); ng = gk + cst * lc[l] + (0.5 if pk is not None and pk[0] == l and (x - pk[2], y - pk[1]) != (dx, dy) else 0) + (PEN if lt[l][ny, nx] else 0)
                if ng < best.get(nk, 1e18):
                    best[nk] = ng; par[nk] = k; heapq.heappush(pq, (ng + hh(nx, ny), nk))
            if not vb[y, x]:
                for l2 in range(4):
                    if l2 == l or blk[l2][y, x] or not (ok_layer[l2] or fr[l2][y, x]): continue
                    nk = (l2, y, x); ng = gk + VC + (PEN * 6 if labv[y, x] else 0)
                    if ng < best.get(nk, 1e18):
                        best[nk] = ng; par[nk] = k; heapq.heappush(pq, (ng + hh(x, y), nk))
        if found is None:
            if not quiet: print("  route %s: NO PATH in window (%.1f, %.1f)-(%.1f, %.1f), %d cells searched" % (net, x0, y0, x1, y1, n_exp))
            self.ok = False; return None
        cells = []; k = found
        while k is not None: cells.append(k); k = par[k]
        cells.reverse()
        if ghost:                                              # report whose routes are in the way, add nothing
            v = set(); where = {}
            for i, (l, y, x) in enumerate(cells):
                if lt[l][y, x]: n_ = gn[lt[l][y, x] - 1]; v.add(n_); where.setdefault(n_, (SIG[l][:-3], round(x0 + x * g, 1), round(y0 + y * g, 1)))
                if i and cells[i - 1][0] != l and labv[y, x]: n_ = gn[labv[y, x] - 1]; v.add(n_); where.setdefault(n_, ("via", round(x0 + x * g, 1), round(y0 + y * g, 1)))
            return ("RIP", sorted(v), where)
        pts = [(SIG[l], round(x0 + x * g, 3), round(y0 + y * g, 3)) for l, y, x in cells]
        # split into per-layer runs, drop collinear points
        runs = []; cur = [pts[0]]
        for p in pts[1:]:
            if p[0] != cur[-1][0]: runs.append(cur); cur = [(p[0], cur[-1][1], cur[-1][2])]
            else: cur.append(p)
        runs.append(cur); out = []
        for i, r in enumerate(runs):
            if i > 0:
                vx, vy = r[0][1], r[0][2]; self.J["vias"].append({"net": net, "x": vx, "y": vy}); self.vias.append((vx, vy, 0.45, net))
                for L in SIG: self._add(L, Point(vx, vy).buffer(0.225), net, "via")
            s2 = [r[0]]
            for j in range(1, len(r) - 1):
                if (round(r[j][1] - r[j - 1][1], 3), round(r[j][2] - r[j - 1][2], 3)) != (round(r[j + 1][1] - r[j][1], 3), round(r[j + 1][2] - r[j][2], 3)): s2.append(r[j])
            if len(r) > 1: s2.append(r[-1])
            if len(s2) > 1:
                self.J["routes"].append({"net": net, "w": w, "path": [[p[0], p[1], p[2]] for p in s2]})
                self._add(r[0][0], LineString([(p[1], p[2]) for p in s2]).buffer(w / 2), net, "track")
            out += s2
        if not quiet: print("  route %s: %.1f mm, %d vias, layers %s" % (net, sum(math.hypot(out[i + 1][1] - out[i][1], out[i + 1][2] - out[i][2]) for i in range(len(out) - 1)), len(runs) - 1, "/".join(dict.fromkeys(p[0][:-3] for p in out))))
        return out
    def npads(self, net): return len({name for L in SIG for _, n, kind, name in self.items[L] if n == net and kind == "pad"})
    def rip(self, net):
        """Pull every track and via of a net (the board's and this session's) so it can be laid again."""
        from shapely.strtree import STRtree
        for L in SIG:
            self.items[L] = [i for i in self.items[L] if not (i[1] == net and i[2] in ("track", "via"))]; self.tree[L] = STRtree([i[0] for i in self.items[L]])
        self.vias = [v for v in self.vias if v[3] != net]
        self.J["routes"] = [r for r in self.J["routes"] if r["net"] != net]; self.J["vias"] = [v for v in self.J["vias"] if v["net"] != net]
        if not any(d["net"] == net for d in self.J["drop"]): self.J["drop"].append({"net": net, "layer": None, "box": [0, 0, 999, 999]})
    def rip_tracks(self, net, layer, box):
        """Pull the tracks of a net on one layer that lie inside a box (vias stay): for moving a power strap."""
        from shapely.strtree import STRtree
        bx = sbox(*box)
        self.items[layer] = [i for i in self.items[layer] if not (i[1] == net and i[2] == "track" and bx.contains(i[0]))]
        self.tree[layer] = STRtree([i[0] for i in self.items[layer]])
        self.J["drop"].append({"net": net, "layer": layer, "box": list(box), "tracks_only": True})
    def strap(self, net, a, b, w, layer):
        """A wide single-layer track between two via fields of a power net, even when a pour already joins them."""
        at = lambda p: {L: [geo for geo, n, kind, name in self.items[L] if n == net and kind in ("via", "pad") and geo.distance(Point(p)) < 0.03] for L in SIG}
        return self._search(net, (min(a[0], b[0]) - 6, min(a[1], b[1]) - 6, max(a[0], b[0]) + 6, max(a[1], b[1]) + 6), at(a), at(b), w, layers=(layer,), quiet=True)
