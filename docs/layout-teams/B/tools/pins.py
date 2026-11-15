"""pins.py <spec.json in> <cu.json> <spec.json out> [options]          (team B, phase 2: pin escapes before routing)
A copper-plan filter (the call form of straps.py, used by final_route.sh --filters="pins.py ..."). It lays the copper
for connections no router can start: pins boxed in by their neighbours, their own part or a pour. Every added
segment and via is checked exactly (tools/pinlib.py, shapely) against other nets' pads, vias, tracks, pours,
keep-outs and the board edge, with the router's via rules and the 0.25 mm HighCurrent rule; a pour is cut only where
a rule or a table entry allows it, by clearance + track + clearance, and never a hot-loop pour.

Rules, in this order:
  ep     A GND / 3V3 pin of a U part whose own exposed pad (same net, area > 1 mm2) lies inward: a straight stub from
         the pin into the exposed pad (0.2 mm, 0.15 mm where 0.2 does not fit). KiCad then counts the pin as joined.
  rail   A GND / 3V3 pad the copper planner left to the router (spec report 'left_to_router', or every GND pad of a
         U part with no planned copper) that the ep rule did not tie: a via with a short stub, the via on the first
         free spot found by an exact search from the pad (outward first), never in front of another pin's escape lane
         unless nothing else fits. GND vias land on the In1/In4 planes. Pads that need a pour cut are left to the table.
  gate   A GateDrive pad of a FET whose partner pad (same net, other part) is within --gate_mm and that has no free
         way to it: the hard pours of its own stage (other nets of the same FET, not GND, not hot unless --gate_hot)
         are cut back by clearance + track + clearance along the shortest way and the gate track (--gate_w) is laid.
  table  Entries of --table (default plan/p2-pins.json), relative to part and pad, so they survive a small part
         nudge and apply to both ports:
           {"ref": "U405|U505", "pad": "4", "dir": "N", "via": true, "w": 0.15, "max": 1.6, "cut": [], "why": "..."}
             a via escape: a lead straight out of the pad in dir (N/S/E/W, or "out" = away from the part centre),
             then the shortest exact way to a free via spot within max mm; "cut": nets whose (non-hot) pours may be cut.
           {"ref": "J501", "pad": "B5", "to": "U505.5", "w": 0.15, "cut": ["/USB Port 2/VBUS"]}
             a whole short connection on one layer from pad to pad (the second pad of the same part family is given
             as REF.PAD; with "ref": "A|B" use "to": "C|D" in the same order).
         Keys: layer (default the pad's copper layer), lead (mm beyond the pad edge, default 0.15), via_dir_only.
Options: --rules=ep,rail,gate,table  --table=<file>  --only=REF.PAD,...  --gate_mm=2.5 --gate_w=0.3  --png=<dir>
         --rail_r=1.6 (search radius of the rail rule)  --dry (report only)
Exit 1 only on a clearance fault in the final exact check (nothing then is written). Prints one line per item and a
summary as the last line."""
import sys, os, json, math, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pinlib
from pinlib import CU, VIA_D, VIA_DRILL
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, box as sbox
from shapely.ops import unary_union

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 3: print(__doc__); sys.exit(2)
HERE = os.path.dirname(os.path.abspath(__file__)); TEAM = os.path.dirname(HERE)
RULES = O.get("rules", "ep,rail,gate,table").split(",")
TABLE = O.get("table", os.path.join(TEAM, "plan/p2-pins.json"))
ONLY = set(O["only"].split(",")) if "only" in O else None
GATE_MM, GATE_W = float(O.get("gate_mm", 2.5)), float(O.get("gate_w", 0.3))
RAIL_R = float(O.get("rail_r", 1.6))
PNG = O.get("png")
t0 = time.time()
S, D, G = pinlib.load_spec(A[0], A[1])
RAILS = ("GND", "3V3")
FPS = {f["ref"]: f for f in D["fps"]}
PADS = {}
for p in D["pads"]:
    if p["shapes"] and p["num"]:
        PADS.setdefault((p["ref"], p["num"]), []).append(p)
LOG, ADDED_T, ADDED_V, CUTS = [], [], [], []      # report lines; tracks, vias added; (zone, layer, geom) cuts
if PNG: os.makedirs(PNG, exist_ok=True)


def say(s):
    LOG.append(s); print(s, flush=True)


def shp(p, L):
    return unary_union([pinlib.poly(r) for r in p["shapes"].get(L, [])])


def pad_layer(p):
    return "F.Cu" if "F.Cu" in p["shapes"] and p.get("drill", 0) == 0 else ("B.Cu" if p.get("drill", 0) == 0 else "F.Cu")


def axis(p, L):
    """Unit vector along the pad's long side pointing away from its part centre, half length along it."""
    g = shp(p, L); x0, y0, x1, y1 = g.bounds; f = FPS[p["ref"]]
    vx, vy = p["x"] - f["x"], p["y"] - f["y"]
    if (x1 - x0) > 1.2 * (y1 - y0): return ((1.0 if vx > 0 else -1.0), 0.0), (x1 - x0) / 2, (y1 - y0) / 2
    if (y1 - y0) > 1.2 * (x1 - x0): return (0.0, (1.0 if vy > 0 else -1.0)), (y1 - y0) / 2, (x1 - x0) / 2
    if abs(vx) >= abs(vy): return ((1.0 if vx > 0 else -1.0), 0.0), (x1 - x0) / 2, (y1 - y0) / 2
    return (0.0, (1.0 if vy > 0 else -1.0)), (y1 - y0) / 2, (x1 - x0) / 2


DIRS = {"N": (0.0, -1.0), "S": (0.0, 1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def picture(name, net, L, bx, extra=()):
    if not PNG: return
    try:
        pinlib.draw(G, os.path.join(PNG, name + ".png"), bx, L, 80, net, extra=extra)
    except Exception as e:
        say("  (picture failed: %s)" % e)


# ---- search: free area with optional cut nets, raster Dijkstra with a cost per cell ---------------------------------
def cut_ok_zone(it, cut):
    return it[1] == "zone" and it[0] in cut


def free_with_cut(net, L, w, bx, cut):
    """(strict free area, extra area that is free once the pours of the cut nets are cut)."""
    strict = G.free_area(net, L, w, bx)
    if not cut: return strict, None
    B = sbox(*bx); obst = []
    for i in G.tree[L].query(B.buffer(1.0)):
        it = G.items[L][int(i)]
        n2, k2, g2 = it[0], it[1], it[2]
        if k2 == "ko": obst.append(g2.buffer(w / 2)); continue
        if n2 == net and k2 != "hole": continue
        if cut_ok_zone(it, cut): continue
        obst.append(g2.buffer(G.need(net, "track", it) + w / 2 + 0.005, 12))
    ok = B.intersection(G.board.buffer(-(pinlib.EDGE + w / 2 + 0.005)))
    loose = ok.difference(unary_union(obst)) if obst else ok
    return strict, loose


def raster_search(strict, loose, start, goal_pts, step=0.02, cutpen=4.0, avoid=None, avoidpen=6.0, goal_geom=None):
    """Dijkstra from start over cells of strict (cost 1) and loose (cost cutpen) to the nearest goal point / area.
    Returns (polyline, end point) or (None, None)."""
    import heapq
    from PIL import Image, ImageDraw
    allf = strict if loose is None else strict.union(loose)
    if allf.is_empty: return None, None
    x0, y0, x1, y1 = allf.bounds; x0 -= 0.1; y0 -= 0.1; x1 += 0.1; y1 += 0.1
    nx, ny = int((x1 - x0) / step) + 3, int((y1 - y0) / step) + 3
    def ras(g, shrink=0.75):
        im = Image.new("1", (nx, ny), 0); d = ImageDraw.Draw(im)
        g = g.buffer(-step * shrink) if shrink else g
        for q in ([g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))):
            if not isinstance(q, Polygon) or q.is_empty: continue
            d.polygon([((x - x0) / step, (y - y0) / step) for x, y in q.exterior.coords], fill=1)
            for h in q.interiors: d.polygon([((x - x0) / step, (y - y0) / step) for x, y in h.coords], fill=0)
        return np.array(im, dtype=bool)
    Fs = ras(strict); Fl = ras(loose) & ~Fs if loose is not None else np.zeros_like(Fs)
    Av = ras(avoid, 0) if avoid is not None and not avoid.is_empty else np.zeros_like(Fs)
    cost = np.where(Fs, 1.0, np.where(Fl, cutpen, np.inf)) * np.where(Av, avoidpen, 1.0)
    Gm = np.zeros_like(Fs)
    for gx, gy in goal_pts:
        i, j = int(round((gx - x0) / step)), int(round((gy - y0) / step))
        if 0 <= i < nx and 0 <= j < ny and np.isfinite(cost[j, i]): Gm[j, i] = True
    if goal_geom is not None: Gm |= ras(goal_geom.intersection(allf), 0.5) & np.isfinite(cost)
    if not Gm.any(): return None, None
    si, sj = int(round((start[0] - x0) / step)), int(round((start[1] - y0) / step))
    if not (0 <= si < nx and 0 <= sj < ny): return None, None
    if not np.isfinite(cost[sj, si]): cost[sj, si] = 1.0
    dist = {(si, sj): 0.0}; prev = {}; q = [(0.0, si, sj)]; end = None
    D8 = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    while q:
        d, i, j = heapq.heappop(q)
        if d > dist.get((i, j), 1e18): continue
        if Gm[j, i] and (i, j) != (si, sj): end = (i, j); break
        for di, dj, c in D8:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and np.isfinite(cost[b, a]):
                nd = d + c * cost[b, a]
                if nd < dist.get((a, b), 1e18):
                    dist[(a, b)] = nd; prev[(a, b)] = (i, j); heapq.heappush(q, (nd, a, b))
    if end is None: return None, None
    cells = [end]
    while cells[-1] in prev: cells.append(prev[cells[-1]])
    pts = [(x0 + i * step, y0 + j * step) for i, j in cells[::-1]]
    pts[0] = tuple(start)
    endp = pts[-1]
    if goal_pts:
        endp = min(goal_pts, key=lambda g: math.hypot(g[0] - pts[-1][0], g[1] - pts[-1][1]))
        if math.hypot(endp[0] - pts[-1][0], endp[1] - pts[-1][1]) < step * 1.5: pts[-1] = endp
    return pts, endp


def straighten(pts, check):
    """Few straight pieces: from each point, the farthest later point the check accepts."""
    out = [pts[0]]; k = 0
    while k < len(pts) - 1:
        j = len(pts) - 1
        while j > k + 1 and not check(pts[k], pts[j]): j -= 1
        out.append(pts[j]); k = j
    # drop collinear middles
    res = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = res[-1], out[i], out[i + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) < 1e-6: continue
        res.append(b)
    res.append(out[-1])
    return [(round(x, 4), round(y, 4)) for x, y in res]


def check_seg(net, L, a, b, w, cut):
    f = G.check_track(net, L, a, b, w)
    return [x for x in f if not (x[1].startswith("zone ") and x[1][5:] in cut)]


VGAP = [pinlib.VIA_MIN_OTHER]


def check_via(net, x, y, cut):
    f = G.check_via(net, x, y, other_min=VGAP[0])
    return [q for q in f if not (q[1].startswith("zone ") and q[1][5:] in cut)]


def lanes_of_others(net, bx):
    """Escape lanes of other nets' fine-pitch pins (1.4 mm strip in front of each U pin) inside the box."""
    B = sbox(*bx); out = []
    for p in D["pads"]:
        if p["net"] in ("", net) or p["net"].startswith("unconnected-") or not re.match(r"U\d+$", p["ref"]) or not p["shapes"].get("F.Cu"): continue
        if not B.buffer(1.5).contains(Point(p["x"], p["y"])): continue
        g = shp(p, "F.Cu"); x0, y0, x1, y1 = g.bounds
        if min(x1 - x0, y1 - y0) > 0.36: continue
        (dx, dy), hl, hw = axis(p, "F.Cu")
        ex, ey = p["x"] + dx * (hl + 1.4), p["y"] + dy * (hl + 1.4)
        out.append(LineString([(p["x"] + dx * hl, p["y"] + dy * hl), (ex, ey)]).buffer(hw + 0.05, cap_style=2))
    return unary_union(out) if out else None


# ---- laying, with pour cuts ------------------------------------------------------------------------------------
def cut_split(net, geoms_by_layer, cut):
    """None, or why the cut would leave a pour piece that holds a pad or via of its net apart from the rest."""
    for z in S["zones"]:
        if z["net"] not in cut: continue
        new = [g for g, Lg in geoms_by_layer if Lg == z["layer"]]
        if not new: continue
        hcpair = (G.K.hc(z["net"]) and G.K.small(net)) or (G.K.small(z["net"]) and G.K.hc(net))
        hole = unary_union([g.buffer((pinlib.HCCLR if hcpair else pinlib.ZCLR) + 0.01, 16) for g in new])
        items = [shp(p, z["layer"]) for p in D["pads"] if p["net"] == z["net"] and p["shapes"].get(z["layer"])]
        items += [Point(v["x"], v["y"]).buffer(v["size"] / 2) for v in S["vias"] if v["net"] == z["net"]]
        for pr in z["polys"]:
            g = pinlib.poly(pr)
            if not g.intersects(hole): continue
            d = g.difference(hole)
            parts = [q for q in ([d] if isinstance(d, Polygon) else list(getattr(d, "geoms", []))) if isinstance(q, Polygon) and q.area > 0.05]
            held = [q for q in parts if any(q.intersects(it) for it in items)]
            if len(held) > 1:
                return "cut splits the %s pour on %s into %d pieces that hold its pads / vias" % (z["net"], z["layer"], len(held))
    return None


def apply_cuts(net, L, geoms_by_layer, cut):
    """Cut the pours of the cut nets round the new copper (per layer) by the clearance they need + 0.01."""
    for zi, z in enumerate(S["zones"]):
        if z["net"] not in cut: continue
        Lz = z["layer"]
        new = [g for g, Lg in geoms_by_layer if Lg == Lz]
        if not new: continue
        hcpair = (G.K.hc(z["net"]) and G.K.small(net)) or (G.K.small(z["net"]) and G.K.hc(net))
        c = (pinlib.HCCLR if hcpair else pinlib.ZCLR) + 0.01
        hole = unary_union([g.buffer(c, 16) for g in new])
        polys = []; changed = 0.0; before = len(z["polys"])
        for pr in z["polys"]:
            g = pinlib.poly(pr)
            if g.intersects(hole):
                d = g.difference(hole); changed += g.area - d.area
                for q in ([d] if isinstance(d, Polygon) else list(getattr(d, "geoms", []))):
                    if isinstance(q, Polygon) and q.area > 0.05:
                        polys.append(dict(ring=[[round(x, 4), round(y, 4)] for x, y in q.exterior.coords],
                                          holes=[[[round(x, 4), round(y, 4)] for x, y in h.coords] for h in q.interiors]))
            else:
                polys.append(pr)
        if changed > 0:
            z["polys"] = polys
            CUTS.append(dict(net=z["net"], layer=Lz, mm2=round(changed, 3), pieces=[before, len(polys)]))
            say("    cut %s on %s: %.3f mm2, pieces %d -> %d" % (z["net"], Lz, changed, before, len(polys)))


def rebuild():
    global G
    G = pinlib.Geo(D["pads"], S["tracks"], S["vias"], S["zones"], D.get("keepouts", []), D["outline"])


def lay(net, L, pts, w, via=None, cut=(), tag=""):
    segs = [dict(net=net, layer=L, a=[a[0], a[1]], b=[b[0], b[1]], w=w, pins=tag) for a, b in zip(pts, pts[1:]) if a != b]
    geoms = [(LineString([s["a"], s["b"]]).buffer(w / 2, 16), L) for s in segs]
    if via is not None:
        geoms += [(Point(via).buffer(VIA_D / 2, 24), Lx) for Lx in CU]
    if cut: apply_cuts(net, L, geoms, cut)
    if "dry" in O: return segs
    S["tracks"] += segs; ADDED_T.extend(segs)
    if via is not None:
        v = dict(net=net, x=round(via[0], 4), y=round(via[1], 4), size=VIA_D, drill=VIA_DRILL, pins=tag, gap=VGAP[0])
        S["vias"].append(v); ADDED_V.append(v)
    rebuild()
    return segs


# ---- rule ep ----------------------------------------------------------------------------------------------------
def big_pads(ref, net):
    out = []
    for (r, n), ps in PADS.items():
        if r != ref: continue
        for p in ps:
            if p["net"] == net:
                for L in ("F.Cu", "B.Cu"):
                    g = shp(p, L)
                    if g.area > 1.0: out.append((p, L, g))
    return out


def touches_own(p, L):
    g = shp(p, L)
    for t in S["tracks"]:
        if t["net"] == p["net"] and t["layer"] == L and LineString([t["a"], t["b"]]).buffer(t["w"] / 2).intersects(g): return True
    for v in S["vias"]:
        if v["net"] == p["net"] and Point(v["x"], v["y"]).buffer(v["size"] / 2).intersects(g): return True
    for z in S["zones"]:
        if z["net"] == p["net"] and z["layer"] == L and any(pinlib.poly(q).intersects(g) for q in z["polys"]): return True
    return False


def rule_ep():
    n = 0
    for (ref, num), ps in sorted(PADS.items()):
        if not re.match(r"U\d+$", ref): continue
        for p in ps:
            if p["net"] not in RAILS or p.get("drill", 0) > 0: continue
            if ONLY and "%s.%s" % (ref, num) not in ONLY: continue
            L = pad_layer(p); g = shp(p, L)
            if g.area > 0.5: continue
            eps = [e for e in big_pads(ref, p["net"]) if e[1] == L and not e[2].intersects(g)]
            if not eps: continue
            (dx, dy), hl, hw = axis(p, L)
            ep = min(eps, key=lambda e: e[2].distance(g))
            if ep[2].distance(g) > 0.8: continue
            done = False
            for w in (0.2, 0.15):
                if w > 2 * hw + 1e-6 and w > 0.15: continue
                core = ep[2].buffer(-(w / 2 + 0.05))
                if core.is_empty: continue
                for k in range(1, 40):                       # straight inward first
                    L_ = hl + 0.02 * k
                    b = (p["x"] - dx * L_, p["y"] - dy * L_)
                    if core.contains(Point(b)):
                        if not check_seg(p["net"], L, (p["x"], p["y"]), b, w, ()):
                            lay(p["net"], L, [(p["x"], p["y"]), (round(b[0], 4), round(b[1], 4))], w, tag="ep %s.%s" % (ref, num))
                            say("ep    %s.%s %s: straight stub %.2f mm, w %.2f, into pad %s" % (ref, num, p["net"], L_, w, ep[0]["num"]))
                            done = True
                        break
                if done: break
                m = 1.2; bx = (p["x"] - m, p["y"] - m, p["x"] + m, p["y"] + m)
                strict, _ = free_with_cut(p["net"], L, w, bx, ())
                pts, endp = raster_search(strict, None, (p["x"], p["y"]), [], goal_geom=core)
                if pts:
                    pl = straighten(pts, lambda a, b: not check_seg(p["net"], L, a, b, w, ()))
                    ln = sum(math.dist(a, b) for a, b in zip(pl, pl[1:]))
                    if ln <= 1.2 and all(not check_seg(p["net"], L, a, b, w, ()) for a, b in zip(pl, pl[1:])):
                        lay(p["net"], L, pl, w, tag="ep %s.%s" % (ref, num))
                        say("ep    %s.%s %s: stub %.2f mm in %d pieces, w %.2f, into pad %s" % (ref, num, p["net"], ln, len(pl) - 1, w, ep[0]["num"]))
                        done = True
                if done: break
            if done: n += 1
            else: say("ep    %s.%s %s: no stub fits (left to the rail rule)" % (ref, num, p["net"]))
    return n


# ---- via escape (rail rule and table) ------------------------------------------------------------------------------
def keep_strips(specs):
    """'REF.PAD:DIR:LEN' -> a strip from the pad edge LEN mm in DIR, as wide as the pad (kept free for that pad's escape)."""
    out = []
    for k in specs:
        rp, dr, ln = k.split(":"); r_, n_ = rp.split(".", 1); q = PADS[(r_, n_)][0]; L_ = pad_layer(q); b = shp(q, L_).bounds
        dx, dy = DIRS[dr]; ln = float(ln)
        if dx: x0 = b[2] if dx > 0 else b[0]; out.append(sbox(min(x0, x0 + dx * ln), b[1], max(x0, x0 + dx * ln), b[3]))
        else: y0 = b[3] if dy > 0 else b[1]; out.append(sbox(b[0], min(y0, y0 + dy * ln), b[2], max(y0, y0 + dy * ln)))
    return unary_union(out) if out else None


def via_escape(p, L, net, w=0.2, R=1.6, d=None, lead=0.15, cut=(), avoid_lanes=True, tag="", via=True, goal_geom=None, keep=None, at=None):
    """Lead out of the pad (direction d, or none), then the cheapest exact way to a free via spot (or into goal_geom)."""
    (ax_, ay_), hl, hw = axis(p, L)
    start = (p["x"], p["y"]); lead_pts = [start]
    if d is not None:
        hx = (shp(p, L).bounds[2] - shp(p, L).bounds[0]) / 2 if d[0] else (shp(p, L).bounds[3] - shp(p, L).bounds[1]) / 2
        e = (round(p["x"] + d[0] * (hx + lead), 4), round(p["y"] + d[1] * (hx + lead), 4))
        f = check_seg(net, L, start, e, w, cut)
        if f: return None, "lead %s blocked: %s" % (d, f[:2])
        lead_pts.append(e); start = e
    bx = (start[0] - R, start[1] - R, start[0] + R, start[1] + R)
    strict, loose = free_with_cut(net, L, w, bx, cut)
    av = lanes_of_others(net, bx) if avoid_lanes else None
    if keep is not None:                                   # strips kept free for another pad: closed to this escape
        strict = strict.difference(keep.buffer(w / 2 + 0.05))
        if loose is not None: loose = loose.difference(keep.buffer(w / 2 + 0.05))
    goals = []
    if via:
        vfree = G.free_area(net, L, VIA_D, bx)
        if cut:
            _, vl = free_with_cut(net, L, VIA_D, bx, cut); vfree = vfree.union(vl) if vl is not None else vfree
        xs = np.arange(bx[0], bx[2], 0.05); ys = np.arange(bx[1], bx[3], 0.05)
        cand = [(round(x, 3), round(y, 3)) for x in xs for y in ys if math.hypot(x - start[0], y - start[1]) <= R]
        from shapely import contains_xy
        m = contains_xy(vfree, np.array([c[0] for c in cand]), np.array([c[1] for c in cand])) if cand else []
        cand = [c for c, ok in zip(cand, m) if ok]
        if keep is not None:
            kb = keep.buffer(VIA_D / 2 + 0.1); cand = [c for c in cand if not kb.contains(Point(c))]
        cand.sort(key=lambda c: math.hypot(c[0] - start[0], c[1] - start[1]))
        if at is not None:                                 # table 'at': the via spot itself, relative to the pad centre
            cand = [(round(p["x"] + at[0], 4), round(p["y"] + at[1], 4))]
        for c in cand[:600]:
            if not check_via(net, c[0], c[1], cut) and (net != "GND" or inside_plane(c)):
                goals.append(c)
        old = [(vx, vy) for vx, vy, vn in G.vias if vn == net and math.hypot(vx - start[0], vy - start[1]) <= R]
        goals += old
        if not goals: return None, ("via spot %s blocked: %s" % (cand, check_via(net, cand[0][0], cand[0][1], cut)[:2])) if at is not None else "no free via spot within %.1f mm" % R
        if av is not None:                                  # a via in front of another pin takes its escape: only if nothing else fits
            from shapely import contains_xy as _cxy
            inl = _cxy(av, np.array([g[0] for g in goals]), np.array([g[1] for g in goals]))
            if not all(inl): goals = [g for g, i in zip(goals, inl) if not i]
    pts, endp = raster_search(strict, loose, start, goals, avoid=av, goal_geom=goal_geom)
    if pts is None: return None, "no way to a via spot" if via else "no way"
    pl = straighten(pts, lambda a, b: not check_seg(net, L, a, b, w, cut))
    pl = lead_pts[:-1] + pl if len(lead_pts) > 1 else pl
    bad = [(a, b, check_seg(net, L, a, b, w, cut)) for a, b in zip(pl, pl[1:]) if check_seg(net, L, a, b, w, cut)]
    if bad: return None, "path fails the exact check: %s" % str(bad[0])[:160]
    if cut:
        gl = [(LineString([a, b]).buffer(w / 2, 16), L) for a, b in zip(pl, pl[1:]) if a != b]
        if via: gl += [(Point(endp).buffer(VIA_D / 2, 24), Lx) for Lx in CU]
        why = cut_split(net, gl, cut)
        if why: return None, why
    if via:
        if any(abs(vx - endp[0]) < 1e-6 and abs(vy - endp[1]) < 1e-6 and vn == net for vx, vy, vn in G.vias):
            return (pl, None), "ok, ends on an existing via"
        vf = check_via(net, endp[0], endp[1], cut)
        if vf: return None, "via fails: %s" % vf[:2]
    return (pl, endp if via else None), "ok"


def inside_plane(c):
    for z in S["zones"]:
        if z["net"] == "GND" and z["layer"] in ("In1.Cu", "In4.Cu"):
            if any(pinlib.poly(q).buffer(-0.35).contains(Point(c)) for q in z["polys"]): return True
    return False


def rule_rail():
    rep = S.get("report", {}).get("return_pads", {}).get("left_to_router")
    names = []
    if rep is not None: names = rep
    else:
        for (ref, num), ps in PADS.items():
            if re.match(r"U\d+$", ref) and any(p["net"] == "GND" for p in ps): names.append("%s.%s" % (ref, num))
    n = 0
    for nm in names:
        ref, num = nm.split(".", 1)
        if ONLY and nm not in ONLY: continue
        for p in PADS.get((ref, num), []):
            if p["net"] not in RAILS or p.get("drill", 0) > 0: continue
            L = pad_layer(p)
            if touches_own(p, L): continue
            res, why = None, ""
            for w in (0.2, 0.15):
                res, why = via_escape(p, L, p["net"], w=w, R=RAIL_R, d=axis(p, L)[0], tag="rail " + nm)
                if res is None: res, why2 = via_escape(p, L, p["net"], w=w, R=RAIL_R, d=None, tag="rail " + nm)
                if res: break
            if res is None:
                say("rail  %s %s: no via escape (%s); needs a table entry" % (nm, p["net"], why)); continue
            pl, v = res
            lay(p["net"], L, pl, w, via=v, tag="rail " + nm); n += 1
            ln = sum(math.dist(a, b) for a, b in zip(pl, pl[1:]))
            say("rail  %s %s: %s, stub %.2f mm, w %.2f" % (nm, p["net"], ("via at %.3f,%.3f" % v) if v else "to an existing via", ln, w))
            picture("rail_" + nm.replace(".", "_"), p["net"], L, (p["x"] - 1.5, p["y"] - 1.5, p["x"] + 1.5, p["y"] + 1.5))
    return n


# ---- rule gate ------------------------------------------------------------------------------------------------------
def rule_gate():
    n = 0
    gates = [p for p in D["pads"] if p["shapes"] and G.K.of(p["net"]) == "GateDrive" and re.match(r"Q\d+$", p["ref"])]
    for p in gates:
        L = pad_layer(p)
        partners = [q for q in D["pads"] if q["net"] == p["net"] and q["ref"] != p["ref"] and q["shapes"].get(L)
                    and math.hypot(q["x"] - p["x"], q["y"] - p["y"]) <= GATE_MM]
        for q in partners:
            nm = "%s.%s-%s.%s" % (p["ref"], p["num"], q["ref"], q["num"])
            if ONLY and "%s.%s" % (p["ref"], p["num"]) not in ONLY and "%s.%s" % (q["ref"], q["num"]) not in ONLY: continue
            if touches_tracks(p, q, L): continue
            m = 1.0; bx = (min(p["x"], q["x"]) - m, min(p["y"], q["y"]) - m, max(p["x"], q["x"]) + m, max(p["y"], q["y"]) + m)
            strict, _ = free_with_cut(p["net"], L, 0.15, bx, ())     # the router's narrowest track: is there a way at all?
            gq = shp(q, L)
            pts, _ = raster_search(strict, None, (p["x"], p["y"]), [], goal_geom=gq.buffer(-0.05))
            if pts is not None: continue                        # the router has a way
            # own stage: the FET's other nets (not GND), hard pours, not hot unless allowed
            stage = {x["net"] for x in D["pads"] if x["ref"] == p["ref"] and x["net"] not in ("GND", p["net"], "")}
            cut = tuple(sorted(stage))
            hot_block = []
            res = None
            for w in (GATE_W, 0.25, 0.2):
                strict, loose = free_with_cut(p["net"], L, w, bx, cut)
                # hot pours count as cut-able only for the gate rule (the gate pad sits inside its own loop's pour)
                loose = hot_loose(p["net"], L, w, bx, cut, loose)
                pts, _ = raster_search(strict, loose, (p["x"], p["y"]), [], goal_geom=gq.buffer(-0.05), cutpen=2.0)
                if pts is None: continue
                pl = straighten(pts, lambda a, b: not check_hot(p["net"], L, a, b, w, cut))
                if all(not check_hot(p["net"], L, a, b, w, cut) for a, b in zip(pl, pl[1:])):
                    pl[-1] = (q["x"], q["y"]) if not check_hot(p["net"], L, pl[-2], (q["x"], q["y"]), w, cut) else pl[-1]
                    res = (pl, w); break
            if res is None:
                say("gate  %s %s: no way even with the stage pours %s cut" % (nm, p["net"], list(cut))); continue
            pl, w = res
            nc = len(CUTS)
            lay_hot(p["net"], L, pl, w, cut, tag="gate " + nm); n += 1
            ln = sum(math.dist(a, b) for a, b in zip(pl, pl[1:]))
            say("gate  %s %s: track %.2f mm, w %.2f, pours cut back: %s" % (nm, p["net"], ln, w, ", ".join("%s %s %.3f mm2" % (c["net"], c["layer"], c["mm2"]) for c in CUTS[nc:]) or "none"))
            picture("gate_" + nm.replace(".", "_"), p["net"], L, bx)
    return n


def touches_tracks(p, q, L):
    gp, gq = shp(p, L), shp(q, L)
    ts = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in S["tracks"] if t["net"] == p["net"] and t["layer"] == L]
    if not ts: return False
    u = unary_union(ts + [gp, gq])
    parts = [u] if isinstance(u, Polygon) else list(u.geoms)
    return any(x.intersects(gp) and x.intersects(gq) for x in parts)


def hot_loose(net, L, w, bx, cut, loose):
    B = sbox(*bx); obst = []
    for i in G.tree[L].query(B.buffer(1.0)):
        it = G.items[L][int(i)]
        if it[1] == "ko": obst.append(it[2].buffer(w / 2)); continue
        if it[0] == net and it[1] != "hole": continue
        if it[1] in ("zone", "hotzone") and it[0] in cut: continue
        obst.append(it[2].buffer(G.need(net, "track", it) + w / 2 + 0.005, 12))
    ok = B.intersection(G.board.buffer(-(pinlib.EDGE + w / 2 + 0.005)))
    return ok.difference(unary_union(obst)) if obst else ok


def check_hot(net, L, a, b, w, cut):
    f = G.check_track(net, L, a, b, w)
    return [x for x in f if not ((x[1].startswith("zone ") or x[1].startswith("hotzone ")) and x[1].split(" ", 1)[1] in cut)]


def lay_hot(net, L, pts, w, cut, tag):
    segs = [dict(net=net, layer=L, a=[a[0], a[1]], b=[b[0], b[1]], w=w, pins=tag) for a, b in zip(pts, pts[1:]) if a != b]
    geoms = [(LineString([s["a"], s["b"]]).buffer(w / 2, 16), L) for s in segs]
    apply_cuts(net, L, geoms, cut)
    if "dry" in O: return
    S["tracks"] += segs; ADDED_T.extend(segs); rebuild()


# ---- table --------------------------------------------------------------------------------------------------------
def rule_table():
    if not os.path.exists(TABLE): say("table %s: not found" % TABLE); return 0
    T = json.load(open(TABLE)); n = 0
    for e in (T if isinstance(T, list) else T.get("escapes", [])):
        refs = e["ref"].split("|"); tos = e.get("to", "").split("|") if e.get("to") else [None] * len(refs)
        for ref, to in zip(refs, tos):
            nm = "%s.%s" % (ref, e["pad"])
            if ONLY and nm not in ONLY: continue
            ps = PADS.get((ref, e["pad"]))
            if not ps: say("table %s: no such pad" % nm); continue
            p = ps[0]; L = e.get("layer", pad_layer(p)); net = p["net"]
            k_ = refs.index(ref)
            cut = tuple(c.split("|")[k_] if "|" in c else c for c in e.get("cut", []))
            cut = tuple(c for c in cut if c)
            d = None
            if e.get("dir") == "out": d = axis(p, L)[0]
            elif e.get("dir") in DIRS: d = DIRS[e["dir"]]
            if touches_own(p, L) and not e.get("force"):
                say("table %s %s: already has copper, skipped" % (nm, net)); continue
            res, why = None, ""
            vg_ = str(e.get("via_gap", pinlib.VIA_MIN_OTHER)); VGAP[0] = float(vg_.split("|")[k_] if "|" in vg_ else vg_)
            ws = [e["w"]] if "w" in e else [0.2, 0.15]
            for w in ws:
                if to:
                    tr, tn = to.split(".", 1); q = PADS.get((tr, tn), [None])[0]
                    if q is None: why = "no pad " + to; break
                    res, why = via_escape(p, L, net, w=w, R=e.get("max", 4.0), d=d, lead=e.get("lead", 0.15), cut=cut,
                                          avoid_lanes=False, via=False, goal_geom=shp(q, L).buffer(-0.04), tag="table " + nm)
                else:
                    at_ = str(e.get("at", "")); at_ = at_.split("|")[k_] if "|" in at_ else at_
                    at_ = tuple(float(v) for v in at_.split(",")) if at_ else None
                    res, why = via_escape(p, L, net, w=w, R=e.get("max", 1.6), d=d, lead=e.get("lead", 0.15), cut=cut, at=at_,
                                          avoid_lanes=e.get("avoid_lanes", True) and at_ is None, tag="table " + nm, keep=keep_strips([c.split("|")[k_] if "|" in c else c for c in e.get("keep", []) if (c.split("|")[k_] if "|" in c else c)]))
                if res: break
            if res is None:
                say("table %s %s: FAILED (%s)" % (nm, net, why)); continue
            pl, v = res
            if to and pl:
                q = PADS[tuple(to.split(".", 1))][0]
                if not check_seg(net, L, pl[-2], (q["x"], q["y"]), w, cut): pl[-1] = (q["x"], q["y"])
            lay(net, L, pl, w, via=v, cut=cut, tag="table " + nm); n += 1
            ln = sum(math.dist(a, b) for a, b in zip(pl, pl[1:]))
            say("table %s %s: %s, %.2f mm in %d pieces, w %.2f%s  (%s)" % (nm, net, ("via at %.3f,%.3f" % v) if v else ("to " + to if to else "to an existing via"), ln, len(pl) - 1, w,
                                                                    (", cut " + ",".join(cut)) if cut else "", e.get("why", "")[:60]))
            bx = (min(x for x, y in pl) - 1.2, min(y for x, y in pl) - 1.2, max(x for x, y in pl) + 1.2, max(y for x, y in pl) + 1.2)
            picture("table_" + nm.replace(".", "_"), net, L, bx)
    return n


counts = {}
if "ep" in RULES: counts["ep"] = rule_ep()
if "gate" in RULES: counts["gate"] = rule_gate()
if "table" in RULES: counts["table"] = rule_table()
VGAP[0] = pinlib.VIA_MIN_OTHER
if "rail" in RULES: counts["rail"] = rule_rail()

# ---- final exact check of every added item against everything else (pours as cut) ------------------------------------
rebuild(); faults = []
for t in ADDED_T:
    f = G.check_track(t["net"], t["layer"], t["a"], t["b"], t["w"])
    if f: faults.append((t["pins"], t["a"], t["b"], f))
for v in ADDED_V:
    f = G.check_via(v["net"], v["x"], v["y"], self_ok=True, other_min=min(v.get("gap", 0.75), min([u.get("gap", 0.75) for u in ADDED_V if (u["x"] - v["x"]) ** 2 + (u["y"] - v["y"]) ** 2 < 1] or [0.75])))
    if f: faults.append((v["pins"], (v["x"], v["y"]), f))
for f in faults: say("FAULT %s" % (f,))
S.setdefault("pins", []).append(dict(rules=RULES, table=os.path.basename(TABLE), tracks=len(ADDED_T), vias=len(ADDED_V), cuts=CUTS,
                                     counts=counts, faults=len(faults), log=LOG))
if not faults:
    json.dump(S, open(A[2], "w"), indent=1)
print("pins: %s; %d tracks (%.1f mm), %d vias, %d pour cuts (%.3f mm2); exact-check faults %d; %.0f s" % (
    ", ".join("%s %d" % kv for kv in counts.items()), len(ADDED_T), sum(math.dist(t["a"], t["b"]) for t in ADDED_T), len(ADDED_V),
    len(CUTS), sum(c["mm2"] for c in CUTS), len(faults), time.time() - t0))
sys.exit(1 if faults else 0)
