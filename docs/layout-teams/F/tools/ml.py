"""ml.py: multi-layer hand-route search with the board's REAL rules (team F). Builds on obst.HR.

    from ml import ML
    h = ML(dir, board)                               # <dir>/<board>.kicad_pcb (+ .kicad_pro for the net classes)
    h.route(net, (x, y), (x, y))                     # pad/via/track point to pad/via/track point, any layers, vias where legal
    h.route(net, a, b, w=0.15, layers=('F.Cu', 'In3.Cu'), via_cost=2.0, margin=5)
    h.to_net(net, (x, y))                            # from this point to the nearest other copper of the same net
    h.close(drc_json, only=regex, skip=regex)        # try every open connection of a DRC report, report what is left
    h.drop(net, layer_or_None, box)                  # remove routed copper (also from the obstacle map) to re-lay it
    h.save('routes/<name>.json')                     # apply with tools/hr2.py

Rules used (template .kicad_pro / .kicad_dru): copper clearance 0.15 mm; 0.25 between HighCurrent copper and
small-signal copper when neither is a pad; hard pours 0.3 (they refill with their own clearance); copper to board
edge 0.25; copper to a hole of another net 0.2; via 0.45 / 0.3, via centres 0.5 apart (same net) or 0.6 (other net);
via hole to a pad hole of 0.5 mm or more 0.45. Pours of GND, PACK_P and 3V3 refill and are not obstacles.
Grid 0.05 mm. A track that stays inside a pad of its own net is always allowed (that is how it leaves a fine-pitch row).
Everything routed is checked again by the real DRC when hr2.py applies it."""
import sys, os, json, math, re, fnmatch, heapq
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, Point, LineString, box as sbox
from shapely.strtree import STRtree
from obst import HR, SIG
G = 0.05
TOL = 0.025                                          # raster margin on every halo
EMPTY, MULTI = -1, -2

try:
    from numba import njit
except Exception:                                    # pragma: no cover
    njit = lambda *a, **k: (lambda f: f)

@njit(cache=True)
def _astar(blk, viaok, vpen, start, goal, tx, ty, lcost, via_cost, bend):
    NL, H, W = blk.shape
    INF = 1e18
    best = np.full((NL, H, W), INF)
    par = np.full((NL, H, W), -1, np.int64)
    done = np.zeros((NL, H, W), np.uint8)
    dxs = np.array([1, -1, 0, 0, 1, 1, -1, -1]); dys = np.array([0, 0, 1, -1, 1, -1, 1, -1])
    dc = np.array([1.0, 1.0, 1.0, 1.0, 1.4142, 1.4142, 1.4142, 1.4142])
    pq = [(0.0, 0, 0, 0)]
    pq.pop()
    for l in range(NL):
        for y in range(H):
            for x in range(W):
                if start[l, y, x]:
                    best[l, y, x] = 0.0
                    heapq.heappush(pq, (math.hypot(x - tx, y - ty), l, y, x))
    end = -1
    while len(pq) > 0:
        f, l, y, x = heapq.heappop(pq)
        if done[l, y, x]:
            continue
        done[l, y, x] = 1
        if goal[l, y, x]:
            end = (l * H + y) * W + x
            break
        g0 = best[l, y, x]
        p = par[l, y, x]
        pdx = 0; pdy = 0; pl = l
        if p >= 0:
            pl = p // (H * W); py = (p // W) % H; px = p % W
            pdx = x - px; pdy = y - py
        for k in range(8):
            nx = x + dxs[k]; ny = y + dys[k]
            if nx < 0 or ny < 0 or nx >= W or ny >= H:
                continue
            if blk[l, ny, nx] or done[l, ny, nx]:
                continue
            if k >= 4 and (blk[l, y, nx] or blk[l, ny, x]):
                continue                              # no corner cutting
            c = g0 + dc[k] * lcost[l]
            if p >= 0 and pl == l and (pdx != dxs[k] or pdy != dys[k]):
                c += bend
            if c < best[l, ny, nx]:
                best[l, ny, nx] = c; par[l, ny, nx] = (l * H + y) * W + x
                heapq.heappush(pq, (c + math.hypot(nx - tx, ny - ty), l, ny, nx))
        if viaok[y, x]:
            for nl in range(NL):
                if nl == l or blk[nl, y, x] or done[nl, y, x]:
                    continue
                c = g0 + via_cost + vpen[y, x]
                if c < best[nl, y, x]:
                    best[nl, y, x] = c; par[nl, y, x] = (l * H + y) * W + x
                    heapq.heappush(pq, (c + math.hypot(x - tx, y - ty), nl, y, x))
    out = [end]
    if end < 0:
        return out
    c = end
    while True:
        l = c // (H * W); y = (c // W) % H; x = c % W
        p = par[l, y, x]
        if p < 0:
            break
        out.append(p); c = p
    return out


class ML(HR):
    def __init__(self, d, board, pro=None):
        super().__init__(d, board)
        d = os.path.abspath(d); self.dir = d; self.board = board
        D = json.load(open("%s/%s.json" % (d, board)))
        pro = pro or "%s/%s.kicad_pro" % (d, board)
        if not os.path.exists(pro): pro = d + "/cu.kicad_pro"
        pats = json.load(open(pro))["net_settings"].get("netclass_patterns", [])
        self._pats = [(p["pattern"], p["netclass"]) for p in pats]; self._cls = {}
        bx = self.outline.bounds
        self.x0, self.y0 = bx[0] - 0.5, bx[1] - 0.5
        self.W, self.H = int((bx[2] - bx[0] + 1.0) / G) + 1, int((bx[3] - bx[1] + 1.0) / G) + 1
        self.holes = [(p["x"], p["y"], p["drill"], p["net"], bool(p.get("npth"))) for p in D["pads"] if p.get("drill")]
        self.npth = [Polygon(r["ring"]).buffer(0) for p in D["pads"] if p.get("npth") for r in list(p["shapes"].values())[0] if len(r["ring"]) > 2]
        self.ko = []                                   # (poly, layers, no_tracks, no_vias)
        for k in D.get("keepouts", []):
            for pl in k["poly"]:
                self.ko.append((Polygon(pl["ring"]).buffer(0), set(k["layers"]), bool(k.get("no_tracks")), bool(k.get("no_vias"))))
        for L in SIG:                                  # obst.py lumps keep-outs and pre-buffered holes in: take them out
            self.items[L] = [i for i in self.items[L] if i[2] not in ("keepout", "hole")]
        self.tree = {L: STRtree([i[0] for i in self.items[L]]) for L in SIG}
        self._nid = {}; self._grids = {}; self._edge = {}
        self.fail = []

    # ---- net classes
    def cls(self, net):
        if net not in self._cls:
            c = "Default"
            for pat, k in self._pats:
                if fnmatch.fnmatchcase(net, pat): c = k; break
            self._cls[net] = c
        return self._cls[net]
    def nid(self, net):
        if net not in self._nid: self._nid[net] = len(self._nid)
        return self._nid[net]

    # ---- rasters: owner grid per (layer, halo radius, which items)
    def _draw(self, arr, geom, val):
        if geom.is_empty: return
        b = geom.bounds
        c0, r0 = max(0, int((b[0] - self.x0) / G) - 1), max(0, int((b[1] - self.y0) / G) - 1)
        c1, r1 = min(self.W, int((b[2] - self.x0) / G) + 2), min(self.H, int((b[3] - self.y0) / G) + 2)
        if c1 <= c0 or r1 <= r0: return
        im = Image.new("L", (c1 - c0, r1 - r0), 0); dr = ImageDraw.Draw(im)
        for q in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            if q.geom_type != "Polygon" or q.is_empty: continue
            dr.polygon([((x - self.x0) / G - c0, (y - self.y0) / G - r0) for x, y in q.exterior.coords], fill=1, outline=1)
            for hole in q.interiors:
                dr.polygon([((x - self.x0) / G - c0, (y - self.y0) / G - r0) for x, y in hole.coords], fill=0, outline=1)
        m = np.asarray(im, dtype=bool); sub = arr[r0:r1, c0:c1]
        sub[m & (sub != EMPTY) & (sub != val)] = MULTI
        sub[m & (sub == EMPTY)] = val
    def _item_halo(self, it, r, mode):
        """halo polygon of one obstacle item for a route centre line that needs r = clearance 0.15 + half width;
        mode 'hc' = only the extra 0.1 mm of the HighCurrent / small-signal rule."""
        g, n, kind, name = it
        if kind == "pour" and n in self.soft: return None
        if mode == "base":
            return g.buffer(r + (0.15 if kind == "pour" else 0.0), 8)       # hard pours 0.3
        c = self.cls(n)
        if kind == "pad" or (mode == "hc" and c != "HighCurrent") or (mode == "small" and c != "Default"): return None
        return g.buffer(r + 0.1, 8)
    def grid(self, L, r, mode="base"):
        key = (L, round(r, 3), mode)
        if key not in self._grids:
            a = np.full((self.H, self.W), EMPTY, np.int32)
            for it in self.items[L]:
                h = self._item_halo(it, r, mode)
                if h is not None: self._draw(a, h, self.nid(it[1]))
            if mode == "base":
                for x, y, dr, n, np_ in self.holes:    # copper to a hole of another net: 0.2 from the hole wall (0.25 unplated)
                    self._draw(a, Point(x, y).buffer(dr / 2 + (0.25 if np_ else 0.2) + (r - 0.15), 8), MULTI if np_ else self.nid(n))
                for poly in self.npth: self._draw(a, poly.buffer(r - 0.15 + 0.25, 8), MULTI)   # counts as board edge
                for poly, layers, nt, nv in self.ko:
                    if nt and L in layers: self._draw(a, poly.buffer(r - 0.15, 8), MULTI)
            self._grids[key] = a
        return self._grids[key]
    def edge(self, r):
        """cells where a centre line with half-size r (track half width / via radius) is too near the board edge"""
        r = round(r, 3)
        if r not in self._edge:
            ob = self.outline.buffer(-(0.25 + r + TOL))
            im = Image.new("L", (self.W, self.H), 1); dr = ImageDraw.Draw(im)
            for q in (ob.geoms if hasattr(ob, "geoms") else [ob]):
                dr.polygon([((x - self.x0) / G, (y - self.y0) / G) for x, y in q.exterior.coords], fill=0)
                for hole in q.interiors: dr.polygon([((x - self.x0) / G, (y - self.y0) / G) for x, y in hole.coords], fill=1)
            self._edge[r] = np.asarray(im, dtype=bool)
        return self._edge[r]
    def _viahole(self):
        """cells where no via centre may go whatever its net: hole-to-hole"""
        if "vh" not in self._grids:
            a = np.full((self.H, self.W), EMPTY, np.int32)
            for x, y, dr, n, np_ in self.holes:
                self._draw(a, Point(x, y).buffer(dr / 2 + 0.15 + (0.45 if dr >= 0.5 else 0.2) + 0.02, 8), MULTI)
            for x, y, s, n in self.vias: self._draw(a, Point(x, y).buffer(0.5 + 0.02, 8), MULTI)
            for poly, layers, nt, nv in self.ko:
                if nv: self._draw(a, poly.buffer(0.225, 8), MULTI)
            self._grids["vh"] = a
        return self._grids["vh"]
    def _blocked(self, net, L, half, win):
        """True where a centre line of this net with this half width may not go (window = r0, r1, c0, c1)"""
        r0, r1, c0, c1 = win; me = self.nid(net); r = 0.15 + half + TOL
        a = self.grid(L, r)[r0:r1, c0:c1]; b = (a != EMPTY) & (a != me)
        c = self.cls(net)
        if c in ("Default", "HighCurrent"):
            e = self.grid(L, r, "hc" if c == "Default" else "small")[r0:r1, c0:c1]; b |= (e != EMPTY) & (e != me)
        return b | self.edge(half)[r0:r1, c0:c1]
    def _add(self, L, g, net, kind):
        self.items[L].append((g, net, kind, net)); self.tree[L] = STRtree([i[0] for i in self.items[L]])
        for (LL, r, mode), a in [(k, v) for k, v in self._grids.items() if k != "vh"]:
            if LL != L: continue
            h = self._item_halo((g, net, kind, net), r, mode)
            if h is not None: self._draw(a, h, self.nid(net))
    def via(self, net, x, y, quiet=True):
        self.J["vias"].append({"net": net, "x": x, "y": y}); self.vias.append((x, y, 0.45, net))
        for L in SIG: self._add(L, Point(x, y).buffer(0.225, 8), net, "via")
        if "vh" in self._grids: self._draw(self._grids["vh"], Point(x, y).buffer(0.52, 8), MULTI)
        return True
    def drop(self, net, L, box):
        """remove routed tracks (both ends in the box) and vias (in the box) of a net; the obstacle map forgets them too"""
        self.J["drop"].append({"net": net, "layer": L, "box": box}); B = sbox(*box)
        for LL in SIG:
            keep = []
            for it in self.items[LL]:
                g, n, kind, name = it
                if n == net and ((kind == "track" and (L is None or LL == L) and B.contains(g)) or (kind == "via" and B.contains(g.centroid))): continue
                keep.append(it)
            self.items[LL] = keep
        self.vias = [v for v in self.vias if not (v[3] == net and B.contains(Point(v[0], v[1])))]
        self.tree = {LL: STRtree([i[0] for i in self.items[LL]]) for LL in SIG}; self._grids = {}

    def via_free(self, net, x, y):
        """True if a 0.45 / 0.3 via of this net is legal at this point by the real rules"""
        c = int(round((x - self.x0) / G)); r = int(round((y - self.y0) / G)); me = self.nid(net); vr = 0.15 + 0.225 + TOL; k = self.cls(net)
        for L in SIG:
            v = self.grid(L, vr)[r, c]
            if v != EMPTY and v != me: return False
            if k in ("Default", "HighCurrent"):
                v = self.grid(L, vr, "hc" if k == "Default" else "small")[r, c]
                if v != EMPTY and v != me: return False
        return self._viahole()[r, c] == EMPTY and not self.edge(0.225)[r, c]
    def via_near(self, net, x, y, r=1.0, n=1, inside=None):
        """nearest legal via spots to a point (optionally only inside a shapely shape): [(dist, x, y)]"""
        out = []; k = int(r / G)
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                px, py = round(x + i * G, 3), round(y + j * G, 3); d = math.hypot(px - x, py - y)
                if d <= r and (inside is None or inside.contains(Point(px, py))) and self.via_free(net, px, py): out.append((round(d, 3), px, py))
        out.sort(); res = []
        for o in out:
            if all(math.hypot(o[1] - q[1], o[2] - q[2]) > 0.3 for q in res): res.append(o)
            if len(res) >= n: break
        return res
    def pad(self, ref, num, n=0):
        """pad centre and shape from the board dump: (x, y, polygon, net, layer)"""
        if not hasattr(self, "_pads"):
            D = json.load(open("%s/%s.json" % (self.dir, self.board))); self._pads = {}
            for p in D["pads"]:
                if not p["shapes"]: continue
                L = "F.Cu" if "F.Cu" in p["shapes"] else list(p["shapes"])[0]
                self._pads.setdefault((p["ref"], p["num"]), []).append((p["x"], p["y"], Polygon(p["shapes"][L][0]["ring"]).buffer(0), p["net"], L))
        return self._pads[(ref, str(num))][n]

    # ---- search
    def _own(self, net, p, layers):
        """same-net copper under a point: {layer: [geoms]} (pads, vias, tracks, pours of the net that contain it)"""
        out = {}; P = Point(p)
        for L in layers:
            for i in self.tree[L].query(P.buffer(0.03)):
                g, n, kind, name = self.items[L][int(i)]
                if n == net and kind != "pour" and g.distance(P) < 0.03: out.setdefault(L, []).append(g)
        return out
    def route(self, net, a, b, w=0.2, layers=SIG, margin=4.0, via_cost=1.5, quiet=False, goal_geoms=None, box=None, end_via=False, start_geoms=None):
        """a, b = (x, y) on copper of the net (pad centre, via, track end). Returns the path [[layer, x, y], ...] or None."""
        layers = tuple(layers); half = w / 2
        xs = [a[0], b[0]]; ys = [a[1], b[1]]
        if box: xs += [box[0], box[2]]; ys += [box[1], box[3]]; margin = 0.5 if margin == 4.0 else margin
        c0 = max(0, int((min(xs) - margin - self.x0) / G)); c1 = min(self.W, int((max(xs) + margin - self.x0) / G) + 1)
        r0 = max(0, int((min(ys) - margin - self.y0) / G)); r1 = min(self.H, int((max(ys) + margin - self.y0) / G) + 1)
        win = (r0, r1, c0, c1); Hh, Ww = r1 - r0, c1 - c0
        blk = np.zeros((len(layers), Hh, Ww), np.uint8)
        for li, L in enumerate(layers): blk[li] = self._blocked(net, L, half, win)
        # vias: legal on every signal layer (a via goes through all of them), spacing to holes and vias
        vb = np.zeros((Hh, Ww), bool); me = self.nid(net); vr = 0.15 + 0.225 + TOL; c = self.cls(net)
        for L in SIG:
            g_ = self.grid(L, vr)[r0:r1, c0:c1]; vb |= (g_ != EMPTY) & (g_ != me)
            if c in ("Default", "HighCurrent"):
                e = self.grid(L, vr, "hc" if c == "Default" else "small")[r0:r1, c0:c1]; vb |= (e != EMPTY) & (e != me)
        vb |= self._viahole()[r0:r1, c0:c1] != EMPTY; vb |= self.edge(0.225)[r0:r1, c0:c1]
        viaok = (~vb).astype(np.uint8)
        vpen = np.zeros((Hh, Ww)); pm = Image.new("L", (Ww, Hh), 0); pd = ImageDraw.Draw(pm)
        wb = sbox(self.x0 + c0 * G, self.y0 + r0 * G, self.x0 + c1 * G, self.y0 + r1 * G)
        for L in ("F.Cu", "B.Cu"):                     # a via inside an SMD pad of the net itself: last resort
            for i in self.tree[L].query(wb):
                g, n, kind, name = self.items[L][int(i)]
                if n == net and kind == "pad":
                    for q in (g.geoms if hasattr(g, "geoms") else [g]):
                        pd.polygon([((x - self.x0) / G - c0, (y - self.y0) / G - r0) for x, y in q.exterior.coords], fill=1)
        vpen[np.asarray(pm, dtype=bool)] = 6.0 / G
        def mask(geoms_by_layer, pt):
            m = np.zeros((len(layers), Hh, Ww), np.uint8)
            for li, L in enumerate(layers):
                gs = geoms_by_layer.get(L, [])
                if not gs: continue
                im = Image.new("L", (Ww, Hh), 0); dr = ImageDraw.Draw(im)
                for g in gs:
                    g2 = g.buffer(-0.02) if g.area > 0.01 else g
                    for q in (g2.geoms if hasattr(g2, "geoms") else [g2]):
                        if q.is_empty: continue
                        dr.polygon([((x - self.x0) / G - c0, (y - self.y0) / G - r0) for x, y in q.exterior.coords], fill=1)
                cx, cy = int(round((pt[0] - self.x0) / G)) - c0, int(round((pt[1] - self.y0) / G)) - r0
                mm = np.asarray(im, dtype=np.uint8).copy()
                if 0 <= cx < Ww and 0 <= cy < Hh: mm[cy, cx] = 1
                m[li] = mm
            return m
        A = start_geoms if start_geoms is not None else self._own(net, a, layers); B = goal_geoms if goal_geoms is not None else self._own(net, b, layers)
        if not A or not B:
            if not quiet: print("  route %s: no copper of the net at %s" % (net, a if not A else b))
            self.ok = False; return None
        start = mask(A, a); goal = mask(B, b)
        if end_via:                                    # the goal is "any legal via spot inside these shapes"
            goal = goal & viaok[None, :, :] & (1 - (vpen > 0).astype(np.uint8))[None, :, :]; blk[start > 0] = 0
        else:
            blk[(start > 0) | (goal > 0)] = 0          # inside its own copper a track is always allowed
        lc = np.array([{"F.Cu": 1.15, "B.Cu": 1.15}.get(L, 1.0) for L in layers])
        tx, ty = (b[0] - self.x0) / G - c0, (b[1] - self.y0) / G - r0
        res = _astar(blk, viaok, vpen, start, goal, tx, ty, lc, via_cost / G, 3.0)
        if res[0] < 0:
            if not quiet: print("  route %s (%.2f, %.2f)->(%.2f, %.2f): NO PATH" % (net, a[0], a[1], b[0], b[1]))
            self.ok = False; return None
        cells = [(c_ // (Hh * Ww), (c_ // Ww) % Hh, c_ % Ww) for c_ in res][::-1]
        P = lambda cc: (round(self.x0 + (cc[2] + c0) * G, 3), round(self.y0 + (cc[1] + r0) * G, 3))
        pts = []                                       # [layer, x, y] corner points
        for i, cc in enumerate(cells):
            L = layers[cc[0]]; x, y = P(cc)
            if i == 0 or i == len(cells) - 1 or cells[i - 1][0] != cc[0] or cells[i + 1][0] != cc[0]: pts.append([L, x, y]); continue
            p, n = cells[i - 1], cells[i + 1]
            if (cc[1] - p[1], cc[2] - p[2]) != (n[1] - cc[1], n[2] - cc[2]): pts.append([L, x, y])
        # snap the ends to the exact points when they lie in the start / goal copper
        def snap(pt, first):
            L = pts[0][0] if first else pts[-1][0]; own = self._own(net, pt, (L,))
            if own:
                e = [L, round(pt[0], 3), round(pt[1], 3)]
                if first and (pts[0][1], pts[0][2]) != (e[1], e[2]): pts.insert(0, e)
                if not first and (pts[-1][1], pts[-1][2]) != (e[1], e[2]): pts.append(e)
        if start_geoms is None: snap(a, True)
        if goal_geoms is None: snap(b, False)
        if end_via: pts.append([[L_ for L_ in SIG if L_ != pts[-1][0]][-1], pts[-1][1], pts[-1][2]]); pts.append(list(pts[-1]))
        self.J["routes"].append({"net": net, "w": w, "path": pts})
        for p, q in zip(pts, pts[1:]):
            if p[0] != q[0]:
                self.vias.append((p[1], p[2], 0.45, net))
                for L in SIG: self._add(L, Point(p[1], p[2]).buffer(0.225, 8), net, "via")
                if "vh" in self._grids: self._draw(self._grids["vh"], Point(p[1], p[2]).buffer(0.52, 8), MULTI)
            elif (p[1], p[2]) != (q[1], q[2]):
                self._add(q[0], LineString([(p[1], p[2]), (q[1], q[2])]).buffer(half, 8), net, "track")
        if not quiet:
            nv = sum(1 for p, q in zip(pts, pts[1:]) if p[0] != q[0]); ln = sum(math.hypot(q[1] - p[1], q[2] - p[2]) for p, q in zip(pts, pts[1:]))
            print("  route %s ok: %.1f mm, %d vias, layers %s" % (net, ln, nv, "".join(sorted({p[0][:3] for p in pts}))))
        return pts
    PLANE = {"GND": None, "3V3": "In3.Cu", "PACK_P": "In2.Cu"}
    def plane(self, net, a, reach=3.0, w=0.2, layers=("F.Cu",), quiet=False):
        """a pad of GND / 3V3 / PACK_P: a short track on the pad's layer to the nearest legal via spot that lands on the
        net's plane (GND: anywhere, In1/In4 are solid; 3V3: inside its In3 pour; PACK_P: inside its In2 pour)."""
        pl = self.PLANE[net]; bx = sbox(a[0] - reach, a[1] - reach, a[0] + reach, a[1] + reach)
        if pl is None: gg = {L: [bx] for L in layers}
        else:
            ps = [self.items[pl][int(i)][0] for i in self.tree[pl].query(bx) if self.items[pl][int(i)][1] == net and self.items[pl][int(i)][2] in ("pour", "track")]
            ps = [g.buffer(-0.45).intersection(bx) for g in ps]; ps = [g for g in ps if not g.is_empty]
            if not ps:
                if not quiet: print("  plane %s: no %s copper of the net within %.1f mm" % (net, pl, reach))
                return None
            gg = {L: ps for L in layers}
        return self.route(net, a, a, w=w, layers=layers, margin=reach, goal_geoms=gg, end_via=True, quiet=quiet)
    def force(self, net, layer, pts, w=0.2):
        """a track through exact points that the search grid cannot find (0.05 mm grid); NOT checked here, the real DRC
        in hr2.py is the check. Use for short stubs out of fine-pitch pins and for exact 0.1 mm nudges."""
        self.J["routes"].append({"net": net, "w": w, "path": [[layer, round(x, 3), round(y, 3)] for x, y in pts]})
        self._add(layer, LineString(pts).buffer(w / 2, 8), net, "track")
    def try_route(self, net, a, b, **kw):
        """route with fall-backs: 0.2 mm, then 0.15 mm, then a wider window"""
        for w, m in ((kw.pop("w", 0.2), 4.0), (0.15, 4.0), (0.15, 12.0)):
            p = self.route(net, a, b, w=w, margin=m, quiet=True, **kw)
            if p: self.ok = True; return p
        return None

    # ---- open connections from a DRC report
    @staticmethod
    def opens(drc, only=None, skip=None):
        D = json.load(open(drc)) if isinstance(drc, str) else drc; out = []
        for u in D.get("unconnected_items", []):
            it = u["items"][:2]; m = re.search(r"\[(.*?)\]", it[0]["description"])
            if not m: continue
            net = m.group(1)
            if (only and not re.search(only, net)) or (skip and re.search(skip, net)): continue
            out.append((net, (it[0]["pos"]["x"], it[0]["pos"]["y"]), (it[1]["pos"]["x"], it[1]["pos"]["y"]),
                        re.sub(r"\s+", " ", it[0]["description"])[:60], re.sub(r"\s+", " ", it[1]["description"])[:60]))
        return out
    def close(self, drc, only=None, skip=None, **kw):
        todo = self.opens(drc, only, skip); todo.sort(key=lambda t: math.hypot(t[1][0] - t[2][0], t[1][1] - t[2][1])); left = []
        for net, a, b, da, db in todo:
            p = self.try_route(net, a, b, **kw) if net not in self.PLANE else None
            if p is None and net in self.PLANE:        # plane nets: each end gets its own via to the plane
                p = self.plane(net, a, quiet=True) or self.plane(net, b, quiet=True)
            if p is None: left.append((net, a, b, da, db)); print("  LEFT %s  %s @%.2f,%.2f -> %s @%.2f,%.2f" % (net, da, a[0], a[1], db, b[0], b[1]))
            else: print("  closed %s (%.2f, %.2f)->(%.2f, %.2f)" % (net, a[0], a[1], b[0], b[1]))
        print("closed %d of %d, %d left" % (len(todo) - len(left), len(todo), len(left))); self.fail = left; return left
