"""cpower.py: package power, hook module for cplace.py (HOOKS=cpower,...).
Every power stage is built and LOCKED in pre_place, before any signal part, by rule from constraints.json, with no
board coordinates in the code:

  hot_loops  {name: caps (first = high-frequency one), supply, ret, switch_pins}
  pin_pads   pin name -> pad numbers (Q401.D1 -> 2,3,4)
  draw       per stage: kind bridge4 (switch, q_out, inductor, cin, cout, rin, rout) or buck (switch IC, inductor,
             cin, cout, boot, bst pin name)

setup: the switch parts get their true courtyard as body (the shared bodies add 0.5 mm escape room round every part
with 12+ pads, which keeps a hot-loop capacitor 0.5 mm further from a power FET than the courtyard rule needs);
restore_body() gives the escape room back afterwards on every side the stage left free.

Hot-loop capacitor (place_loop_cap): the shared search ctx.place() with an extra cost
  W_LOOP x (copper distance supply pad -> switch supply pads + return pad -> switch return pads)
  + W_AREA x distance to the switch's hot pins + W_ALIGN x turn against the loop axis + W_BOX outside its section box,
  and a hard rule (1e5): every supply pad on the supply side of the switch's supply/return mid line and every return
  pad on the return side (SEP_M). Copper distances are geodesic fields (Dijkstra on a 0.1 mm raster) on the stage
  layer, around other nets' pads + 0.2 mm. Later capacitors of a loop may close through the earlier ones.
  Why the separation rule: plan_copper.py step 2 draws one hull over the loop's supply pads and one over its return
  pads (or pairs to the nearest switch pad); a bulk capacitor turned the other way cut the first capacitor's supply
  off (measured: Port 1 HL_OUT open, 6 of 7).
bridge4 (one function for both ports): each switch (draw key, then q_out) is tried at the 6 best legal poses per turn
  round its fixed inductor's pad of the switch-node net (pre-filter: pad-to-pad gap + section box); per pose all its
  loop capacitors are placed for real (trial_loop: first + W_BULK x bulk), then the switch node (geodesic SW pad ->
  inductor pad, obstacles grown for a 0.6 mm path) and the gate pins' escape are measured; the cheapest pose is kept
  (seed noise CP_NOISE among near-equal ones). Then the loop capacitors, the sense resistors rin/rout (pad of the
  stage net at the stage copper, no box term), and the rest of cin/cout (C424/C427) at the stage copper.
buck (one function for U404, U504, U204): IC poses in its section box; per pose the loop capacitors and the inductor
  (SW pad at the IC's SW pin) are placed for real; the cheapest kept; then boot capacitor (BST + SW pins), output
  capacitors (at the inductor's output pad, return toward the IC ground), other cin.
Protection (protect_loop, reserve_gap): 2 via sites beside every loop capacitor's return pad and 3 beside the switch's
  return pads (0.9 mm squares, both sides, 0.2 mm clear of other nets' pads, as plan_copper places return vias),
  the first capacitor + switch-pin box (stage side) and the straight gap switch SW pad -> inductor pad (stage side)
  become obstacles. Every part placed here goes into ctx.LOCK.
Env: CP_STEP (cap search grid, 0.05), CP_NQ (switch candidates per turn, 6), CP_NB (buck IC candidates per turn, 6),
CP_NOISE (mm-equivalent noise on the candidate choice when SEED is set, 0.3), CP_LOG=1 prints every step.
Run time: about 35 s on top of the base 10 s."""
import json, math, zlib, os
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy import ndimage

CLR = 0.2          # copper clearance to other nets (the board rules, and plan_copper's clearance)
VIA_R = 0.225      # 0.45 mm via
RES = 0.1          # field raster, mm
BIG = 50.0         # field value for "no path"
W_LOOP = 60.0      # cost per mm of loop copper path (dominates wiring and near terms of the base cost)
W_AREA = 8.0       # cost per mm from the capacitor centre to the switch's hot pins
W_ALIGN = 20.0     # capacitor turned against the loop direction (supply pad must face the supply pins)
W_SW = 10.0        # switch node path, per mm
W_GATE = 3.0       # gate pin escape path, per mm
W_BOX = 30.0       # cost per mm a stage part's body sticks out of its own floorplan section box (+ BOX_M)
BOX_M = 0.5
SEP_M = 0.1        # pad edge past the switch's supply/return mid line, mm
W_HOME = 0.5       # buck IC distance from its section box centre, per mm

S = {}             # module state


def log(*a):
    if S.get("log"): print("[cpower]", *a, flush=True)


def bare(n): return (n or "").lstrip("/")


def setup(ctx):
    C = json.load(open(ctx.env["CONSTRAINTS"]))
    S.update(C=C, log=ctx.env.get("CP_LOG") == "1", step=float(ctx.env.get("CP_STEP", 0.05)), nq=int(ctx.env.get("CP_NQ", 6)),
             nb=int(ctx.env.get("CP_NB", 6)), noise=float(ctx.env.get("CP_NOISE", 0.3)), seed=int(ctx.env.get("SEED", 0)), resv=0, report=[])
    # pad boxes in each part's dump frame: ref -> [(box, net, num, on F in the dump pose?, through?)]
    pb = {}
    for f in ctx.d["fps"]: pb[f["ref"]] = []
    for p in ctx.d["pads"]:
        x0, y0 = ctx.pos0[p["ref"]]; b = p["box"]; L = p.get("layers", [])
        pb[p["ref"]].append(((b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0), p["net"] or "", p["num"], "F.Cu" in L or "*.Cu" in L, "*.Cu" in L or ("F.Cu" in L and "B.Cu" in L)))
    S["pb"] = pb
    # switch parts: the shared bodies add escape room (ESC) round every part with 12 or more pads; a power FET's sides
    # are its hot-loop pins, so the stage is built on the true courtyard and the escape room is given back afterwards
    # on the sides the stage left free (restore_body)
    S["body0"] = {}
    fp = {f["ref"]: f for f in ctx.d["fps"]}
    for hl in C["hot_loops"].values():
        dev = hl["switch_pins"][0].split(".")[0]
        if dev in ctx.fill and "court" in fp[dev]:
            i = ctx.ri[dev]; c = fp[dev]["court"]; x0, y0 = ctx.pos0[dev]
            S["body0"][dev] = ctx.bbx[i].copy(); ctx.bbx[i] = (c[0] - x0, c[1] - y0, c[2] - x0, c[3] - y0)


# ---------------------------------------------------------------- geometry
def pads(ctx, r, P=None):
    """pads of a placed part in board coordinates: [(box, net, num, onF)] for its CURRENT side"""
    x, y, k = (P or ctx.P)[r]; out = []
    flip = ctx.sideF[r] != ctx.side0[r]
    for b, n, num, onF0, thr in S["pb"][r]:
        if flip: b = (-b[2], b[1], -b[0], b[3]); onF = thr or not onF0
        else: onF = onF0
        rb = ctx.rbox(b, k); out.append(((x + rb[0], y + rb[1], x + rb[2], y + rb[3]), n, num, onF if not thr else None))
    return out


def on_layer(p, F):
    return p[3] is None or p[3] == F


def local_pads(ctx, r, k):
    """pad boxes of an unplaced part, relative to its origin, turned by k (current side)"""
    flip = ctx.sideF[r] != ctx.side0[r]; out = []
    for b, n, num, onF0, thr in S["pb"][r]:
        if flip: b = (-b[2], b[1], -b[0], b[3])
        out.append((ctx.rbox(b, k), n, num))
    return out


def ctr(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def grow(b, g): return (b[0] - g, b[1] - g, b[2] + g, b[3] + g)


def union(bs):
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def boxgap(a, b):
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2])); dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3])); return math.hypot(dx, dy)


def switch_pads(ctx, hl):
    """(switch ref, supply pad boxes, return pad boxes) of a hot loop, switch placed"""
    dev = hl["switch_pins"][0].split(".")[0]; pp = S["C"]["pin_pads"]
    nums = {n for t in hl["switch_pins"] for n in pp.get(t, [])}
    ps = [p for p in pads(ctx, dev) if p[2] in nums]
    sp = [p[0] for p in ps if bare(p[1]) == hl["supply"]]; rp = [p[0] for p in ps if bare(p[1]) == hl["ret"]]
    return dev, sp, rp


# ---------------------------------------------------------------- copper distance fields
def field(ctx, win, src, net, F, grow_obs=0.0, skip=()):
    """geodesic distance (mm) on layer F (True = F.Cu) from the source boxes over the window, through cells that keep
    CLR + grow_obs from every pad of another net (placed parts only). Returns (x0, y0, dist array [ny, nx])."""
    x0, y0, x1, y1 = win; nx = int((x1 - x0) / RES) + 1; ny = int((y1 - y0) / RES) + 1
    blk = np.zeros((ny, nx), bool); bx = ctx.box
    gx = x0 + (np.arange(nx) + 0.5) * RES; gy = y0 + (np.arange(ny) + 0.5) * RES
    blk[:, (gx < bx[0] + 0.3) | (gx > bx[2] - 0.3)] = True; blk[(gy < bx[1] + 0.3) | (gy > bx[3] - 0.3), :] = True
    g = CLR + grow_obs
    def stamp(a, b_, v=True):
        i0 = max(0, int(math.floor((b_[0] - x0) / RES))); i1 = min(nx, int(math.ceil((b_[2] - x0) / RES)))
        j0 = max(0, int(math.floor((b_[1] - y0) / RES))); j1 = min(ny, int(math.ceil((b_[3] - y0) / RES)))
        if i1 > i0 and j1 > j0: a[j0:j1, i0:i1] = v
    wg = grow(win, 3.0)
    for q in ctx.P:
        if q in skip: continue
        qx, qy = ctx.P[q][0], ctx.P[q][1]
        if not (wg[0] < qx < wg[2] and wg[1] < qy < wg[3]): continue
        for b, n, num, onF in pads(ctx, q):
            if not n or not on_layer((b, n, num, onF), F) or n == net: continue
            stamp(blk, grow(b, g))
    s = np.zeros((ny, nx), bool)
    for b in src: stamp(s, b)
    s &= ~blk
    free = ~blk; idx = -np.ones((ny, nx), np.int64); N = int(free.sum()); idx[free] = np.arange(N)
    if not s.any() or N == 0: return x0, y0, np.full((ny, nx), BIG)
    rows = []; cols = []; ws = []
    for dj, di, w in ((0, 1, RES), (1, 0, RES), (1, 1, RES * 1.4142), (1, -1, RES * 1.4142)):
        ia0, ia1 = max(0, -di), nx - max(0, di)
        A = idx[0:ny - dj, ia0:ia1]; Bm = idx[dj:ny, ia0 + di:ia1 + di]
        m = (A >= 0) & (Bm >= 0)
        rows.append(A[m]); cols.append(Bm[m]); ws.append(np.full(int(m.sum()), w))
    rows = np.concatenate(rows); cols = np.concatenate(cols); ws = np.concatenate(ws)
    G = csr_matrix((ws, (rows, cols)), shape=(N, N))
    dd = dijkstra(G, directed=False, indices=idx[s], min_only=True)
    D = np.full((ny, nx), np.inf); D[free] = dd
    # a pad centre can sit in a blocked cell (inflated neighbour): let the field leak 2 cells into blocked ground
    for _ in range(3):
        e = ndimage.grey_erosion(np.where(np.isfinite(D), D, 1e9), size=3) + RES
        D = np.where(np.isfinite(D), D, np.where(e < 1e8, e, np.inf))
    D = np.where(np.isfinite(D), D, BIG); D = np.minimum(D, BIG)
    return x0, y0, D


def look(f, X, Y):
    x0, y0, D = f; ny, nx = D.shape
    i = np.floor((X - x0) / RES).astype(int); j = np.floor((Y - y0) / RES).astype(int)
    ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
    return np.where(ok, D[np.clip(j, 0, ny - 1), np.clip(i, 0, nx - 1)], BIG)


def fmin_in(f, b):
    x0, y0, D = f; ny, nx = D.shape
    i0 = max(0, int((b[0] - x0) / RES)); i1 = min(nx, int(math.ceil((b[2] - x0) / RES))); j0 = max(0, int((b[1] - y0) / RES)); j1 = min(ny, int(math.ceil((b[3] - y0) / RES)))
    return float(D[j0:j1, i0:i1].min()) if i1 > i0 and j1 > j0 else BIG


# ---------------------------------------------------------------- placing with the shared search
def tent(ctx, r, pose):
    ctx.P[r] = pose; ctx.add_obstacle(r)


def untent(ctx, r):
    ctx.P.pop(r, None); ctx.OB.pop(r, None)


def commit(ctx, r, best, why):
    ctx.put(r, best); ctx.LOCK.add(r)
    log(f"{r}: {best[1]:.2f},{best[2]:.2f} k{best[3]} cost {best[0]:.1f} ({why})")


def box_pen(ctx, r, k, xs, ys):
    """W_BOX per mm the body of r sticks out of its own section box (Logan's floorplan): a stage that spills out
    takes the room its controller's section needs (the charger then lands far from its gate pins)"""
    bx = ctx.boxof.get(r)
    if not bx or W_BOX <= 0: return 0.0
    b = ctx.rbox(ctx.bbx[ctx.ri[r]], k); X = xs[None, :]; Y = ys[:, None]; R = grow(bx, BOX_M)
    return W_BOX * (np.maximum(0, R[0] - (X + b[0])) + np.maximum(0, X + b[2] - R[2]) + np.maximum(0, R[1] - (Y + b[1])) + np.maximum(0, Y + b[3] - R[3]))


def search(ctx, r, win, extra, step=None, use_box=True):
    """the shared placer's search (legal mask, other hooks' illegal/extra cost, base wiring) on r's current side,
    plus the section-box penalty"""
    bp = (lambda r_, k, xs, ys: box_pen(ctx, r_, k, xs, ys)) if use_box else (lambda r_, k, xs, ys: 0.0)
    ex = (lambda r_, k, xs, ys: extra(r_, k, xs, ys) + bp(r_, k, xs, ys)) if extra is not None else bp
    return ctx.place(r, win, step or S["step"], extra=ex, sides=[ctx.sideF[r]])


def pad_aff_cost(ctx, r, terms):
    """extra cost: sum over terms (net, field, weight) of weight * field at r's pads of that net (nearest pad)"""
    def ex(r_, k, xs, ys):
        X = xs[None, :]; Y = ys[:, None]; c = 0.0
        lp = local_pads(ctx, r_, k)
        for net, f, w in terms:
            best = None
            for b, n, num in lp:
                if n != net: continue
                cx, cy = ctr(b); v = look(f, X + cx, Y + cy); best = v if best is None else np.minimum(best, v)
            if best is not None: c = c + w * best
        return c
    return ex


def loop_cost_fn(ctx, r, sup_net, ret_net, fS, fG, hot_ctr, axis, mid=None):
    """the hot-loop cost of a capacitor pose: copper path supply pad -> switch supply pads + return pad -> switch
    return pads (fields), distance to the switch's hot pins (area), and turn (supply pad toward the supply pins)"""
    def ex(r_, k, xs, ys):
        X = xs[None, :]; Y = ys[:, None]
        lp = local_pads(ctx, r_, k)
        s = [ctr(b) for b, n, num in lp if n == sup_net]; g = [ctr(b) for b, n, num in lp if n == ret_net]
        if not s or not g: return BIG * W_LOOP
        a = min((look(fS, X + cx, Y + cy) for cx, cy in s), key=lambda v: float(np.min(v)))
        b = min((look(fG, X + cx, Y + cy) for cx, cy in g), key=lambda v: float(np.min(v)))
        sx = np.mean([p[0] for p in s]); sy = np.mean([p[1] for p in s]); gx = np.mean([p[0] for p in g]); gy = np.mean([p[1] for p in g])
        v = np.array([sx - gx, sy - gy]); v = v / (np.hypot(*v) + 1e-9); cos = float(v @ axis)
        c = W_LOOP * (a + b) + W_AREA * np.hypot(X + (sx + gx) / 2 - hot_ctr[0], Y + (sy + gy) / 2 - hot_ctr[1]) + W_ALIGN * (1 - cos)
        if mid is not None:
            # separation: the rule copper (plan_copper step 2) draws one hull over all supply pads of the loop and one
            # over all return pads, or pairs to the nearest switch pad of the net. Both close only when every supply
            # pad lies on the supply side of the switch's mid line and every return pad on the return side.
            sp_ = [q for b_, n, num in lp if n == sup_net for q in (b_[0] * axis[0] + b_[1] * axis[1], b_[2] * axis[0] + b_[3] * axis[1], b_[0] * axis[0] + b_[3] * axis[1], b_[2] * axis[0] + b_[1] * axis[1])]
            gp_ = [q for b_, n, num in lp if n == ret_net for q in (b_[0] * axis[0] + b_[1] * axis[1], b_[2] * axis[0] + b_[3] * axis[1], b_[0] * axis[0] + b_[3] * axis[1], b_[2] * axis[0] + b_[1] * axis[1])]
            pr = X * axis[0] + Y * axis[1]
            bad = (pr + min(sp_) < mid + SEP_M) | (pr + max(gp_) > mid - SEP_M)
            c = c + np.where(bad, 1e5, 0.0)
        return c
    return ex


def place_loop_cap(ctx, hl, c, idx, commit_it=True):
    """put hot-loop capacitor c at the best loop pose next to its switch; returns (best, loop cost part)"""
    dev, sp, rp = switch_pads(ctx, hl); F = ctx.sideF[dev]
    sup = next(n for b, n, num in local_pads(ctx, c, 0) if bare(n) == hl["supply"]); ret = next(n for b, n, num in local_pads(ctx, c, 0) if bare(n) == hl["ret"])
    # earlier capacitors of the loop are sources too (their pads join the pours), at their own distance
    srcS = list(sp); srcG = list(rp)
    for c0 in hl["caps"][:idx]:
        if c0 in ctx.P and c0 in S.get("locked_caps", ()):
            for b, n, num, onF in pads(ctx, c0):
                if n == sup: srcS.append(b)
                elif n == ret: srcG.append(b)
    hb = union(sp + rp); win = grow(hb, 5.0 if idx == 0 else 9.0)
    fS = field(ctx, win, srcS, sup, F); fG = field(ctx, win, srcG, ret, F)
    hc = ctr(union(sp + rp)); cs = ctr(union(sp)); cg = ctr(union(rp)); axis = np.array([cs[0] - cg[0], cs[1] - cg[1]]); axis = axis / (np.hypot(*axis) + 1e-9)
    mid = 0.5 * ((cs[0] + cg[0]) * axis[0] + (cs[1] + cg[1]) * axis[1])
    ex = loop_cost_fn(ctx, c, sup, ret, fS, fG, hc, axis, mid)
    best = search(ctx, c, win, ex)
    if best is None: return None, None
    xs = np.array([best[1]]); ys = np.array([best[2]])
    lc = float(np.asarray(ex(c, best[3], xs, ys)).reshape(-1)[0])
    if S["log"]:
        lp = local_pads(ctx, c, best[3]); s_ = [ctr(b) for b, n, num in lp if n == sup][0]; g_ = [ctr(b) for b, n, num in lp if n == ret][0]
        log(f"    {c} k{best[3]}: supply path {float(look(fS, best[1] + s_[0], best[2] + s_[1])):.2f} mm, return path {float(look(fG, best[1] + g_[0], best[2] + g_[1])):.2f} mm")
    if commit_it: commit(ctx, c, best, f"{hl['switch_pins'][0]} loop cap {idx}, loop cost {lc:.1f}"); S.setdefault("locked_caps", set()).add(c)
    return best, lc


# ---------------------------------------------------------------- reservations (vias, loop box, switch node gap)
def reserve(ctx, b, both=True, side=True):
    S["resv"] += 1; key = f"_cpower_{S['resv']}"
    ctx.OB[key] = [(side, b, "b"), (side, b, "t")] + ([(not side, b, "b"), (not side, b, "t")] if both else [])


def reserve_vias(ctx, ret_pads, net, toward, F, count):
    """count via sites beside the given return pad boxes: 0.45 mm vias, CLR from other nets' pads of placed parts,
    0.65 mm apart, nearest to `toward` first; reserved as body obstacles on both sides"""
    near = []
    for q in ctx.P:
        qx, qy = ctx.P[q][0], ctx.P[q][1]
        if abs(qx - toward[0]) > 15 or abs(qy - toward[1]) > 15: continue
        near += [p for p in pads(ctx, q) if p[1] and p[1] != net]
    have = S.setdefault("vias", []); got = 0
    for pb_ in ret_pads:
        cx, cy = ctr(pb_); cand = []
        for d in (0.45, 0.7, 0.95):
            for t in (-0.5, -0.25, 0.0, 0.25, 0.5):
                cand += [(pb_[0] - d, cy + t * (pb_[3] - pb_[1])), (pb_[2] + d, cy + t * (pb_[3] - pb_[1])), (cx + t * (pb_[2] - pb_[0]), pb_[1] - d), (cx + t * (pb_[2] - pb_[0]), pb_[3] + d)]
        cand.sort(key=lambda q: math.hypot(q[0] - toward[0], q[1] - toward[1]) + 0.5 * boxgap((q[0], q[1], q[0], q[1]), pb_))
        n = 0
        for x, y in cand:
            if n >= count: break
            if not (ctx.box[0] + 0.8 < x < ctx.box[2] - 0.8 and ctx.box[1] + 0.8 < y < ctx.box[3] - 0.8): continue
            if any(boxgap((x, y, x, y), p[0]) < VIA_R + CLR + 0.02 for p in near if (p[3] is None or True)): continue
            if any(math.hypot(x - a, y - b) < 0.65 for a, b in have): continue
            have.append((x, y)); reserve(ctx, (x - 0.45, y - 0.45, x + 0.45, y + 0.45), both=True, side=F); n += 1; got += 1
    return got


def reserve_gap(ctx, a, b, F):
    """reserve the straight gap between two pad boxes that face each other (switch node), on the stage side"""
    if min(a[2], b[2]) - max(a[0], b[0]) > 0.3:      # overlap in x: vertical gap
        x0, x1 = max(a[0], b[0]), min(a[2], b[2]); y0, y1 = min(a[3], b[3]), max(a[1], b[1])
        if y1 > y0: reserve(ctx, (x0, y0, x1, y1), both=False, side=F); return True
    if min(a[3], b[3]) - max(a[1], b[1]) > 0.3:
        y0, y1 = max(a[1], b[1]), min(a[3], b[3]); x0, x1 = min(a[2], b[2]), max(a[0], b[0])
        if x1 > x0: reserve(ctx, (x0, y0, x1, y1), both=False, side=F); return True
    return False


def protect_loop(ctx, hl):
    dev, sp, rp = switch_pads(ctx, hl); F = ctx.sideF[dev]; ret = None
    caps = [c for c in hl["caps"] if c in ctx.P]
    for c in caps:
        rpc = [p[0] for p in pads(ctx, c) if bare(p[1]) == hl["ret"]]; ret = next(p[1] for p in pads(ctx, c) if bare(p[1]) == hl["ret"])
        reserve_vias(ctx, rpc, ret, ctr(union(rp)), F, 2)
    if ret: reserve_vias(ctx, rp, ret, ctr(union(rp)), F, 3)
    if caps:
        c0 = caps[0]; b = union(sp + rp + [p[0] for p in pads(ctx, c0) if p[1]]); reserve(ctx, grow(b, 0.3), both=False, side=F)


# ---------------------------------------------------------------- stage parts helpers
def hl_of_switch(dev):
    for name, hl in S["C"]["hot_loops"].items():
        if hl["switch_pins"][0].split(".")[0] == dev: return name, hl
    return None, None


def net_of_pin(ctx, ref, pin):
    nums = S["C"]["pin_pads"].get(f"{ref}.{pin}", [])
    return next((n for b, n, num, f, t in S["pb"][ref] if num in nums), None)


def gate_pads(ctx, dev, hl):
    """the switch's own small signal pads (gate drive): pads on signal nets other than supply/ret/switch node"""
    out = []
    for p in pads(ctx, dev):
        n = p[1]
        if n and n in ctx.sig and bare(n) not in (hl["supply"], hl["ret"]): out.append(p)
    return out


def noise(tag):
    if not S["seed"]: return 0.0
    return S["noise"] * (zlib.crc32(f"{tag}{S['seed']}".encode()) % 1000) / 1000.0


def candidates(ctx, r, win, cost, n, step=0.25, sep=0.6):
    """legal poses of r in the window (own scan, legal mask only), the n cheapest per turn, spread by sep mm"""
    out = []
    xs = np.arange(max(win[0], ctx.box[0]), min(win[2], ctx.box[2]), step); ys = np.arange(max(win[1], ctx.box[1]), min(win[3], ctx.box[3]), step)
    for k in range(4):
        L = ctx.legal_mask(r, k, xs, ys)
        if not L.any(): continue
        c = np.where(L, cost(r, k, xs, ys) + box_pen(ctx, r, k, xs, ys) / W_LOOP, np.inf); order = np.argsort(c, axis=None); got = []
        for o in order:
            if not np.isfinite(c.flat[o]) or len(got) >= n: break
            j, i = np.unravel_index(o, c.shape); x, y = xs[i], ys[j]
            if any(math.hypot(x - a, y - b) < sep for a, b in got): continue
            got.append((x, y)); out.append((float(c.flat[o]), float(x), float(y), k))
    return out


W_BULK = 0.3       # weight of the bulk capacitors' loop cost against the first capacitor's when choosing a switch pose


def trial_loop(ctx, hl):
    """tentatively place every movable capacitor of the loop in order; returns (first cap cost, weighted total,
    placed refs) or None when the first one has no spot. The caller removes them with untent()."""
    lk = S.setdefault("locked_caps", set()); placed = []; first = None; tot = 0.0
    for i, c in enumerate(hl["caps"]):
        if c in ctx.P or c not in ctx.fill: continue
        b, lc = place_loop_cap(ctx, hl, c, i, commit_it=False)
        if b is None:
            if i == 0: break
            tot += W_BULK * 1e5; continue
        tent(ctx, c, (b[1], b[2], b[3])); lk.add(c); placed.append(c)
        if i == 0: first = lc; tot += lc
        else: tot += W_BULK * lc
    for c in placed: lk.discard(c)
    if first is None:
        for c in placed: untent(ctx, c)
        return None
    return first, tot, placed


# ---------------------------------------------------------------- four-switch stage round a fixed inductor
def place_bridge_switch(ctx, dev, ind):
    name, hl = hl_of_switch(dev)
    if dev in ctx.P: return
    F = ctx.sideF[dev]
    lp0 = local_pads(ctx, dev, 0)
    swn = None
    for b, n, num in lp0:                       # switch-node net: the net the switch shares with the inductor
        if n and any(n == p[1] for p in pads(ctx, ind)): swn = n; break
    Lp = [p[0] for p in pads(ctx, ind) if p[1] == swn]; Lb = union(Lp)
    def pre(r, k, xs, ys):
        X = xs[None, :]; Y = ys[:, None]; c = 0.0
        sw = [b for b, n, num in local_pads(ctx, r, k) if n == swn]
        if not sw: return np.zeros((len(ys), len(xs)))
        b = union(sw)
        dx = np.maximum(0, np.maximum(X + b[0], Lb[0]) - np.minimum(X + b[2], Lb[2])); dy = np.maximum(0, np.maximum(Y + b[1], Lb[1]) - np.minimum(Y + b[3], Lb[3]))
        return np.hypot(dx, dy)
    win = grow(Lb, 9.0)
    cands = candidates(ctx, dev, win, pre, S["nq"])
    log(f"{dev}: {len(cands)} candidate poses round {ind} ({swn})")
    best = None; c0 = hl["caps"][0]
    for ci, (pc, x, y, k) in enumerate(cands):
        tent(ctx, dev, (x, y, k))
        tr = trial_loop(ctx, hl)
        if tr is None: untent(ctx, dev); continue
        lc0, lc, placed = tr
        swp = [p[0] for p in pads(ctx, dev) if p[1] == swn]
        fw = field(ctx, grow(union(Lp + swp), 3.0), Lp, swn, F, grow_obs=0.3)
        swl = min(fmin_in(fw, b) for b in swp)
        gp = gate_pads(ctx, dev, hl); gl = 0.0
        if gp:
            gw = grow(union([p[0] for p in pads(ctx, dev)]), 3.0)
            border = [(gw[0], gw[1], gw[2], gw[1] + RES), (gw[0], gw[3] - RES, gw[2], gw[3]), (gw[0], gw[1], gw[0] + RES, gw[3]), (gw[2] - RES, gw[1], gw[2], gw[3])]
            for p in gp:
                fg = field(ctx, gw, border, p[1], F, grow_obs=0.1); gl += min(fmin_in(fg, p[0]), 8.0)
        bp = float(np.asarray(box_pen(ctx, dev, k, np.array([x]), np.array([y]))).reshape(-1)[0])
        tot = lc + W_SW * swl + W_GATE * gl + bp + noise(f"{dev}{ci}")
        log(f"  cand {ci} {x:.2f},{y:.2f} k{k}: loop {lc0:.1f} / {lc:.1f} sw {swl:.2f} mm gate {gl:.2f} mm box {bp:.1f} total {tot:.1f}")
        for c in placed: untent(ctx, c)
        untent(ctx, dev)
        if best is None or tot < best[0]: best = (tot, x, y, k, F)
    if best is None: log(f"{dev}: no pose"); return
    commit(ctx, dev, best, f"switch at {ind}")
    place_loop_cap(ctx, hl, c0, 0)
    swp = [p[0] for p in pads(ctx, dev) if p[1] == swn]
    for b in swp:
        for l in Lp: reserve_gap(ctx, b, l, F)


def place_rest_of_loop(ctx, dev):
    name, hl = hl_of_switch(dev)
    for i, c in enumerate(hl["caps"]):
        if c in ctx.P or c not in ctx.fill: continue
        place_loop_cap(ctx, hl, c, i)
    protect_loop(ctx, hl)


def stage_net_pads(ctx, net, refs):
    return [p[0] for r in refs if r in ctx.P for p in pads(ctx, r) if p[1] == net]


def place_affine(ctx, r, terms, win, why, w_extra=None, use_box=True):
    """place r with cost sum w * copper distance of its pad on net to the given source boxes"""
    F = ctx.sideF[r]; tf = []
    for net, src, w in terms:
        if not src: continue
        tf.append((net, field(ctx, win, src, net, F), w))
    ex = pad_aff_cost(ctx, r, tf)
    if w_extra is not None:
        e0 = ex; ex = lambda r_, k, xs, ys: e0(r_, k, xs, ys) + w_extra(r_, k, xs, ys)
    best = search(ctx, r, win, ex, step=0.1, use_box=use_box)
    if best is None:
        best = search(ctx, r, grow(win, 6), ex, step=0.2, use_box=use_box)
    if best is None: log(f"{r}: no spot"); return None
    commit(ctx, r, best, why); return best


def build_bridge(ctx, key, st):
    qa, qb, ind = key, st["q_out"], st["inductor"]
    if ind not in ctx.P: log(f"{key}: inductor {ind} not placed"); return
    for dev in (qa, qb):
        if dev in ctx.fill: place_bridge_switch(ctx, dev, ind)
    for dev in (qa, qb): place_rest_of_loop(ctx, dev)
    stage = [qa, qb] + [c for c in st.get("cin", []) + st.get("cout", []) if c in ctx.P]
    # sense resistors: the pad on a stage net at the stage copper of that net, the other pad toward its other parts
    for rr in (st.get("rin"), st.get("rout")):
        if not rr or rr in ctx.P or rr not in ctx.fill: continue
        nets = [n for b, n, num in local_pads(ctx, rr, 0)]
        terms = []
        for n in nets:
            src = stage_net_pads(ctx, n, stage)
            if src: terms.append((n, src, 20.0))
        allp = [p[0] for p in pads(ctx, qa)] + [p[0] for p in pads(ctx, qb)]
        # (no section-box term: the floorplan files the sense resistors under the charger section for their Kelvin
        # taps, but their 5-10 A pads belong at the stage copper)
        place_affine(ctx, rr, terms, grow(union(allp), 12.0), f"sense resistor of {key}", use_box=False)
        stage.append(rr)
    for c in st.get("cin", []) + st.get("cout", []):
        if c in ctx.P or c not in ctx.fill: continue
        nets = [n for b, n, num in local_pads(ctx, c, 0)]; terms = []
        for n in nets:
            src = stage_net_pads(ctx, n, stage)
            if src: terms.append((n, src, 10.0))
        allp = [p[0] for p in pads(ctx, qa)] + [p[0] for p in pads(ctx, qb)]
        place_affine(ctx, c, terms, grow(union(allp), 12.0), f"bulk capacitor of {key}")
        stage.append(c)


# ---------------------------------------------------------------- small buck
def build_buck(ctx, key, st):
    dev = key; ind = st.get("inductor"); name, hl = hl_of_switch(dev)
    if dev not in ctx.fill or dev in ctx.P or hl is None: return
    F = ctx.sideF[dev]
    swn = net_of_pin(ctx, dev, st.get("sw", "SW"))
    if not swn and ind: swn = next((n for b, n, num in local_pads(ctx, dev, 0) if n and any(n == q[1] for q in local_pads(ctx, ind, 0))), None)
    bstn = net_of_pin(ctx, dev, st["bst"]) if st.get("bst") else None
    bx = ctx.boxof.get(dev) or ctx.box; hc = ctr(bx)
    def pre(r, k, xs, ys):
        return np.hypot(xs[None, :] - hc[0], ys[:, None] - hc[1])
    win = grow(bx, 1.5)
    cands = candidates(ctx, dev, win, pre, S["nb"], step=0.25, sep=1.0)
    if not cands: cands = candidates(ctx, dev, grow(bx, 6), pre, S["nb"], step=0.25, sep=1.0)
    log(f"{dev}: {len(cands)} candidate poses in its box")
    best = None; c0 = hl["caps"][0]
    for ci, (pc, x, y, k) in enumerate(cands):
        tent(ctx, dev, (x, y, k))
        tr = trial_loop(ctx, hl)
        if tr is None: untent(ctx, dev); continue
        lc0, lc, placed = tr
        il = 0.0; bl = None
        if ind and ind in ctx.fill:
            swp = [p[0] for p in pads(ctx, dev) if p[1] == swn]
            fw = field(ctx, grow(union(swp), 9.0), swp, swn, F, grow_obs=0.3)
            ex = pad_aff_cost(ctx, ind, [(swn, fw, W_SW)])
            bl = search(ctx, ind, grow(union(swp), 9.0), ex, step=0.1)
            il = bl[0] if bl else 1e4
        tot = lc + il + W_HOME * pc + noise(f"{dev}{ci}")
        log(f"  cand {ci} {x:.2f},{y:.2f} k{k}: loop {lc0:.1f} / {lc:.1f} inductor {il:.1f} home {pc:.1f} total {tot:.1f}")
        for c in placed: untent(ctx, c)
        untent(ctx, dev)
        if best is None or tot < best[0]: best = (tot, x, y, k, F)
    if best is None: log(f"{dev}: no pose"); return
    commit(ctx, dev, best, "buck IC")
    place_loop_cap(ctx, hl, c0, 0)
    if ind and ind in ctx.fill:
        swp = [p[0] for p in pads(ctx, dev) if p[1] == swn]
        place_affine(ctx, ind, [(swn, swp, W_SW)], grow(union(swp), 9.0), f"inductor of {dev}")
        for b in swp:
            for l in [p[0] for p in pads(ctx, ind) if p[1] == swn]: reserve_gap(ctx, b, l, F)
    for i, c in enumerate(hl["caps"]):
        if c in ctx.P or c not in ctx.fill: continue
        place_loop_cap(ctx, hl, c, i)
    protect_loop(ctx, hl)
    devp = pads(ctx, dev); W = grow(union([p[0] for p in devp]), 10.0)
    # bootstrap capacitor: BST pin and SW pin
    bc = st.get("boot")
    if bc and bc in ctx.fill and bc not in ctx.P:
        place_affine(ctx, bc, [(bstn, [p[0] for p in devp if p[1] == bstn], 10.0), (swn, [p[0] for p in devp if p[1] == swn], 10.0)], W, f"boot capacitor of {dev}")
    # output capacitors: at the inductor's output pad, return toward the IC's ground pins
    outn = None
    if ind and ind in ctx.P:
        outn = next((p[1] for p in pads(ctx, ind) if p[1] and p[1] != swn), None)
    gnd = hl["ret"]; gpads = [p[0] for p in devp if bare(p[1]) == gnd]
    stage = [dev, ind] if ind else [dev]
    for c in st.get("cout", []):
        if c in ctx.P or c not in ctx.fill: continue
        nets = {n for b, n, num in local_pads(ctx, c, 0)}; terms = []
        for n in nets:
            if bare(n) == gnd: terms.append((n, gpads + stage_net_pads(ctx, n, [q for q in stage if q != dev]), 3.0))
            else:
                src = stage_net_pads(ctx, n, stage)
                if src: terms.append((n, src, 10.0))
        place_affine(ctx, c, terms, grow(W, 4), f"output capacitor of {dev}"); stage.append(c)
    for c in st.get("cin", []):
        if c in ctx.P or c not in ctx.fill: continue
        nets = {n for b, n, num in local_pads(ctx, c, 0)}; terms = []
        for n in nets:
            src = stage_net_pads(ctx, n, stage + [q for q in hl["caps"] if q in ctx.P])
            if src: terms.append((n, src, 10.0))
        place_affine(ctx, c, terms, grow(W, 4), f"input capacitor of {dev}"); stage.append(c)


def restore_body(ctx, dev):
    """give the switch its escape room back on every side where no stage part sits in it"""
    if dev not in S["body0"] or dev not in ctx.P: return
    i = ctx.ri[dev]; c = np.array(ctx.bbx[i], float); e = np.array(S["body0"][dev], float); new = c.copy()
    others = [b for q, v in ctx.OB.items() if q != dev and not str(q).startswith("_cpower") for (s_, b, kd) in v if kd == "b" and s_ == ctx.sideF[dev]]
    for side in range(4):
        t = c.copy(); t[side] = e[side]
        ctx.bbx[i] = tuple(t); x, y, k = ctx.P[dev]; bb = ctx.body_of(dev, x, y, k)
        if not any(bb[0] < o[2] and bb[2] > o[0] and bb[1] < o[3] and bb[3] > o[1] for o in others): new[side] = e[side]
    ctx.bbx[i] = tuple(new); ctx.add_obstacle(dev)
    log(f"{dev}: body {np.round(c, 2).tolist()} -> {np.round(new, 2).tolist()}")


def pre_place(ctx):
    D = S["C"]["draw"]
    for key, st in sorted(D.items(), key=lambda kv: (kv[1].get("kind") != "bridge4", kv[0])):
        if st.get("kind") == "bridge4": build_bridge(ctx, key, st)
    for key, st in sorted(D.items()):
        if st.get("kind") == "buck": build_buck(ctx, key, st)
    for dev in list(S["body0"]): restore_body(ctx, dev)
    print(f"[cpower] stage parts placed and locked: {len(ctx.LOCK)}; reserved boxes: {S['resv']}", flush=True)


def post_place(ctx):
    """report per hot loop: first capacitor pad gaps to the switch pads (box to box, mm)"""
    for name, hl in sorted(S["C"]["hot_loops"].items()):
        dev = hl["switch_pins"][0].split(".")[0]
        if dev not in ctx.P or hl["caps"][0] not in ctx.P: continue
        _, sp, rp = switch_pads(ctx, hl); c = hl["caps"][0]
        cs = [p[0] for p in pads(ctx, c) if bare(p[1]) == hl["supply"]]; cg = [p[0] for p in pads(ctx, c) if bare(p[1]) == hl["ret"]]
        gs = min(boxgap(a, b) for a in cs for b in sp); gg = min(boxgap(a, b) for a in cg for b in rp)
        print(f"[cpower] {name}: {c} supply gap {gs:.2f} mm, return gap {gg:.2f} mm", flush=True)
