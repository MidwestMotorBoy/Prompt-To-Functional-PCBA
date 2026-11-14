"""greedy_fill.py <fz_dump.json> <fz_clusters.json> <intent.json> <floorplan.json> <bodies.json> <out placement.json>
Constructive fill at pin targets, legal from the first part (worker 1).
Bodies, keep-outs and through-hole boxes are exactly place_pack.py's (dumped by pp_w1.py DUMP_BODIES), so a
placement this script accepts has zero overlap in place_pack's eyes and its repair step leaves it alone.
 1. parts with BIG_PADS or more pads first: every legal spot in and near the box, cost = wiring to placed pads
    + a penalty when the free area within RING mm is under ROOM_X times the courtyards of its small parts.
 2. then the unplaced part most connected to what is placed (near statements weighted) goes to the legal spot and
    rotation with the least wiring to placed pads (half-perimeter growth of each net) + near-statement distance.
Env knobs: STEP (search grid, mm, default 0.1), BOXW (cost per mm outside box+BOXM), BOXM (mm, default 3),
RING, ROOM_X, BIG_PADS, NEARW."""
import json, sys, os, math, zlib
from collections import defaultdict
import numpy as np

STEP = float(os.environ.get("STEP", 0.1)); BOXW = float(os.environ.get("BOXW", 1.0)); BOXM = float(os.environ.get("BOXM", 3.0))
RING = float(os.environ.get("RING", 4.0)); ROOM_X = float(os.environ.get("ROOM_X", 1.5)); BIG_PADS = int(os.environ.get("BIG_PADS", 12))
NEARW = float(os.environ.get("NEARW", 3.0)); ROOMW = float(os.environ.get("ROOMW", 20)); CENTW = float(os.environ.get("CENTW", 0.5)); SECW = float(os.environ.get("SECW", 0.5)); INTERLEAVE = int(os.environ.get("INTERLEAVE", 1)); SWAP = int(os.environ.get("SWAP", 1)); SWAPD = float(os.environ.get("SWAPD", 8)); SEED = int(os.environ.get("SEED", 0)); NOISE = float(os.environ.get("NOISE", 0.15)); PWRW = float(os.environ.get("PWRW", 0.0)); M = 0.02

def rotv(x, y, k):
    k %= 4
    if k == 0: return x, y
    if k == 1: return -y, x
    if k == 2: return -x, -y
    return y, -x

def rbox(b, k):
    a = rotv(b[0], b[1], k); c = rotv(b[2], b[3], k)
    return (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))

def main(dumpf, clf, intf, fpf, bodf, outf):
    d = json.load(open(dumpf)); cl = json.load(open(clf)); it = json.load(open(intf)); BF = json.load(open(fpf))["blocks"]; B = json.load(open(bodf))
    refs = B["refs"]; ri = {r: i for i, r in enumerate(refs)}; bbx = np.array(B["bbx"]); tbx = np.array(B["tbx"]); thru = np.array(B["thru"]); TM = B["TM"]
    box = B["box"]; KO = B["KO"]
    fps = {f["ref"]: f for f in d["fps"]}; pos0 = {r: (f["x"], f["y"]) for r, f in fps.items()}; sideF = {r: fps[r]["side"] == "F.Cu" for r in fps}
    fill = {}; boxof = {}
    for name, parts in cl.items():
        for r in parts: fill[r] = name; boxof[r] = BF.get(name)
    # pads in each part's frame
    lp = defaultdict(list); netpads = defaultdict(list)
    for p in d["pads"]:
        x0, y0 = pos0[p["ref"]]; lp[p["ref"]].append((p["x"] - x0, p["y"] - y0, p["net"], p["num"]))
        if p["net"]: netpads[p["net"]].append(p["ref"])
    power = {n for n, rs in netpads.items() if len(rs) >= 12}
    sig = {n for n, rs in netpads.items() if n not in power and len(rs) >= 2}
    npads = {r: len(lp[r]) for r in lp}
    area = {r: (bbx[ri[r]][2] - bbx[ri[r]][0]) * (bbx[ri[r]][3] - bbx[ri[r]][1]) for r in refs}
    # near statements: (part, pad nums of part or None, [(target ref, target pad num or None)], max, weight)
    near = []
    for st in it.get("near", []):
        tg = []
        for t in st["to"]:
            tr, _, tp = t.partition("."); tg.append((tr, tp or None))
        near.append((st["part"], st["pad"].split(".", 1)[1] if "pad" in st else None, tg, st["max_mm"], st.get("weight", 1)))
    P = {}                                  # placed: ref -> (x, y, k)
    for r in refs:
        if r not in fill: P[r] = (pos0[r][0], pos0[r][1], 0)
    def pad_xy(r, j):
        x, y, k = P[r]; dx, dy = rotv(lp[r][j][0], lp[r][j][1], k); return x + dx, y + dy
    # obstacles per side, as place_pack LO/HI (body +- M) and through-hole boxes (+- TM)
    obs = {True: [], False: []}            # side F? -> boxes a body on that side may not touch (keep-outs)
    tobs = {True: [], False: []}
    OB = {}                                # ref -> [(side, box, kind)] kind b: blocks bodies; kind t: body seen by through-hole boxes
    for kb, onF, onB in KO:
        if onF: obs[True].append(tuple(kb))
        if onB: obs[False].append(tuple(kb))
    IGN = set()
    def all_obs(s, kind):
        base = obs[s] if kind == "b" else tobs[s]
        return base + [b for q, v in OB.items() if q not in IGN for (s2, b, k2) in v if s2 == s and k2 == kind]
    def body_of(r, x, y, k, which="b"):
        i = ri[r]; b = rbox(bbx[i] if which == "b" else tbx[i], k); m = M if which == "b" else TM
        return (x + b[0] - m, y + b[1] - m, x + b[2] + m, y + b[3] + m)
    def add_obstacle(r):
        x, y, k = P[r]; s = sideF[r]; bb = body_of(r, x, y, k)
        OB[r] = [(s, bb, "b"), (s, bb, "t")]
        if thru[ri[r]]: OB[r].append((not s, body_of(r, x, y, k, "t"), "b"))
    fixed_thru = []                         # fixed-fixed thru pairs are ignored by place_pack, but fill parts are never fixed, so all count
    for r in list(P): add_obstacle(r)
    # keep-free round frozen pads of power nets that are planned only after the fill (not frozen as skeleton copper)
    KEEPN = [n for n in os.environ.get("KEEP_NETS", "/USB Port 1/PP5V,/USB Port 2/PP5V,/USB Port 1/VBUS,/USB Port 2/VBUS").split(",") if n]
    KEEPM = float(os.environ.get("KEEP_MM", 1.0)); KEEPB = []    # (side F?, box, net)
    for p in d["pads"]:
        if p["net"] in KEEPN and p["ref"] not in fill:
            b = p["box"]; bb = (b[0] - KEEPM, b[1] - KEEPM, b[2] + KEEPM, b[3] + KEEPM)
            for L in p["layers"]:
                if L in ("F.Cu", "*.Cu"): KEEPB.append((True, bb, p["net"]))
                if L in ("B.Cu", "*.Cu"): KEEPB.append((False, bb, p["net"]))
    print(f"keep-free boxes: {len(KEEPB)}")
    # occupancy raster per side (for the free-area test of the large parts)
    RS = 0.25; gx = np.arange(box[0], box[2], RS) + RS / 2; gy = np.arange(box[1], box[3], RS) + RS / 2
    def occ_map(s):
        o = np.zeros((len(gy), len(gx)), bool)
        o[:, (gx < box[0] + 0.5) | (gx > box[2] - 0.5)] = True; o[(gy < box[1] + 0.5) | (gy > box[3] - 0.5), :] = True
        for b in all_obs(s, "b"):
            i0 = np.searchsorted(gx, b[0]); i1 = np.searchsorted(gx, b[2]); j0 = np.searchsorted(gy, b[1]); j1 = np.searchsorted(gy, b[3])
            o[j0:j1, i0:i1] = True
        return o
    def integral(o):
        f = (~o).astype(np.int32); I = np.zeros((f.shape[0] + 1, f.shape[1] + 1), np.int64); I[1:, 1:] = f.cumsum(0).cumsum(1); return I
    def free_in(I, x0, y0, x1, y1):        # free cells in a box (arrays allowed)
        i0 = np.clip(np.searchsorted(gx, x0), 0, len(gx)); i1 = np.clip(np.searchsorted(gx, x1), 0, len(gx))
        j0 = np.clip(np.searchsorted(gy, y0), 0, len(gy)); j1 = np.clip(np.searchsorted(gy, y1), 0, len(gy))
        return (I[j1, i1] - I[j0, i1] - I[j1, i0] + I[j0, i0]) * RS * RS
    def legal_mask(r, k, xs, ys):
        """bool [len(ys), len(xs)]: True where part r at (x, y, k) touches nothing"""
        i = ri[r]; s = sideF[r]; b = rbox(bbx[i], k); b = (b[0] - M, b[1] - M, b[2] + M, b[3] + M)
        bad = np.zeros((len(ys), len(xs)), bool)
        # board edge (place_pack: LO >= box0 + 0.5 ...)
        bad[:, (xs + b[0] < box[0] + 0.5) | (xs + b[2] > box[2] - 0.5)] = True
        bad[(ys + b[1] < box[1] + 0.5) | (ys + b[3] > box[3] - 0.5), :] = True
        X0, X1, Y0, Y1 = xs[0] + b[0], xs[-1] + b[2], ys[0] + b[1], ys[-1] + b[3]
        def stamp(o, b):
            if o[2] <= X0 or o[0] >= X1 or o[3] <= Y0 or o[1] >= Y1: return
            i0 = np.searchsorted(xs, o[0] - b[2], "right"); i1 = np.searchsorted(xs, o[2] - b[0], "left")
            j0 = np.searchsorted(ys, o[1] - b[3], "right"); j1 = np.searchsorted(ys, o[3] - b[1], "left")
            if i1 > i0 and j1 > j0: bad[j0:j1, i0:i1] = True
        for o in all_obs(s, "b"): stamp(o, b)
        mynets = {v[2] for v in lp[r]}
        for s2, o, n in KEEPB:
            if s2 == s and n not in mynets: stamp(o, b)
        if thru[i]:
            t = rbox(tbx[i], k); t = (t[0] - TM, t[1] - TM, t[2] + TM, t[3] + TM)
            for o in all_obs(not s, "t"): stamp(o, t)
        return ~bad
    def nets_of(r):
        out = defaultdict(list)
        for j, (_, _, n, _) in enumerate(lp[r]):
            if n in sig: out[n].append(j)
        return out
    def wiring(r, k, xs, ys):
        """half-perimeter growth of r's signal nets over the placed pads, for every grid spot"""
        X = xs[None, :]; Y = ys[:, None]; c = np.zeros((len(ys), len(xs)))
        for n, js in nets_of(r).items():
            q = [pad_xy(o, j) for o in set(netpads[n]) if o in P and o != r for j, v in enumerate(lp[o]) if v[2] == n]
            off = [rotv(lp[r][j][0], lp[r][j][1], k) for j in js]
            ox0 = min(a for a, _ in off); ox1 = max(a for a, _ in off); oy0 = min(b for _, b in off); oy1 = max(b for _, b in off)
            if not q:
                c += (ox1 - ox0) + (oy1 - oy0); continue
            qx0 = min(a for a, _ in q); qx1 = max(a for a, _ in q); qy0 = min(b for _, b in q); qy1 = max(b for _, b in q)
            c += (np.maximum(qx1, X + ox1) - np.minimum(qx0, X + ox0) - (qx1 - qx0)) + (np.maximum(qy1, Y + oy1) - np.minimum(qy0, Y + oy0) - (qy1 - qy0))
        return c
    def near_cost(r, k, xs, ys):
        X = xs[None, :]; Y = ys[:, None]; c = np.zeros((len(ys), len(xs)))
        for part, pad, tg, lim, w in near:
            if part == r:
                mine = [j for j, v in enumerate(lp[r]) if pad is None or v[3] == pad]
                tq = [pad_xy(tr, j) for tr, tp in tg if tr in P and tr != r for j, v in enumerate(lp[tr]) if tp is None or v[3] == tp]
            elif any(tr == r for tr, _ in tg) and part in P:
                mine = [j for tr, tp in tg if tr == r for j, v in enumerate(lp[r]) if tp is None or v[3] == tp]
                tq = [pad_xy(part, j) for j, v in enumerate(lp[part]) if pad is None or v[3] == pad]
            else: continue
            if not mine or not tq: continue
            dmin = None
            for j in mine:
                ox, oy = rotv(lp[r][j][0], lp[r][j][1], k)
                for tx, ty in tq:
                    dd = np.hypot(X + ox - tx, Y + oy - ty); dmin = dd if dmin is None else np.minimum(dmin, dd)
            c += NEARW * min(w, 4) * dmin + 25 * w * np.maximum(0, dmin - lim)
        return c
    def box_cost(r, k, xs, ys):
        bx = boxof.get(r)
        if not bx: return 0.0
        i = ri[r]; b = rbox(bbx[i], k); X = xs[None, :]; Y = ys[:, None]
        R = (bx[0] - BOXM, bx[1] - BOXM, bx[2] + BOXM, bx[3] + BOXM)
        return BOXW * (np.maximum(0, R[0] - (X + b[0])) + np.maximum(0, X + b[2] - R[2]) + np.maximum(0, R[1] - (Y + b[1])) + np.maximum(0, Y + b[3] - R[3]))
    def pwr_cost(r, k, xs, ys):
        if PWRW <= 0: return 0.0
        X = xs[None, :]; Y = ys[:, None]; c = np.zeros((len(ys), len(xs)))
        for j, (lx, ly, n, _) in enumerate(lp[r]):
            if n not in power or n == "GND": continue
            q = np.array([pad_xy(o, jj) for o in set(netpads[n]) if o in P and o != r for jj, v in enumerate(lp[o]) if v[2] == n])
            if not len(q): continue
            ox, oy = rotv(lx, ly, k); dmin = None
            for tx, ty in q[np.argsort(np.hypot(q[:, 0] - np.mean(xs), q[:, 1] - np.mean(ys)))[:40]]:
                dd = np.abs(X + ox - tx) + np.abs(Y + oy - ty); dmin = dd if dmin is None else np.minimum(dmin, dd)
            c += PWRW * dmin
        return c
    # support parts of each large part: small fill parts sharing a signal net with it or serving one of its pins
    def support(r):
        s = set()
        for n in nets_of(r):
            for o in netpads[n]:
                if o != r and o in fill and npads[o] < BIG_PADS: s.add(o)
        for part, pad, tg, lim, w in near:
            if any(tr == r for tr, _ in tg) and part in fill and npads[part] < BIG_PADS: s.add(part)
        return s
    def target_window(r):
        pts = []
        for n in nets_of(r):
            for o in set(netpads[n]):
                if o in P and o != r: pts += [pad_xy(o, j) for j, v in enumerate(lp[o]) if v[2] == n]
        for part, pad, tg, lim, w in near:
            if part == r: pts += [pad_xy(tr, j) for tr, tp in tg if tr in P for j, v in enumerate(lp[tr]) if tp is None or v[3] == tp] * 3
        return pts
    def place(r, win, step, extra=None):
        best = None
        xs = np.arange(max(win[0], box[0]), min(win[2], box[2]) + 1e-9, step); ys = np.arange(max(win[1], box[1]), min(win[3], box[3]) + 1e-9, step)
        if len(xs) == 0 or len(ys) == 0: return None
        for k in range(4):
            L = legal_mask(r, k, xs, ys)
            if not L.any(): continue
            c = wiring(r, k, xs, ys) + near_cost(r, k, xs, ys) + box_cost(r, k, xs, ys) + pwr_cost(r, k, xs, ys)
            if extra is not None: c = c + extra(r, k, xs, ys)
            c = np.where(L, c, np.inf); j = np.unravel_index(np.argmin(c), c.shape)
            if np.isfinite(c[j]) and (best is None or c[j] < best[0]): best = (float(c[j]), float(xs[j[1]]), float(ys[j[0]]), k)
        return best
    fails = []
    def score(r):
        s = 0.0
        for n, js in nets_of(r).items():
            m = sum(1 for o in netpads[n] if o in P and o != r)
            if m: s += 1.0 + (2.0 if len(netpads[n]) == 2 else 0.0)
        for part, pad, tg, lim, w in near:
            if part == r and any(tr in P for tr, _ in tg): s += 3.0 * w
        if SEED: s *= 1 + NOISE * (zlib.crc32(f"{r}{SEED}".encode()) % 1000) / 1000.0
        return (s, npads[r], area[r])
    def place_small(r):
        pts = target_window(r)
        if pts:
            xs_ = [p[0] for p in pts]; ys_ = [p[1] for p in pts]; c0 = (min(xs_), min(ys_), max(xs_), max(ys_))
        else:
            bx = boxof.get(r) or box; c0 = tuple(bx)
        best = None
        for grow in (3.0, 6.0, 12.0, 25.0, 80.0):
            best = place(r, (c0[0] - grow, c0[1] - grow, c0[2] + grow, c0[3] + grow), STEP if grow < 20 else 0.25)
            if best is not None: break
        if best is None:
            # no free spot: take the best spot clear of everything but small fill parts, and send those back to the queue
            sm = {q for q in P if q in fill and area[q] < 0.5 * area[r]}
            IGN.update(sm); bx = boxof.get(r) or box
            best = place(r, (min(c0[0], bx[0]) - 6, min(c0[1], bx[1]) - 6, max(c0[2], bx[2]) + 6, max(c0[3], bx[3]) + 6), 0.1)
            if best is None: best = place(r, tuple(box), 0.25)
            IGN.clear()
            if best is None: fails.append(r); return
            P[r] = (best[1], best[2], best[3]); add_obstacle(r)
            Bb = OB[r]; ev = []
            for q in sm:
                if any(s1 == s2 and b1[0] < b2[2] and b1[2] > b2[0] and b1[1] < b2[3] and b1[3] > b2[1] for (s1, b1, k1) in OB[q] if k1 == "b" for (s2, b2, k2) in Bb if k2 == "t") or \
                   any(s1 == s2 and b1[0] < b2[2] and b1[2] > b2[0] and b1[1] < b2[3] and b1[3] > b2[1] for (s1, b1, k1) in OB[q] if k1 == "t" for (s2, b2, k2) in Bb if k2 == "b"):
                    ev.append(q)
            for q in ev: del P[q]; OB.pop(q)
            print(f"  {r}: no free spot, evicted {ev}", flush=True)
            for q in ev: place_small(q)
            return
        P[r] = (best[1], best[2], best[3]); add_obstacle(r)
    def own_support(r):      # small parts tied to r alone: a near statement to r, or a two-pad net to r
        s = set()
        for part, pad, tg, lim, w in near:
            if part in fill and part not in P and npads[part] < BIG_PADS and any(tr == r for tr, _ in tg): s.add(part)
        for n in nets_of(r):
            if len(netpads[n]) == 2:
                for o in netpads[n]:
                    if o != r and o in fill and o not in P and npads[o] < BIG_PADS: s.add(o)
        return s
    log = []
    # 1. large parts
    bigs = sorted([r for r in fill if npads[r] >= BIG_PADS], key=lambda r: -npads[r])
    for r in bigs:
        sup = support(r); need = ROOM_X * sum(area[o] for o in sup if o not in P)
        I = integral(occ_map(sideF[r])); i = ri[r]
        def room(r_, k, xs, ys, I=I, need=need):
            b = rbox(bbx[ri[r_]], k); X = xs[None, :]; Y = ys[:, None]
            fa = free_in(I, X + b[0] - RING, Y + b[1] - RING, X + b[2] + RING, Y + b[3] + RING) - (b[2] - b[0]) * (b[3] - b[1])
            return ROOMW * np.maximum(0, need - fa)
        # second order: a small unplaced part on one of r's pins will sit between that pin and the placed pads of its other nets
        sec = []
        for n, js in nets_of(r).items():
            for o in set(netpads[n]):
                if o in P or o == r or npads[o] > 4: continue
                for j2, v in enumerate(lp[o]):
                    if v[2] == n or not v[2] or v[2] == "GND": continue
                    q = [pad_xy(o2, j3) for o2 in set(netpads[v[2]]) if o2 in P and o2 != r for j3, v3 in enumerate(lp[o2]) if v3[2] == v[2]]
                    if q: sec.append((js, q))
        bx = boxof[r]; cxb = (bx[0] + bx[2]) / 2; cyb = (bx[1] + bx[3]) / 2
        def room2(r_, k, xs, ys, room=room, sec=sec):
            X = xs[None, :]; Y = ys[:, None]; c = room(r_, k, xs, ys) + CENTW * (np.abs(X - cxb) + np.abs(Y - cyb))
            for js, q in sec:
                qx0 = min(a for a, _ in q); qx1 = max(a for a, _ in q); qy0 = min(b for _, b in q); qy1 = max(b for _, b in q)
                for j in js[:1]:
                    ox, oy = rotv(lp[r_][j][0], lp[r_][j][1], k); px = X + ox; py = Y + oy
                    c = c + SECW * (np.maximum(0, qx0 - px) + np.maximum(0, px - qx1) + np.maximum(0, qy0 - py) + np.maximum(0, py - qy1))
            return c
        win = (bx[0] - 8, bx[1] - 8, bx[2] + 8, bx[3] + 8)
        best = place(r, win, 0.25, room2)
        if best is None: best = place(r, (box[0], box[1], box[2], box[3]), 0.25, room2)
        if best is None: raise SystemExit(f"no legal spot for {r}")
        xs1 = np.array([best[1]]); ys1 = np.array([best[2]]); kk = best[3]
        P[r] = (best[1], best[2], best[3]); add_obstacle(r)
        print(f"  {r}: at {best[1]:.1f},{best[2]:.1f} box {[round(v) for v in bx]} cost {best[0]:.0f} wiring {float(wiring(r, kk, xs1, ys1)[0,0]):.0f} room {float(room(r, kk, xs1, ys1)[0,0]):.0f} near {float(near_cost(r, kk, xs1, ys1)[0,0]):.0f} sup {len(sup)} need {need:.0f}", flush=True)
        if INTERLEAVE:
            own = own_support(r)
            while own:
                q = max(own, key=score); own.remove(q); place_small(q)
    # 2. the rest, most connected first
    left = set(fill) - set(P)
    while left:
        r = max(left, key=score); left.remove(r); place_small(r)
    if fails: print("NO SPOT:", fails)
    def cur_cost(r):
        x, y, k = P[r]; xs = np.array([x]); ys = np.array([y])
        return float((wiring(r, k, xs, ys) + near_cost(r, k, xs, ys) + box_cost(r, k, xs, ys) + pwr_cost(r, k, xs, ys))[0, 0])
    for ps in range(int(os.environ.get("PASSES", 3))):
        moved = 0; gain = 0.0
        order = sorted([r for r in fill if r in P and (npads[r] < BIG_PADS or os.environ.get("MOVE_BIG"))], key=lambda r: -score(r)[0])
        for r in order:
            c0 = cur_cost(r); x, y, k = P[r]; del P[r]; ob = OB.pop(r)
            pts = target_window(r) + [(x, y)]
            xs_ = [p[0] for p in pts]; ys_ = [p[1] for p in pts]; g = 3.0
            # keep the current spot on the grid so the search can always fall back to it
            win = (x - STEP * math.ceil((x - min(xs_) + g) / STEP), y - STEP * math.ceil((y - min(ys_) + g) / STEP), max(xs_) + g, max(ys_) + g)
            best = place(r, win, STEP)
            if best is not None and best[0] < c0 - 0.05:
                P[r] = (best[1], best[2], best[3]); moved += 1; gain += c0 - best[0]
            else: P[r] = (x, y, k)
            add_obstacle(r)
        sw = 0
        if SWAP:
            sm = [r for r in fill if r in P and npads[r] < BIG_PADS]
            for ia, a in enumerate(sm):
                for b in sm[ia + 1:]:
                    if sideF[a] != sideF[b] or abs(P[a][0] - P[b][0]) + abs(P[a][1] - P[b][1]) > SWAPD: continue
                    if not (0.5 < area[a] / area[b] < 2.0): continue
                    c0 = cur_cost(a) + cur_cost(b); pa, pb = P[a], P[b]; del P[a], P[b]; OB.pop(a); OB.pop(b)
                    h = 0.3; ok = False
                    ba = place(a, (pb[0] - h, pb[1] - h, pb[0] + h, pb[1] + h), 0.1)
                    if ba is not None:
                        P[a] = ba[1:]; add_obstacle(a)
                        bb_ = place(b, (pa[0] - h, pa[1] - h, pa[0] + h, pa[1] + h), 0.1)
                        if bb_ is not None:
                            P[b] = bb_[1:]; add_obstacle(b)
                            if cur_cost(a) + cur_cost(b) < c0 - 0.2: ok = True
                    if not ok:
                        P.pop(a, None); P.pop(b, None); OB.pop(a, None); OB.pop(b, None)
                        P[a] = pa; P[b] = pb; add_obstacle(a); add_obstacle(b)
                    else: sw += 1
        print(f"pass {ps}: moved {moved}, cost gain {gain:.0f}, swaps {sw}", flush=True)
        if moved == 0 and sw == 0: break
    json.dump({r: [round(P[r][0], 4), round(P[r][1], 4), P[r][2] * 90] for r in fill if r in P}, open(outf, "w"))
    print(f"placed {sum(1 for r in fill if r in P)} of {len(fill)}")

if __name__ == "__main__":
    main(*sys.argv[1:])
