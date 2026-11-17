#!/usr/bin/env python3
"""capfix.py <spec.json> <bare.json> [options]       (team A r6_caps; in place on spec.json unless --out=)

Copper step after split_spec / STRAPS / BUS4 / BUS4B, before write_copper. It makes the joins of the router's SOFT
nets (router.py --softnets=GND,PACK_P,3V3: every zone of these nets may be cut by signal routes) survive routing,
by adding copper the router cannot cut:

1. --band=3V3 : a copy of the net on In4 (the router never routes In4; KiCad refill only clears signal VIAS there),
   as a Steiner tree of bands (--band_w mm) grown over the net's planned vias (+ pads of the net as soft targets with a
   --band_pad mm disc where room), routed on a grid around other nets' In4 zones (the PACK_P In4 copy), other-net
   vias and through-hole pads.  Vias the In4 band cannot reach (another In4 component, e.g. walled off by the PACK_P
   copy) are joined by --cross: a HARD track on an outer layer, laid only inside a planned zone of the net (so it is
   legal where the zone was), from the unreached via / pad to a NEW via placed inside that zone in the band's
   component, and the band is grown to the new via.
2. --stubs : hard stub tracks (router obstacles) from pads of soft nets that sit in a SMALL planned zone polygon
   (< --stub_area mm2) with no planned track/via on them, to the nearest planned hard copper of the net (via or track)
   reached inside that zone polygon (<= --stub_max mm).  --stub_refs=REF.PAD,... adds pads in any zone size.
3. --links=[NET:]REF.PAD>REF.PAD;... (net defaults to the first pad's) : extra planned hard tracks (grid path on --link_layer, default F.Cu, around all
   other-net copper; zones of GND are passable since they refill) - used for the PPHV VAC cap pads.

Every added zone is single-outline.  Clearance --clr (0.3 mm: above the 0.25 mm HighCurrent rule).  Report under
spec["report"]["capfix"]."""
import sys, json, math, heapq
import numpy as np
import shapely
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, mapping
from shapely.ops import unary_union
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy import ndimage

a = [x for x in sys.argv[1:] if not x.startswith("--")]
opt = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
S = json.load(open(a[0])); D = json.load(open(a[1])); OUT = opt.get("out", a[0])
G = float(opt.get("g", 0.1)); CLR = float(opt.get("clr", 0.3))
VIA_D, VIA_DR = 0.45, 0.3
PASS = set(opt.get("pass", "GND").split(","))           # other nets whose zones a hard track may cross (refill carves)
REP = []
def log(*x):
    s = " ".join(str(v) for v in x); print("[capfix]", s); REP.append(s)

board = unary_union([Polygon(o["ring"]) for o in D["outline"]])
X0, Y0, X1, Y1 = board.bounds
NX, NY = int((X1 - X0) / G) + 1, int((Y1 - Y0) / G) + 1
XS = X0 + np.arange(NX) * G; YS = Y0 + np.arange(NY) * G
GX, GY = np.meshgrid(XS, YS)
def zpoly(p): return Polygon(p["ring"], p.get("holes", [])).buffer(0)
def pshape(p, L):
    return unary_union([Polygon(r["ring"], r.get("holes", [])).buffer(0) for r in p["shapes"].get(L, [])])
OUTER = ("F.Cu", "B.Cu")

def other_copper(L, net, zones=True):
    """other-net copper on layer L (pads, tracks, vias, hard zones that do not refill around us)"""
    g = []
    for p in D["pads"]:
        if p.get("net") != net and L in p["shapes"]: g.append(pshape(p, L))
        if p.get("drill") and p.get("net") != net and L not in p["shapes"]: g.append(Point(p["x"], p["y"]).buffer(p["drill"] / 2 + 0.1))
    for t in S["tracks"]:
        if t["layer"] == L and t["net"] != net: g.append(LineString([t["a"], t["b"]]).buffer(t["w"] / 2) if t["a"] != t["b"] else Point(t["a"]).buffer(t["w"] / 2))
    for v in S["vias"]:
        if v["net"] != net: g.append(Point(v["x"], v["y"]).buffer(v["size"] / 2))
    if zones:
        for z in S["zones"]:
            if z["layer"] == L and z["net"] != net and z["net"] not in PASS and not z.get("soft"):
                g += [zpoly(p) for p in z["polys"]]
    for k in D.get("keepouts", []):
        if L in k["layers"] and (k.get("no_tracks") or k.get("no_pours")):
            g += [zpoly(p) for p in k["poly"]]
    return unary_union(g)

def rast(geom):
    if geom.is_empty: return np.zeros((NY, NX), bool)
    return shapely.contains_xy(geom, GX, GY)

def cellof(x, y): return int(round((y - Y0) / G)), int(round((x - X0) / G))
def xyof(i, j): return (X0 + j * G, Y0 + i * G)

def grid_graph(free, cost=None, wdir=(1.0, 1.0)):
    idx = -np.ones(free.shape, int); fi = np.flatnonzero(free); idx.flat[fi] = np.arange(len(fi))
    rows, cols, ws = [], [], []
    wh, wv = wdir
    for di, dj, w in ((0, 1, wh), (1, 0, wv), (1, 1, 1.4142 * max(wh, wv)), (1, -1, 1.4142 * max(wh, wv))):
        a0 = idx[0:NY - di, max(0, -dj):NX - max(0, dj)]; b0 = idx[di:NY, max(0, dj):NX - max(0, -dj)]
        m = (a0 >= 0) & (b0 >= 0)
        rows.append(a0[m]); cols.append(b0[m]); ws.append(np.full(m.sum(), w))
    r = np.concatenate(rows); c = np.concatenate(cols); w = np.concatenate(ws)
    M = csr_matrix((np.concatenate([w, w]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(len(fi), len(fi)))
    return M, idx, fi

def pull(path_xy, ok):
    """string-pull a polyline: greedy longest straight shortcut that stays inside geometry ok"""
    out = [path_xy[0]]; i = 0
    while i < len(path_xy) - 1:
        j = len(path_xy) - 1
        while j > i + 1 and not ok.covers(LineString([path_xy[i], path_xy[j]])): j -= 1
        out.append(path_xy[j]); i = j
    return out

def shortest(free, M, idx, fi, src_cells, dst_cells):
    s = [idx[c] for c in src_cells if idx[c] >= 0]; d = {idx[c]: c for c in dst_cells if idx[c] >= 0}
    if not s or not d: return None
    dist, pred, srcs = dijkstra(M, indices=s, min_only=True, return_predecessors=True)
    best = min(d, key=lambda k: dist[k])
    if not np.isfinite(dist[best]): return None
    path = [best]
    while pred[path[-1]] >= 0: path.append(pred[path[-1]])
    return [divmod(int(fi[k]), NX) for k in path[::-1]], float(dist[best]) * G

def cells_in(geom, free):
    m = rast(geom) & free
    return [tuple(c) for c in np.argwhere(m)]

def near_cells(x, y, free, r=0.3):
    return cells_in(Point(x, y).buffer(r), free) or []

new_tracks, new_vias, new_zones = [], [], []

def add_track(net, L, pts, w, kind):
    for p, q in zip(pts, pts[1:]):
        if p != q: new_tracks.append({"net": net, "layer": L, "a": [round(p[0], 4), round(p[1], 4)], "b": [round(q[0], 4), round(q[1], 4)], "w": w, "kind": kind})
def add_zone(net, L, geom, prio, kind):
    for g in getattr(geom, "geoms", [geom]):
        if g.area < 0.3: continue
        g = g.simplify(0.02)
        new_zones.append({"net": net, "layer": L, "priority": prio, "soft": False, "kinds": [kind],
                          "polys": [{"ring": [list(map(lambda v: round(v, 4), c)) for c in g.exterior.coords[:-1]],
                                     "holes": [[list(map(lambda v: round(v, 4), c)) for c in h.coords[:-1]] for h in g.interiors]}],
                          "area_mm2": round(g.area, 2)})

def via_ok(x, y, net):
    """a new via of net at (x, y): clear of other-net copper on every layer it crosses (hard zones; soft pours refill)"""
    c = Point(x, y)
    for L in D["layers"]:
        g = OC.setdefault(L, other_copper(L, net, zones=L in OUTER or opt.get("via_inner_zones") == "1"))
        if g.distance(c) < VIA_D / 2 + CLR: return False
    for v in S["vias"] + new_vias:
        if math.dist((v["x"], v["y"]), (x, y)) < (0.65 if v["net"] != net else 0.5): return False
    for p in D["pads"]:
        if p.get("drill") and math.dist((p["x"], p["y"]), (x, y)) < p["drill"] / 2 + VIA_DR / 2 + 0.45: return False
    if not board.buffer(-0.25 - VIA_D / 2).contains(c): return False
    return True
OC = {}; VM = {}

_AV = {}
def avoid_maps(net):
    """--avoid=<routed.kicad_pcb>: per routing layer, the cells a previous full route of this placement used for signal
    tracks / vias (+0.3 mm): planned links pay --avoid_cost there, so they take the gaps the router left"""
    if "avoid" not in opt: return None
    if not _AV:
        sys.path.insert(0, "/home/claude/repo/tools/copper"); from dc_score import load_copper
        Z_, S_, V_ = load_copper(opt["avoid"])
        pw = {z["net"] for z in S["zones"]} | {"GND", "PACK_P", "3V3"}
        for L in ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu"):
            g = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + 0.3) for t in S_ if t["layer"] == L and t["net"] not in pw and t["a"] != t["b"]]
            g += [Point(v["x"], v["y"]).buffer(v["size"] / 2 + 0.3) for v in V_ if v["net"] not in pw]
            _AV[L] = rast(unary_union(g))
        log(f"avoid map from {opt['avoid']}: " + ", ".join(f"{L} {int(m.sum() * G * G)} mm2" for L, m in _AV.items()))
    return _AV
def viamask(net):
    if net not in VM:
        m = rast(board.buffer(-0.25 - VIA_D / 2))
        for L in D["layers"]: m &= ~rast(other_copper(L, net, zones=L in OUTER or opt.get("via_inner_zones") == "1").buffer(VIA_D / 2 + CLR + 0.05))   # inner pours refill round a via
        sp = unary_union([pshape(p, L) for p in D["pads"] if p.get("net") == net and not p.get("drill") for L in p["shapes"] if pshape(p, L).area < float(opt.get("vip_area", 0.6))])
        if not sp.is_empty: m &= ~rast(sp.buffer(VIA_D / 2 + 0.05))      # no via in a small (fine-pitch) pad of its own net
        VM[net] = m
    return VM[net]
SEALED = {"R425.1", "R426.1", "R428.1", "R429.1", "R525.1", "R526.1", "R528.1", "R529.1", "R107.1", "R108.1"}   # router.py Kelvin taps

# ---------------------------------------------------------------- 3. links (first: they are hard copper the others see)
for spec in [s for s in opt.get("links", "").split(";") if s]:
    pr = spec.split(":", 1)[-1]; A_, B_ = pr.split(">")
    L = opt.get("link_layer", "F.Cu"); w = float(opt.get("link_w", 0.3))
    pa = {(p["ref"] + "." + p["num"]): p for p in D["pads"]}
    net = spec.split(":", 1)[0] if ":" in spec else pa[A_]["net"]
    pA, pB = pa[A_], pa[B_]
    if pA["net"] != net or pB["net"] != net: log("link", spec, "net mismatch"); continue
    pclr = float(opt.get("link_padclr", 0.16))    # pad edges: footprint spacing (the HighCurrent 0.25 mm rule excludes pads)
    padg = unary_union([pshape(p, L) for p in D["pads"] if p.get("net") != net and L in p["shapes"] and not p.get("drill")])   # drilled pads keep CLR (hole clearance)
    PASS = set(opt.get("link_pass", "GND").split(","))   # zones of these nets refill around the link
    obst = other_copper(L, net).difference(padg.buffer(0.001)).buffer(CLR + w / 2).union(padg.buffer(pclr + w / 2))
    free = rast(board.buffer(-0.3 - w / 2).difference(obst))
    own = unary_union([pshape(pA, L), pshape(pB, L)])
    free |= rast(own.buffer(-0.02)) & ~rast(obst)
    M, idx, fi = grid_graph(free)
    r = shortest(free, M, idx, fi, cells_in(pshape(pA, L).buffer(-0.05), free), cells_in(pshape(pB, L).buffer(-0.05), free))
    if r is None: log("link", spec, "NO PATH"); continue
    path, ln = r
    okg = board.buffer(-0.3 - w / 2).difference(obst).union(own.buffer(-0.02))
    pts = pull([xyof(*c) for c in path], okg)
    pts = [(pA["x"], pA["y"])] + pts[1:-1] + [(pB["x"], pB["y"])] if okg.covers(LineString([(pA["x"], pA["y"]), pts[min(1, len(pts) - 1)]])) and okg.covers(LineString([pts[max(0, len(pts) - 2)], (pB["x"], pB["y"])])) else pts
    add_track(net, L, pts, w, "capfix link"); OC.clear(); PASS = set(opt.get("pass", "GND").split(","))
    log(f"link {net} {A_}->{B_} on {L}: {ln:.1f} mm, {len(pts) - 1} segments")
S["tracks"] += new_tracks; nt0 = len(new_tracks)

# ---------------------------------------------------------------- 3b. multi-layer links (--link3d=PADA>PADB;...): a planned hard path
# from pad A to the planned copper of pad B's net piece (pad B and every planned zone of the net that holds pad B), on
# --l3_layers (F.Cu,In2.Cu,In3.Cu,B.Cu = the router's layers; soft pours of other nets are crossed, they refill), with vias
# where a via is legal on all six layers.  Used for the PPHV VAC link (charger VAC pins/cap to the PD chip's PPHV tree),
# which the router "routes" as a zero-length edge to the zone and so never joins.
for spec in [s_ for s_ in opt.get("link3d", "").split(";") if s_]:
    A_, B_ = spec.split(">"); pa = {(p["ref"] + "." + p["num"]): p for p in D["pads"]}
    pA, pB = pa[A_], pa[B_]; net = pA["net"]; w = float(opt.get("l3_w", 0.25))
    LS = opt.get("l3_layers", "F.Cu,In2.Cu,In3.Cu,B.Cu").split(","); LC = [float(c) for c in opt.get("l3_cost", "1.5,1.0,1.0,1.8").split(",")]
    PASS = set(opt.get("link_pass", "GND").split(","))
    OC.clear(); VM.clear()
    pclr = float(opt.get("link_padclr", 0.16))
    frees, okgs = [], []
    for L in LS:
        padg = unary_union([pshape(p, L) for p in D["pads"] if p.get("net") != net and L in p["shapes"] and not p.get("drill")])   # drilled pads keep CLR (hole clearance)
        ob = other_copper(L, net).difference(padg.buffer(0.001)).buffer(CLR + w / 2).union(padg.buffer(pclr + w / 2))
        okg = board.buffer(-0.3 - w / 2).difference(ob); okgs.append(okg); frees.append(rast(okg))
    vm = viamask(net)
    N1 = NX * NY; rows, cols, ws = [], [], []
    OFF = float(opt.get("l3_off", 3.0))           # router.py: In2 vertical, In3 horizontal; off-direction steps cost more
    AVM = avoid_maps(net)
    for k, (fr, c) in enumerate(zip(frees, LC)):
        wd = (OFF, 1.0) if LS[k] == "In2.Cu" else ((1.0, OFF) if LS[k] == "In3.Cu" else (1.0, 1.0))
        M, idx, fi = grid_graph(fr, wdir=wd); M = M.tocoo()
        wmul = 1.0
        if AVM is not None and LS[k] in AVM:
            occ = AVM[LS[k]].flat[fi]; wmul = np.where(occ[M.row] | occ[M.col], float(opt.get("avoid_cost", 6.0)), 1.0)
        rows.append(fi[M.row] + k * N1); cols.append(fi[M.col] + k * N1); ws.append(M.data * c * wmul)
    vcost = float(opt.get("l3_via", 3.0)) / G
    vc = np.flatnonzero(vm.ravel() & np.all([f.ravel() for f in frees], axis=0))
    # escape room: a via within --l3_keep mm of another net's small SMD pad (fine-pitch pins, 0402s) costs --l3_keepcost more
    small = unary_union([pshape(p, L) for p in D["pads"] if p.get("net") != net and not p.get("drill") for L in p["shapes"] if L in OUTER and pshape(p, L).area < 1.5])
    vpen = np.where(rast(small.buffer(float(opt.get("l3_keep", 1.0)))).ravel()[vc], float(opt.get("l3_keepcost", 4.0)) / G, 0.0)
    for k in range(len(LS) - 1):
        for k2 in range(k + 1, len(LS)):
            rows += [vc + k * N1, vc + k2 * N1]; cols += [vc + k2 * N1, vc + k * N1]; ws += [vcost + vpen] * 2
    r_ = np.concatenate(rows); c_ = np.concatenate(cols); w_ = np.concatenate(ws)
    MG = csr_matrix((w_, (r_, c_)), shape=(N1 * len(LS), N1 * len(LS)))
    LA = [L for L in pA["shapes"] if L in LS][0]; kA = LS.index(LA)
    src = [i * NX + j + kA * N1 for (i, j) in np.argwhere(rast(pshape(pA, LA).buffer(-0.05)))]
    tgt = unary_union([pshape(pB, L) for L in pB["shapes"] if L in LS])
    zB = [(z["layer"], zpoly(p)) for z in S["zones"] if z["net"] == net and z["layer"] in LS for p in z["polys"] if zpoly(p).intersects(tgt)]
    dst = set()
    cu = [(t["layer"], LineString([t["a"], t["b"]]).buffer(t["w"] / 2)) for t in S["tracks"] + new_tracks if t["net"] == net and t["layer"] in LS and t["a"] != t["b"] and t.get("kind") == "capfix link3d"]
    cu += [(L, Point(v["x"], v["y"]).buffer(v["size"] / 2)) for v in S["vias"] if v["net"] == net and v.get("kind") == "capfix link3d" for L in LS]
    for L, g in [(L, pshape(pB, L)) for L in pB["shapes"] if L in LS] + zB + cu:
        k = LS.index(L)
        for (i, j) in np.argwhere(rast(g.buffer(-0.1)) & frees[k] if g.area > 2 else rast(g)): dst.add(i * NX + j + k * N1)
    dist, pred, _ = dijkstra(MG, indices=src, min_only=True, return_predecessors=True)
    dl = [d for d in dst if np.isfinite(dist[d])]
    if not dl: log(f"link3d {A_}>{B_}: NO PATH"); continue
    best = min(dl, key=lambda d: dist[d]); path = [best]
    while pred[path[-1]] >= 0: path.append(pred[path[-1]])
    path = path[::-1]
    runs = []                                  # split into per-layer runs
    for n_ in path:
        k, cidx = divmod(int(n_), N1); i, j = divmod(cidx, NX)
        if runs and runs[-1][0] == k: runs[-1][1].append(xyof(i, j))
        else: runs.append((k, [xyof(i, j)]))
    nv = 0; ln = 0.0
    for ri, (k, pts) in enumerate(runs):
        if len(pts) > 1:
            pp = pull(pts, okgs[k].union(Point(pts[0]).buffer(0.1)).union(Point(pts[-1]).buffer(0.1)))
            if ri == 0 and okgs[k].union(pshape(pA, LS[k]).buffer(-0.02)).covers(LineString([(pA["x"], pA["y"]), pp[min(1, len(pp) - 1)]])): pp = [(pA["x"], pA["y"])] + pp[1:]
            add_track(net, LS[k], pp, w, "capfix link3d"); ln += LineString(pp).length
        if ri < len(runs) - 1:
            q = pts[-1]; new_vias.append({"net": net, "x": round(q[0], 4), "y": round(q[1], 4), "size": VIA_D, "drill": VIA_DR, "kind": "capfix link3d"}); nv += 1
    S["vias"] += new_vias[len(new_vias) - nv:]
    log(f"link3d {net} {A_}>{B_}: {ln:.1f} mm on {'/'.join(LS[k] for k, _ in runs)}, {nv} vias")
    PASS = set(opt.get("pass", "GND").split(",")); OC.clear(); VM.clear()

# ---------------------------------------------------------------- 3c. ratsnest anchors (--anchor=REF.PAD>REF.PAD;...): router.py turns a
# DRC unconnected item "Zone ... | Pad" of a non-plane net into a zero-length route at the pad (its zone goal mask is
# searched only in the window round the pad), so such a net is never joined.  An anchor is a via of the net just outside
# the planned zone that holds the first pad, on the side facing the second pad, joined by a short track: KiCad's ratsnest
# then reports "Via | Pad" and the router routes a real connection to it.
for spec in [s_ for s_ in opt.get("anchor", "").split(";") if s_]:
    A_, B_ = spec.split(">"); pa = {(p["ref"] + "." + p["num"]): p for p in D["pads"]}
    pA, pB = pa[A_], pa[B_]; net = pA["net"]; OC.clear(); VM.clear()
    Zs = [zpoly(p) for z in S["zones"] if z["net"] == net and z["layer"] in OUTER for p in z["polys"] if zpoly(p).intersects(pshape(pA, "F.Cu").union(pshape(pA, "B.Cu")))]
    if not Zs: log(f"anchor {spec}: no zone at {A_}"); continue
    Z = unary_union(Zs); tB = Point(pB["x"], pB["y"])
    from shapely.ops import nearest_points
    bd_ = Z.exterior if hasattr(Z, "exterior") else Z.boundary
    pts_ = sorted((bd_.interpolate(t_ * 0.2) for t_ in range(int(bd_.length / 0.2))), key=lambda q: q.distance(tB))
    done = False; zbuf = Z.buffer(0.55)
    for e, track_only in [(e_, t_) for t_ in (False, True) for e_ in pts_[:80]]:
        for off in ([0.75 + 0.15 * k for k in range(10)] if not track_only else [0.6, 0.8, 1.0]):
            for ang in (0, 30, -30, 60, -60):
                dx, dy = tB.x - e.x, tB.y - e.y; a0 = math.atan2(dy, dx) + math.radians(ang)
                vx, vy = e.x + off * math.cos(a0), e.y + off * math.sin(a0)
                if zbuf.contains(Point(vx, vy)) or Point(vx, vy).distance(tB) > Z.distance(tB) - 0.3: continue
                seg = LineString([(e.x - 0.15 * math.cos(a0), e.y - 0.15 * math.sin(a0)), (vx, vy)])
                if (track_only or via_ok(vx, vy, net)) and OC.setdefault("F.Cu", other_copper("F.Cu", net)).distance(seg) > CLR + 0.125:
                    add_track(net, "F.Cu", list(seg.coords), 0.25, "capfix anchor")
                    if track_only: done = "track"; break
                    v = {"net": net, "x": round(vx, 4), "y": round(vy, 4), "size": VIA_D, "drill": VIA_DR, "kind": "capfix anchor"}
                    new_vias.append(v); S["vias"].append(v); done = True; break
            if done: break
        if done: break
    log(f"anchor {net} {A_}>{B_}: " + (("track end" if done == "track" else "via") + f" ({vx:.2f}, {vy:.2f}), {off:.1f} mm out of the zone" if done else "NO legal spot"))
S["tracks"] += new_tracks[nt0:]; nt0 = len(new_tracks); nv0 = len(new_vias)

# ---------------------------------------------------------------- 1. In4 band for a soft net
BAND = opt.get("band", "")
if BAND:
    net = BAND; L4 = opt.get("band_layer", "In4.Cu"); wb = float(opt.get("band_w", 2.0)); wmin = float(opt.get("band_wmin", 0.8))
    obst4 = other_copper(L4, net).buffer(CLR)
    inner = board.buffer(-0.5)
    def freemask(w): return rast(inner.buffer(-w / 2).difference(obst4.buffer(w / 2)))
    freeB = freemask(wb); freeN = freemask(wmin)       # wide band where room, narrow necks allowed (cost x3)
    cost_free = freeN
    M, idx, fi = grid_graph(cost_free)
    # make narrow-only cells cost more: rebuild weights
    narrow = (freeN & ~freeB).flat[fi]
    M = M.tocoo(); wmul = np.where(narrow[M.row] | narrow[M.col], 3.0, 1.0)
    M = csr_matrix((M.data * wmul, (M.row, M.col)), shape=M.shape)
    lab, nl = ndimage.label(freeN, structure=np.ones((3, 3)))
    vias = [v for v in S["vias"] if v["net"] == net]
    pads = [p for p in D["pads"] if p.get("net") == net]
    # via groups (vias within 1.5 mm = one node)
    nodes = []
    for v in vias:
        for n_ in nodes:
            if min(math.dist((v["x"], v["y"]), q) for q in n_["pts"]) < 1.5: n_["pts"].append((v["x"], v["y"])); break
        else: nodes.append({"pts": [(v["x"], v["y"])], "kind": "via"})
    def node_cells(n_): return [c for q in n_["pts"] for c in near_cells(*q, freeN, 0.25 + wmin / 2)]
    for n_ in nodes: n_["cells"] = node_cells(n_); n_["comp"] = {lab[c] for c in n_["cells"]} - {0}
    # cross: join In4 components that hold nodes, through hard tracks inside planned outer zones of the net + new vias
    par = {}
    def uf(c):
        par.setdefault(c, c)
        while par[c] != c: par[c] = par[par[c]]; c = par[c]
        return c
    def ncomp(n_): return {uf(c) for c in n_["comp"]}
    if opt.get("cross", "1") == "1":
        changed = True
        while changed and len({c for n_ in nodes for c in ncomp(n_)}) > 1:
            changed = False
            for n_ in list(nodes):
                if not n_["cells"]: continue
                mine = ncomp(n_); others = {c for m in nodes for c in ncomp(m)} - mine
                if not others: continue
                zl = [(z["layer"], zpoly(p)) for z in S["zones"] if z["net"] == net and z["layer"] in OUTER for p in z["polys"]]
                zl = [(L, Z) for L, Z in zl if any(Z.buffer(0.05).contains(Point(q)) for q in n_["pts"])] or [(L, None) for L in OUTER]
                for L, Z in zl:
                    if changed: break
                    wt = float(opt.get("cross_w", 0.4)); cmax = float(opt.get("cross_max", 8))
                    oc = other_copper(L, net).buffer(CLR + wt / 2)
                    zin = board.buffer(-0.3 - wt / 2).difference(oc)
                    reach = unary_union([Point(q).buffer(cmax) for q in n_["pts"]])
                    vm = viamask(net) & rast(reach) & (lab > 0)
                    cand = []
                    for (i, j) in np.argwhere(vm):
                        if uf(lab[i, j]) in others: cand.append((*xyof(i, j), uf(lab[i, j])))
                    if not cand: continue
                    freeZ = (rast(zin) & rast(reach)) | rast(unary_union([Point(q[:2]).buffer(0.25) for q in n_["pts"]]))
                    # inside the net's own zone costs 1, outside 2 (prefer the existing copper corridor)
                    MZ, idxZ, fiZ = grid_graph(freeZ)
                    if Z is not None:
                        inz = rast(Z).flat[fiZ]; MZ = MZ.tocoo(); wm = np.where(inz[MZ.row] & inz[MZ.col], 1.0, 2.0)
                        MZ = csr_matrix((MZ.data * wm, (MZ.row, MZ.col)), shape=MZ.shape)
                    src = [c for q in n_["pts"] for c in near_cells(*q, freeZ, 0.2)]
                    cset = {cellof(q[0], q[1]): q for q in cand}
                    # site choice: path length + escape-room penalty (other-net small pads within --l3_keep) + avoid map
                    small = unary_union([pshape(p, L2) for p in D["pads"] if p.get("net") != net and not p.get("drill") for L2 in p["shapes"] if L2 in OUTER and pshape(p, L2).area < 1.5])
                    near_small = rast(small.buffer(float(opt.get("l3_keep", 1.0))))
                    AVM = avoid_maps(net)
                    s_ = [idxZ[c] for c in src if idxZ[c] >= 0]
                    dist, pred, _ = dijkstra(MZ, indices=s_, min_only=True, return_predecessors=True)
                    def pen(c):
                        p_ = float(opt.get("l3_keepcost", 4.0)) if near_small[c] else 0.0
                        if AVM is not None: p_ += sum(float(opt.get("avoid_cost", 6.0)) * 0.5 for L2 in AVM if AVM[L2][c])
                        return p_
                    sc = sorted((dist[idxZ[c]] * G + pen(c), c) for c in cset if freeZ[c] and idxZ[c] >= 0 and np.isfinite(dist[idxZ[c]]))
                    r = None
                    for _, c in sc[:40]:
                        site = cset[c]
                        if not via_ok(site[0], site[1], net): continue
                        path = [idxZ[c]]
                        while pred[path[-1]] >= 0: path.append(pred[path[-1]])
                        path = [divmod(int(fiZ[k]), NX) for k in path[::-1]]; ln = dist[idxZ[c]] * G; r = (path, ln); break
                    if r is None: continue
                    okg = zin.union(unary_union([Point(q[:2]).buffer(0.25) for q in [*n_["pts"], site]]))
                    pts = pull([xyof(*c) for c in path], okg); pts[-1] = site[:2]
                    start = min(n_["pts"], key=lambda q: math.dist(q, pts[0]))
                    if okg.covers(LineString([start, pts[0]])): pts = [start] + pts
                    add_track(net, L, pts, wt, "capfix cross")
                    new_vias.append({"net": net, "x": round(site[0], 4), "y": round(site[1], 4), "size": VIA_D, "drill": VIA_DR, "kind": "capfix cross"}); OC.clear(); VM.clear()
                    nn = {"pts": [site[:2]], "kind": "cross", "cells": near_cells(site[0], site[1], freeN, 0.25 + wmin / 2)}
                    nn["comp"] = {lab[c] for c in nn["cells"]} - {0}; nodes.append(nn)
                    for c in mine: par[uf(c)] = uf(site[2])
                    log(f"cross {net}: new via ({site[0]:.2f}, {site[1]:.2f}), {L} hard track {ln:.1f} mm ({len(pts) - 1} segments) from {n_['pts'][0]}" + (f" mostly inside its zone ({Z.area:.1f} mm2)" if Z is not None else ""))
                    changed = True
                if changed: break
        for n_ in nodes:
            if len({c for m in nodes for c in ncomp(m)}) > 1: log(f"cross {net}: node {n_['pts'][0]} in In4 comp {sorted(ncomp(n_))}")
    # Steiner tree over all nodes of the main component; pads as soft targets afterwards
    from collections import Counter
    cnt = Counter(uf(c) for n_ in nodes for c in n_["comp"]); main = cnt.most_common(1)[0][0]
    lines = []; reached = []; tree = set()
    for lc in sorted({c for n_ in nodes for c in n_["comp"] if uf(c) == main}):       # one Steiner tree per In4 piece
        todo = [n_ for n_ in nodes if lc in n_["comp"] and n_ not in reached]
        if not todo: continue
        t_ = set(c for c in todo[0]["cells"] if lab[c] == lc); reached.append(todo[0]); todo = todo[1:]
        while todo:
            allc = [c for n_ in todo for c in n_["cells"] if lab[c] == lc]
            r = shortest(freeN, M, idx, fi, list(t_), allc)
            if r is None: log("band: unreachable", [n_["pts"][0] for n_ in todo]); break
            path, ln = r
            hit = next(n_ for n_ in todo if tuple(path[-1]) in set(n_["cells"]))
            todo.remove(hit); reached.append(hit); t_ |= set(map(tuple, path)) | set(hit["cells"])
            lines.append(([xyof(*c) for c in path], ln))
        tree |= t_
    for n_ in nodes:
        if n_ not in reached: log(f"band {net}: via node {n_['pts'][0]} NOT joined")
    # pads: band spur to pads of the net within --pad_reach mm of the tree (their router via likely lands in the band)
    padr = float(opt.get("pad_reach", 12)); spurs = 0
    for p in sorted(pads, key=lambda p: p["ref"]):
        pc = near_cells(p["x"], p["y"], freeN, 0.6)
        pc = [c for c in pc if lab[c] > 0 and uf(lab[c]) == main]
        if not pc: continue
        if any(math.dist(xyof(*c), (p["x"], p["y"])) < 0.6 for c in tree): continue
        r = shortest(freeN, M, idx, fi, list(tree), pc)
        if r is None or r[1] > padr: continue
        tree |= set(map(tuple, r[0])); lines.append(([xyof(*c) for c in r[0]], r[1])); spurs += 1
    # geometry: wide where freeB, narrow elsewhere, all clipped to legal space
    legalB = inner.difference(obst4)
    geo = []
    for pts, ln in lines:
        ls = LineString(pts) if len(pts) > 1 else Point(pts[0])
        geo.append(ls.buffer(wb / 2, 8).intersection(legalB))
        geo.append(ls.buffer(wmin / 2 + 0.02, 8))
    for n_ in reached: geo += [Point(q).buffer(max(wmin, 1.0), 16).intersection(legalB) for q in n_["pts"]]
    band = unary_union(geo).intersection(legalB)
    # keep only the pieces that hold nodes (clipping can leave slivers)
    keep = [g for g in getattr(band, "geoms", [band]) if any(g.distance(Point(q)) < 0.3 for n_ in reached for q in n_["pts"])]
    band = unary_union(keep)
    prio = int(opt.get("band_prio", 10))
    add_zone(net, L4, band, prio, "capfix band")
    tl = sum(ln for _, ln in lines)
    log(f"band {net} on {L4}: {len(reached)} of {len(nodes)} via nodes joined, {spurs} pad spurs, {tl:.0f} mm of path, "
        f"{band.area:.0f} mm2 in {len(getattr(band, 'geoms', [band]))} piece(s)")

# ---------------------------------------------------------------- 2. stubs
if opt.get("stubs", "0") == "1" or opt.get("stub_refs"):
    nets = opt.get("stub_nets", "3V3,PACK_P").split(","); amax = float(opt.get("stub_area", 40)); smax = float(opt.get("stub_max", 8))
    refs = set(r for r in opt.get("stub_refs", "").split(",") if r)
    wt = float(opt.get("stub_w", 0.4))
    allt = S["tracks"] + new_tracks; allv = S["vias"] + new_vias
    for p in D["pads"]:
        key = p["ref"] + "." + p["num"]
        if p.get("net") not in nets or p.get("drill") or key in SEALED: continue
        if key not in refs and not any(p["ref"].startswith(x) for x in opt.get("stub_prefix", "C").split(",")): continue
        for L in p["shapes"]:
            if L not in OUTER: continue
            ps = pshape(p, L)
            if any(LineString([t["a"], t["b"]]).buffer(t["w"] / 2).intersects(ps) for t in allt if t["net"] == p["net"] and t["layer"] == L and t["a"] != t["b"]): continue
            if any(ps.buffer(0.05).contains(Point(v["x"], v["y"])) for v in allv if v["net"] == p["net"]): continue
            for z in S["zones"]:
                if z["net"] != p["net"] or z["layer"] != L: continue
                for zp in z["polys"]:
                    Z = zpoly(zp)
                    if not Z.intersects(ps): continue
                    if Z.area > amax and key not in refs: continue
                    tg = [Point(v["x"], v["y"]).buffer(v["size"] / 2 - 0.05) for v in allv if v["net"] == p["net"] and Z.contains(Point(v["x"], v["y"]))]
                    tg += [LineString([t["a"], t["b"]]).buffer(max(0.02, t["w"] / 2 - 0.05)) for t in allt if t["net"] == p["net"] and t["layer"] == L and t["a"] != t["b"] and Z.intersects(LineString([t["a"], t["b"]]))]
                    tg = [g.intersection(Z) for g in tg]; tg = [g for g in tg if not g.is_empty and g.distance(ps) > 0.01]
                    if not tg: log(f"stub {key}: no hard copper in its zone ({Z.area:.1f} mm2)"); continue
                    oc = other_copper(L, p["net"]).buffer(CLR + wt / 2)
                    ok = Z.buffer(-wt / 2 - 0.02).difference(oc).union(ps.buffer(-0.02)).union(unary_union(tg))
                    freeZ = rast(ok); MZ, idxZ, fiZ = grid_graph(freeZ)
                    r = shortest(freeZ, MZ, idxZ, fiZ, cells_in(ps.buffer(-0.05), freeZ), cells_in(unary_union(tg), freeZ))
                    if r is None or r[1] > smax: log(f"stub {key}: no path inside zone ({Z.area:.1f} mm2)" if r is None else f"stub {key}: {r[1]:.1f} mm > max"); continue
                    pts = pull([xyof(*c) for c in r[0]], ok)
                    if ok.covers(LineString([(p["x"], p["y"]), pts[min(1, len(pts) - 1)]])): pts = [(p["x"], p["y"])] + pts[1:]
                    add_track(p["net"], L, pts, wt, "capfix stub")
                    log(f"stub {key} on {L}: {r[1]:.1f} mm inside its zone ({Z.area:.1f} mm2)")
                    break
                else: continue
                break

S["tracks"] += new_tracks[nt0:]; S["vias"] += new_vias[nv0:]; S["zones"] += new_zones
S.setdefault("report", {})["capfix"] = REP
json.dump(S, open(OUT, "w"), indent=0)
print(f"[capfix] added {len(new_tracks)} tracks, {len(new_vias)} vias, {len(new_zones)} zones -> {OUT}")
