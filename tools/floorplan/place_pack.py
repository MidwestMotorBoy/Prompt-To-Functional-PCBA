"""place_pack.py <clusters.json> <board dump.json> <out placement.json> [moves] [seed] [refine moves] [intent.json]
Step 2 of the section placer: put the clusters from place_sections.py on the board.
Each cluster moves and turns as one rigid piece (annealing over about 30 pieces); fixed parts stay where the
dump board has them. Cost = half-perimeter of all signal nets at pad level + body overlap + parts off the board
+ with an intent file, how far each `near` statement is over its limit and each `keepapart` under it.
Step 3 (refine): every part then moves on its own with small steps at low temperature to close the gaps;
in its last quarter overlap costs far more than wiring, which removes what overlap is left.
Bodies are courtyards when the dump has them; no-footprint keep-outs on a part's side count as overlap.
Step 4 (repair): a part that still overlaps is moved to the best free spot within 8 mm.
Prints the same signal half-perimeter that floorplan.py score reports, so it compares directly with a board."""
import json, sys, math, random
import numpy as np
import floorplan as F

def main(clf, dumpf, outf, moves=60000, seed=1, refine=150000, intentf=None):
    moves, seed, refine = int(moves), int(seed), int(refine); rnd = random.Random(seed)
    cl = json.load(open(clf)); d, pos0, side, blk, pads0 = F.load(dumpf); power = F.power_nets(pads0); box = d["box"]
    refs = sorted({p["ref"] for p in d["pads"]}); ri = {r: i for i, r in enumerate(refs)}; N = len(refs)
    cid = -np.ones(N, int); loc = np.zeros((N, 2)); lrot = np.zeros(N, int); names = list(cl)
    for c, (name, parts) in enumerate(cl.items()):
        xs = [v[0] for v in parts.values()]; ys = [v[1] for v in parts.values()]; cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for r, (x, y, a) in parts.items(): i = ri[r]; cid[i] = c; loc[i] = (x - cx, y - cy); lrot[i] = a // 90
    C = len(names); fixed = cid < 0
    # pads and bodies in each part's own frame
    pr = []; pl = []; pn = []; bbx = np.tile(np.array([1e9, 1e9, -1e9, -1e9]), (N, 1)); netid = {}
    for p in d["pads"]:
        i = ri[p["ref"]]; x0, y0 = pos0[p["ref"]]; b = p["box"]
        bbx[i] = (min(bbx[i][0], b[0] - x0), min(bbx[i][1], b[1] - y0), max(bbx[i][2], b[2] - x0), max(bbx[i][3], b[3] - y0))
        if p["net"] and p["net"] not in power and len(pads0[p["net"]]) >= 2:
            pr.append(i); pl.append((p["x"] - x0, p["y"] - y0)); pn.append(netid.setdefault(p["net"], len(netid)))
    # intent statements as cost terms: near (excess distance) and keepapart (shortfall)
    ap = [(ri[p["ref"]], p["x"] - pos0[p["ref"]][0], p["y"] - pos0[p["ref"]][1], p["num"], p["net"]) for p in d["pads"]]
    apr = np.array([a[0] for a in ap]); apl = np.array([[a[1], a[2]] for a in ap]); nearS = []; apartS = []
    if intentf:
        it = json.load(open(intentf))
        for st in it.get("near", []):
            A = [j for j, a in enumerate(ap) if refs[a[0]] == st["part"]]
            B = [j for j, a in enumerate(ap) for t in st["to"] if (f"{refs[a[0]]}.{a[3]}" == t or refs[a[0]] == t)]
            if A and B: nearS.append((np.array(A), np.array(B), st["max_mm"]))
        for st in it.get("keepapart", []):
            A = [j for j, a in enumerate(ap) if a[4] in st["a_nets"]]; B = [j for j, a in enumerate(ap) if a[4] in st["b_nets"]]
            if A and B: apartS.append((np.array(A), np.array(B), st["min_mm"]))
    def intent_cost(xy, k):
        if not nearS and not apartS: return 0.0
        q = xy[apr] + rotv(apl, k[apr]); c = 0.0
        for A, B, lim in nearS:
            dd = np.sqrt(((q[A][:, None, :] - q[B][None, :, :]) ** 2).sum(-1)).min(); c += max(0.0, dd - lim)
        for A, B, lim in apartS:
            dd = np.sqrt(((q[A][:, None, :] - q[B][None, :, :]) ** 2).sum(-1)); dd[apr[A][:, None] == apr[B][None, :]] = 1e9; c += 3 * max(0.0, lim - dd.min())
        return c
    for f in d["fps"]:
        if "court" in f and f["ref"] in ri:
            i = ri[f["ref"]]; c = f["court"]; bbx[i] = (min(bbx[i][0], c[0] - f["x"]), min(bbx[i][1], c[1] - f["y"]), max(bbx[i][2], c[2] - f["x"]), max(bbx[i][3], c[3] - f["y"]))
    KO = [(np.array(k["box"]), "F.Cu" in k["layers"], "B.Cu" in k["layers"]) for k in d.get("keepouts", []) if k.get("no_footprints")]
    pr = np.array(pr); pl = np.array(pl); pn = np.array(pn); order = np.argsort(pn, kind="stable"); pr, pl, pn = pr[order], pl[order], pn[order]
    starts = np.r_[0, np.nonzero(np.diff(pn))[0] + 1]
    sideF = np.array([side[r] == "F.Cu" for r in refs]); p0 = np.array([pos0[r] for r in refs])
    R = [np.array([[1, 0], [0, 1]]), np.array([[0, -1], [1, 0]]), np.array([[-1, 0], [0, -1]]), np.array([[0, 1], [-1, 0]])]
    def rotv(v, k):          # rows of v turned by k quarter turns (k array)
        out = v.copy()
        for q in (1, 2, 3):
            m = k == q
            if m.any(): out[m] = v[m] @ R[q].T
        return out
    def parts_xy(T):         # T: C x 3 (x, y, k) -> part centres and part rotations
        xy = p0.copy(); k = np.zeros(N, int); m = ~fixed; ck = T[cid[m], 2].astype(int)
        xy[m] = T[cid[m], :2] + rotv(loc[m], ck); k[m] = (lrot[m] + ck) % 4
        return xy, k
    def cost(xy, k, detail=False):
        pads = xy[pr] + rotv(pl, k[pr])
        hp = (np.maximum.reduceat(pads[:, 0], starts) - np.minimum.reduceat(pads[:, 0], starts) + np.maximum.reduceat(pads[:, 1], starts) - np.minimum.reduceat(pads[:, 1], starts)).sum()
        c1 = rotv(bbx[:, :2], k); c2 = rotv(bbx[:, 2:], k); lo = xy + np.minimum(c1, c2) - 0.02; hi = xy + np.maximum(c1, c2) + 0.02
        ox = np.minimum(hi[:, None, 0], hi[None, :, 0]) - np.maximum(lo[:, None, 0], lo[None, :, 0])
        oy = np.minimum(hi[:, None, 1], hi[None, :, 1]) - np.maximum(lo[:, None, 1], lo[None, :, 1])
        same = (sideF[:, None] == sideF[None, :]) & ~(fixed[:, None] & fixed[None, :]); np.fill_diagonal(same, False)
        ov = (np.clip(ox, 0, None) * np.clip(oy, 0, None) * same).sum() / 2
        off = (np.clip(box[0] + 0.5 - lo[:, 0], 0, None) + np.clip(lo[:, 0] * 0 + hi[:, 0] - box[2] + 0.5, 0, None) + np.clip(box[1] + 0.5 - lo[:, 1], 0, None) + np.clip(hi[:, 1] - box[3] + 0.5, 0, None))[~fixed].sum()
        for kb, onF, onB in KO:              # courtyard area inside a no-footprint keep-out on the part's side
            m = (~fixed) & ((sideF & onF) | (~sideF & onB))
            ov += (np.clip(np.minimum(hi[m, 0], kb[2]) - np.maximum(lo[m, 0], kb[0]), 0, None) * np.clip(np.minimum(hi[m, 1], kb[3]) - np.maximum(lo[m, 1], kb[1]), 0, None)).sum()
        ic = intent_cost(xy, k)
        return (hp, ov, off, ic) if detail else hp + WOV[0] * ov + 60 * off + 25 * ic
    WOV = [30.0]
    T = np.array([[rnd.uniform(box[0] + 5, box[2] - 5), rnd.uniform(box[1] + 5, box[3] - 5), rnd.randrange(4)] for _ in range(C)])
    cur = cost(*parts_xy(T)); T0, T1 = 60.0, 0.5
    for s in range(moves):
        t = T0 * (T1 / T0) ** (s / moves); c = rnd.randrange(C); old = T[c].copy(); u = rnd.random()
        if u < 0.2: T[c, 2] = rnd.randrange(4)
        elif u < 0.3 and C > 1:
            e = rnd.randrange(C); T[[c, e], :2] = T[[e, c], :2]; olde = e
        else: rad = 0.5 + 25 * (t / T0); T[c, 0] += rnd.uniform(-rad, rad); T[c, 1] += rnd.uniform(-rad, rad)
        new = cost(*parts_xy(T))
        if new < cur or rnd.random() < math.exp(-(new - cur) / t): cur = new
        else:
            if 0.2 <= u < 0.3 and C > 1: T[[c, olde], :2] = T[[olde, c], :2]
            else: T[c] = old
    xy, k = parts_xy(T); a = cost(xy, k, True)
    print(json.dumps(dict(step="clusters packed", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1), intent_excess_mm=round(float(a[3]), 1))), flush=True)
    # refine: single parts, small steps. Only what the moved part touches is recomputed, so a move costs
    # tens of microseconds and millions of moves are affordable.
    R4 = [((1, 0), (0, 1)), ((0, -1), (1, 0)), ((-1, 0), (0, -1)), ((0, 1), (-1, 0))]
    def r1(v, q): m = R4[q]; return (m[0][0] * v[0] + m[0][1] * v[1], m[1][0] * v[0] + m[1][1] * v[1])
    pads_of = [np.nonzero(pr == i)[0] for i in range(N)]; net_of_pad = np.searchsorted(starts, np.arange(len(pr)), side="right") - 1
    ends = np.r_[starts[1:], len(pr)]; nets_of_part = [np.unique(net_of_pad[p]) for p in pads_of]
    pads = xy[pr] + rotv(pl, k[pr]); apads_of = [np.nonzero(apr == i)[0] for i in range(N)]; q_all = xy[apr] + rotv(apl, k[apr])
    st_of = [[] for _ in range(N)]
    for j, (A, B, lim) in enumerate(nearS):
        for i in set(apr[A]) | set(apr[B]): st_of[i].append(("n", j))
    for j, (A, B, lim) in enumerate(apartS):
        for i in set(apr[A]) | set(apr[B]): st_of[i].append(("a", j))
    def box_of(i, p, kk):
        c1 = r1(bbx[i, :2], kk); c2 = r1(bbx[i, 2:], kk)
        return (p[0] + min(c1[0], c2[0]) - 0.02, p[1] + min(c1[1], c2[1]) - 0.02, p[0] + max(c1[0], c2[0]) + 0.02, p[1] + max(c1[1], c2[1]) + 0.02)
    LO = np.zeros((N, 2)); HI = np.zeros((N, 2))
    for i in range(N): bx = box_of(i, xy[i], int(k[i])); LO[i] = bx[:2]; HI[i] = bx[2:]
    same_side = [np.nonzero((sideF == sideF[i]) & (np.arange(N) != i))[0] for i in range(N)]
    def local(i):
        c = 0.0
        for n in nets_of_part[i]:
            seg = pads[starts[n]:ends[n]]; c += seg[:, 0].max() - seg[:, 0].min() + seg[:, 1].max() - seg[:, 1].min()
        o = same_side[i]
        ox = np.minimum(HI[o, 0], HI[i, 0]) - np.maximum(LO[o, 0], LO[i, 0]); oy = np.minimum(HI[o, 1], HI[i, 1]) - np.maximum(LO[o, 1], LO[i, 1])
        ov = float((np.clip(ox, 0, None) * np.clip(oy, 0, None)).sum())
        for kb, onF, onB in KO:
            if (sideF[i] and onF) or (not sideF[i] and onB):
                ov += max(0.0, min(HI[i, 0], kb[2]) - max(LO[i, 0], kb[0])) * max(0.0, min(HI[i, 1], kb[3]) - max(LO[i, 1], kb[1]))
        off = max(0.0, box[0] + 0.5 - LO[i, 0]) + max(0.0, HI[i, 0] - box[2] + 0.5) + max(0.0, box[1] + 0.5 - LO[i, 1]) + max(0.0, HI[i, 1] - box[3] + 0.5)
        ic = 0.0
        for kind, j in st_of[i]:
            A, B, lim = nearS[j] if kind == "n" else apartS[j]
            dd = np.sqrt(((q_all[A][:, None, :] - q_all[B][None, :, :]) ** 2).sum(-1))
            if kind == "n": ic += max(0.0, dd.min() - lim)
            else: dd[apr[A][:, None] == apr[B][None, :]] = 1e9; ic += 3 * max(0.0, lim - dd.min())
        return c + WOV[0] * ov + 60 * off + 25 * ic
    def put(i, p, kk):
        xy[i] = p; k[i] = kk; bx = box_of(i, p, kk); LO[i] = bx[:2]; HI[i] = bx[2:]
        if len(pads_of[i]): pads[pads_of[i]] = xy[i] + rotv(pl[pads_of[i]], np.full(len(pads_of[i]), kk))
        if len(apads_of[i]): q_all[apads_of[i]] = xy[i] + rotv(apl[apads_of[i]], np.full(len(apads_of[i]), kk))
    mv = np.nonzero(~fixed)[0]; T0, T1 = 1.5, 0.02
    for s in range(refine):
        if s == int(refine * 0.75): WOV[0] = 400.0
        t = T0 * (T1 / T0) ** (s / refine); i = int(mv[rnd.randrange(len(mv))]); op, ok = xy[i].copy(), int(k[i])
        before = local(i)
        if rnd.random() < 0.1: put(i, op, rnd.randrange(4))
        else: rad = 0.2 + 2.0 * (t / T0); put(i, (op[0] + rnd.uniform(-rad, rad), op[1] + rnd.uniform(-rad, rad)), ok)
        dc = local(i) - before
        if not (dc < 0 or rnd.random() < math.exp(-dc / t)): put(i, op, ok)
    # repair: a part still overlapping something (usually a large part stuck against a fixed one) is moved to the
    # best free spot within 8 mm, searched on a 0.25 mm grid in all four rotations.
    def ovl(i):
        o = same_side[i]; ox = np.minimum(HI[o, 0], HI[i, 0]) - np.maximum(LO[o, 0], LO[i, 0]); oy = np.minimum(HI[o, 1], HI[i, 1]) - np.maximum(LO[o, 1], LO[i, 1])
        m = (ox > 0.03) & (oy > 0.03); return float((ox[m] * oy[m]).sum())
    WOV[0] = 5000.0; repaired = []
    for i in [int(j) for j in mv if ovl(int(j)) > 0]:
        if ovl(i) <= 0: continue
        op, ok = xy[i].copy(), int(k[i]); best = (local(i), op, ok)
        for kk in range(4):
            for dx in np.arange(-8, 8.01, 0.25):
                for dy in np.arange(-8, 8.01, 0.25):
                    put(i, (op[0] + dx, op[1] + dy), kk); c = local(i)
                    if c < best[0]: best = (c, xy[i].copy(), kk)
        put(i, best[1], best[2]); repaired.append(refs[i])
    if repaired: print(json.dumps(dict(step="repaired", parts=repaired)), flush=True)
    a = cost(xy, k, True)
    print(json.dumps(dict(step="refined", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1), intent_excess_mm=round(float(a[3]), 1))))
    json.dump({r: [round(float(xy[i][0]), 3), round(float(xy[i][1]), 3), int(k[i]) * 90] for r, i in ri.items()}, open(outf, "w"))

if __name__ == "__main__":
    main(*sys.argv[1:])
