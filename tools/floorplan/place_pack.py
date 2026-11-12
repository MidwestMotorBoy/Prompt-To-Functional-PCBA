"""place_pack.py <clusters.json> <board dump.json> <out placement.json> [moves] [seed] [refine moves] [intent.json] [crossing weight, mm per crossing, default 3] [escape room round parts with 12 or more pads, mm, default 0.5]
Step 2 of the section placer: put the clusters from place_sections.py on the board.
Each cluster moves and turns as one rigid piece (annealing over about 30 pieces); fixed parts stay where the
dump board has them. Cost = half-perimeter of all signal nets at pad level + body overlap + parts off the board
+ with an intent file, how far each `near` statement is over its limit and each `keepapart` under it.
Step 3 (refine): every part then moves on its own with small steps at low temperature to close the gaps;
in its last quarter overlap costs far more than wiring, which removes what overlap is left.
Bodies are courtyards when the dump has them; through-hole pads also block the other side; no-footprint keep-outs on a part's side count as overlap.
Step 4 (repair): a small part that still overlaps is moved to the best free spot within 8 mm. A large part
is treated as an anchor: it may take any spot clear of fixed and other large parts, and the small parts round
it are re-annealed.
Prints the same signal half-perimeter that floorplan.py score reports, so it compares directly with a board."""
import json, sys, math, random
FAST_CLUSTER_X = 20        # with the compiled core the cluster stage runs this many times the requested moves
import numpy as np
import floorplan as F
try:
    import fastcore as FC          # compiled refine loop; needs numba
except ImportError:
    FC = None

def main(clf, dumpf, outf, moves=60000, seed=1, refine=150000, intentf=None, wx=3.0, esc=0.5):
    global WX, ESC; WX = float(wx); ESC = float(esc)
    moves, seed, refine = int(moves), int(seed), int(refine); rnd = random.Random(seed)
    cl = json.load(open(clf)); d, pos0, side, blk, pads0 = F.load(dumpf); power = F.power_nets(pads0); box = d["box"]
    refs = sorted({p["ref"] for p in d["pads"]}); ri = {r: i for i, r in enumerate(refs)}; N = len(refs)
    cid = -np.ones(N, int); loc = np.zeros((N, 2)); lrot = np.zeros(N, int); names = list(cl)
    for c, (name, parts) in enumerate(cl.items()):
        xs = [v[0] for v in parts.values()]; ys = [v[1] for v in parts.values()]; cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for r, (x, y, a) in parts.items(): i = ri[r]; cid[i] = c; loc[i] = (x - cx, y - cy); lrot[i] = a // 90
    C = len(names); fixed = cid < 0
    # pads and bodies in each part's own frame
    tbx = np.tile(np.array([1e9, 1e9, -1e9, -1e9]), (N, 1))      # box of a part's pads that reach the other side (through-hole pads, thermal pads on the back)
    pr = []; pl = []; pn = []; bbx = np.tile(np.array([1e9, 1e9, -1e9, -1e9]), (N, 1)); netid = {}
    for p in d["pads"]:
        i = ri[p["ref"]]; x0, y0 = pos0[p["ref"]]; b = p["box"]
        bbx[i] = (min(bbx[i][0], b[0] - x0), min(bbx[i][1], b[1] - y0), max(bbx[i][2], b[2] - x0), max(bbx[i][3], b[3] - y0))
        if "*.Cu" in p["layers"] or ("B.Cu" if side[p["ref"]] == "F.Cu" else "F.Cu") in p["layers"]:
            tbx[i] = (min(tbx[i][0], b[0] - x0), min(tbx[i][1], b[1] - y0), max(tbx[i][2], b[2] - x0), max(tbx[i][3], b[3] - y0))
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
    # escape room: a part with many pads needs space round it for its pins to get out. The first trial route failed on
    # this, not on congestion: 40 of 45 failed connections had no path even on an empty board, nearly all at the ICs,
    # which had 9 to 18 parts within 0.3 mm against 2 to 5 on the scripted board that routes best.
    npads = np.bincount([ri[p["ref"]] for p in d["pads"]], minlength=N); many = (npads >= 12) & ~fixed
    bbx[many] += np.array([-ESC, -ESC, ESC, ESC])
    # a large part on a fixed part (connector, mounting hole, test point) is the failure repair cannot undo on a full board,
    # so it costs ten times an ordinary overlap from the first move
    bigfix = (((bbx[:, 2] - bbx[:, 0]) * (bbx[:, 3] - bbx[:, 1]) > 9.0) & ~fixed)[:, None] & fixed[None, :]; bigfix = bigfix | bigfix.T
    thru = tbx[:, 0] < 1e8; tbx[~thru] = 0.0; TM = 0.15
    # keep-outs; areas outside the real board outline (dump_board.py writes them) get the same 0.5 mm margin as the board box
    KO = [(np.array(k["box"]) + (np.array([-0.5, -0.5, 0.5, 0.5]) if k.get("name") == "outside_board" else 0), "F.Cu" in k["layers"], "B.Cu" in k["layers"]) for k in d.get("keepouts", []) if k.get("no_footprints")]
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
    # crossings: per signal net a spanning tree over its pads (topology refreshed now and then, coordinates always current);
    # two tree edges of different nets that cross cost WX mm. Half-perimeter alone does not see tangles: on Monolith the
    # hand board has 391 crossings, the scripted board 612, and placements that matched the scripted board on length had 800.
    ends_ = np.r_[starts[1:], len(pr)]; TOPO = {}
    def topo(pads):
        ea, eb = [], []
        for n in range(len(starts)):
            a, b = starts[n], ends_[n]; Q = pads[a:b]; m = b - a
            if m < 2: continue
            dist = np.hypot(Q[:, 0] - Q[0, 0], Q[:, 1] - Q[0, 1]); par = np.zeros(m, int); left = np.ones(m, bool); left[0] = False
            for _ in range(m - 1):
                j = int(np.where(left, dist, 1e18).argmin()); left[j] = False; ea.append(a + par[j]); eb.append(a + j)
                dj = np.hypot(Q[:, 0] - Q[j, 0], Q[:, 1] - Q[j, 1]); upd = left & (dj < dist); dist[upd] = dj[upd]; par[upd] = j
        TOPO["a"] = np.array(ea); TOPO["b"] = np.array(eb); TOPO["n"] = pn[TOPO["a"]]
        eop = [[] for _ in range(N)]
        for e, (u, v) in enumerate(zip(ea, eb)):
            eop[pr[u]].append(e)
            if pr[v] != pr[u]: eop[pr[v]].append(e)
        TOPO["of"] = [np.array(x, int) for x in eop]
    def xcount(pads, sel=None):
        A, B, n = TOPO["a"], TOPO["b"], TOPO["n"]; ax, ay, bx, by = pads[A, 0], pads[A, 1], pads[B, 0], pads[B, 1]
        if sel is None: sx, sy, tx, ty, sn = ax, ay, bx, by, n
        else: sx, sy, tx, ty, sn = ax[sel], ay[sel], bx[sel], by[sel], n[sel]
        o = lambda px, py, qx, qy, rx, ry: (qx - px) * (ry - py) - (qy - py) * (rx - px)
        r = lambda v: v[:, None]; c = lambda v: v[None, :]
        X = (o(r(sx), r(sy), r(tx), r(ty), c(ax), c(ay)) * o(r(sx), r(sy), r(tx), r(ty), c(bx), c(by)) < 0) & \
            (o(c(ax), c(ay), c(bx), c(by), r(sx), r(sy)) * o(c(ax), c(ay), c(bx), c(by), r(tx), r(ty)) < 0) & (r(sn) != c(n))
        return int(X.sum()) // (2 if sel is None else 1)
    def cost(xy, k, detail=False):
        pads = xy[pr] + rotv(pl, k[pr])
        if not TOPO: topo(pads)
        xc = xcount(pads) if WX else 0
        hp = (np.maximum.reduceat(pads[:, 0], starts) - np.minimum.reduceat(pads[:, 0], starts) + np.maximum.reduceat(pads[:, 1], starts) - np.minimum.reduceat(pads[:, 1], starts)).sum()
        c1 = rotv(bbx[:, :2], k); c2 = rotv(bbx[:, 2:], k); lo = xy + np.minimum(c1, c2) - 0.02; hi = xy + np.maximum(c1, c2) + 0.02
        ox = np.minimum(hi[:, None, 0], hi[None, :, 0]) - np.maximum(lo[:, None, 0], lo[None, :, 0])
        oy = np.minimum(hi[:, None, 1], hi[None, :, 1]) - np.maximum(lo[:, None, 1], lo[None, :, 1])
        same = (sideF[:, None] == sideF[None, :]) & ~(fixed[:, None] & fixed[None, :]); np.fill_diagonal(same, False)
        ov = (np.clip(ox, 0, None) * np.clip(oy, 0, None) * same * (1 + 9 * bigfix)).sum() / 2
        t1 = rotv(tbx[:, :2], k); t2 = rotv(tbx[:, 2:], k); tlo = xy + np.minimum(t1, t2) - TM; thi = xy + np.maximum(t1, t2) + TM; tlo[~thru] = 1e9; thi[~thru] = -1e9
        tox = np.minimum(thi[:, None, 0], hi[None, :, 0]) - np.maximum(tlo[:, None, 0], lo[None, :, 0]); toy = np.minimum(thi[:, None, 1], hi[None, :, 1]) - np.maximum(tlo[:, None, 1], lo[None, :, 1])
        ov += (np.clip(tox, 0, None) * np.clip(toy, 0, None) * ((sideF[:, None] != sideF[None, :]) & ~(fixed[:, None] & fixed[None, :]))).sum()
        off = (np.clip(box[0] + 0.5 - lo[:, 0], 0, None) + np.clip(lo[:, 0] * 0 + hi[:, 0] - box[2] + 0.5, 0, None) + np.clip(box[1] + 0.5 - lo[:, 1], 0, None) + np.clip(hi[:, 1] - box[3] + 0.5, 0, None))[~fixed].sum()
        for kb, onF, onB in KO:              # courtyard area inside a no-footprint keep-out on the part's side
            m = (~fixed) & ((sideF & onF) | (~sideF & onB))
            ov += (np.clip(np.minimum(hi[m, 0], kb[2]) - np.maximum(lo[m, 0], kb[0]), 0, None) * np.clip(np.minimum(hi[m, 1], kb[3]) - np.maximum(lo[m, 1], kb[1]), 0, None)).sum()
        ic = intent_cost(xy, k)
        return (hp, ov, off, ic, xc) if detail else hp + WOV[0] * ov + 60 * off + 25 * ic + WX * xc
    WOV = [30.0]
    def xy_pads(T): xy_, k_ = parts_xy(T); return xy_[pr] + rotv(pl, k_[pr])
    T = np.array([[rnd.uniform(box[0] + 5, box[2] - 5), rnd.uniform(box[1] + 5, box[3] - 5), rnd.randrange(4)] for _ in range(C)])
    if FC is None:
        cur = cost(*parts_xy(T)); T0, T1 = 60.0, 0.5
        for s in range(moves):
            if WX and s % 200 == 0 and s: topo(xy_pads(T)); cur = cost(*parts_xy(T))
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
    if FC is None: print(json.dumps(dict(step="clusters packed", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1), intent_excess_mm=round(float(a[3]), 1), crossings=int(a[4]))), flush=True)
    # refine: single parts, small steps. Only what the moved part touches is recomputed, so a move costs
    # tens of microseconds and millions of moves are affordable.
    R4 = [((1, 0), (0, 1)), ((0, -1), (1, 0)), ((-1, 0), (0, -1)), ((0, 1), (-1, 0))]
    def r1(v, q): m = R4[q]; return (m[0][0] * v[0] + m[0][1] * v[1], m[1][0] * v[0] + m[1][1] * v[1])
    pads_of = [np.nonzero(pr == i)[0] for i in range(N)]; net_of_pad = np.searchsorted(starts, np.arange(len(pr)), side="right") - 1
    ends = np.r_[starts[1:], len(pr)]; nets_of_part = [np.unique(net_of_pad[p]) for p in pads_of]
    pads = xy[pr] + rotv(pl, k[pr]); topo(pads); apads_of = [np.nonzero(apr == i)[0] for i in range(N)]; q_all = xy[apr] + rotv(apl, k[apr])
    st_of = [[] for _ in range(N)]
    for j, (A, B, lim) in enumerate(nearS):
        for i in set(apr[A]) | set(apr[B]): st_of[i].append(("n", j))
    for j, (A, B, lim) in enumerate(apartS):
        for i in set(apr[A]) | set(apr[B]): st_of[i].append(("a", j))
    def box_of(i, p, kk):
        c1 = r1(bbx[i, :2], kk); c2 = r1(bbx[i, 2:], kk)
        return (p[0] + min(c1[0], c2[0]) - 0.02, p[1] + min(c1[1], c2[1]) - 0.02, p[0] + max(c1[0], c2[0]) + 0.02, p[1] + max(c1[1], c2[1]) + 0.02)
    def tbox_of(i, p, kk):
        if not thru[i]: return (1e9, 1e9, -1e9, -1e9)
        c1 = r1(tbx[i, :2], kk); c2 = r1(tbx[i, 2:], kk)
        return (p[0] + min(c1[0], c2[0]) - TM, p[1] + min(c1[1], c2[1]) - TM, p[0] + max(c1[0], c2[0]) + TM, p[1] + max(c1[1], c2[1]) + TM)
    LO = np.zeros((N, 2)); HI = np.zeros((N, 2)); TLO = np.zeros((N, 2)); THI = np.zeros((N, 2))
    for i in range(N):
        bx = box_of(i, xy[i], int(k[i])); LO[i] = bx[:2]; HI[i] = bx[2:]; bx = tbox_of(i, xy[i], int(k[i])); TLO[i] = bx[:2]; THI[i] = bx[2:]
    opp_side = [np.nonzero((sideF != sideF[i]) & ~(fixed & fixed[i]))[0] for i in range(N)]
    def thru_ov(i, o, tol=0.0):      # through-hole pads of i under parts o on the other side, and theirs under i
        a = 0.0
        for (l1, h1, l2, h2) in ((TLO[i], THI[i], LO[o], HI[o]), (LO[i], HI[i], TLO[o], THI[o])):
            ox = np.minimum(h2[:, 0], h1[0]) - np.maximum(l2[:, 0], l1[0]); oy = np.minimum(h2[:, 1], h1[1]) - np.maximum(l2[:, 1], l1[1])
            m = (ox > tol) & (oy > tol); a += float((ox[m] * oy[m]).sum())
        return a
    same_side = [np.nonzero((sideF == sideF[i]) & (np.arange(N) != i))[0] for i in range(N)]
    def local(i):
        c = 0.0
        for n in nets_of_part[i]:
            seg = pads[starts[n]:ends[n]]; c += seg[:, 0].max() - seg[:, 0].min() + seg[:, 1].max() - seg[:, 1].min()
        if WX and len(TOPO["of"][i]): c += WX * xcount(pads, TOPO["of"][i])
        o = same_side[i]
        ox = np.minimum(HI[o, 0], HI[i, 0]) - np.maximum(LO[o, 0], LO[i, 0]); oy = np.minimum(HI[o, 1], HI[i, 1]) - np.maximum(LO[o, 1], LO[i, 1])
        ov = float((np.clip(ox, 0, None) * np.clip(oy, 0, None) * (1 + 9 * bigfix[i, o])).sum()) + thru_ov(i, opp_side[i])
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
        if thru[i]: bx = tbox_of(i, p, kk); TLO[i] = bx[:2]; THI[i] = bx[2:]
        if len(pads_of[i]): pads[pads_of[i]] = xy[i] + rotv(pl[pads_of[i]], np.full(len(pads_of[i]), kk))
        if len(apads_of[i]): q_all[apads_of[i]] = xy[i] + rotv(apl[apads_of[i]], np.full(len(apads_of[i]), kk))
    mv = np.nonzero(~fixed)[0]
    def anneal(n, T0, T1, legal_from=0.75, only=None):
        pool = mv if only is None else only
        for s in range(n):
            if s == int(n * legal_from): WOV[0] = 400.0
            if WX and s % 50000 == 0 and s: topo(pads)
            t = T0 * (T1 / T0) ** (s / n); i = int(pool[rnd.randrange(len(pool))]); op, ok = xy[i].copy(), int(k[i])
            before = local(i)
            if rnd.random() < 0.1: put(i, op, rnd.randrange(4))
            else: rad = 0.2 + 2.0 * (t / 1.5); put(i, (op[0] + rnd.uniform(-rad, rad), op[1] + rnd.uniform(-rad, rad)), ok)
            dc = local(i) - before
            if not (dc < 0 or rnd.random() < math.exp(-dc / t)): put(i, op, ok)
    # repair. Small parts: best free spot within 8 mm. Large parts (over 9 mm2) are anchors: they may take any spot
    # on the board that is clear of fixed parts and other large parts, pushing small parts aside; the small parts
    # around them are then re-annealed and repaired. This is what a person does: big parts first.
    area = (bbx[:, 2] - bbx[:, 0]) * (bbx[:, 3] - bbx[:, 1]); big = area > 9.0
    def ovl(i, against=None):
        o = same_side[i] if against is None else same_side[i][against[same_side[i]]]
        ox = np.minimum(HI[o, 0], HI[i, 0]) - np.maximum(LO[o, 0], LO[i, 0]); oy = np.minimum(HI[o, 1], HI[i, 1]) - np.maximum(LO[o, 1], LO[i, 1])
        m = (ox > 0.03) & (oy > 0.03); o2 = opp_side[i] if against is None else opp_side[i][against[opp_side[i]]]
        return float((ox[m] * oy[m]).sum()) + thru_ov(i, o2, 0.03)
    def search(i, reach, step, hard=None):
        op, ok = xy[i].copy(), int(k[i]); best = None
        for kk in range(4):
            for dx in np.arange(-reach, reach + 0.01, step):
                for dy in np.arange(-reach, reach + 0.01, step):
                    put(i, (op[0] + dx, op[1] + dy), kk)
                    if LO[i, 0] < box[0] + 0.5 or LO[i, 1] < box[1] + 0.5 or HI[i, 0] > box[2] - 0.5 or HI[i, 1] > box[3] - 0.5: continue
                    if hard is not None and ovl(i, hard) > 0: continue
                    c = local(i)
                    if best is None or c < best[0]: best = (c, xy[i].copy(), kk)
        if best: put(i, best[1], best[2])
        else: put(i, op, ok)
        return best is not None
    if FC is not None:
        i64 = np.int64; csr = lambda L: (np.cumsum([0] + [len(x) for x in L]).astype(i64), np.array([v for x in L for v in x], dtype=i64))
        pp_ptr, pp_idx = csr(pads_of); pn_ptr, pn_idx = csr(nets_of_part); ap_ptr, ap_idx = csr(apads_of)
        S_ = [(0, A, B, lim) for A, B, lim in nearS] + [(1, A, B, lim) for A, B, lim in apartS]
        sk = np.array([q[0] for q in S_], dtype=i64); slim = np.array([q[3] for q in S_], dtype=float)
        sa_ptr, sa_idx = csr([q[1] for q in S_]); sb_ptr, sb_idx = csr([q[2] for q in S_])
        ps_ptr, ps_idx = csr([[j if kind == "n" else len(nearS) + j for kind, j in st_of[i]] for i in range(N)])
        ko = np.array([kb for kb, _, _ in KO], dtype=float).reshape(-1, 4); koF = np.array([f for _, f, _ in KO], dtype=bool); koB = np.array([b for _, _, b in KO], dtype=bool)
        boxa = np.array(box, dtype=float); bigmov = big & ~fixed; k = k.astype(i64); st64, en64, apr64 = starts.astype(i64), ends.astype(i64), apr.astype(i64); E = {}
        def settopo():
            topo(pads); E["a"], E["b"], E["n"] = TOPO["a"].astype(i64), TOPO["b"].astype(i64), TOPO["n"].astype(i64); E["p"], E["i"] = csr(TOPO["of"])
        geom = lambda: (xy, k, fixed, sideF, bigmov, bbx, tbx, thru, LO, HI, TLO, THI)
        tail = lambda: (pads, pl, st64, en64, pp_ptr, pp_idx, pn_ptr, pn_idx, q_all, apr64, apl, ap_ptr, ap_idx, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, E["a"], E["b"], E["n"], E["p"], E["i"])
        def anneal(n, T0, T1, legal_from=0.75, only=None):
            pool = (mv if only is None else only).astype(i64); early = WOV[0]
            for s0 in range(0, n, 50000):
                settopo(); FC.anneal(rnd.randrange(2 ** 31), n, s0, min(n, s0 + 50000), T0, T1, legal_from, early, 400.0, pool, float(WX), TM, boxa, *geom(), *tail())
            WOV[0] = 400.0
        def local(i): return FC.local(i, WOV[0], float(WX), boxa, fixed, sideF, bigmov, thru, LO, HI, TLO, THI, pads, st64, en64, pn_ptr, pn_idx, q_all, apr64, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, E["a"], E["b"], E["n"], E["p"], E["i"])
        def put(i, p, kk): FC.put(i, float(p[0]), float(p[1]), int(kk), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        def ovl(i, against=None): return FC.overlap_area(i, 0.03, against is not None, fixed if against is None else against, fixed, sideF, bigmov, thru, LO, HI, TLO, THI)
        def search(i, reach, step, hard=None): return bool(FC.search(i, float(reach), float(step), hard is not None, fixed if hard is None else hard, WOV[0], float(WX), TM, boxa, *geom(), *tail()))
        settopo()
        # cluster stage, compiled: about 100 times the moves of the numpy loop in the same time, overlap weight rising 30 -> 150
        cid64 = cid.astype(i64); cm_ptr, cm_idx = csr([np.nonzero(cid == c)[0] for c in range(C)]); loc64 = loc.astype(float); lrot64 = lrot.astype(i64)
        uniq = lambda L: sorted({int(v) for x in L for v in x})
        cn_ptr, cn_idx = csr([uniq([nets_of_part[i] for i in np.nonzero(cid == c)[0]]) for c in range(C)])
        cs_ptr, cs_idx = csr([uniq([ps_idx[ps_ptr[i]:ps_ptr[i + 1]] for i in np.nonzero(cid == c)[0]]) for c in range(C)])
        nc = moves * (1 if FAST_CLUSTER_X is None else FAST_CLUSTER_X)
        for s0 in range(0, nc, 20000):
            settopo(); ce_ptr, ce_idx = csr([uniq([TOPO["of"][i] for i in np.nonzero(cid == c)[0]]) for c in range(C)])
            FC.anneal_clusters(rnd.randrange(2 ** 31), nc, s0, min(nc, s0 + 20000), 60.0, 0.5, 30.0, 150.0, float(WX), TM, T, loc64, lrot64, cid64, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx,
                               boxa, *geom(), pads, pl, st64, en64, pp_ptr, pp_idx, q_all, apr64, apl, ap_ptr, ap_idx, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, E["a"], E["b"], E["n"])
        settopo(); a = cost(xy, k, True)
        print(json.dumps(dict(step="clusters packed", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1), intent_excess_mm=round(float(a[3]), 1), crossings=int(a[4]))), flush=True)
        WOV[0] = 30.0
    anneal(refine, 1.5, 0.02)
    repaired = []; hard = fixed | big
    offb = lambda j: LO[j, 0] < box[0] + 0.5 or LO[j, 1] < box[1] + 0.5 or HI[j, 0] > box[2] - 0.5 or HI[j, 1] > box[3] - 0.5
    for rnd_ in range(6):
        stuck = sorted([int(j) for j in mv if ovl(int(j)) > 0 or offb(int(j))], key=lambda j: -area[j])
        if not stuck: break
        for i in stuck:
            if ovl(i) <= 0 and not offb(i): continue
            if big[i] and ovl(i, hard) > 0:
                WOV[0] = 30.0; search(i, 30.0, 0.5, hard); repaired.append(refs[i])
                near_i = np.array([int(j) for j in mv if not big[j] and abs(xy[j][0] - xy[i][0]) < 12 and abs(xy[j][1] - xy[i][1]) < 12])
                if len(near_i): WOV[0] = 400.0; anneal(60000, 0.6, 0.02, 0.0, near_i)
            else:
                WOV[0] = 5000.0; search(i, 8.0, 0.25); repaired.append(refs[i])
    WOV[0] = 400.0
    if repaired: print(json.dumps(dict(step="repaired", parts=repaired)), flush=True)
    topo(pads); a = cost(xy, k, True)
    print(json.dumps(dict(step="refined", signal_half_perimeter_mm=round(float(a[0])), overlap_mm2=round(float(a[1]), 1), off_board_mm=round(float(a[2]), 1), intent_excess_mm=round(float(a[3]), 1), crossings=int(a[4]))))
    json.dump({r: [round(float(xy[i][0]), 3), round(float(xy[i][1]), 3), int(k[i]) * 90] for r, i in ri.items()}, open(outf, "w"))

if __name__ == "__main__":
    main(*sys.argv[1:])
