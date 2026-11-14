"""fastcore.py: the refine loop of place_pack.py compiled with numba (same cost, same moves; about 100 times the speed
of the numpy version, which place_pack.py still uses when numba is not installed). State is passed as flat arrays:
  parts   xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI
  signal pads (sorted by net)  pads, pr, pl, starts, ends; per part: pp_ptr/pp_idx (its pads), pn_ptr/pn_idx (its nets)
  intent pads  q_all, apr, apl; per part ap_ptr/ap_idx; statements: sk (0 near, 1 apart), slim, sa_ptr/sa_idx, sb_ptr/sb_idx;
               per part ps_ptr/ps_idx
  keep-outs  ko (K x 4), koF, koB;   crossing edges  EA, EB, EN; per part pe_ptr/pe_idx;   box (4); reg (N x 4): each part's box from a block floorplan
  (costed like being off the board), x1 <= x0 for none"""
import numpy as np
from numba import njit

@njit(cache=True)
def rot(vx, vy, q):
    if q == 0: return vx, vy
    if q == 1: return -vy, vx
    if q == 2: return -vx, -vy
    return vy, -vx

@njit(cache=True)
def put(i, px, py, kk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx):
    xy[i, 0] = px; xy[i, 1] = py; k[i] = kk
    ax, ay = rot(bbx[i, 0], bbx[i, 1], kk); bx, by = rot(bbx[i, 2], bbx[i, 3], kk)
    LO[i, 0] = px + min(ax, bx) - 0.02; LO[i, 1] = py + min(ay, by) - 0.02; HI[i, 0] = px + max(ax, bx) + 0.02; HI[i, 1] = py + max(ay, by) + 0.02
    if thru[i]:
        ax, ay = rot(tbx[i, 0], tbx[i, 1], kk); bx, by = rot(tbx[i, 2], tbx[i, 3], kk)
        TLO[i, 0] = px + min(ax, bx) - TM; TLO[i, 1] = py + min(ay, by) - TM; THI[i, 0] = px + max(ax, bx) + TM; THI[i, 1] = py + max(ay, by) + TM
    for t in range(pp_ptr[i], pp_ptr[i + 1]):
        j = pp_idx[t]; vx, vy = rot(pl[j, 0], pl[j, 1], kk); pads[j, 0] = px + vx; pads[j, 1] = py + vy
    for t in range(ap_ptr[i], ap_ptr[i + 1]):
        j = ap_idx[t]; vx, vy = rot(apl[j, 0], apl[j, 1], kk); q_all[j, 0] = px + vx; q_all[j, 1] = py + vy

@njit(cache=True)
def overlap_area(i, tol, only_hard, hard, fixed, sideF, big, thru, LO, HI, TLO, THI):
    """body overlap of part i with parts on its side plus far-side pad conflicts; unweighted, pieces under tol ignored"""
    a = 0.0
    for j in range(len(fixed)):
        if j == i or (only_hard and not hard[j]): continue
        if sideF[j] == sideF[i]:
            ox = min(HI[j, 0], HI[i, 0]) - max(LO[j, 0], LO[i, 0]); oy = min(HI[j, 1], HI[i, 1]) - max(LO[j, 1], LO[i, 1])
            if ox > tol and oy > tol: a += ox * oy
        elif not (fixed[i] and fixed[j]):
            if thru[i]:
                ox = min(HI[j, 0], THI[i, 0]) - max(LO[j, 0], TLO[i, 0]); oy = min(HI[j, 1], THI[i, 1]) - max(LO[j, 1], TLO[i, 1])
                if ox > tol and oy > tol: a += ox * oy
            if thru[j]:
                ox = min(THI[j, 0], HI[i, 0]) - max(TLO[j, 0], LO[i, 0]); oy = min(THI[j, 1], HI[i, 1]) - max(TLO[j, 1], LO[i, 1])
                if ox > tol and oy > tol: a += ox * oy
    return a

@njit(cache=True)
def net_hp(n, pads, starts, ends):
    x0 = 1e18; x1 = -1e18; y0 = 1e18; y1 = -1e18
    for p in range(starts[n], ends[n]):
        x = pads[p, 0]; y = pads[p, 1]
        if x < x0: x0 = x
        if x > x1: x1 = x
        if y < y0: y0 = y
        if y > y1: y1 = y
    return x1 - x0 + y1 - y0

@njit(cache=True)
def net_w(n, pads, starts, ends, box):
    """w3 change D: half-perimeter, plus box[5] x the excess over box[4] mm for nets of 2 or 3 pads (box[4..6]: short length, short weight, near weight)"""
    h = net_hp(n, pads, starts, ends)
    if ends[n] - starts[n] <= 3 and h > box[4]: h += box[5] * (h - box[4])
    return h

@njit(cache=True)
def edge_cross(e, pads, EA, EB, EN):
    nx = 0; ax = pads[EA[e], 0]; ay = pads[EA[e], 1]; bx = pads[EB[e], 0]; by = pads[EB[e], 1]; ne = EN[e]
    for f in range(len(EA)):
        if EN[f] == ne: continue
        cx = pads[EA[f], 0]; cy = pads[EA[f], 1]; dx = pads[EB[f], 0]; dy = pads[EB[f], 1]
        d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax); d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
        if d1 * d2 >= 0: continue
        d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx); d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
        if d3 * d4 < 0: nx += 1
    return nx

@njit(cache=True)
def part_ov(i, skip, cid, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB):
    """weighted overlap of part i (parts of cluster `skip` left out; -1 skips none) and how far it is off the board"""
    ov = 0.0
    for j in range(len(fixed)):
        if j == i or (skip >= 0 and cid[j] == skip): continue
        if sideF[j] == sideF[i]:
            ox = min(HI[j, 0], HI[i, 0]) - max(LO[j, 0], LO[i, 0])
            if ox <= 0: continue
            oy = min(HI[j, 1], HI[i, 1]) - max(LO[j, 1], LO[i, 1])
            if oy > 0: ov += ox * oy * (10.0 if ((big[i] and fixed[j]) or (big[j] and fixed[i])) else (box[8] if (big[i] and big[j]) else 1.0))
        elif not (fixed[i] and fixed[j]):
            if thru[i]:
                ox = min(HI[j, 0], THI[i, 0]) - max(LO[j, 0], TLO[i, 0]); oy = min(HI[j, 1], THI[i, 1]) - max(LO[j, 1], TLO[i, 1])
                if ox > 0 and oy > 0: ov += ox * oy
            if thru[j]:
                ox = min(THI[j, 0], HI[i, 0]) - max(TLO[j, 0], LO[i, 0]); oy = min(THI[j, 1], HI[i, 1]) - max(TLO[j, 1], LO[i, 1])
                if ox > 0 and oy > 0: ov += ox * oy
    for q in range(len(koF)):
        if (sideF[i] and koF[q]) or ((not sideF[i]) and koB[q]):
            ox = min(HI[i, 0], ko[q, 2]) - max(LO[i, 0], ko[q, 0]); oy = min(HI[i, 1], ko[q, 3]) - max(LO[i, 1], ko[q, 1])
            if ox > 0 and oy > 0: ov += ox * oy * (box[9] if big[i] else 1.0)
    off = max(0.0, box[0] + 0.5 - LO[i, 0]) + max(0.0, HI[i, 0] - box[2] + 0.5) + max(0.0, box[1] + 0.5 - LO[i, 1]) + max(0.0, HI[i, 1] - box[3] + 0.5)
    return ov, off

@njit(cache=True)
def stmt(s, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx):
    best = 1e18
    for u in range(sa_ptr[s], sa_ptr[s + 1]):
        a = sa_idx[u]
        for v in range(sb_ptr[s], sb_ptr[s + 1]):
            b = sb_idx[v]
            if sk[s] == 1 and apr[a] == apr[b]: continue
            d = (q_all[a, 0] - q_all[b, 0]) ** 2 + (q_all[a, 1] - q_all[b, 1]) ** 2
            if d < best: best = d
    best = np.sqrt(best)
    return max(0.0, best - slim[s]) if sk[s] == 0 else 3.0 * max(0.0, slim[s] - best)

@njit(cache=True)
def local(i, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx,
          q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg):
    c = 0.0
    for t in range(pn_ptr[i], pn_ptr[i + 1]): c += net_w(pn_idx[t], pads, starts, ends, box)
    if WX > 0.0:
        for t in range(pe_ptr[i], pe_ptr[i + 1]): c += WX * edge_cross(pe_idx[t], pads, EA, EB, EN)
    ov, off = part_ov(i, -1, fixed, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB)
    ic = 0.0
    for t in range(ps_ptr[i], ps_ptr[i + 1]): ic += stmt(ps_idx[t], q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx) * (box[6] / 25.0 if sk[ps_idx[t]] == 0 else 1.0)
    if reg[i, 2] > reg[i, 0]:      # a box the part belongs in (a reviewed block floorplan): mm outside it
        off += max(0.0, reg[i, 0] - LO[i, 0]) + max(0.0, HI[i, 0] - reg[i, 2]) + max(0.0, reg[i, 1] - LO[i, 1]) + max(0.0, HI[i, 1] - reg[i, 3])
    return c + wov * ov + 60.0 * off + 25.0 * ic

@njit(cache=True)
def cluster_cost(c, wov, WX, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx, box, fixed, sideF, big, thru, LO, HI, TLO, THI,
                 pads, starts, ends, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg):
    """everything in the cost that changes when cluster c moves as one piece"""
    v = 0.0
    for t in range(cn_ptr[c], cn_ptr[c + 1]): v += net_w(cn_idx[t], pads, starts, ends, box)
    if WX > 0.0:
        for t in range(ce_ptr[c], ce_ptr[c + 1]): v += WX * edge_cross(ce_idx[t], pads, EA, EB, EN)
    for t in range(cm_ptr[c], cm_ptr[c + 1]):
        i = cm_idx[t]; ov, off = part_ov(i, c, cid, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB)
        if reg[i, 2] > reg[i, 0]:
            off += max(0.0, reg[i, 0] - LO[i, 0]) + max(0.0, HI[i, 0] - reg[i, 2]) + max(0.0, reg[i, 1] - LO[i, 1]) + max(0.0, HI[i, 1] - reg[i, 3])
        v += wov * ov + box[7] * off
    for t in range(cs_ptr[c], cs_ptr[c + 1]): v += (box[6] if sk[cs_idx[t]] == 0 else 25.0) * stmt(cs_idx[t], q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx)
    return v

@njit(cache=True)
def set_cluster(c, T, loc, lrot, cm_ptr, cm_idx, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx):
    ck = int(T[c, 2])
    for t in range(cm_ptr[c], cm_ptr[c + 1]):
        i = cm_idx[t]; vx, vy = rot(loc[i, 0], loc[i, 1], ck)
        put(i, T[c, 0] + vx, T[c, 1] + vy, (lrot[i] + ck) % 4, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)

@njit(cache=True)
def anneal_clusters(seed, n, s_from, s_to, T0, T1, wov0, wov1, WX, TM, T, loc, lrot, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx,
                    box, xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, starts, ends, pp_ptr, pp_idx, q_all, apr, apl, ap_ptr, ap_idx,
                    sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg, rad0, rad1):
    """rigid clusters: shift (70 %), turn (20 %), swap places with another cluster (10 %); overlap weight rises from wov0 to wov1"""
    np.random.seed(seed); C = len(T)
    for s in range(s_from, s_to):
        t = T0 * (T1 / T0) ** (s / n); wov = wov0 + (wov1 - wov0) * s / n; c = np.random.randint(C); u = np.random.random(); e = -1
        if 0.2 <= u < 0.3 and C > 1:
            e = np.random.randint(C)
            if e == c: continue
        before = cluster_cost(c, wov, WX, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg)
        if e >= 0: before += cluster_cost(e, wov, WX, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg)
        o0 = T[c, 0]; o1 = T[c, 1]; o2 = T[c, 2]
        if u < 0.2: T[c, 2] = np.random.randint(4)
        elif e >= 0:
            T[c, 0] = T[e, 0]; T[c, 1] = T[e, 1]; T[e, 0] = o0; T[e, 1] = o1
            set_cluster(e, T, loc, lrot, cm_ptr, cm_idx, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        else:
            rad = rad0 + rad1 * (t / T0); T[c, 0] += np.random.uniform(-rad, rad); T[c, 1] += np.random.uniform(-rad, rad)
        set_cluster(c, T, loc, lrot, cm_ptr, cm_idx, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        after = cluster_cost(c, wov, WX, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg)
        if e >= 0: after += cluster_cost(e, wov, WX, cid, cm_ptr, cm_idx, cn_ptr, cn_idx, cs_ptr, cs_idx, ce_ptr, ce_idx, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ko, koF, koB, EA, EB, EN, reg)
        dc = after - before
        if not (dc < 0 or np.random.random() < np.exp(-dc / t)):
            if e >= 0:
                T[e, 0] = T[c, 0]; T[e, 1] = T[c, 1]
                set_cluster(e, T, loc, lrot, cm_ptr, cm_idx, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
            T[c, 0] = o0; T[c, 1] = o1; T[c, 2] = o2
            set_cluster(c, T, loc, lrot, cm_ptr, cm_idx, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)

@njit(cache=True)
def anneal(seed, n, s_from, s_to, T0, T1, legal_from, wov_early, wov_late, pool, WX, TM, box, xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI,
           pads, pl, starts, ends, pp_ptr, pp_idx, pn_ptr, pn_idx, q_all, apr, apl, ap_ptr, ap_idx,
           sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg, ppart, area, plong, pswap, lspread):
    np.random.seed(seed); late = int(n * legal_from)
    for s in range(s_from, s_to):
        wov = wov_late if s >= late else wov_early
        t = T0 * (T1 / T0) ** (s / n); i = pool[np.random.randint(len(pool))]; ox = xy[i, 0]; oy = xy[i, 1]; ok = k[i]
        before = local(i, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
        u = np.random.random(); j = -1
        if u < pswap:            # w3 change B: swap with a part of similar size on the same side
            j = pool[np.random.randint(len(pool))]
            if j == i or sideF[j] != sideF[i] or area[j] > 1.4 * area[i] or area[i] > 1.4 * area[j]: continue
            jx = xy[j, 0]; jy = xy[j, 1]; jk = k[j]
            before += local(j, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
            put(i, jx, jy, ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
            put(j, ox, oy, jk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        elif u < pswap + plong:  # w3 change B: long move to near the centroid of the other pads of its nets
            sx = 0.0; sy = 0.0; nn = 0
            for t2 in range(pn_ptr[i], pn_ptr[i + 1]):
                nt = pn_idx[t2]; cx = 0.0; cy = 0.0; m = 0
                for p in range(starts[nt], ends[nt]):
                    if ppart[p] != i: cx += pads[p, 0]; cy += pads[p, 1]; m += 1
                if m > 0: sx += cx / m; sy += cy / m; nn += 1
            if nn == 0: continue
            if box[10] > 0:      # legal long move: the first of up to box[10] random spots round the centroid that is clear of parts and keep-outs
                got = False
                for tr in range(int(box[10])):
                    sp = lspread * (1.0 + 4.0 * tr / box[10])
                    put(i, sx / nn + np.random.uniform(-sp, sp), sy / nn + np.random.uniform(-sp, sp), np.random.randint(4), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
                    if LO[i, 0] < box[0] + 0.5 or LO[i, 1] < box[1] + 0.5 or HI[i, 0] > box[2] - 0.5 or HI[i, 1] > box[3] - 0.5: continue
                    bad = False
                    for q in range(len(koF)):
                        if (sideF[i] and koF[q]) or ((not sideF[i]) and koB[q]):
                            if min(HI[i, 0], ko[q, 2]) - max(LO[i, 0], ko[q, 0]) > 0.0 and min(HI[i, 1], ko[q, 3]) - max(LO[i, 1], ko[q, 1]) > 0.0:
                                bad = True; break
                    if bad: continue
                    if overlap_area(i, 0.0, False, fixed, fixed, sideF, big, thru, LO, HI, TLO, THI) > 0: continue
                    got = True; break
                if not got:
                    put(i, ox, oy, ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx); continue
            else:
                put(i, sx / nn + np.random.uniform(-lspread, lspread), sy / nn + np.random.uniform(-lspread, lspread), np.random.randint(4), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        elif u < pswap + plong + 0.1:
            put(i, ox, oy, np.random.randint(4), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        else:
            rad = 0.2 + 2.0 * (t / 1.5)
            put(i, ox + np.random.uniform(-rad, rad), oy + np.random.uniform(-rad, rad), ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        after = local(i, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
        if j >= 0: after += local(j, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
        dc = after - before
        if not (dc < 0 or np.random.random() < np.exp(-dc / t)):
            put(i, ox, oy, ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
            if j >= 0: put(j, jx, jy, jk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)

@njit(cache=True)
def search(i, reach, step, use_hard, hard, wov, WX, TM, box, xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI,
           pads, pl, starts, ends, pp_ptr, pp_idx, pn_ptr, pn_idx, q_all, apr, apl, ap_ptr, ap_idx,
           sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg):
    """best spot for part i within reach (all four turns); with use_hard only spots clear of the hard parts"""
    ox = xy[i, 0]; oy = xy[i, 1]; ok = k[i]; best = 1e300; bx = ox; by = oy; bk = ok; found = False; m = int(round(2 * reach / step)) + 1
    for kk in range(4):
        for a in range(m):
            for b in range(m):
                px = ox - reach + a * step; py = oy - reach + b * step
                put(i, px, py, kk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
                if LO[i, 0] < box[0] + 0.5 or LO[i, 1] < box[1] + 0.5 or HI[i, 0] > box[2] - 0.5 or HI[i, 1] > box[3] - 0.5: continue
                if use_hard and overlap_area(i, 0.03, True, hard, fixed, sideF, big, thru, LO, HI, TLO, THI) > 0: continue
                c = local(i, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
                if c < best: best = c; bx = px; by = py; bk = kk; found = True
    put(i, bx, by, bk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
    return found

@njit(cache=True)
def search_legal(i, reach, step, use_hard, hard, wov, WX, TM, box, xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI,
                 pads, pl, starts, ends, pp_ptr, pp_idx, pn_ptr, pn_idx, q_all, apr, apl, ap_ptr, ap_idx,
                 sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg):
    """w3 change C: cheapest spot for part i within reach (all four turns) that is clear of every part, every keep-out on
    its side and the board edge; the part stays where it is when there is none"""
    ox = xy[i, 0]; oy = xy[i, 1]; ok = k[i]; best = 1e300; bx = ox; by = oy; bk = ok; found = False; m = int(round(2 * reach / step)) + 1
    for kk in range(4):
        for a in range(m):
            for b in range(m):
                px = ox - reach + a * step; py = oy - reach + b * step
                put(i, px, py, kk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
                if LO[i, 0] < box[0] + 0.5 or LO[i, 1] < box[1] + 0.5 or HI[i, 0] > box[2] - 0.5 or HI[i, 1] > box[3] - 0.5: continue
                if box[11] > 0 and reg[i, 2] > reg[i, 0] and (LO[i, 0] < reg[i, 0] or LO[i, 1] < reg[i, 1] or HI[i, 0] > reg[i, 2] or HI[i, 1] > reg[i, 3]): continue
                bad = False
                for q in range(len(koF)):
                    if (sideF[i] and koF[q]) or ((not sideF[i]) and koB[q]):
                        if min(HI[i, 0], ko[q, 2]) - max(LO[i, 0], ko[q, 0]) > 0.03 and min(HI[i, 1], ko[q, 3]) - max(LO[i, 1], ko[q, 1]) > 0.03:
                            bad = True; break
                if bad: continue
                if overlap_area(i, 0.03, use_hard, hard, fixed, sideF, big, thru, LO, HI, TLO, THI) > 0: continue
                c = local(i, wov, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
                c += 0.05 * ((px - ox) ** 2 + (py - oy) ** 2) ** 0.5
                if c < best: best = c; bx = px; by = py; bk = kk; found = True
    put(i, bx, by, bk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
    return found

@njit(cache=True)
def is_legal(i, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB):
    if LO[i, 0] < box[0] + 0.5 or LO[i, 1] < box[1] + 0.5 or HI[i, 0] > box[2] - 0.5 or HI[i, 1] > box[3] - 0.5: return False
    for q in range(len(koF)):
        if (sideF[i] and koF[q]) or ((not sideF[i]) and koB[q]):
            if min(HI[i, 0], ko[q, 2]) - max(LO[i, 0], ko[q, 0]) > 0.03 and min(HI[i, 1], ko[q, 3]) - max(LO[i, 1], ko[q, 1]) > 0.03: return False
    return overlap_area(i, 0.03, False, fixed, fixed, sideF, big, thru, LO, HI, TLO, THI) == 0.0

@njit(cache=True)
def anneal_legal(seed, n, T0, T1, pool, WX, TM, box, xy, k, fixed, sideF, big, bbx, tbx, thru, LO, HI, TLO, THI,
                 pads, pl, starts, ends, pp_ptr, pp_idx, pn_ptr, pn_idx, q_all, apr, apl, ap_ptr, ap_idx,
                 sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg, ppart, area, plong, pswap, lspread):
    """w3: detailed placement that keeps every part legal: a move that leaves a part overlapping, on a keep-out or off the
    board is undone before it is scored; shifts, turns, swaps of similar parts and long moves near the centroid of its nets"""
    np.random.seed(seed); acc = 0
    for s in range(n):
        t = T0 * (T1 / T0) ** (s / n); i = pool[np.random.randint(len(pool))]; ox = xy[i, 0]; oy = xy[i, 1]; ok = k[i]; j = -1
        before = local(i, 400.0, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
        u = np.random.random()
        if u < pswap:
            j = pool[np.random.randint(len(pool))]
            if j == i or sideF[j] != sideF[i] or area[j] > 1.4 * area[i] or area[i] > 1.4 * area[j]: continue
            jx = xy[j, 0]; jy = xy[j, 1]; jk = k[j]
            before += local(j, 400.0, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
            put(i, jx, jy, ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
            put(j, ox, oy, jk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        elif u < pswap + plong:
            sx = 0.0; sy = 0.0; nn = 0
            for t2 in range(pn_ptr[i], pn_ptr[i + 1]):
                nt = pn_idx[t2]; cx = 0.0; cy = 0.0; m = 0
                for p in range(starts[nt], ends[nt]):
                    if ppart[p] != i: cx += pads[p, 0]; cy += pads[p, 1]; m += 1
                if m > 0: sx += cx / m; sy += cy / m; nn += 1
            if nn == 0: continue
            put(i, sx / nn + np.random.uniform(-lspread, lspread), sy / nn + np.random.uniform(-lspread, lspread), np.random.randint(4), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        elif u < pswap + plong + 0.1:
            put(i, ox, oy, np.random.randint(4), TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        else:
            rad = 0.1 + 1.5 * (t / T0)
            put(i, ox + np.random.uniform(-rad, rad), oy + np.random.uniform(-rad, rad), ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        legal = is_legal(i, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB)
        if legal and j >= 0: legal = is_legal(j, box, fixed, sideF, big, thru, LO, HI, TLO, THI, ko, koF, koB)
        if legal:
            after = local(i, 400.0, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
            if j >= 0: after += local(j, 400.0, WX, box, fixed, sideF, big, thru, LO, HI, TLO, THI, pads, starts, ends, pn_ptr, pn_idx, q_all, apr, sk, slim, sa_ptr, sa_idx, sb_ptr, sb_idx, ps_ptr, ps_idx, ko, koF, koB, EA, EB, EN, pe_ptr, pe_idx, reg)
            dc = after - before
            if dc < 0 or np.random.random() < np.exp(-dc / t):
                acc += 1; continue
        put(i, ox, oy, ok, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
        if j >= 0: put(j, jx, jy, jk, TM, xy, k, bbx, tbx, thru, LO, HI, TLO, THI, pads, pl, pp_ptr, pp_idx, q_all, apl, ap_ptr, ap_idx)
    return acc
