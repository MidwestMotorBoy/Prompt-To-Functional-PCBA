"""obst.py: what is in the way on a board with copper, for hand routing.
  python3 obst.py <dir> <board name without .kicad_pcb> via  <net> <x> <y> [radius=1.5]   nearest free through-via spots for this net
  python3 obst.py <dir> <board> path <routes.json>                                        clearance check of every hand route in the file
  python3 obst.py <dir> <board> at   <x> <y> [r=0.5]                                      what copper is within r of a point, per layer
<dir>/<board>.kicad_pcb must exist; <dir>/<board>.json (cu_dump) is made with docker if missing.
Clearances used: 0.2 mm to other-net copper (0.3 to pours of other nets), via 0.45/0.3, 0.75 mm via centre to other-net via,
0.6 to same-net via. Inner planes In1/In4 (GND) are ignored: a via gets its own antipad there.
As a module:  O = Obst(dir, board); O.free_vias(net, x, y, r); O.check(net, layer, a, b, w); O.near(x, y, r)"""
import sys, os, json, math, subprocess
from shapely.geometry import Polygon, Point, LineString
from shapely.strtree import STRtree
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.abspath(HERE + "/../../../..")
sys.path.insert(0, R + "/tools/copper")
from dc_score import load_copper
SIG = ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu")

class Obst:
    def __init__(self, d, board):
        d = os.path.abspath(d); pcb = "%s/%s.kicad_pcb" % (d, board); dump = "%s/%s.json" % (d, board)
        if not os.path.exists(dump) or os.path.getmtime(dump) < os.path.getmtime(pcb):
            import shutil; shutil.copy(R + "/tools/copper/cu_dump.py", d)
            subprocess.run(["docker", "run", "--rm", "-u", "0", "-v", d + ":/w", "-w", "/w", "kicad/kicad:10.0", "sh", "-c",
                            "python3 cu_dump.py %s.kicad_pcb %s.json 2>&1 | grep -v swig" % (board, board)], check=False)
        D = json.load(open(dump)); Z, T, V = load_copper(pcb)
        self.items = {L: [] for L in SIG}                    # layer -> [(geom, net, kind, name)]
        for p in D["pads"]:
            for L, recs in p["shapes"].items():
                for r in recs:
                    if len(r["ring"]) > 2:
                        g = Polygon(r["ring"]).buffer(0)
                        for LL in (SIG if p.get("drill") else [L]):
                            if LL in self.items: self.items[LL].append((g, p["net"], "pad", p["ref"] + "." + p["num"]))
            if p.get("drill"):
                g = Point(p["x"], p["y"]).buffer(p["drill"] / 2 + 0.25)
                for LL in SIG: self.items[LL].append((g, p["net"], "hole", p["ref"] + "." + p["num"]))
        for z in Z:
            if z["layer"] in self.items and len(z["pts"]) > 2:
                self.items[z["layer"]].append((Polygon(z["pts"]).buffer(0), z["net"], "pour", z["net"]))
        for t in T:
            if t["layer"] in self.items:
                self.items[t["layer"]].append((LineString([t["a"], t["b"]]).buffer(t["w"] / 2), t["net"], "track", t["net"]))
        self.vias = [(v["x"], v["y"], v["size"], v["net"]) for v in V]
        for x, y, s, n in self.vias:
            for L in SIG: self.items[L].append((Point(x, y).buffer(s / 2), n, "via", n))
        for k in D.get("keepouts", []):
            if k.get("no_tracks") or k.get("no_vias"):
                for pl in k["poly"]:
                    for L in k["layers"]:
                        if L in self.items: self.items[L].append((Polygon(pl["ring"]).buffer(0), "<keepout>", "keepout", k["name"]))
        self.outline = Polygon(D["outline"][0]["ring"], D["outline"][0].get("holes", []))
        self.tree = {L: STRtree([i[0] for i in self.items[L]]) for L in SIG}
        self.soft = ("GND", "PACK_P", "3V3")                 # their pours refill round a new track or via

    def hits(self, geom, net, L, clr=0.2, pour_clr=0.3):
        out = []
        for i in self.tree[L].query(geom.buffer(pour_clr)):
            g, n, kind, name = self.items[L][int(i)]
            if n == net: continue
            if kind == "pour" and n in self.soft: continue
            d = geom.distance(g)
            if d < (pour_clr if kind == "pour" else clr) - 1e-6: out.append((round(d, 3), kind, name, L))
        return out

    def via_ok(self, net, x, y, size=0.45):
        g = Point(x, y).buffer(size / 2); bad = []
        if not self.outline.contains(g.buffer(0.3)): return [(0, "edge", "board edge", "")]
        for L in SIG: bad += self.hits(g, net, L)
        for vx, vy, s, n in self.vias:
            d = math.hypot(vx - x, vy - y)
            if 1e-6 < d < (0.6 if n == net else 0.75): bad.append((round(d, 3), "via spacing", n, ""))
        return bad

    def free_vias(self, net, x, y, r=1.5, step=0.05, n=8):
        c = []; k = int(r / step)
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                px, py = round(x + i * step, 3), round(y + j * step, 3); d = math.hypot(px - x, py - y)
                if d <= r and not self.via_ok(net, px, py): c.append((d, px, py))
        c.sort(); out = []
        for d, px, py in c:                                   # spread the answers out a little
            if all(math.hypot(px - q[1], py - q[2]) > 0.3 for q in out): out.append((round(d, 2), px, py))
            if len(out) >= n: break
        return out

    def check(self, net, L, a, b, w=0.2):
        return self.hits(LineString([a, b]).buffer(w / 2), net, L)

    def near(self, x, y, r=0.5):
        out = []
        for L in SIG:
            for i in self.tree[L].query(Point(x, y).buffer(r)):
                g, n, kind, name = self.items[L][int(i)]; d = g.distance(Point(x, y))
                if d <= r: out.append((L, round(d, 2), kind, name, n))
        return sorted(set(out))

    def check_routes(self, J):
        bad = 0
        for r in J.get("routes", []):
            pts = r["path"]
            for a, b in zip(pts, pts[1:]):
                if a[0] != b[0]:
                    for h in self.via_ok(r["net"], a[1], a[2]): bad += 1; print("  VIA  %s (%.2f, %.2f): %s" % (r["net"], a[1], a[2], h))
                if (a[1], a[2]) != (b[1], b[2]):
                    for h in self.check(r["net"], b[0], (a[1], a[2]), (b[1], b[2]), r.get("w", 0.2)):
                        bad += 1; print("  SEG  %s %s (%.2f, %.2f)-(%.2f, %.2f): %s" % (r["net"], b[0], a[1], a[2], b[1], b[2], h))
        for v in J.get("vias", []):
            for h in self.via_ok(v["net"], v["x"], v["y"]): bad += 1; print("  VIA  %s (%.2f, %.2f): %s" % (v["net"], v["x"], v["y"], h))
        print("clearance problems: %d" % bad); return bad

if __name__ == "__main__":
    O = Obst(sys.argv[1], sys.argv[2]); cmd = sys.argv[3]; a = sys.argv[4:]
    if cmd == "via":
        for d, x, y in O.free_vias(a[0], float(a[1]), float(a[2]), float(a[3]) if len(a) > 3 else 1.5): print("  free via at (%.2f, %.2f), %.2f mm away" % (x, y, d))
    elif cmd == "path": O.check_routes(json.load(open(a[0])))
    elif cmd == "at":
        for h in O.near(float(a[0]), float(a[1]), float(a[2]) if len(a) > 2 else 0.5): print("  ", h)


class HR(Obst):
    """Hand-route builder. Every item added becomes an obstacle for the next, so pairs can be laid side by side.
        h = HR(dir, board)
        h.via(net, x, y)                      a through via (checked; prints the problems, returns False if any)
        h.seg(net, layer, [(x, y), ...])      a track through the points, checked
        h.auto(net, layer, (x, y), (x, y))    a track found on ONE layer between two points, round everything in the way
                                              (45 degree steps, 0.1 mm grid); returns the points or None
        h.link(net, (x, y), (x, y), layer)    via at both ends (nearest free spot within r) + auto on an inner layer + F stubs
        h.cut(net, layer, box) / h.pour(net, layer, box) / h.drop(net, layer, box)
        h.save(path)                          the routes JSON for hr.py"""
    def __init__(self, d, board):
        super().__init__(d, board); self.J = {"routes": [], "vias": [], "cuts": [], "pours": [], "drop": []}; self.ok = True
    def _add(self, L, g, net, kind):
        self.items[L].append((g, net, kind, net)); self.tree[L] = STRtree([i[0] for i in self.items[L]])
    def via(self, net, x, y, quiet=False):
        bad = self.via_ok(net, x, y)
        if bad and not quiet: print("  via %s (%.2f, %.2f) PROBLEM: %s" % (net, x, y, bad[:4])); self.ok = False
        self.J["vias"].append({"net": net, "x": x, "y": y}); self.vias.append((x, y, 0.45, net))
        for L in SIG: self._add(L, Point(x, y).buffer(0.225), net, "via")
        return not bad
    def seg(self, net, L, pts, w=0.2):
        good = True
        for a, b in zip(pts, pts[1:]):
            bad = self.check(net, L, a, b, w)
            if bad: print("  seg %s %s (%.2f, %.2f)-(%.2f, %.2f) PROBLEM: %s" % (net, L, a[0], a[1], b[0], b[1], bad[:4])); good = False; self.ok = False
        self.J["routes"].append({"net": net, "w": w, "path": [[L, round(p[0], 3), round(p[1], 3)] for p in pts]})
        self._add(L, LineString(pts).buffer(w / 2), net, "track"); return good
    def auto(self, net, L, a, b, w=0.2, clr=0.2, margin=3.0, g=0.1):
        import heapq
        from PIL import Image, ImageDraw
        x0, y0 = min(a[0], b[0]) - margin, min(a[1], b[1]) - margin; x1, y1 = max(a[0], b[0]) + margin, max(a[1], b[1]) + margin
        W, H = int((x1 - x0) / g) + 1, int((y1 - y0) / g) + 1; im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im)
        win = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        for i in self.tree[L].query(win):
            geo, n, kind, name = self.items[L][int(i)]
            if n == net or (kind == "pour" and n in self.soft): continue
            bg = geo.buffer((0.3 if kind == "pour" else clr) + w / 2 + g * 0.5)
            for q in (bg.geoms if hasattr(bg, "geoms") else [bg]):
                d.polygon([((x - x0) / g, (y - y0) / g) for x, y in q.exterior.coords], fill=1)
        ob = self.outline.buffer(-(0.35 + w / 2))              # copper keeps 0.3 mm from the board edge
        em = Image.new("L", (W, H), 1); ed = ImageDraw.Draw(em)
        for q in (ob.geoms if hasattr(ob, "geoms") else [ob]):
            ed.polygon([((x - x0) / g, (y - y0) / g) for x, y in q.exterior.coords], fill=0)
            for hole in q.interiors: ed.polygon([((x - x0) / g, (y - y0) / g) for x, y in hole.coords], fill=1)
        from PIL import ImageChops
        im = ImageChops.lighter(im, em)
        px = im.load(); C = lambda p: (int(round((p[0] - x0) / g)), int(round((p[1] - y0) / g)))
        s, t = C(a), C(b)
        for c in (s, t):                                       # the ends are allowed (inside their own pad / via halo)
            for i in range(-3, 4):
                for j in range(-3, 4):
                    if 0 <= c[0] + i < W and 0 <= c[1] + j < H and abs(i) + abs(j) <= 3: px[c[0] + i, c[1] + j] = 0
        pq = [(0, s, None)]; seen = {}; best = {s: 0}
        D8 = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while pq:
            f, c, par = heapq.heappop(pq)
            if c in seen: continue
            seen[c] = par
            if c == t: break
            for dx, dy, cst in D8:
                n = (c[0] + dx, c[1] + dy)
                if not (0 <= n[0] < W and 0 <= n[1] < H) or px[n[0], n[1]] or n in seen: continue
                bend = 0.3 if par is not None and (c[0] - par[0], c[1] - par[1]) != (dx, dy) else 0
                gn = best[c] + cst + bend
                if gn < best.get(n, 1e18):
                    best[n] = gn; h = math.hypot(n[0] - t[0], n[1] - t[1]); heapq.heappush(pq, (gn + h, n, c))
        if t not in seen: print("  auto %s %s (%.2f, %.2f)->(%.2f, %.2f): NO PATH" % (net, L, a[0], a[1], b[0], b[1])); self.ok = False; return None
        cells = []; c = t
        while c is not None: cells.append(c); c = seen[c]
        cells.reverse(); pts = [cells[0]]
        for i in range(1, len(cells) - 1):
            if (cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1]) != (cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]): pts.append(cells[i])
        pts.append(cells[-1]); P = [a] + [(round(x0 + c[0] * g, 3), round(y0 + c[1] * g, 3)) for c in pts[1:-1]] + [b]
        self.J["routes"].append({"net": net, "w": w, "path": [[L, p[0], p[1]] for p in P]})
        self._add(L, LineString(P).buffer(w / 2), net, "track"); return P
    def link(self, net, a, b, L="In3.Cu", r=1.0, w=0.2, va=None, vb=None):
        """pad point a -> pad point b: via near each (or the given via spots), inner-layer auto route, short F stubs."""
        ends = []
        for p, v in ((a, va), (b, vb)):
            if v is None:
                f = self.free_vias(net, p[0], p[1], r, n=1)
                if not f: print("  link %s: no free via within %.1f of (%.2f, %.2f)" % (net, r, p[0], p[1])); self.ok = False; return None
                v = (f[0][1], f[0][2])
            self.via(net, v[0], v[1]); ends.append(v)
            if math.hypot(v[0] - p[0], v[1] - p[1]) > 0.05: self.seg(net, "F.Cu", [p, v], w)
        return self.auto(net, L, ends[0], ends[1], w)
    def cut(self, net, L, box): self.J["cuts"].append({"net": net, "layer": L, "box": box})
    def pour(self, net, L, box): self.J["pours"].append({"net": net, "layer": L, "box": box})
    def drop(self, net, L, box): self.J["drop"].append({"net": net, "layer": L, "box": box})
    def save(self, path):
        json.dump(self.J, open(path, "w"), indent=0); print("saved %s: %d routes, %d vias, %s" % (path, len(self.J["routes"]), len(self.J["vias"]), "clean" if self.ok else "WITH PROBLEMS"))
    def load(self, path):
        """Take the routes of another routes file as obstacles (they are not saved again): build on a colleague's copper."""
        J = json.load(open(path))
        for v in J.get("vias", []):
            self.vias.append((v["x"], v["y"], 0.45, v["net"]))
            for L in SIG: self.items[L].append((Point(v["x"], v["y"]).buffer(0.225), v["net"], "via", v["net"]))
        for r in J.get("routes", []):
            p = r["path"]
            for a, b in zip(p, p[1:]):
                if a[0] != b[0]:
                    self.vias.append((a[1], a[2], 0.45, r["net"]))
                    for L in SIG: self.items[L].append((Point(a[1], a[2]).buffer(0.225), r["net"], "via", r["net"]))
                if (a[1], a[2]) != (b[1], b[2]): self.items[b[0]].append((LineString([(a[1], a[2]), (b[1], b[2])]).buffer(r.get("w", 0.2) / 2), r["net"], "track", r["net"]))
        self.tree = {L: STRtree([i[0] for i in self.items[L]]) for L in SIG}
