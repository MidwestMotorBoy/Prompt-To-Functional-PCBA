"""A* signal router for the ground-up Monolith layout (adapted from hardware/DevBoard/tools/route_signals6.py).
   router.py in.kicad_pcb drc.json out.kicad_pcb [--w=0.2] [--only=regex] [--skip=regex] [--max=N] [--relaxed]"""
import heapq
import math
import os
import re
import sys

import numpy as np
import pcbnew
from PIL import Image, ImageDraw

import json
PCB, RPT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
OPT = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[4:] if a.startswith("--"))
MAX_EDGES = int(OPT.get("max", 10 ** 6))
RELAXED = "strict" not in OPT            # inner layers: preferred direction, off-direction steps cost more
ONLY = re.compile(OPT["only"]) if "only" in OPT else None
SKIP = re.compile(OPT["skip"]) if "skip" in OPT else None

G = float(OPT.get("g", 0.05))             # grid, mm
W, CLR, TOL = float(OPT.get("w", 0.2)), 0.15, (0.04 if G <= 0.05 else 0.08)             # track width, clearance, raster tolerance (discs rasterise a cell small)
VIA_D, VIA_DRILL = 0.45, 0.3
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
LCOST = [1.6, 1.0, 1.0, 1.8]
VERT, HORZ = 1, 2                         # Manhattan pair: In2 vertical only, In3 horizontal only
VIA_COST = 4.0 / G                        # in grid steps
VIA_GAP_PATH = int(0.8 / G)                          # cells between two vias of one route (no via-hop-via-back)
VIA_MIN_SAME, VIA_MIN_OTHER = [float(v) for v in OPT.get("vs", "0.6,0.75").split(",")]   # mm between via centres
PTH_MIN_SAME, PTH_MIN_OTHER = 0.9, 1.1    # mm from a via centre to a through-hole pad (measured as before)
TOLX = 0.012                              # margin on exactly rasterised shapes (pads, tracks, vias)
BEND = 0.4
SOFT = ("GND_PLANE", "PACK_P_PLANE", "3V3_PLANE", "GND_FILL")       # zones that refill around new tracks
PLANE_NETS = ("PACK_P", "3V3")                                       # reached by a via / track to their plane or pours
SEALED = [("R425", "1"), ("R426", "1"), ("R428", "1"), ("R429", "1"), ("R525", "1"), ("R526", "1"), ("R528", "1"),
          ("R529", "1"), ("R107", "1"), ("R108", "1")]                # Kelvin tap pads: nothing else may attach

mm = pcbnew.FromMM
MM = pcbnew.ToMM
board = pcbnew.LoadBoard(PCB)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = MM(bb.GetLeft()), MM(bb.GetTop())
NX, NY = int(MM(bb.GetWidth()) / G) + 2, int(MM(bb.GetHeight()) / G) + 2
EMPTY, MULTI = -1, -2
grid = [np.full((NY, NX), EMPTY, dtype=np.int32) for _ in LAYERS]      # copper grown by clearance (obstacles)
copper = [np.full((NY, NX), EMPTY, dtype=np.int32) for _ in LAYERS]    # true copper (route ends)
zc = [np.full((NY, NX), EMPTY, dtype=np.int32) for _ in LAYERS]        # zone-fill copper only (plane / pour goals)
hz = [np.full((NY, NX), EMPTY, dtype=np.int32) for _ in LAYERS]        # hard (non-refilling) zone copper
gridv = [np.full((NY, NX), EMPTY, dtype=np.int32) for _ in LAYERS]     # obstacles grown for a via centre
VGROW = VIA_D / 2 - W / 2
DEST = [grid]
FIX = {}                                  # snapshot of the grids without the rip-able routes
HC = re.compile(r"(^PACK_P$|^CELL_N$|/Cells and Gauge/CELL|/FET_MID|/PPHV|/VBUS$|/SW[12]$|/AC_SNS_N|/BAT_SNS_P)")
hc = {board.FindNet(str(nm)).GetNetCode() for nm in board.GetNetsByName().keys() if HC.search(str(nm))}


def cell(x, y):
    return int(round((x - X0) / G)), int(round((y - Y0) / G))


def mark(li, net, draw_fn, x0, y0, x1, y1):
    """Rasterise one shape (drawn by draw_fn on a local PIL canvas) into layer li as net."""
    cx0, cy0 = cell(x0, y0)
    cx1, cy1 = cell(x1, y1)
    cx0, cy0, cx1, cy1 = max(cx0 - 1, 0), max(cy0 - 1, 0), min(cx1 + 2, NX), min(cy1 + 2, NY)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    im = Image.new("1", (cx1 - cx0, cy1 - cy0), 0)
    draw_fn(ImageDraw.Draw(im), lambda x, y: ((x - X0) / G - cx0, (y - Y0) / G - cy0))
    m = np.array(im, dtype=bool)
    if DEST[0] is copper or DEST[0] is zc or DEST[0] is hz:
        DEST[0][li][cy0:cy1, cx0:cx1][m] = net
        return
    reg = DEST[0][li][cy0:cy1, cx0:cx1]
    free = m & (reg == EMPTY)
    clash = m & (reg != EMPTY) & (reg != net)
    reg[free] = net
    reg[clash] = MULTI


def grow(net):
    return CLR + W / 2 + TOLX + (0.1 if net in hc else 0.0)


def growp(net):
    return grow(net) + TOL - TOLX


def _xapply(arr, li, net, w, m):
    cx0, cy0 = w[0], w[1]
    reg = arr[li][cy0:cy0 + m.shape[0], cx0:cx0 + m.shape[1]]
    if not (arr is copper or arr is zc or arr is hz or arr is FIX.get("copper")):
        free = m & (reg == EMPTY)
        clash = m & (reg != EMPTY) & (reg != net)
        reg[free] = net
        reg[clash] = MULTI
    else:
        reg[m] = net


def _xwin(x0, y0, x1, y1):
    cx0, cy0 = cell(x0, y0)
    cx1, cy1 = cell(x1, y1)
    cx0, cy0, cx1, cy1 = max(cx0 - 1, 0), max(cy0 - 1, 0), min(cx1 + 2, NX), min(cy1 + 2, NY)
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    return cx0, cy0, (X0 + np.arange(cx0, cx1) * G)[None, :], (Y0 + np.arange(cy0, cy1) * G)[:, None]


def xrect(arr, li, net, rc, g):
    """Cells whose centre is within g of the rectangle rc (exact)."""
    w = _xwin(rc[0] - g, rc[1] - g, rc[2] + g, rc[3] + g)
    if w:
        dx = np.maximum(np.maximum(rc[0] - w[2], w[2] - rc[2]), 0.0)
        dy = np.maximum(np.maximum(rc[1] - w[3], w[3] - rc[3]), 0.0)
        _xapply(arr, li, net, w, dx * dx + dy * dy <= g * g + 1e-9)


def xseg(arr, li, net, a, b, half):
    w = _xwin(min(a[0], b[0]) - half, min(a[1], b[1]) - half, max(a[0], b[0]) + half, max(a[1], b[1]) + half)
    if w:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        px, py = w[2] - a[0], w[3] - a[1]
        t = np.clip((px * dx + py * dy) / L, 0.0, 1.0) if L > 0 else 0.0
        ex, ey = px - t * dx, py - t * dy
        _xapply(arr, li, net, w, ex * ex + ey * ey <= half * half + 1e-9)


def mark_poly(li, net, poly, g):
    ps = pcbnew.SHAPE_POLY_SET(poly)
    if g > 0:
        ps.Inflate(mm(g), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        pts = [(MM(o.CPoint(j).x), MM(o.CPoint(j).y)) for j in range(o.PointCount())]
        if len(pts) < 3:
            continue
        holes = []
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h)
            holes.append([(MM(hh.CPoint(j).x), MM(hh.CPoint(j).y)) for j in range(hh.PointCount())])
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]

        def draw(d, T, pts=pts, holes=holes):
            d.polygon([T(*p) for p in pts], fill=1)
            for h in holes:
                if len(h) >= 3:
                    d.polygon([T(*p) for p in h], fill=0)
        mark(li, net, draw, min(xs), min(ys), max(xs), max(ys))


def mark_seg(li, net, a, b, half):
    if DEST[0] is grid:
        xseg(grid, li, net, a, b, half)
        xseg(gridv, li, net, a, b, half + VGROW)
    else:
        xseg(DEST[0], li, net, a, b, half)


def mark_disc(li, net, c, r):
    mark_seg(li, net, c, c, r)


def mark_poly2(li, net, poly, g):
    """Polygon into the track grid and, grown further, into the via grid."""
    mark_poly(li, net, poly, g)
    DEST[0] = gridv
    mark_poly(li, net, poly, g + VGROW)
    DEST[0] = grid


RECTSHAPES = (pcbnew.PAD_SHAPE_RECTANGLE, pcbnew.PAD_SHAPE_ROUNDRECT)


# ---- obstacles (grown) and true copper ----------------------------------------------------------------------------
def pad_layers(p):
    return [li for li, lay in enumerate(LAYERS) if p.IsOnLayer(lay) or p.HasHole()]


for dest, k in ((grid, 1.0), (copper, 0.0)):
    DEST[0] = dest
    for fp in board.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetCode()
            for li in pad_layers(p):
                if dest is copper:
                    mark_poly(li, n, p.GetEffectivePolygon(LAYERS[li], pcbnew.ERROR_INSIDE), 0.0)
                elif p.GetShape(LAYERS[li]) in RECTSHAPES and abs(p.GetOrientationDegrees() % 90) < 0.01:
                    bq = p.GetBoundingBox()
                    rc = (MM(bq.GetLeft()), MM(bq.GetTop()), MM(bq.GetRight()), MM(bq.GetBottom()))
                    xrect(grid, li, n, rc, grow(n))
                    xrect(gridv, li, n, rc, grow(n) + VGROW)
                else:
                    mark_poly2(li, n, p.GetEffectivePolygon(LAYERS[li], pcbnew.ERROR_INSIDE), growp(n))
    for t in board.GetTracks():
        n = t.GetNetCode()
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            for li in range(len(LAYERS)):
                mark_disc(li, n, (MM(c.x), MM(c.y)), MM(t.GetWidth(pcbnew.F_Cu)) / 2 + k * grow(n))
        elif t.GetLayer() in LAYERS:
            li = LAYERS.index(t.GetLayer())
            a, b = t.GetStart(), t.GetEnd()
            mark_seg(li, n, (MM(a.x), MM(a.y)), (MM(b.x), MM(b.y)), MM(t.GetWidth()) / 2 + k * grow(n))
    if dest is copper:
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue
            for li, lay in enumerate(LAYERS):
                if z.IsOnLayer(lay):
                    mark_poly(li, z.GetNetCode(), z.GetFilledPolysList(lay), 0.0)
DEST[0] = zc
for z in board.Zones():
    if not z.GetIsRuleArea():
        for li, lay in enumerate(LAYERS):
            if z.IsOnLayer(lay):
                mark_poly(li, z.GetNetCode(), z.GetFilledPolysList(lay), 0.0)
DEST[0] = hz
for z in board.Zones():
    if not z.GetIsRuleArea() and z.GetZoneName() not in SOFT:
        for li, lay in enumerate(LAYERS):
            if z.IsOnLayer(lay):
                mark_poly(li, z.GetNetCode(), z.GetFilledPolysList(lay), 0.0)
DEST[0] = grid
gnd = board.FindNet("GND").GetNetCode()
for z in board.Zones():
    if z.GetIsRuleArea():
        for li, lay in enumerate(LAYERS):
            if z.IsOnLayer(lay) and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                mark_poly2(li, MULTI, z.Outline(), growp(0))
        continue
    n = z.GetNetCode()
    for li, lay in enumerate(LAYERS):
        if not z.IsOnLayer(lay):
            continue
        if z.GetZoneName() in SOFT:
            continue                       # plane / ground fills: signals may cut them (refill carves around them)
        mark_poly2(li, n, z.GetFilledPolysList(lay), growp(n))
# room for the In2 GND fill's thermal spokes round GND through-hole pads (a signal hugging the pad starves them)
for fp in board.GetFootprints():
    for q in fp.Pads():
        if False:
            c, bq = q.GetPosition(), q.GetBoundingBox()
            mark_disc(1, gnd, (MM(c.x), MM(c.y)), max(MM(bq.GetWidth()), MM(bq.GetHeight())) / 2 + 0.6)
# outside the board (edge rule 0.25 mm)
outline = pcbnew.SHAPE_POLY_SET()
board.GetBoardPolygonOutlines(outline, False)
inside = pcbnew.SHAPE_POLY_SET(outline)
inside.Deflate(mm(0.25 + W / 2 + TOL), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
inmask = Image.new("1", (NX, NY), 0)
dr = ImageDraw.Draw(inmask)
for i in range(inside.OutlineCount()):
    o = inside.Outline(i)
    dr.polygon([((MM(o.CPoint(j).x) - X0) / G, (MM(o.CPoint(j).y) - Y0) / G) for j in range(o.PointCount())], fill=1)
outside = ~np.array(inmask, dtype=bool)
inside2 = pcbnew.SHAPE_POLY_SET(outline)
inside2.Deflate(mm(0.25 + VIA_D / 2 + TOL), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
inmask2 = Image.new("1", (NX, NY), 0)
dr2 = ImageDraw.Draw(inmask2)
for i in range(inside2.OutlineCount()):
    o = inside2.Outline(i)
    dr2.polygon([((MM(o.CPoint(j).x) - X0) / G, (MM(o.CPoint(j).y) - Y0) / G) for j in range(o.PointCount())], fill=1)
outside2 = ~np.array(inmask2, dtype=bool)
for li in range(len(LAYERS)):
    gridv[li][outside2] = MULTI
for li in range(len(LAYERS)):
    grid[li][outside] = MULTI
    ax0, ay0 = cell(118.12 - 0.4, 119.88 - 0.4)        # antenna keep-out: no routing on any layer
    ax1, ay1 = cell(121.32 + 0.4, 125.28 + 0.4)
    grid[li][ay0:ay1 + 1, ax0:ax1 + 1] = MULTI
    gridv[li][ay0 - 3:ay1 + 4, ax0 - 3:ax1 + 4] = MULTI
# GND plane on In1: a via anywhere on it grounds a GND pad
gim = Image.new("1", (NX, NY), 0)
gdr = ImageDraw.Draw(gim)
for z in board.Zones():
    if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.In1_Cu) and z.GetNetCode() == gnd:
        ps = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(pcbnew.In1_Cu))
        ps.Deflate(mm(0.35), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            if o.PointCount() >= 3:
                gdr.polygon([((MM(o.CPoint(j).x) - X0) / G, (MM(o.CPoint(j).y) - Y0) / G) for j in range(o.PointCount())], fill=1)
            for h in range(ps.HoleCount(i)):
                hh = ps.Hole(i, h)
                if hh.PointCount() >= 3:
                    gdr.polygon([((MM(hh.CPoint(j).x) - X0) / G, (MM(hh.CPoint(j).y) - Y0) / G) for j in range(hh.PointCount())], fill=0)
GNDPLANE = np.array(gim, dtype=bool)
# sealed Kelvin pads (and the stubs on them): obstacles for everything, never a route end
SEALED_PADS = set()
for ref, num in SEALED:
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        continue
    for p in fp.Pads():
        if p.GetNumber() == num:
            SEALED_PADS.add((ref, num))
            bq = p.GetBoundingBox()
            cx0, cy0 = cell(MM(bq.GetLeft()) - 0.3, MM(bq.GetTop()) - 0.3)
            cx1, cy1 = cell(MM(bq.GetRight()) + 0.3, MM(bq.GetBottom()) + 0.3)
            grid[0][cy0:cy1 + 1, cx0:cx1 + 1] = MULTI
            gridv[0][cy0 - 3:cy1 + 4, cx0 - 3:cx1 + 4] = MULTI
            copper[0][cy0:cy1 + 1, cx0:cx1 + 1] = MULTI
VIA_EXTRA = int(math.ceil((VIA_D / 2 - W / 2) / G))   # a via needs this much more room than a track centre line

HOLES, BIG_HOLES = {}, []                 # 1 mm buckets of (x, y, r_extra, net); large PTH pads kept apart
HOLE_CACHE = {}


def add_hole(x, y, r, n):
    if r > 1.0:
        BIG_HOLES.append((x, y, r, n))
    else:
        HOLES.setdefault((int(x), int(y)), []).append((x, y, r, n))
    HOLE_CACHE.clear()


for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        v = t.GetPosition()
        add_hole(MM(v.x), MM(v.y), 0.0, t.GetNetCode())
for fp in board.GetFootprints():
    for q in fp.Pads():
        if q.HasHole():
            c = q.GetPosition()
            r = max(MM(q.GetBoundingBox().GetWidth()), MM(q.GetBoundingBox().GetHeight())) / 2 - VIA_D / 2
            add_hole(MM(c.x), MM(c.y), max(r, 0.0), q.GetNetCode())


def via_spacing_ok(x, y, net):
    key = (round(x, 2), round(y, 2), net)
    if key in HOLE_CACHE:
        return HOLE_CACHE[key]
    near = [h for i in range(int(x) - 3, int(x) + 4) for j in range(int(y) - 3, int(y) + 4) for h in HOLES.get((i, j), ())]
    ok = True
    for hx, hy, r, hn in near + BIG_HOLES:
        if math.hypot(hx - x, hy - y) - r < ((VIA_MIN_SAME if hn == net else VIA_MIN_OTHER) if r <= 0 else
                                             (PTH_MIN_SAME if hn == net else PTH_MIN_OTHER)):
            ok = False
            break
    HOLE_CACHE[key] = ok
    return ok


# ---- edges from the DRC report ----------------------------------------------------------------------------------
edges = []
SEEN = set()
KELV = re.compile(r"(ACP_F|ACN_F|SRP_F|SRN_F|/Cells and Gauge/SR[PN]$)")
GATE = re.compile(r"/(HIDRV|LODRV)\d$")
FINEPIN = re.compile(r"[Pp]ad \S+ \[.*?\] of (U\d+|J401|J501|J301|J302)\b")
PRIO = [l.rstrip("\n") for l in open(OPT["prio"])] if "prio" in OPT and os.path.exists(OPT["prio"]) else []
for u in json.load(open(RPT))["unconnected_items"]:
    it = u["items"]
    if len(it) < 2:
        continue
    A = (it[0]["pos"]["x"], it[0]["pos"]["y"], it[0]["description"])
    B = (it[1]["pos"]["x"], it[1]["pos"]["y"], it[1]["description"])
    if A[2].startswith("Zone") and not B[2].startswith("Zone"):
        A, B = B, A
    netm = re.search(r"\[(.*?)\]", A[2])
    if not netm:
        continue
    name = netm.group(1)
    if (ONLY and not ONLY.search(name)) or (SKIP and SKIP.search(name)):
        continue
    if A[2].startswith("Zone") and B[2].startswith("Zone"):
        continue
    d = math.hypot(A[0] - B[0], A[1] - B[1])
    if name in PLANE_NETS or name == "GND":
        for I in (A, B):
            if not I[2].startswith("Zone") and I[2] not in SEEN:
                SEEN.add(I[2])
                edges.append((2 + PRIO.index(name + "@" + I[2]) / 10000.0 if name + "@" + I[2] in PRIO else 4, 0.5, name, I, (I[0], I[1], "Zone plane")))
        continue
    if B[2].startswith("Zone"):
        d, B = 0.5, (A[0], A[1], B[2])
    fine = any(FINEPIN.search(I[2]) for I in (A, B))
    rank = 0 if KELV.search(name) else (1 if GATE.search(name) else (2 + PRIO.index(name) / 10000.0 if name in PRIO else (3 if fine else 4)))
    edges.append((rank, d, name, A, B))
edges.sort()
print("edges to route:", len(edges))


CUR = [None]                              # items of the route being laid: (object, "T"/"V", layer, a, b, half width)
ROUTES = {}                               # edge id -> {net, items, rips}
TRK_BY_NET = {}                           # pre-existing tracks / vias (route_power fanouts) per net
for _t in board.GetTracks():
    TRK_BY_NET.setdefault(_t.GetNetCode(), []).append(_t)


def island_cells(pad, net, seeds=None):
    """Cells of the hand-placed stubs and vias hanging off a pad (fanned-out fine-pitch pins: the pad itself is boxed
    in, the route starts / ends on its via). With seeds (tracks / vias) instead of a pad, flood from those."""
    items, frontier, seen = [], [], set()
    for t in (seeds if seeds is not None else TRK_BY_NET.get(net, ())):
        if seeds is not None or (t.GetClass() != "PCB_VIA" and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()))):
            ends = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
            items.append(t); seen.add(t.m_Uuid.AsString()); frontier += ends
    for _ in range(6):
        nxt = []
        for t in TRK_BY_NET.get(net, ()):
            if t.m_Uuid.AsString() in seen:
                continue
            ends = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
            if any(abs(e.x - f.x) + abs(e.y - f.y) < mm(0.05) for e in ends for f in frontier):
                items.append(t); seen.add(t.m_Uuid.AsString()); nxt += ends
        if not nxt:
            break
        frontier = nxt
    out = []
    for t in items:
        if t.GetClass() == "PCB_VIA":
            c, r = t.GetPosition(), MM(t.GetWidth(pcbnew.F_Cu)) / 2
            cx, cy = cell(MM(c.x), MM(c.y))
            k = int(r / G)
            cand = [(li, cx + dx, cy + dy) for li in range(len(LAYERS)) for dx in range(-k, k + 1) for dy in range(-k, k + 1)]
        elif t.GetLayer() in LAYERS:
            li = LAYERS.index(t.GetLayer())
            a, b = t.GetStart(), t.GetEnd()
            ax, ay, bx, by = MM(a.x), MM(a.y), MM(b.x), MM(b.y)
            n = max(1, int(math.hypot(bx - ax, by - ay) / (G / 2)))
            cand = [(li,) + cell(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n + 1)]
        else:
            continue
        out += [c for c in cand if 0 <= c[1] < NX and 0 <= c[2] < NY
                and copper[c[0]][c[2], c[1]] == net and grid[c[0]][c[2], c[1]] == net]
    return out


def item_cells(desc, x, y, net):
    """True-copper cells (li, cx, cy) of the item DRC reported: the exact pad, or the track / via end at (x, y)."""
    m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[.*?\] of (\S+)", desc)
    out = []
    if m and (m.group(2), m.group(1)) in SEALED_PADS:
        return []
    if m:
        fp = board.FindFootprintByReference(m.group(2))
        pads = [p for p in fp.Pads() if p.GetNumber() == m.group(1)]
        pads.sort(key=lambda p: math.hypot(MM(p.GetPosition().x) - x, MM(p.GetPosition().y) - y))
        p = pads[0]
        bbp = p.GetBoundingBox()
        cx0, cy0 = cell(MM(bbp.GetLeft()), MM(bbp.GetTop()))
        cx1, cy1 = cell(MM(bbp.GetRight()), MM(bbp.GetBottom()))
        for li in pad_layers(p):
            poly = p.GetEffectivePolygon(LAYERS[li], pcbnew.ERROR_INSIDE)
            for X in range(cx0, cx1 + 1):
                for Y in range(cy0, cy1 + 1):
                    if poly.Contains(pcbnew.VECTOR2I(mm(X0 + X * G), mm(Y0 + Y * G))) and grid[li][Y, X] == net:
                        out.append((li, X, Y))
        return out + island_cells(p, net)
    seeds = []
    for t in TRK_BY_NET.get(net, ()):                    # the reported track / via itself, if it is pre-existing
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            if math.hypot(MM(c.x) - x, MM(c.y) - y) < MM(t.GetWidth(pcbnew.F_Cu)) / 2 + 0.05:
                seeds.append(t)
        else:
            a, b = t.GetStart(), t.GetEnd()
            if _seg_pt(MM(a.x), MM(a.y), MM(b.x), MM(b.y), x, y) < MM(t.GetWidth()) / 2 + 0.05:
                seeds.append(t)
    if seeds:
        found = island_cells(None, net, seeds)
        if found:
            return found
    cx, cy = cell(x, y)
    lays = range(len(LAYERS))
    if " on F.Cu" in desc:
        lays = [0]
    elif " on B.Cu" in desc:
        lays = [3]
    elif "In2" in desc:
        lays = [1]
    elif "In3" in desc:
        lays = [2]
    R = int((1.5 if desc.startswith("Zone") else 0.2) / G)
    for li in lays:
        for dx in range(-R, R + 1):
            for dy in range(-R, R + 1):
                X, Y = cx + dx, cy + dy
                if 0 <= X < NX and 0 <= Y < NY and copper[li][Y, X] == net and grid[li][Y, X] == net:
                    out.append((li, X, Y))
    return out


def net_cells(net, x0, y0, x1, y1):
    """True-copper cells of this net inside a window."""
    out = set()
    for li in range(len(LAYERS)):
        sub = (copper[li][y0:y1, x0:x1] == net) & (grid[li][y0:y1, x0:x1] == net)
        ys, xs = np.nonzero(sub)
        out.update((li, x0 + int(a), y0 + int(b)) for a, b in zip(xs, ys))
    return out


STAT = [0]
RIPCOST = 12.0
from scipy import ndimage as _ndi
_DIRS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))


def astar(net, starts, goals, win, wh=1.0, cap=None, gmask=None, gndvia=False, ghost=False):
    """A* over (layer, x, y) inside the window. Free cells, via sites and goals are precomputed as byte masks, the
    open set is keyed by one integer per cell (memory stays bounded by cap). The bend cost uses the direction the
    best path arrived by; a via needs VIA_GAP_PATH steps since the last one."""
    cap = min(cap or NODE_CAP, 6000000)
    x0, y0, x1, y1 = win
    ww, hh = x1 - x0, y1 - y0
    if ww <= 0 or hh <= 0 or not starts or (not goals and gmask is None and not gndvia):
        return None
    A = ww * hh
    fmn = [((g[y0:y1, x0:x1] == EMPTY) | (g[y0:y1, x0:x1] == net)) for g in (FIX["grid"] if ghost else grid)]
    viam = np.logical_and.reduce([((g[y0:y1, x0:x1] == EMPTY) | (g[y0:y1, x0:x1] == net)) for g in (FIX["gridv"] if ghost else gridv)])
    fm = [m.tobytes() for m in fmn]
    vm = viam.tobytes()
    hb = [np.ascontiguousarray(h_[y0:y1, x0:x1]).tobytes() for h_ in hist] if "hist" in globals() else None
    if ghost:                                             # cells / via sites that only a rip-able route blocks: passable at a price
        fa = [((g[y0:y1, x0:x1] == EMPTY) | (g[y0:y1, x0:x1] == net)).tobytes() for g in grid]
        va = np.logical_and.reduce([((g[y0:y1, x0:x1] == EMPTY) | (g[y0:y1, x0:x1] == net)) for g in gridv]).tobytes()
    gp = (viam & GNDPLANE[y0:y1, x0:x1]).tobytes() if gndvia else None
    hbox = None
    if gmask is not None:
        gb = [np.ascontiguousarray(gmask[li][y0:y1, x0:x1]).tobytes() for li in range(len(LAYERS))]
    else:
        gb = [bytearray(A) for _ in LAYERS]
        xs, ys = [], []
        for g_ in goals:
            gx, gy = g_[1] - x0, g_[2] - y0
            if 0 <= gx < ww and 0 <= gy < hh:
                gb[g_[0]][gy * ww + gx] = 1
                xs.append(gx); ys.append(gy)
        if xs:
            hbox = (min(xs), min(ys), max(xs), max(ys))
        elif not gndvia:
            return None
    if hbox:
        bx0, by0, bx1, by1 = hbox

        def h(x, y):
            a = bx0 - x if x < bx0 else (x - bx1 if x > bx1 else 0)
            b = by0 - y if y < by0 else (y - by1 if y > by1 else 0)
            return a + b - 0.586 * (a if a < b else b)
    else:
        def h(x, y):
            return 0.0
    info, openq = {}, []
    for s in starts:
        x, y = s[1] - x0, s[2] - y0
        if 0 <= x < ww and 0 <= y < hh:
            idx = s[0] * A + y * ww + x
            info[idx] = (0.0, -1, -1, VIA_GAP_PATH)
            heapq.heappush(openq, (wh * h(x, y), 0.0, idx))
    seen, goal_idx = 0, None
    push, pop = heapq.heappush, heapq.heappop
    while openq:
        f, gc, idx = pop(openq)
        if idx < 0:
            goal_idx = idx
            break
        rec = info[idx]
        if rec[0] < gc - 1e-9:
            continue
        li, r = divmod(idx, A)
        y, x = divmod(r, ww)
        if gc > 0 and gb[li][r]:
            goal_idx = idx
            break
        seen += 1
        if seen > cap:
            STAT[0] = -seen
            return None
        d0, sv, lc, f_li = rec[2], rec[3], LCOST[li], fm[li]
        sv1 = sv + 1 if sv < VIA_GAP_PATH else sv
        for kk in range(8):
            dx, dy, c = _DIRS[kk]
            if (li == VERT and dx) or (li == HORZ and dy):
                if not RELAXED:
                    continue
                c = c * 2.5
            X, Y = x + dx, y + dy
            if X < 0 or Y < 0 or X >= ww or Y >= hh:
                continue
            r2 = Y * ww + X
            if not f_li[r2]:
                continue
            if dx and dy and not (f_li[y * ww + X] or f_li[Y * ww + x]):
                continue
            nc = gc + c * lc + (BEND if (d0 != -1 and d0 != kk) else 0.0)
            if hb is not None:
                nc += HW * hb[li][r2]
            if ghost and not fa[li][r2]:
                nc += RIPCOST
            ni = li * A + r2
            o = info.get(ni)
            if o is None or nc < o[0]:
                info[ni] = (nc, idx, kk, sv1)
                push(openq, (nc + wh * h(X, Y), nc, ni))
        if sv >= VIA_GAP_PATH and vm[r] and via_spacing_ok(X0 + (x + x0) * G, Y0 + (y + y0) * G, net):
            nc = gc + VIA_COST
            if ghost and not va[r]:
                nc += 3 * RIPCOST
            if gndvia and gp[r]:
                push(openq, (nc, nc, -1 - idx))
            for lj in range(len(LAYERS)):
                if lj != li and fm[lj][r]:
                    ni = lj * A + r
                    o = info.get(ni)
                    if o is None or nc < o[0]:
                        info[ni] = (nc, idx, -1, 0)
                        push(openq, (nc + wh * h(x, y), nc, ni))
    STAT[0] = seen
    if goal_idx is None:
        return None
    path = []
    if goal_idx < 0:
        cur = -1 - goal_idx
        li, r = divmod(cur, A)
        y, x = divmod(r, ww)
        path.append((4, x + x0, y + y0, -1))
    else:
        cur = goal_idx
    while cur != -1:
        li, r = divmod(cur, A)
        y, x = divmod(r, ww)
        path.append((li, x + x0, y + y0, -1))
        cur = info[cur][1]
    return path[::-1]


PADS_BY_NET = {}
for _fp in board.GetFootprints():
    for _q in _fp.Pads():
        if _q.IsOnLayer(pcbnew.F_Cu) and _q.GetShape(pcbnew.F_Cu) in (
                pcbnew.PAD_SHAPE_RECTANGLE, pcbnew.PAD_SHAPE_ROUNDRECT, pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL):
            PADS_BY_NET.setdefault(_q.GetNetCode(), []).append(_q)


VIAS_BY_NET = {}
for _t in board.GetTracks():
    if _t.GetClass() == "PCB_VIA":
        _c = _t.GetPosition()
        VIAS_BY_NET.setdefault(_t.GetNetCode(), []).append((MM(_c.x), MM(_c.y), MM(_t.GetWidth(pcbnew.F_Cu)) / 2))


def snap(pt, n):
    """Centre of the convex F.Cu pad, or of the existing via, of net n that contains a path end, or None (a route
    that stops inside a pad or via ring but off its centre leaves a thin wedge)."""
    for x, y, r in VIAS_BY_NET.get(n, ()):
        if math.hypot(x - pt[0], y - pt[1]) < r + G * 1.2:
            return x, y
    if pt[2] != 0:
        return None
    if copper[0][cell(pt[0], pt[1])[1], cell(pt[0], pt[1])[0]] == MULTI:
        return None
    v = pcbnew.VECTOR2I(mm(pt[0]), mm(pt[1]))
    for q in PADS_BY_NET.get(n, ()):
        if q.HitTest(v, mm(G * 1.2)):                     # grid cells at a rounded corner sit just outside
            c = q.GetPosition()
            return MM(c.x), MM(c.y)
    return None


def emit(net_obj, path, added):
    """Turn a cell path into tracks (merged straight runs) and vias; mark them in the grid. ca / cb: pad centres the
    route finishes on when it ends inside a pad (snap)."""
    n = net_obj.GetNetCode()
    pts = [(X0 + p[1] * G, Y0 + p[2] * G, p[0]) for p in path]
    ca, cb = snap(pts[0], n), snap(pts[-1], n)
    if ca:
        d0 = math.hypot(ca[0] - pts[0][0], ca[1] - pts[0][1])
        if d0 > 0.35:
            pts.insert(0, (ca[0], ca[1], pts[0][2]))
        elif d0 > 0.02 and len(pts) > 1:
            pts[0] = (ca[0], ca[1], pts[0][2])
    if cb:
        d1 = math.hypot(cb[0] - pts[-1][0], cb[1] - pts[-1][1])
        if d1 > 0.35:
            pts.append((cb[0], cb[1], pts[-1][2]))
        elif d1 > 0.02 and len(pts) > 1:
            pts[-1] = (cb[0], cb[1], pts[-1][2])
    i = 0
    while i < len(pts) - 1:
        j = i + 1
        if pts[j][2] != pts[i][2]:                          # layer change: via
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(pts[i][0]), mm(pts[i][1])))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net_obj)
            v.SetRemoveUnconnected(True); v.SetKeepStartEnd(True)
            board.Add(v)
            added.append(v.m_Uuid.AsString())
            if CUR[0] is not None:
                CUR[0].append((v, "V", -1, (pts[i][0], pts[i][1]), (pts[i][0], pts[i][1]), VIA_D / 2))
            add_hole(pts[i][0], pts[i][1], 0.0, n)
            for li in range(len(LAYERS)):
                mark_disc(li, n, pts[i][:2], VIA_D / 2 + grow(n))
                copper[li][cell(*pts[i][:2])[1], cell(*pts[i][:2])[0]] = n
            i = j
            continue
        dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        while j + 1 < len(pts) and pts[j + 1][2] == pts[i][2] and \
                abs((pts[j + 1][0] - pts[j][0]) - dx) < 1e-6 and abs((pts[j + 1][1] - pts[j][1]) - dy) < 1e-6:
            j += 1
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(pts[i][0]), mm(pts[i][1])))
        t.SetEnd(pcbnew.VECTOR2I(mm(pts[j][0]), mm(pts[j][1])))
        t.SetWidth(mm(W)); t.SetLayer(LAYERS[pts[i][2]]); t.SetNet(net_obj)
        board.Add(t)
        added.append(t.m_Uuid.AsString())
        if CUR[0] is not None:
            CUR[0].append((t, "T", pts[i][2], tuple(pts[i][:2]), tuple(pts[j][:2]), W / 2))
        TRK_BY_NET.setdefault(n, []).append(t)
        mark_seg(pts[i][2], n, pts[i][:2], pts[j][:2], W / 2 + grow(n))
        DEST[0] = copper
        mark_seg(pts[i][2], n, pts[i][:2], pts[j][:2], W / 2)
        DEST[0] = grid
        i = j


# ---- fine-pitch pin escapes ---------------------------------------------------------------------------------------
# A pin on a 0.4/0.5 mm-pitch package is boxed in on the grid by its neighbours' clearance halos. Before searching,
# lay a 0.15 mm stub straight out of the package from the pin, checked exactly (pad rectangles, track segments, vias)
# against other nets with 0.15 mm clearance; the search then starts / ends at the open end of the stub.
FINE = re.compile(r"^(U\d+|Q40[12]|Q50[12]|J401|J501|J301|J302)$")
ESC_W, ESC_LEN = min(0.15 if W < 0.25 else 0.2, W), 0.7
NODE_CAP = int(600000 * (0.1 / G) ** 2)


def _seg_pt(ax, ay, bx, by, px, py):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def _seg_rect(a, b, r):
    """Distance from segment a-b to rectangle r (x0, y0, x1, y1); 0 if they touch."""
    for k in range(21):
        x, y = a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            return 0.0
    best = 1e9
    for k in range(21):
        x, y = a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20
        dx = max(r[0] - x, 0, x - r[2])
        dy = max(r[1] - y, 0, y - r[3])
        best = min(best, math.hypot(dx, dy))
    return best


PADRECTS = []
for fp in board.GetFootprints():
    for q in fp.Pads():
        bq = q.GetBoundingBox()
        PADRECTS.append((q.GetNetCode(), pad_layers(q), (MM(bq.GetLeft()), MM(bq.GetTop()), MM(bq.GetRight()),
                                                        MM(bq.GetBottom()))))


WHY = [None]


def exact_clear(a, b, net, li, width, clr=CLR):
    """True if a straight track a-b of this width on routing layer li keeps clr to every other net's pads, tracks, vias
    and hard pours (exact geometry, not the grid)."""
    need = clr + width / 2 + 0.005
    lo = (min(a[0], b[0]) - need - 3, min(a[1], b[1]) - need - 3, max(a[0], b[0]) + need + 3, max(a[1], b[1]) + need + 3)
    for n2, lays, rc in PADRECTS:
        if n2 != net and li in lays and rc[2] > lo[0] and rc[0] < lo[2] and rc[3] > lo[1] and rc[1] < lo[3] and _seg_rect(a, b, rc) < need:
            WHY[0] = ("pad", n2, rc)
            return False
    k = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
    samples = [(a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k) for i in range(k + 1)]
    for t in board.GetTracks():
        if t.GetNetCode() == net:
            continue
        if t.GetClass() == "PCB_VIA":
            v = t.GetPosition()
            vx, vy = MM(v.x), MM(v.y)
            if lo[0] < vx < lo[2] and lo[1] < vy < lo[3] and _seg_pt(a[0], a[1], b[0], b[1], vx, vy) < need + MM(t.GetWidth(pcbnew.F_Cu)) / 2:
                return False
        elif t.GetLayer() == LAYERS[li]:
            s0, s1 = t.GetStart(), t.GetEnd()
            sx0, sy0, sx1, sy1 = MM(s0.x), MM(s0.y), MM(s1.x), MM(s1.y)
            if max(sx0, sx1) < lo[0] or min(sx0, sx1) > lo[2] or max(sy0, sy1) < lo[1] or min(sy0, sy1) > lo[3]:
                continue
            w2 = MM(t.GetWidth()) / 2
            if min(_seg_pt(sx0, sy0, sx1, sy1, px, py) for px, py in samples) < need + w2:
                WHY[0] = ("track", t.GetNetname(), sx0, sy0, sx1, sy1)
                return False
    rr = int(math.ceil((need + 0.1 + 0.05) / G))
    for px, py in samples:
        cx, cy = cell(px, py)
        sub = hz[li][max(cy - rr, 0):cy + rr + 1, max(cx - rr, 0):cx + rr + 1]
        if np.any((sub != EMPTY) & (sub != net)):
            WHY[0] = ("zone", px, py)
            return False
        if not (0 <= cx < NX and 0 <= cy < NY) or outside[cy, cx]:
            WHY[0] = ("outside", px, py)
            return False
    return True


def add_track(net_obj, a, b, li, width, added):
    n = net_obj.GetNetCode()
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    t.SetWidth(mm(width)); t.SetLayer(LAYERS[li]); t.SetNet(net_obj)
    board.Add(t)
    if CUR[0] is not None:
        CUR[0].append((t, "T", li, (a[0], a[1]), (b[0], b[1]), width / 2))
    added.append(t.m_Uuid.AsString())
    TRK_BY_NET.setdefault(n, []).append(t)
    mark_seg(li, n, a, b, width / 2 + grow(n))
    DEST[0] = copper
    mark_seg(li, n, a, b, width / 2)
    DEST[0] = grid
    return t


ESC_HIT = [False]


def escape(desc, x, y, net, added, pre=False):
    """Lay an escape stub from a boxed-in pad; return the stub-end cells, or None. Tries straight out of the package
    (and, for two-pad parts, away from the other pad and sideways) at a few lengths, checked on exact geometry."""
    m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[.*?\] of (\S+)", desc)
    if not m or (m.group(2), m.group(1)) in SEALED_PADS:
        return None
    li = 0 if " on F.Cu" in desc else (3 if " on B.Cu" in desc else None)
    if li is None:
        return None
    fp = board.FindFootprintByReference(m.group(2))
    pads = [q for q in fp.Pads() if q.GetNumber() == m.group(1)]
    pads.sort(key=lambda q: math.hypot(MM(q.GetPosition().x) - x, MM(q.GetPosition().y) - y))
    q = pads[0]
    c, f = q.GetPosition(), fp.GetPosition()
    px, py = MM(c.x), MM(c.y)
    vx, vy = px - MM(f.x), py - MM(f.y)
    bq = q.GetBoundingBox()
    hw, hh = MM(bq.GetWidth()) / 2, MM(bq.GetHeight()) / 2
    if pre and 2 * min(hw, hh) > 0.36:
        return None
    if hw > 1.3 * hh:                                     # a pin leaves along its long axis
        dirs_ = [(1.0 if vx > 0 else -1.0, 0.0)]
    elif hh > 1.3 * hw:
        dirs_ = [(0.0, 1.0 if vy > 0 else -1.0)]
    elif abs(vx) >= abs(vy):
        dirs_ = [(1.0 if vx > 0 else -1.0, 0.0)]
    else:
        dirs_ = [(0.0, 1.0 if vy > 0 else -1.0)]
    if pre:
        pass
    elif not FINE.match(m.group(2)):
        dirs_ += [(d[1], d[0]) for d in dirs_] + [(-d[1], -d[0]) for d in dirs_]
    else:
        dirs_ += [(-dirs_[0][0], -dirs_[0][1])]           # inward: a pin on the exposed pad's net ties straight to it
    ESC_HIT[0] = False
    ew = min(ESC_W, 2 * min(hw, hh))
    net_obj = q.GetNet()
    for d in dirs_:
        for ext in ((0.3, 0.45, 0.6) if pre else (0.45, 0.6, 0.8, 1.0, 1.3, 1.7)):
            L = (hw if d[0] else hh) + ext
            a, b = (px, py), (px + d[0] * L, py + d[1] * L)
            ex, ey = cell(*b)
            inward = FINE.match(m.group(2)) and d is dirs_[-1] and len(dirs_) > 1
            if inward and not (0 <= ex < NX and 0 <= ey < NY and copper[li][ey, ex] == net):
                continue
            if not (0 <= ex < NX and 0 <= ey < NY) or grid[li][ey, ex] not in (net, EMPTY):
                if "debug" in OPT: print("   esc", m.group(2), m.group(1), d, ext, "end cell blocked", grid[li][ey, ex])
                continue
            if not exact_clear(a, b, net, li, ew):
                if "debug" in OPT: print("   esc", m.group(2), m.group(1), d, ext, "exact check failed", WHY)
                break
            b = (X0 + ex * G, Y0 + ey * G)
            ESC_HIT[0] = bool(copper[li][ey, ex] == net) and not (abs(b[0] - px) <= hw and abs(b[1] - py) <= hh)
            t = add_track(net_obj, a, b, li, ew, added)
            STUBS.append(t)
            ALLSTUBS.append((t.m_Uuid.AsString(), t, (px, py)))
            return [(li, ex, ey)]
    return None


added, failed, done = [], [], 0
failkeys = []
STUBS, ALLSTUBS, PRE = [], [], set()
if "nopre" not in OPT:                                    # fan every fine-pitch signal pin out before anything is routed
    for rank, dist, name, A, B in edges[:MAX_EDGES]:
        if name == "GND" or name in PLANE_NETS or board.FindNet(name) is None:
            continue
        for I in (A, B):
            if FINEPIN.search(I[2]) and I[2] not in PRE:
                PRE.add(I[2])
                escape(I[2], I[0], I[1], board.FindNet(name).GetNetCode(), added, pre=True)
    print("fan-out stubs:", len(ALLSTUBS))
FIXEDN = [0]
hist = [np.zeros((NY, NX), dtype=np.uint8) for _ in LAYERS]   # cells routes were pulled from: dearer for everyone afterwards
HINC, HW = int(OPT.get("hinc", 6)), 0.5


def add_hist(items, n):
    for obj, kind, li, a, b, half in items:
        g = half + grow(n)
        w = _xwin(min(a[0], b[0]) - g, min(a[1], b[1]) - g, max(a[0], b[0]) + g, max(a[1], b[1]) + g)
        if not w:
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        LL = dx * dx + dy * dy
        px, py = w[2] - a[0], w[3] - a[1]
        t = np.clip((px * dx + py * dy) / LL, 0.0, 1.0) if LL > 0 else 0.0
        m = (px - t * dx) ** 2 + (py - t * dy) ** 2 <= g * g
        for lj in ([li] if kind == "T" else range(len(LAYERS))):
            reg = hist[lj][w[1]:w[1] + m.shape[0], w[0]:w[0] + m.shape[1]]
            reg[m] = np.minimum(reg[m].astype(np.int32) + HINC, 240).astype(np.uint8)


def snapshot():
    FIX["grid"] = [g.copy() for g in grid]
    FIX["gridv"] = [g.copy() for g in gridv]
    FIX["copper"] = [g.copy() for g in copper]
    FIXEDN[0] += len(ROUTES)
    ROUTES.clear()


def bake(eid):
    """A route that has been pulled too often stays: lay it into the snapshot."""
    R = ROUTES.pop(eid)
    n = R["net"]
    FIXEDN[0] += 1
    for obj, kind, li, a, b, half in R["items"]:
        for lj in ([li] if kind == "T" else range(len(LAYERS))):
            xseg(FIX["grid"], lj, n, a, b, half + grow(n))
            xseg(FIX["gridv"], lj, n, a, b, half + grow(n) + VGROW)
            if kind == "T":
                xseg(FIX["copper"], lj, n, a, b, half)
            else:
                FIX["copper"][lj][cell(*a)[1], cell(*a)[0]] = n


def remark(items, n):
    for obj, kind, li, a, b, half in items:
        if kind == "T":
            mark_seg(li, n, a, b, half + grow(n))
            DEST[0] = copper
            mark_seg(li, n, a, b, half)
            DEST[0] = grid
        else:
            for lj in range(len(LAYERS)):
                mark_disc(lj, n, a, half + grow(n))
                copper[lj][cell(*a)[1], cell(*a)[0]] = n


def rebuild(box):
    """Reset the grids inside box (mm) to the snapshot and lay the remaining routes back in."""
    if not FIX:
        return
    (cx0, cy0), (cx1, cy1) = cell(box[0], box[1]), cell(box[2], box[3])
    cx0, cy0, cx1, cy1 = max(cx0 - 2, 0), max(cy0 - 2, 0), min(cx1 + 3, NX), min(cy1 + 3, NY)
    for li in range(len(LAYERS)):
        grid[li][cy0:cy1, cx0:cx1] = FIX["grid"][li][cy0:cy1, cx0:cx1]
        gridv[li][cy0:cy1, cx0:cx1] = FIX["gridv"][li][cy0:cy1, cx0:cx1]
        copper[li][cy0:cy1, cx0:cx1] = FIX["copper"][li][cy0:cy1, cx0:cx1]
    for R in ROUTES.values():
        near = [it for it in R["items"] if min(it[3][0], it[4][0]) < box[2] + 1.0 and max(it[3][0], it[4][0]) > box[0] - 1.0
                and min(it[3][1], it[4][1]) < box[3] + 1.0 and max(it[3][1], it[4][1]) > box[1] - 1.0]
        if near:
            remark(near, R["net"])


def drop_items(items, n):
    box = [1e9, 1e9, -1e9, -1e9]
    for obj, kind, li, a, b, half in items:
        uid = obj.m_Uuid.AsString()
        board.Remove(obj)
        if uid in added:
            added.remove(uid)
        if kind == "T":
            TRK_BY_NET[n] = [o for o in TRK_BY_NET.get(n, []) if o.m_Uuid.AsString() != uid]
            ALLSTUBS[:] = [s for s in ALLSTUBS if s[0] != uid]
        else:
            key = (int(a[0]), int(a[1]))
            HOLES[key] = [h for h in HOLES.get(key, []) if not (abs(h[0] - a[0]) < 1e-6 and abs(h[1] - a[1]) < 1e-6 and h[3] == n)]
            HOLE_CACHE.clear()
        m = half + grow(n) + VGROW + 0.15
        box = [min(box[0], a[0] - m, b[0] - m), min(box[1], a[1] - m, b[1] - m), max(box[2], a[0] + m, b[0] + m), max(box[3], a[1] + m, b[1] + m)]
    if items:
        rebuild(box)


def unroute(eid):
    R = ROUTES.pop(eid)
    add_hist(R["items"], R["net"])
    drop_items(R["items"], R["net"])


def blockers(path, n):
    """Edge ids of the routes whose copper a ghost path runs into."""
    pts = [(p[0], X0 + p[1] * G, Y0 + p[2] * G) for p in path]
    P = np.array([[x, y] for _, x, y in pts])
    L = np.array([li for li, _, _ in pts])
    isvia = np.zeros(len(pts), bool)
    for i in range(len(pts) - 1):
        if pts[i][0] != pts[i + 1][0]:
            isvia[i] = isvia[i + 1] = True
    out = []
    for eid, R in ROUTES.items():
        if R["net"] == n:
            continue
        extra = 0.1 if R["net"] in hc else 0.0
        hit = False
        for obj, kind, li, a, b, half in R["items"]:
            dx, dy = b[0] - a[0], b[1] - a[1]
            LL = dx * dx + dy * dy
            px, py = P[:, 0] - a[0], P[:, 1] - a[1]
            t = np.clip((px * dx + py * dy) / LL, 0.0, 1.0) if LL > 0 else 0.0
            d = np.hypot(px - t * dx, py - t * dy)
            need = half + CLR + extra + TOLX + 1e-6 + np.where(isvia, VIA_D / 2, W / 2)
            same = isvia | (L == li) if kind == "T" else np.ones(len(pts), bool)
            if np.any((d < need) & same):
                hit = True
                break
        if hit:
            out.append(eid)
    return out


def route_edge(eid, ghost=False):
    """Route one edge; returns True when connected. With ghost: only search, through rip-able routes, and return the path."""
    global STUBS
    rank, dist, name, A, B = edges[eid]
    net_obj = board.FindNet(name)
    if net_obj is None:
        return True
    n = net_obj.GetNetCode()
    ax, ay, ad = A
    bx, by, bd = B
    pad = 6.0 if dist < 10 else (12.0 if dist < 30 else 30.0)
    wx0, wy0 = cell(min(A[0], B[0]) - pad, min(A[1], B[1]) - pad)
    wx1, wy1 = cell(max(A[0], B[0]) + pad, max(A[1], B[1]) + pad)
    win = (max(wx0, 0), max(wy0, 0), min(wx1, NX), min(wy1, NY))
    if ghost:                                             # ends as they would be with the rip-able routes gone
        keep = [grid, copper]
        globals()["grid"], globals()["copper"] = FIX["grid"], FIX["copper"]
    starts = item_cells(ad, A[0], A[1], n)
    goals = item_cells(bd, B[0], B[1], n)
    if ghost:
        globals()["grid"], globals()["copper"] = keep
    CUR[0] = []
    STUBS = []
    ma, mb = re.match(r"(?:PTH )?[Pp]ad \S+ \[.*?\] of (\S+)", ad), re.match(r"(?:PTH )?[Pp]ad \S+ \[.*?\] of (\S+)", bd)
    onF = lambda d_: (" on F.Cu" in d_ or "PTH" in d_)
    if not ghost and ma and mb and dist < 2.2 and onF(ad) and onF(bd) and (ma.group(1), "x") not in SEALED_PADS \
            and not any((mm_.group(1), re.match(r"(?:PTH )?[Pp]ad (\S+)", dd).group(1)) in SEALED_PADS for mm_, dd in ((ma, ad), (mb, bd))):
        wd = 0.25 if ma.group(1) == mb.group(1) else min(W, 0.2)
        for wtry in (wd, 0.15):
            if exact_clear((A[0], A[1]), (B[0], B[1]), n, 0, wtry):
                add_track(net_obj, (A[0], A[1]), (B[0], B[1]), 0, wtry, added)
                ROUTES[eid] = dict(net=n, items=CUR[0], rips=ROUTES.get(eid, {}).get("rips", 0))
                CUR[0] = None
                return True
    gmask, gndvia = None, False
    if name == "GND":
        goals, gndvia = [], True
    elif name in PLANE_NETS or bd.startswith("Zone") or not goals:
        gsrc = FIX["grid"] if ghost else grid
        gm = [(zc[li] == n) & ((gsrc[li] == n) | (gsrc[li] == EMPTY)) for li in range(len(LAYERS))]
        if any(g[win[1]:win[3], win[0]:win[2]].any() for g in gm):
            goals, gmask = [], gm
    WH, CAP = (1.15, NODE_CAP) if dist < 15 else ((1.4, 2 * NODE_CAP) if dist < 30 else (1.7, 4 * NODE_CAP))
    path = astar(n, starts, goals, win, WH, CAP, gmask, gndvia, ghost)
    if ghost:
        CUR[0] = None
        return path
    if path is None:                                      # retry from / to escape stubs on fine-pitch pins
        ea = escape(ad, A[0], A[1], n, added)
        if ea and ESC_HIT[0]:
            ROUTES[eid] = dict(net=n, items=CUR[0], rips=0)
            CUR[0] = None
            return True
        eb = None if (gndvia or gmask is not None) else escape(bd, B[0], B[1], n, added)
        if ea or eb:
            path = astar(n, ea or starts, eb or goals, win, WH, CAP, gmask, gndvia)
    if path is None:
        items, CUR[0] = CUR[0], None
        drop_items(items, n)                              # escape stubs of the failed try
        FAILINFO[eid] = "%s %.2f,%.2f (%s) -> %.2f,%.2f (%s) starts %d goals %d seen %d" % (name, A[0], A[1], ad.split("[")[0] + ad.split("]")[-1][:9], B[0], B[1], bd.split("[")[0] + bd.split("]")[-1][:9], len(starts), len(goals), STAT[0])
        return False
    emit(net_obj, path, added)
    ROUTES[eid] = dict(net=n, items=CUR[0], rips=0)
    CUR[0] = None
    FAILINFO.pop(eid, None)
    return True


from collections import deque
FAILINFO, RIPS = {}, {}
RIP_BUDGET = [int(OPT.get("rips", 600))]
RIPTIME = float(OPT.get("riptime", 1500))                 # seconds of rip-up work at most
MAXRIP = int(OPT.get("maxrip", 4))                        # times one route may be pulled before it stays
import time
edges = edges[:MAX_EDGES]
queue = deque(range(len(edges)))
nrip, nstep, t_rip = 0, 0, 0.0
while queue:
    eid = queue.popleft()
    rank = edges[eid][0]
    nstep += 1
    if nstep % 40 == 0:
        print("  progress: step %d, queue %d, routed %d, failing %d, pulled %d" % (nstep, len(queue), FIXEDN[0] + len(ROUTES), len(FAILINFO), nrip), flush=True)
    if rank > 1 and not FIX:
        snapshot()                                        # Kelvin, gate drive and fan-out stubs are never pulled
    if route_edge(eid):
        FAILINFO.pop(eid, None)
        continue
    if not FIX or RIP_BUDGET[0] <= 0 or t_rip > RIPTIME or "norip" in OPT:
        continue
    t0 = time.time()
    n_e = board.FindNet(edges[eid][2]).GetNetCode()
    gp, bl = None, []
    for attempt in range(3):
        gp = route_edge(eid, ghost=True)
        if gp is None:
            break
        bl = blockers(gp, n_e)
        frozen = [b for b in bl if RIPS.get(b, 0) >= MAXRIP]
        if not frozen:
            break
        for b in frozen:
            bake(b)
        gp = None
    if gp is not None and bl:
        RIP_BUDGET[0] -= 1
        nrip += len(bl)
        for b in bl:
            RIPS[b] = RIPS.get(b, 0) + 1
            unroute(b)
        ok = route_edge(eid)
        if ok:
            FAILINFO.pop(eid, None)
        for b in reversed(bl):
            queue.appendleft(b)
        if "debug" in OPT:
            print("  rip", edges[eid][2], "pulled", [edges[b][2] for b in bl], "->", ok, flush=True)
    t_rip += time.time() - t0
done = FIXEDN[0] + len(ROUTES)
for eid in sorted(FAILINFO):
    name, ad = edges[eid][2], edges[eid][3][2]
    failed.append(FAILINFO[eid])
    failkeys.append(name + "@" + ad if (name == "GND" or name in PLANE_NETS) else name)
print("routes pulled and re-laid:", nrip)


# ---- GND vias: one in or next to every GND pad, then a stitching grid between the outer fills and the planes -----------
def gnd_via_ok(x, y):
    if not (VIA_EXTRA <= x < NX - VIA_EXTRA and VIA_EXTRA <= y < NY - VIA_EXTRA) or not GNDPLANE[y, x]:
        return False
    for li in range(len(LAYERS)):
        if gridv[li][y, x] not in (EMPTY, gnd):
            return False
    return via_spacing_ok(X0 + x * G, Y0 + y * G, gnd)


def put_gnd_via(x, y):
    px, py = X0 + x * G, Y0 + y * G
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(mm(px), mm(py)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(board.FindNet("GND"))
    v.SetRemoveUnconnected(True); v.SetKeepStartEnd(True)
    board.Add(v)
    add_hole(px, py, 0.0, gnd)
    for li in range(len(LAYERS)):
        mark_disc(li, gnd, (px, py), VIA_D / 2 + grow(gnd))
    return px, py


if "stitch" in OPT:
    VIA_MIN_SAME, VIA_MIN_OTHER = 0.8, 0.95
    HOLE_CACHE.clear()
    gv = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd]
    npad = nin = nnear = nmiss = 0
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() != gnd or p.HasHole():
                continue
            li = 0 if p.IsOnLayer(pcbnew.F_Cu) else 3
            c = p.GetPosition(); px, py = MM(c.x), MM(c.y)
            bq = p.GetBoundingBox(); w, h = MM(bq.GetWidth()), MM(bq.GetHeight())
            npad += 1
            if any(abs(vx - px) < w / 2 + 0.9 and abs(vy - py) < h / 2 + 0.9 for vx, vy in gv):
                continue
            cx, cy = cell(px, py)
            R = int((max(w, h) / 2 + 1.3) / G)
            cand = sorted(((dx * dx + dy * dy, dx, dy) for dx in range(-R, R + 1) for dy in range(-R, R + 1)))
            done_ = False
            for d2, dx, dy in cand:
                X, Y = cx + dx, cy + dy
                inpad = abs(dx * G) <= w / 2 - 0.2 and abs(dy * G) <= h / 2 - 0.2
                if not inpad and min(w, h) >= 0.5 and d2 < 4:
                    continue
                if not gnd_via_ok(X, Y):
                    continue
                if not inpad:
                    # needs a clear straight F/B run back to the pad
                    k = max(2, int(math.sqrt(d2) * 2)); clear = True
                    for i in range(k + 1):
                        gx, gy = cx + dx * i // k, cy + dy * i // k
                        if grid[li][gy, gx] not in (gnd, EMPTY):
                            clear = False; break
                    if not clear:
                        continue
                vx, vy = put_gnd_via(X, Y); gv.append((vx, vy))
                if not inpad:
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(mm(px), mm(py))); t.SetEnd(pcbnew.VECTOR2I(mm(vx), mm(vy)))
                    t.SetWidth(mm(0.25)); t.SetLayer(LAYERS[li]); t.SetNet(board.FindNet("GND")); board.Add(t)
                    mark_seg(li, gnd, (px, py), (vx, vy), 0.125 + grow(gnd))
                    nnear += 1
                else:
                    nin += 1
                done_ = True
                break
            if not done_:
                nmiss += 1
    print("GND pads %d: in-pad vias %d, adjacent vias %d, no room %d" % (npad, nin, nnear, nmiss))
    ngrid = 0
    step = int(float(OPT.get("pitch", 2.5)) / G)
    for Y in range(step // 2, NY, step):
        for X in range(step // 2 + (step // 2 if (Y // step) % 2 else 0), NX, step):
            if (zc[0][Y, X] == gnd or zc[3][Y, X] == gnd) and gnd_via_ok(X, Y):
                px, py = X0 + X * G, Y0 + Y * G
                if all(math.hypot(vx - px, vy - py) > 1.5 for vx, vy in gv):
                    gv.append(put_gnd_via(X, Y)); ngrid += 1
    print("stitching vias on the grid:", ngrid)

# fan-out stubs: drop the unused ones, cut the others back to the last junction
_pts = {}
for o in board.GetTracks():
    if o.GetClass() == "PCB_VIA":
        _pts.setdefault(o.GetNetCode(), []).append((MM(o.GetPosition().x), MM(o.GetPosition().y), o.m_Uuid.AsString()))
    else:
        for e in (o.GetStart(), o.GetEnd()):
            _pts.setdefault(o.GetNetCode(), []).append((MM(e.x), MM(e.y), o.m_Uuid.AsString()))
nrem = ntrim = 0
for uid, t, pc in ALLSTUBS:
    a, b = t.GetStart(), t.GetEnd()
    ax, ay, bx, by = MM(a.x), MM(a.y), MM(b.x), MM(b.y)
    L = math.hypot(bx - ax, by - ay)
    tmax = -1.0
    for x, y, u in _pts.get(t.GetNetCode(), ()):
        if u != uid and _seg_pt(ax, ay, bx, by, x, y) < 0.04:
            tt = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (L * L)
            if tt * L > 0.2:
                tmax = max(tmax, min(tt, 1.0))
    if tmax < 0:
        board.Remove(t); nrem += 1
    elif tmax < 0.97:
        t.SetEnd(pcbnew.VECTOR2I(mm(ax + (bx - ax) * tmax), mm(ay + (by - ay) * tmax))); ntrim += 1
print("fan-out stubs unused (removed) %d, trimmed %d" % (nrem, ntrim))
board.BuildConnectivity()
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.BuildConnectivity()
print("unconnected after fill:", board.GetConnectivity().GetUnconnectedCount(False))
board.Save(OUT)
if "dump" in OPT:
    for i, wtxt in enumerate(OPT["dump"].split(";")):
        a_, b_, c_, d_ = [float(v) for v in wtxt.split(",")]
        (cx0, cy0), (cx1, cy1) = cell(a_, b_), cell(c_, d_)
        np.savez_compressed(OUT + ".dump%d.npz" % i, grid=np.array([g[cy0:cy1, cx0:cx1] for g in grid]), gridv=np.array([g[cy0:cy1, cx0:cx1] for g in gridv]),
                            copper=np.array([g[cy0:cy1, cx0:cx1] for g in copper]), box=np.array([X0 + cx0 * G, Y0 + cy0 * G, G]),
                            nets=np.array([[str(k), v.GetNetCode()] for k, v in board.GetNetsByName().items()]))
print("routed %d edges, %d failed, items added %d" % (done, len(failed), len(added)))
for f in failed:
    print("  FAILED", f)
for k in failkeys:
    print("FAILKEY", k)
