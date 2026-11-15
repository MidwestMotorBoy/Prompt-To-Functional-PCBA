"""cpd.py: power-path pre-placement for cplace.py (team C integration). HOOKS=cpd,cpower,cpdl,ccorr  (cpd FIRST)

Why: on every cpower run (and on the hand board) the copper planner left PP5V and/or PPHV open at the PD chips
U401/U501, and on seeds where Q101 found no room after the stages the cell path opened (FET_MID, CELL_P_RAW).
The PD chip (TPS25751) has, going clockwise round the body, PP5V (34), VBUS (32), VBUS (23), PPHV (20).
plan_copper draws each net on F.Cu, one after another, so the three destinations must sit round the chip in the same
clockwise order: 5 V buck output -> USB-C connector -> charger input. Logan's floorplan box of the port 1 5 V buck lies
EAST of U401 while the connector is north and the charger south, i.e. in the wrong arc: the PP5V copper must cross
VBUS whatever the chip's pose (the order round a chip does not change with rotation). Port 2's box (west) is right.

What it does:
  setup        PD_BUCK1="x0,y0,x1,y1" / PD_BUCK2: replaces the section box of that port's 5 V buck section (cpower
               places the buck, inductor and caps in it). PD_BOX1 / PD_BOX2: the window box of U401 / U501.
               Empty = Logan's floorplan boxes. run_merged.sh sets PD_BUCK1=97,74,105,88 PD_BOX1=106,75,118,90
               (port 1 buck WEST of its PD chip, the chip moved east into the charger-programming box).
  pre_place    CELL_FIRST=1: the cell path chain (CELL_CHAIN, default F102:CELL_P_RAW,Q101:CELL_P,Q102:FET_MID) is
               placed and locked part by part next to the placed pads of the named net (CELL_W per mm).
               PD_FIRST=1: then U401/U501 are placed in their window box grown by PD_WIN mm by ctx.place() (wiring +
               near + every hook's extra_cost, so the topology cost below) and locked, before cpower's stages.
  extra_cost   for U401/U501: each power pin's path is modelled as pin -> 1 mm out along the pad's outward normal ->
               the placed pads of its net (VBUS: the connector; PP5V: the buck output; PPHV: the sense resistor or
               the stage), or, before those exist, the centre of the buck / stage section box. PDW_X per crossing
               between two nets' paths or of a path with the chip's pad box, PDW_B per mm a destination lies behind
               its pin (the copper must wrap round the chip).
  cpdl.py      (listed after cpower) PD_RIN=1: the stage's input sense resistor (draw rin: R424/R524, PPHV -> AC_SNS_N)
               is taken off the stage and put next to the PD chip's PPHV pin (as on the hand board), PD_RIN_W per mm
               from its PPHV pad to the pin + 2 per mm from its other pad to the stage copper. Then the PPHV copper is
               a few mm long and the long run is AC_SNS_N, which plan_copper draws first; cpower put the resistor at
               the stage, where the stage's AC_SNS_N pour walled the PPHV path in on every run.
Knobs: PDW_X=80, PDW_B=8, PD_BUCK1, PD_BUCK2, PD_BOX1, PD_BOX2, PD_FIRST=1, PD_WIN=4, PD_RIN=1, PD_RIN_W=20, PD_RIN_W2=2,
       CELL_FIRST=1, CELL_CHAIN, CELL_W=10, CPD_DEBUG. Off unless cpd is in HOOKS.
"""
import os
import numpy as np

PDW_X = float(os.environ.get("PDW_X", 80.0))
PDW_B = float(os.environ.get("PDW_B", 8.0))
PD = {"U401": "USB Port 1", "U501": "USB Port 2"}
CONN = {"U401": "J401", "U501": "J501"}
NETS = ("PP5V", "VBUS", "PPHV")


def _box(s):
    v = [float(t) for t in s.split(",")]
    return v if len(v) == 4 else None


def setup(ctx):
    for i, port in ((1, "USB Port 1"), (2, "USB Port 2")):
        b = os.environ.get(f"PD_BUCK{i}", "")
        if not b: continue
        bx = _box(b); n = 0
        for r, sec in ctx.fill.items():
            if sec.startswith(port) and "5 V buck" in sec: ctx.boxof[r] = bx; n += 1
        print(f"[cpd] port {i} 5 V buck section box -> {bx} ({n} parts)", flush=True)
    for i, r in ((1, "U401"), (2, "U501")):
        b = os.environ.get(f"PD_BOX{i}", "")
        if b and r in ctx.fill: ctx.boxof[r] = _box(b); print(f"[cpd] {r} window box -> {ctx.boxof[r]}", flush=True)
    ctx.cpd = {}; ctx.cpd_core = {}
    for r in PD:
        if r not in ctx.lp: continue
        L = ctx.lp[r]; ctx.cpd_core[r] = (min(v[0] for v in L), min(v[1] for v in L), max(v[0] for v in L), max(v[1] for v in L))
        b = ctx.bbx[ctx.ri[r]]; cx = (b[0] + b[2]) / 2; cy = (b[1] + b[3]) / 2; hw = (b[2] - b[0]) / 2; hh = (b[3] - b[1]) / 2
        pins = []
        for j, (lx, ly, n, num) in enumerate(ctx.lp[r]):
            tag = next((t for t in NETS if n and n.endswith("/" + t)), None)
            if not tag: continue
            dx = (lx - cx) / hw; dy = (ly - cy) / hh          # outward normal: the body edge the pad is nearest to
            nrm = (np.sign(dx), 0.0) if abs(dx) >= abs(dy) else (0.0, np.sign(dy))
            pins.append((j, n, tag, nrm))
        ctx.cpd[r] = pins


def _rin(ctx, r):
    """the stage's input sense resistor with a pad on this PD chip's PPHV net (constraints draw[*].rin)"""
    import json
    if not hasattr(ctx, "_draw"):
        ctx._draw = json.load(open(ctx.env["CONSTRAINTS"])).get("draw", {})
    pphv = next((n for _, n, t, _ in ctx.cpd.get(r, []) if t == "PPHV"), None)
    for v in ctx._draw.values():
        q = v.get("rin")
        if q and q in ctx.lp and any(p[2] == pphv for p in ctx.lp[q]): return q, pphv
    return None, pphv


def _pads_of(ctx, q, n):
    return [j for j, v in enumerate(ctx.lp[q]) if v[2] == n]


def place_chain(ctx):
    """CELL_CHAIN="F102:CELL_P_RAW,Q101:CELL_P,Q102:FET_MID": each part in turn is placed in its section box (+4 mm)
    with CELL_W x mm from its pads on the named net to the placed pads of that net, then locked. The cell path is a
    10 A, two-terminal chain: on cpower runs Q101 found no room after the stages and landed 40 mm away (FET_MID open)."""
    spec = os.environ.get("CELL_CHAIN", "F102:CELL_P_RAW,Q101:CELL_P,Q102:FET_MID"); W = float(os.environ.get("CELL_W", 10.0))
    for item in [t for t in spec.split(",") if t]:
        q, net = item.split(":"); n = next((m for m in ctx.netpads if m.endswith("/" + net) or m == net), None)
        if q not in ctx.fill or q in ctx.P or n is None: continue
        tg = [ctx.pad_xy(o, j) for o in set(ctx.netpads[n]) if o in ctx.P and o != q for j in _pads_of(ctx, o, n)]
        if not tg: continue
        def ex(r_, k, xs, ys, tg=tg, n=n):
            X = xs[None, :]; Y = ys[:, None]; c = 0.0
            for v in ctx.lp[r_]:
                if v[2] != n: continue
                ox, oy = ctx.rotv(v[0], v[1], k); c = c + W * np.min([np.hypot(X + ox - a, Y + oy - b) for a, b in tg], axis=0)
            return c
        bx = ctx.boxof.get(q) or ctx.box; win = (bx[0] - 4, bx[1] - 4, bx[2] + 4, bx[3] + 4)
        b = ctx.place(q, win, 0.25, extra=ex) or ctx.place(q, ctx.box, 0.25, extra=ex)
        if b is None: print(f"[cpd] chain {q}: no spot", flush=True); continue
        ctx.put(q, b); ctx.LOCK.add(q); print(f"[cpd] chain {q} ({net}) at {b[1]:.2f},{b[2]:.2f} k{b[3]}", flush=True)


def pre_place(ctx):
    """cpd's own pre_place: cell chain, then the PD chips (HOOKS=cpd,cpower,cpdl,...: chips before the stages; or
    HOOKS=cpower,cpd,...: after them). The sense-resistor move (PD_RIN) is done by place_rin(), called from here when
    the stages are already placed, else by cpdl.py (a one-line module listed after cpower)."""
    if os.environ.get("CELL_FIRST", "1") == "1": place_chain(ctx)
    if os.environ.get("PD_FIRST", "1") != "1": return
    g = float(os.environ.get("PD_WIN", 4.0))
    for r in PD:
        if r not in ctx.fill or r in ctx.P: continue
        bx = ctx.boxof.get(r) or ctx.box; win = (bx[0] - g, bx[1] - g, bx[2] + g, bx[3] + g)
        best = ctx.place(r, win, 0.25)
        if best is None and os.environ.get("CPD_DEBUG"):
            xs = np.arange(win[0], win[2], 0.25); ys = np.arange(win[1], win[3], 0.25)
            big = [(q, [round(t, 1) for t in o]) for q, L in ctx.OB.items() for (s_, o, kk) in L if kk == "b" and (o[2] - o[0]) * (o[3] - o[1]) > 60]
            big += [("obs", [round(t, 1) for t in o]) for o in ctx.all_obs(ctx.sideF[r], "b") if (o[2] - o[0]) * (o[3] - o[1]) > 60][:30]
            b0 = ctx.rbox(ctx.bbx[ctx.ri[r]], 0); cov = []
            for o in list(ctx.all_obs(ctx.sideF[r], "b")) + [o for s2, o, n in ctx.KEEPB if s2 == ctx.sideF[r]]:
                ix = max(0, min(win[2], o[2] - b0[0]) - max(win[0], o[0] - b0[2])); iy = max(0, min(win[3], o[3] - b0[1]) - max(win[1], o[1] - b0[3]))
                cov.append((round(ix * iy, 1), [round(float(t), 1) for t in o]))
            print("[cpd] side", ctx.sideF[r], "body", [round(t, 2) for t in b0], "top coverage:", sorted(cov, reverse=True)[:8], flush=True)
            print("[cpd] placed in window:", sorted((q, tuple(round(t, 1) for t in ctx.P[q])) for q in ctx.P if win[0] < ctx.P[q][0] < win[2] and win[1] < ctx.P[q][1] < win[3]))
            print(f"[cpd] {r} window {win}: legal per turn", [int(ctx.legal_mask(r, k, xs, ys).sum()) for k in range(4)],
                  "extra_illegal", [[int(b.sum()) for b in ctx_hook_ill(ctx, r, k, xs, ys)] for k in range(4)], flush=True)
        if best is None: best = ctx.place(r, ctx.box, 0.25)
        if best is None: print(f"[cpd] {r}: no legal spot, left to the main loop", flush=True); continue
        ctx.put(r, best); ctx.LOCK.add(r)
        print(f"[cpd] {r} placed first at {best[1]:.2f},{best[2]:.2f} k{best[3]} cost {best[0]:.0f}", flush=True)
    if any(_rin(ctx, r)[0] in ctx.P for r in PD if r in ctx.P): place_rin(ctx)


def place_rin(ctx):
    if os.environ.get("PD_RIN", "1") != "1" or getattr(ctx, "cpd_rin_done", False): return
    ctx.cpd_rin_done = True; W_PP = float(os.environ.get("PD_RIN_W", 20.0)); W_2 = float(os.environ.get("PD_RIN_W2", 2.0))
    for r in PD:
        if r not in ctx.P: continue
        rin, pphv = _rin(ctx, r)
        if not rin: continue
        if rin in ctx.P:                             # take the stage's sense resistor off: it goes next to the PD chip
            ctx.P.pop(rin); ctx.OB.pop(rin, None); ctx.LOCK.discard(rin)
        jp = _pads_of(ctx, r, pphv)[0]; px, py = ctx.pad_xy(r, jp)
        other = next(v[2] for v in ctx.lp[rin] if v[2] != pphv)
        tg = [ctx.pad_xy(o, j) for o in set(ctx.netpads[other]) if o in ctx.P and o != rin for j in _pads_of(ctx, o, other)]
        def ex(q, k, xs, ys, px=px, py=py, tg=tg, other=other, pphv=pphv):
            X = xs[None, :]; Y = ys[:, None]; c = 0.0
            for j, v in enumerate(ctx.lp[q]):
                ox, oy = ctx.rotv(v[0], v[1], k)
                if v[2] == pphv: c = c + W_PP * np.hypot(X + ox - px, Y + oy - py)
                elif v[2] == other and tg: c = c + W_2 * np.min([np.hypot(X + ox - a, Y + oy - b) for a, b in tg], axis=0)
            return c
        w2 = (px - 10, py - 10, px + 10, py + 10)
        b2 = ctx.place(rin, w2, 0.1, extra=ex)
        if b2 is None: b2 = ctx.place(rin, (px - 20, py - 20, px + 20, py + 20), 0.2, extra=ex)
        if b2 is None: print(f"[cpd] {rin}: no spot near {r}; left to the main loop", flush=True); continue
        ctx.put(rin, b2); ctx.LOCK.add(rin)
        print(f"[cpd] {rin} (PPHV sense) next to {r} at {b2[1]:.2f},{b2[2]:.2f} k{b2[3]}", flush=True)


def _sec_centre(ctx, port, key, layer):
    for r, sec in ctx.fill.items():
        if sec.startswith(port) and key in sec and (layer is None or sec.endswith(layer)):
            b = ctx.boxof.get(r)
            if b: return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return None


def ctx_hook_ill(ctx, r, k, xs, ys):
    import sys
    out = []
    for m in os.environ.get("HOOKS", "").split(","):
        mod = sys.modules.get(m)
        if mod is not None and hasattr(mod, "extra_illegal"):
            b = mod.extra_illegal(ctx, r, k, xs, ys)
            if b is not None: out.append(np.asarray(b))
    return out


def _targets(ctx, r, n):
    pts = []
    for o in set(ctx.netpads[n]):
        if o == r or o not in ctx.P: continue
        if n.endswith("/VBUS") and o != CONN[r]: continue      # VBUS goes to the connector
        for j, v in enumerate(ctx.lp[o]):
            if v[2] == n: pts.append(ctx.pad_xy(o, j))
    if not pts and n.endswith("/PPHV"):                     # sense resistor not placed yet: aim at the stage input copper
        t = _targets(ctx, r, n[:-4] + "AC_SNS_N") if not n.endswith("AC_SNS_N") else None
        if t is not None: return t
        return _sec_centre(ctx, PD[r], "Four-switch power stage", "F.Cu")
    if not pts and n.endswith("/AC_SNS_N"): return None
    if not pts and n.endswith("/PP5V"):                     # buck not placed yet: aim at its section box
        return _sec_centre(ctx, PD[r], "5 V buck", None)
    if not pts: return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _cr(ux, uy, vx, vy): return ux * vy - uy * vx


def _xing(a, b, c, d):
    """segments a-b and c-d (each point a pair of arrays or floats) properly intersect -> bool array"""
    d1 = _cr(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]); d2 = _cr(b[0] - a[0], b[1] - a[1], d[0] - a[0], d[1] - a[1])
    d3 = _cr(d[0] - c[0], d[1] - c[1], a[0] - c[0], a[1] - c[1]); d4 = _cr(d[0] - c[0], d[1] - c[1], b[0] - c[0], b[1] - c[1])
    return (d1 * d2 < 0) & (d3 * d4 < 0)


def extra_cost(ctx, r, k, xs, ys):
    if r not in getattr(ctx, "cpd", {}): return 0.0
    X = xs[None, :]; Y = ys[:, None]; paths = []; cost = np.zeros((len(ys), len(xs)))
    b = ctx.rbox(ctx.cpd_core[r], k); sh = 0.3                        # box of the pad centres, shrunk a little
    bc = [(b[0] + sh, b[1] + sh), (b[2] - sh, b[1] + sh), (b[2] - sh, b[3] - sh), (b[0] + sh, b[3] - sh)]
    for j, n, tag, nrm in ctx.cpd[r]:
        T = _targets(ctx, r, n)
        if T is None: continue
        lx, ly = ctx.lp[r][j][0], ctx.lp[r][j][1]
        ox, oy = ctx.rotv(lx, ly, k); nx, ny = ctx.rotv(nrm[0], nrm[1], k)
        p0 = (X + ox, Y + oy); p1 = (X + ox + nx, Y + oy + ny)
        behind = -((T[0] - p0[0]) * nx + (T[1] - p0[1]) * ny)
        cost = cost + PDW_B * np.maximum(0.0, behind)
        paths.append((n, [p0, p1, (T[0] + 0 * X, T[1] + 0 * Y)]))
        # the straight run from 1 mm out to the destination must not cut through the chip body (copper wraps round it)
        hit = np.zeros(cost.shape, bool)
        for e0, e1 in ((0, 1), (1, 2), (2, 3), (3, 0)):
            hit |= _xing(p1, (T[0] + 0 * X, T[1] + 0 * Y), (X + bc[e0][0], Y + bc[e0][1]), (X + bc[e1][0], Y + bc[e1][1]))
        cost = cost + PDW_X * hit
    for a in range(len(paths)):
        for b in range(a + 1, len(paths)):
            if paths[a][0] == paths[b][0]: continue
            A = paths[a][1]; B = paths[b][1]; hit = np.zeros(cost.shape, bool)
            for i in range(2):
                for m in range(2): hit |= _xing(A[i], A[i + 1], B[m], B[m + 1])
            cost = cost + PDW_X * hit
    return cost


def post_place(ctx):
    for r in getattr(ctx, "cpd", {}):
        if r not in ctx.P: continue
        x, y, k = ctx.P[r]
        c = float(np.asarray(extra_cost(ctx, r, k, np.array([x]), np.array([y]))).reshape(-1)[0])
        print(f"[cpd] {r} at {x:.2f},{y:.2f} k{k}: topology cost {c:.1f}", flush=True)
