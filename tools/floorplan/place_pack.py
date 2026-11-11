"""place_pack.py <clusters.json> <board dump.json> <out placement.json> [moves] [seed] [refine moves]
Step 2 of the section placer: put the clusters from place_sections.py on the board.
Each cluster moves and turns as one rigid piece (annealing over about 30 pieces); fixed parts stay where the
dump board has them. Cost = half-perimeter of all signal nets at pad level + body overlap + parts off the board.
Step 3 (refine): every part then moves on its own with small steps at low temperature to close the gaps.
Prints the same signal half-perimeter that floorplan.py score reports, so it compares directly with a board."""
import json, sys, math, random
import numpy as np
import floorplan as F

def main(clf, dumpf, outf, moves=60000, seed=1, refine=150000):
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
        c1 = rotv(bbx[:, :2], k); c2 = rotv(bbx[:, 2:], k); lo = xy + np.minimum(c1, c2) - 0.1; hi = xy + np.maximum(c1, c2) + 0.1
        ox = np.minimum(hi[:, None, 0], hi[None, :, 0]) - np.maximum(lo[:, None, 0], lo[None, :, 0])
        oy = np.minimum(hi[:, None, 1], hi[None, :, 1]) - np.maximum(lo[:, None, 1], lo[None, :, 1])
        same = (sideF[:, None] == sideF[None, :]) & ~(fixed[:, None] & fixed[None, :]); np.fill_diagonal(same, False)
        ov = (np.clip(ox, 0, None) * np.clip(oy, 0, None) * same).sum() / 2
        off = (np.clip(box[0] + 0.5 - lo[:, 0], 0, None) + np.clip(lo[:, 0] * 0 + hi[:, 0] - box[2] + 0.5, 0, None) + np.clip(box[1] + 0.5 - lo[:, 1], 0, None) + np.clip(hi[:, 1] - box[3] + 0.5, 0, None))[~fixed].sum()
        return (hp, ov, off) if detail else hp + 30 * ov + 60 * off
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
    print(json.dumps(dict(step="clusters packed", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1))), flush=True)
    # refine: single parts, small steps
    cur = cost(xy, k); mv = np.nonzero(~fixed)[0]; T0, T1 = 1.5, 0.02
    for s in range(refine):
        t = T0 * (T1 / T0) ** (s / refine); i = int(mv[rnd.randrange(len(mv))]); ox, ok = xy[i].copy(), k[i]
        if rnd.random() < 0.1: k[i] = rnd.randrange(4)
        else: rad = 0.2 + 2.0 * (t / T0); xy[i] += (rnd.uniform(-rad, rad), rnd.uniform(-rad, rad))
        new = cost(xy, k)
        if new < cur or rnd.random() < math.exp(-(new - cur) / t): cur = new
        else: xy[i] = ox; k[i] = ok
    a = cost(xy, k, True)
    print(json.dumps(dict(step="refined", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1))))
    json.dump({r: [round(float(xy[i][0]), 3), round(float(xy[i][1]), 3), int(k[i]) * 90] for r, i in ri.items()}, open(outf, "w"))

if __name__ == "__main__":
    main(*sys.argv[1:])
