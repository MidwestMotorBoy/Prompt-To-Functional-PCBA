"""crossings.py <board dump.json> [placement.json]: how tangled a placement's signal wiring is before any routing.
Per signal net a minimum spanning tree over its pads; counts pairs of tree edges from different nets that cross.
Also the worst 10 x 10 mm window by crossings, and total tree length. Power nets (floorplan.power_nets) are left out."""
import json, sys, math, collections
import numpy as np
import floorplan as F
def edges(dumpf, placef=None):
    d, pos0, side, blk, pads0 = F.load(dumpf); power = F.power_nets(pads0); P = json.load(open(placef)) if placef else {}
    nets = collections.defaultdict(dict)
    for p in d["pads"]:
        n = p["net"]
        if not n or n in power: continue
        x0, y0 = pos0[p["ref"]]; lx, ly = p["x"] - x0, p["y"] - y0; x, y, a = P.get(p["ref"], [x0, y0, 0])
        for _ in range(int(a) // 90 % 4): lx, ly = -ly, lx
        nets[n].setdefault((p["ref"], p["num"]), (x + lx, y + ly))
    E = []
    for ni, (n, pp) in enumerate(sorted(nets.items())):
        Q = list(pp.values())
        if len(Q) < 2: continue
        best = {j: (math.dist(Q[j], Q[0]), 0) for j in range(1, len(Q))}
        while best:
            j = min(best, key=lambda q: best[q][0]); dd, i = best.pop(j); E.append((ni, *Q[i], *Q[j]))
            for q in best:
                dq = math.dist(Q[q], Q[j])
                if dq < best[q][0]: best[q] = (dq, j)
    return np.array(E), d["box"]
def count(E, box):
    n, ax, ay, bx, by = E.T; o = lambda px, py, qx, qy, rx, ry: (qx - px) * (ry - py) - (qy - py) * (rx - px)
    A = lambda v: v[:, None]; B = lambda v: v[None, :]
    d1 = o(A(ax), A(ay), A(bx), A(by), B(ax), B(ay)); d2 = o(A(ax), A(ay), A(bx), A(by), B(bx), B(by))
    d3 = o(B(ax), B(ay), B(bx), B(by), A(ax), A(ay)); d4 = o(B(ax), B(ay), B(bx), B(by), A(bx), A(by))
    X = (d1 * d2 < 0) & (d3 * d4 < 0) & (A(n) != B(n)); i, j = np.nonzero(np.triu(X, 1))
    # crossing points, for the window count
    t = d3[i, j] / (d3[i, j] - d4[i, j]); cx = ax[i] + t * (bx[i] - ax[i]); cy = ay[i] + t * (by[i] - ay[i])
    H, _, _ = np.histogram2d(cx, cy, bins=[np.arange(box[0], box[2] + 5, 5), np.arange(box[1], box[3] + 5, 5)])
    W = H[:-1, :-1] + H[1:, :-1] + H[:-1, 1:] + H[1:, 1:]; k = np.unravel_index(W.argmax(), W.shape)
    return dict(connections=len(E), tree_length_mm=round(float(np.hypot(bx - ax, by - ay).sum())), crossings=int(len(i)), worst_10mm_window=int(W.max()),
                worst_window_at=[round(box[0] + 5 * k[0] + 5, 1), round(box[1] + 5 * k[1] + 5, 1)])
if __name__ == "__main__":
    print(json.dumps(count(*edges(*sys.argv[1:]))))
