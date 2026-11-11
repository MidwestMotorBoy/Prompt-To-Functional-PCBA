"""lanes.py <dump.json> ...: how many tracks can actually pass a band of the board, against how many nets must.

Free space is rastered at one track pitch per signal layer (blocked: pads, power-net copper, power and ground vias).
For a band 6 mm deep across the board, the capacity is the largest number of separate paths through free cells from one
side of the band to the other on one layer (maximum flow, so pockets and dead ends count for nothing), summed over the
signal layers. Demand is the number of signal nets with pads on both sides of the band's centre line.
Only placement and power copper are read. Signal tracks are used to score: `cut` = signal track on a ground-plane layer."""
import json, sys, math
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_flow
P, CLR, DEPTH, STEP = 0.35, 0.15, 6.0, 2.0

def occupancy(d):
    x0, y0, x1, y1 = d["box"]; nx, ny = int((x1 - x0) / P), int((y1 - y0) / P)
    planes = [l for l in d["layers"] if "GND" in l]; sig = [l for l in d["layers"] if l not in planes]
    zc = {}
    for k, v in d["zones"].items(): zc[k.split("|", 1)[1]] = zc.get(k.split("|", 1)[1], 0) + len(v)
    power = {n for n, c in zc.items() if c >= 200} | {"GND"}
    occ = {l: np.zeros((ny, nx), bool) for l in sig}
    def box(l, a, b, c, e):
        i0, i1 = max(0, int((a - x0) / P)), min(nx - 1, int((c - x0) / P)); j0, j1 = max(0, int((b - y0) / P)), min(ny - 1, int((e - y0) / P))
        if i1 >= i0 and j1 >= j0: occ[l][j0:j1 + 1, i0:i1 + 1] = True
    for p in d["pads"]:
        for l in p["layers"]:
            if l in occ: box(l, p["box"][0] - CLR, p["box"][1] - CLR, p["box"][2] + CLR, p["box"][3] + CLR)
    for v in d["vias"]:
        if v["net"] in power:
            for l in sig: box(l, v["x"] - v["d"] / 2 - CLR, v["y"] - v["d"] / 2 - CLR, v["x"] + v["d"] / 2 + CLR, v["y"] + v["d"] / 2 + CLR)
    zs = d["raster"]["step"]; znx = d["raster"]["nx"]
    for k, cells in d["zones"].items():
        l, n = k.split("|", 1)
        if l in occ and n in power and n != "GND":
            for c in cells: box(l, x0 + (c % znx) * zs - zs / 2, y0 + (c // znx) * zs - zs / 2, x0 + (c % znx) * zs + zs / 2, y0 + (c // znx) * zs + zs / 2)
    for t in d["tracks"]:
        if t["net"] in power and t["l"] in occ:
            n = max(2, int(math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) / (P / 2)) + 1)
            for k in range(n):
                x = t["x1"] + (t["x2"] - t["x1"]) * k / (n - 1); y = t["y1"] + (t["y2"] - t["y1"]) * k / (n - 1)
                box(t["l"], x - t["w"] / 2 - CLR, y - t["w"] / 2 - CLR, x + t["w"] / 2 + CLR, y + t["w"] / 2 + CLR)
    return occ, sig, planes, power

def flow(free):
    """Largest number of cell-disjoint paths from the first row to the last row of a boolean array of free cells."""
    h, w = free.shape; idx = -np.ones((h, w), int); idx[free] = np.arange(free.sum()); n = int(free.sum())
    if n == 0: return 0
    src, dst = 2 * n, 2 * n + 1; r, c = [], []
    ins = idx[free]; r += list(ins); c += list(ins + n)                            # in -> out, capacity 1
    for dj, di in ((0, 1), (1, 0)):
        a = idx[:h - dj, :w - di]; b = idx[dj:, di:]; m = (a >= 0) & (b >= 0)
        r += list(a[m] + n); c += list(b[m]); r += list(b[m] + n); c += list(a[m])
    top = idx[0][idx[0] >= 0]; bot = idx[-1][idx[-1] >= 0]
    r += [src] * len(top); c += list(top); r += list(bot + n); c += [dst] * len(bot)
    g = csr_matrix((np.ones(len(r), np.int32), (r, c)), shape=(2 * n + 2, 2 * n + 2))
    return maximum_flow(g, src, dst).flow_value

def profile(d, occ, sig, planes, power, axis):
    x0, y0, x1, y1 = d["box"]; lo, hi = (y0, y1) if axis == 1 else (x0, x1); rows = []
    pads = {}
    for p in d["pads"]:
        if p["net"] and p["net"] not in power: pads.setdefault(p["net"], []).append((p["x"], p["y"]))
    pos = lo + DEPTH / 2 + 1
    while pos < hi - DEPTH / 2 - 1:
        a, b = int((pos - DEPTH / 2 - lo) / P), int((pos + DEPTH / 2 - lo) / P)
        per = {l: flow(~occ[l][a:b, :] if axis == 1 else ~occ[l][:, a:b].T) for l in sig}
        straight = sum(int((~(occ[l][int((pos - lo) / P), :] if axis == 1 else occ[l][:, int((pos - lo) / P)])).sum()) for l in sig)
        need = [n for n, pts in pads.items() if len(pts) > 1 and min(p[axis] for p in pts) < pos - 0.01 and max(p[axis] for p in pts) > pos + 0.01]
        cut = 0.0
        for t in d["tracks"]:
            if t["l"] in planes and t["net"] not in ("GND",):
                u1, u2 = (t["y1"], t["y2"]) if axis == 1 else (t["x1"], t["x2"])
                if min(u1, u2) <= pos <= max(u1, u2): cut += 1
        rows.append(dict(pos=pos, need=len(need), cap=sum(per.values()), per=per, straight=straight, crossing_on_plane=int(cut)))
        pos += STEP
    return rows

if __name__ == "__main__":
    out = {}
    for f in sys.argv[1:]:
        d = json.load(open(f)); occ, sig, planes, power = occupancy(d)
        print(f"\n{f}: free share per layer", {l.split('.')[0]: round(float((~occ[l]).mean()), 2) for l in sig})
        for axis, name in ((1, "bands across the board at y (tracks running along the board's length)"), (0, "bands at x (tracks running across)")):
            rows = profile(d, occ, sig, planes, power, axis); out[f"{f}|{axis}"] = rows
            print(" ", name)
            print("   pos   need  lanes  straight  need/lanes  per layer                 signal segments on a plane layer here")
            for r in rows:
                print(f"   {r['pos']:5.0f} {r['need']:5d} {r['cap']:6d} {r['straight']:9d} {r['need'] / max(r['cap'], 1):10.2f}   {' '.join(f'{k.split(chr(46))[0]}:{v}' for k, v in r['per'].items()):25s} {r['crossing_on_plane']}")
    json.dump(out, open("lanes.json", "w"), default=int)
