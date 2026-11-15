"""rip.py: RML = ML + local rip-up.  h.rip(net, A, B) joins two pieces of a net when no free path exists:
1. search with the tracks of other small-signal nets taken away (vias, pads, pours and protected nets stay);
2. the tracks the new path collides with are the victims: each is dropped (whole segment) and its net is joined up again
   with a set-to-set search; if a victim does not come back the whole step is undone and the search is repeated with that
   net protected.
h.comps(net) lists the connected pieces of a net (pads, tracks, vias; pours ignored).  h.join(net) joins all pieces."""
import sys, os, re, copy, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ml import ML, SIG
from shapely.geometry import Point, LineString, box as sbox
from shapely.strtree import STRtree
from shapely.ops import unary_union
PROT = r"AC_SNS|BAT_SNS|PPHV|CELL_N|^GND$|^3V3$|PACK_P"

def ends(g):
    """end points and width of a buffered straight segment"""
    r = list(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [(math.hypot(r[i][0] - r[(i + 1) % 4][0], r[i][1] - r[(i + 1) % 4][1]), i) for i in range(4)]
    w = min(e)[0]; i = min(e)[1]
    m1 = ((r[i][0] + r[(i + 1) % 4][0]) / 2, (r[i][1] + r[(i + 1) % 4][1]) / 2); m2 = ((r[(i + 2) % 4][0] + r[(i + 3) % 4][0]) / 2, (r[(i + 2) % 4][1] + r[(i + 3) % 4][1]) / 2)
    L = math.hypot(m2[0] - m1[0], m2[1] - m1[1])
    if L < 1e-6: return m1, m2, w
    ux, uy = (m2[0] - m1[0]) / L, (m2[1] - m1[1]) / L
    return (m1[0] + ux * w / 2, m1[1] + uy * w / 2), (m2[0] - ux * w / 2, m2[1] - uy * w / 2), w

class RML(ML):
    def __init__(self, d, board):
        super().__init__(d, board); self._orig = {id(it) for L in SIG for it in self.items[L]}     # copper of the board itself; only that may be pulled
    def _reset(self): self.tree = {L: STRtree([i[0] for i in self.items[L]]) for L in SIG}; self._grids = {}
    def snap_(self): return ({L: list(v) for L, v in self.items.items()}, list(self.vias), copy.deepcopy(self.J))
    def back_(self, s): self.items = {L: list(v) for L, v in s[0].items()}; self.vias = list(s[1]); self.J = copy.deepcopy(s[2]); self._reset()
    def comps(self, net):
        """connected pieces of a net: list of {layer: [geoms]}"""
        nodes = [(L, g, kind) for L in SIG for g, n, kind, name in self.items[L] if n == net and kind in ("pad", "track", "via")]
        par = list(range(len(nodes)))
        def f(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        byL = {}
        for i, (L, g, k) in enumerate(nodes): byL.setdefault(L, []).append(i)
        for L, idx in byL.items():
            t = STRtree([nodes[i][1] for i in idx])
            for a_, i in enumerate(idx):
                for b_ in t.query(nodes[i][1]):
                    j = idx[int(b_)]
                    if j > i and nodes[i][1].distance(nodes[j][1]) < 0.005: par[f(i)] = f(j)
        thru = {}
        for i, (L, g, k) in enumerate(nodes):
            if k == "via" or (k == "pad" and sum(1 for LL in SIG for g2, n2, k2, _ in () ) == 0 and False): pass
            if k in ("via", "pad"):
                key = (round(g.centroid.x, 2), round(g.centroid.y, 2), round(g.area, 3)); thru.setdefault(key, []).append(i)
        for key, idx in thru.items():
            if len({nodes[i][0] for i in idx}) > 1:
                for i in idx[1:]: par[f(i)] = f(idx[0])
        out = {}
        for i, (L, g, k) in enumerate(nodes): out.setdefault(f(i), {}).setdefault(L, []).append(g)
        return list(out.values())
    def join(self, net, want=1, margin=30.0, quiet=True, **kw):
        """join the pieces of a net with free paths until `want` pieces are left; True if reached"""
        for _ in range(30):
            C = self.comps(net)
            if len(C) <= want: return True
            C.sort(key=lambda c: sum(g.area for gs in c.values() for g in gs)); A = C[0]; B = {}
            for c in C[1:]:
                for L, gs in c.items(): B.setdefault(L, []).extend(gs)
            pa = list(A.values())[0][0].representative_point(); pb = min((g for gs in B.values() for g in gs), key=lambda g: g.distance(pa)).representative_point()
            r = None
            for w in (kw.get("w", 0.2), 0.15):
                r = self.route(net, (pa.x, pa.y), (pb.x, pb.y), w=w, margin=margin, start_geoms=A, goal_geoms=B, quiet=True)
                if r: break
            if not r:
                if not quiet: print("  join %s: NO PATH from the piece at (%.2f, %.2f)" % (net, pa.x, pa.y))
                return False
        return False
    def rip(self, net, A, B, a, b, w=0.2, margin=8.0, protect=(), tries=6, layers=SIG, depth=1):
        """A, B = {layer: [geoms]} start and goal copper (e.g. from comps); a, b = points near them (for the window)."""
        protect = set(protect)
        for t in range(tries):
            s0 = self.snap_(); removed = []
            for L in SIG:
                keep = []
                for it in self.items[L]:
                    g, n, kind, name = it
                    if kind == "track" and id(it) in self._orig and n != net and n not in protect and not re.search(PROT, n) and self.cls(n) != "HighCurrent": removed.append((L, it))
                    else: keep.append(it)
                self.items[L] = keep
            self._reset()
            r = None
            for ww in (w, 0.15):
                r = self.route(net, a, b, w=ww, margin=margin, start_geoms=A, goal_geoms=B, quiet=True, layers=layers)
                if r: break
            if not r: self.back_(s0); print("  rip %s: no way even without the other signal tracks (try %d)" % (net, t)); return None
            newJ = copy.deepcopy(self.J); new_items = {L: self.items[L][len(s0[0][L]) - sum(1 for LL, _ in removed if LL == L):] for L in SIG}
            # victims: removed tracks too close to the new copper
            vict = []
            for L, it in removed:
                near = [g for g, n, k, _ in new_items[L] if g.distance(it[0]) < 0.15 - 0.005]
                if near: vict.append((L, it))
            self.back_(s0)
            vn = sorted({it[1] for L, it in vict}); before = {n: len(self.comps(n)) for n in vn}
            for L, it in vict:
                p, q, _ = ends(it[0]); bx = [min(p[0], q[0]) - 0.02, min(p[1], q[1]) - 0.02, max(p[0], q[0]) + 0.02, max(p[1], q[1]) + 0.02]
                self.J["drop"].append({"net": it[1], "layer": L, "box": [round(v, 3) for v in bx], "tracks_only": True})
                keep = []
                for i2 in self.items[L]:
                    if i2[1] == it[1] and i2[2] == "track":
                        p2, q2, _ = ends(i2[0])
                        if all(bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3] for x, y in (p2, q2)): continue
                    keep.append(i2)
                self.items[L] = keep
            self._reset()
            # the new route goes in first, then the victims come back round it
            for rt in newJ["routes"][len(s0[2]["routes"]):]:
                self.J["routes"].append(rt); pts = rt["path"]
                for p, q in zip(pts, pts[1:]):
                    if p[0] != q[0]: self.via(net, p[1], p[2]); self.J["vias"].pop()
                    elif (p[1], p[2]) != (q[1], q[2]): self._add(q[0], LineString([(p[1], p[2]), (q[1], q[2])]).buffer(rt["w"] / 2, 8), net, "track")
            bad = None
            for n in vn:
                if not self.join(n, want=before[n], margin=margin + 4):
                    ok = False
                    if depth > 0:
                        for _ in range(4):
                            C = self.comps(n)
                            if len(C) <= before[n]: ok = True; break
                            C.sort(key=lambda c: sum(g.area for gs in c.values() for g in gs)); A2 = C[0]; B2 = {}
                            for c in C[1:]:
                                for L, gs in c.items(): B2.setdefault(L, []).extend(gs)
                            pa = list(A2.values())[0][0].representative_point(); pb = min((g for gs in B2.values() for g in gs), key=lambda g: g.distance(pa)).representative_point()
                            if not self.rip(n, A2, B2, (pa.x, pa.y), (pb.x, pb.y), margin=margin, protect=protect | {net} | set(vn), tries=3, depth=depth - 1): break
                            if self.join(n, want=before[n], margin=margin + 4): ok = True; break
                    if not ok: bad = n; break
            if bad is None:
                print("  rip %s ok: pulled and re-laid %s" % (net, vn or "nothing")); return r
            print("  rip %s: %s did not come back, protecting it (try %d)" % (net, bad, t)); self.back_(s0); protect.add(bad)
        return None
    def pull(self, net, box, layer=None):
        """remove the net's track segments with both ends in the box and its vias in the box (same meaning as hr2's drop)"""
        self.J["drop"].append({"net": net, "layer": layer, "box": box}); n0 = 0
        inb = lambda p: box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
        for L in SIG:
            keep = []
            for it in self.items[L]:
                g, n, kind, name = it
                if n == net and kind == "track" and (layer is None or L == layer):
                    p, q, _ = ends(g)
                    if inb(p) and inb(q): n0 += 1; continue
                if n == net and kind == "via" and inb((g.centroid.x, g.centroid.y)): n0 += 1; continue
                keep.append(it)
            self.items[L] = keep
        self.vias = [v for v in self.vias if not (v[3] == net and inb(v))]; self._reset(); return n0
    def lay(self, net, path, w):
        """put a known path [[layer, x, y], ...] in (not checked)"""
        self.J["routes"].append({"net": net, "w": w, "path": path})
        for p, q in zip(path, path[1:]):
            if p[0] != q[0]: self.via(net, p[1], p[2]); self.J["vias"].pop()
            elif (p[1], p[2]) != (q[1], q[2]): self._add(q[0], LineString([(p[1], p[2]), (q[1], q[2])]).buffer(w / 2, 8), net, "track")
