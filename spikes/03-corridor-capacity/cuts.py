"""cuts.py <dump.json> ...: (a) windowed demand/capacity (6 mm windows), (b) straight cut lines across the board:
nets with pads on both sides against free width on the signal layers along the line."""
import json, sys, math
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0]); import corridor as C
def window(a, k=3):
    p = np.pad(a, k // 2, mode="constant"); out = np.zeros_like(a)
    for dj in range(k):
        for di in range(k): out += p[dj:dj + a.shape[0], di:di + a.shape[1]]
    return out
for f in sys.argv[1:]:
    r = C.analyse(f); d = json.load(open(f)); x0, y0, x1, y1 = r["box"]
    cap, dem, cut = window(r["cap"]), window(r["dem"]), r["cut"]; ratio = dem / np.maximum(cap, 0.05 * cap.max())
    print(f"\n{f}  windowed ratio: median {np.median(ratio):.2f}, 90th {np.quantile(ratio, .9):.2f}, max {ratio.max():.2f}")
    tot = cut.sum(); order = np.argsort(-ratio.ravel()); c = cut.ravel()[order]
    print("  plane-cut share in the most loaded 10/20/30 % of cells:", [round(c[:int(s * ratio.size)].sum() / tot * 100) for s in (.1, .2, .3)], f"of {tot:.0f} mm; corr {np.corrcoef(ratio.ravel(), cut.ravel())[0, 1]:.2f}")
    top = np.dstack(np.unravel_index(order[:5], ratio.shape))[0]
    print("  five most loaded windows (x, y mm, ratio, cut mm in cell):", [(round(x0 + (i + .5) * C.CELL), round(y0 + (j + .5) * C.CELL), round(float(ratio[j, i]), 2), round(float(cut[j, i]), 1)) for j, i in top])
    cj, ci = np.unravel_index(np.argsort(-cut.ravel())[:5], cut.shape)
    print("  five cells with most plane cut (x, y, cut mm, ratio):", [(round(x0 + (i + .5) * C.CELL), round(y0 + (j + .5) * C.CELL), round(float(cut[j, i]), 1), round(float(ratio[j, i]), 2)) for j, i in zip(cj, ci)])
    # cut lines, using the 0.5 mm occupancy rebuilt inside analyse via capacity at cell level
    pads = {}
    for p in d["pads"]:
        if p["net"] and p["net"] not in r["power"]: pads.setdefault(p["net"], []).append((p["x"], p["y"]))
    capc = r["cap"] * C.PITCH                      # free share summed over signal layers per cell (0..4)
    for axis, lo, hi, name in ((1, y0, y1, "horizontal line at y"), (0, x0, x1, "vertical line at x")):
        rows = []
        for k in range(capc.shape[0] if axis == 1 else capc.shape[1]):
            pos = lo + (k + .5) * C.CELL
            n = sum(1 for pts in pads.values() if len(pts) > 1 and min(p[axis] for p in pts) < pos < max(p[axis] for p in pts))
            free = (capc[k, :] if axis == 1 else capc[:, k]).sum() * C.CELL / C.PITCH        # tracks that fit across the line
            cutlen = (cut[k, :] if axis == 1 else cut[:, k]).sum()
            rows.append((pos, n, free, n / max(free, 1), cutlen))
        w = max(rows, key=lambda t: t[3])
        print(f"  worst {name} = {w[0]:.0f}: {w[1]} nets must cross, room for {w[2]:.0f} tracks, ratio {w[3]:.2f}; plane cut on that line {w[4]:.0f} mm")
        print("    ratio along the board:", " ".join(f"{t[3]:.2f}" for t in rows))
        print("    plane cut along board:", " ".join(f"{t[4]:.0f}" for t in rows))
