"""corridor.py <dump.json> [...]: routing demand against capacity on a 2 mm grid, from placement and power copper only.

Demand: every signal net spreads its half-perimeter length evenly over its pad bounding box (RUDY).
Capacity: on each signal layer, the share of the cell not blocked by pads, power-net copper and power or ground vias,
divided by the track pitch. Signal tracks and signal vias are not read, except to score the result:
`cut` is the length of signal track drawn on a ground-plane layer in each cell."""
import json, sys, math
import numpy as np
PITCH, CELL, CLR = 0.35, 2.0, 0.15

def analyse(f):
    d = json.load(open(f)); x0, y0, x1, y1 = d["box"]; st = d["raster"]["step"]; nx, ny = d["raster"]["nx"], d["raster"]["ny"]
    planes = [l for l in d["layers"] if "GND" in l]; sig = [l for l in d["layers"] if l not in planes]
    zc = {}
    for k, v in d["zones"].items(): zc[k.split("|", 1)[1]] = zc.get(k.split("|", 1)[1], 0) + len(v)
    power = {n for n, c in zc.items() if c >= 200} | {"GND"}
    occ = {l: np.zeros((ny, nx), bool) for l in sig}
    def box(l, a, b, c, e):
        i0, i1 = max(0, int((a - x0) / st)), min(nx - 1, int(math.ceil((c - x0) / st))); j0, j1 = max(0, int((b - y0) / st)), min(ny - 1, int(math.ceil((e - y0) / st)))
        occ[l][j0:j1 + 1, i0:i1 + 1] = True
    for p in d["pads"]:
        for l in p["layers"]:
            if l in occ: box(l, p["box"][0] - CLR, p["box"][1] - CLR, p["box"][2] + CLR, p["box"][3] + CLR)
    for v in d["vias"]:
        if v["net"] in power:
            for l in v["layers"]:
                if l in occ: box(l, v["x"] - v["d"] / 2 - CLR, v["y"] - v["d"] / 2 - CLR, v["x"] + v["d"] / 2 + CLR, v["y"] + v["d"] / 2 + CLR)
    for k, cells in d["zones"].items():
        l, n = k.split("|", 1)
        if l in occ and n in power and n != "GND":
            a = np.array(cells, int); occ[l][a // nx, a % nx] = True
    for t in d["tracks"]:
        if t["net"] in power and t["l"] in occ:
            n = max(2, int(math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) / (st / 2)) + 1)
            for k in range(n):
                x = t["x1"] + (t["x2"] - t["x1"]) * k / (n - 1); y = t["y1"] + (t["y2"] - t["y1"]) * k / (n - 1)
                box(t["l"], x - t["w"] / 2 - CLR, y - t["w"] / 2 - CLR, x + t["w"] / 2 + CLR, y + t["w"] / 2 + CLR)
    q = int(CELL / st); gx, gy = nx // q, ny // q
    cap = sum((~occ[l])[:gy * q, :gx * q].reshape(gy, q, gx, q).mean(axis=(1, 3)) for l in sig) / PITCH       # mm of track per mm2
    per_layer = {l: float((~occ[l]).mean()) for l in sig}
    pads = {}
    for p in d["pads"]:
        if p["net"] and p["net"] not in power: pads.setdefault(p["net"], []).append((p["x"], p["y"]))
    dem = np.zeros((gy, gx)); nets = 0; hp = 0
    for n, pts in pads.items():
        if len(pts) < 2: continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]; w, h = max(max(xs) - min(xs), PITCH), max(max(ys) - min(ys), PITCH)
        nets += 1; hp += w + h
        i0, i1 = (min(xs) - x0) / CELL, (max(xs) - x0) / CELL; j0, j1 = (min(ys) - y0) / CELL, (max(ys) - y0) / CELL
        for j in range(max(0, int(j0)), min(gy, int(j1) + 1)):
            for i in range(max(0, int(i0)), min(gx, int(i1) + 1)):
                ov = (min(i + 1, max(i1, i0 + PITCH / CELL)) - max(i, i0)) * (min(j + 1, max(j1, j0 + PITCH / CELL)) - max(j, j0)) * CELL * CELL
                if ov > 0: dem[j, i] += (w + h) / (w * h) * ov / (CELL * CELL)
    cut = np.zeros((gy, gx)); used = {l: 0.0 for l in d["layers"]}
    for t in d["tracks"]:
        L = math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"])
        if t["net"] in power: continue
        used[t["l"]] += L
        if t["l"] in planes:
            n = max(2, int(L / 0.1) + 1)
            for k in range(n):
                x = t["x1"] + (t["x2"] - t["x1"]) * k / (n - 1); y = t["y1"] + (t["y2"] - t["y1"]) * k / (n - 1)
                i, j = int((x - x0) / CELL), int((y - y0) / CELL)
                if 0 <= i < gx and 0 <= j < gy: cut[j, i] += L / n
    return dict(box=d["box"], sig=sig, planes=planes, power=sorted(power), cap=cap, dem=dem, cut=cut, nets=nets, hpwl=hp, per_layer=per_layer, used=used)

if __name__ == "__main__":
    res = {}
    for f in sys.argv[1:]:
        r = analyse(f); res[f] = r; cap, dem, cut = r["cap"], r["dem"], r["cut"]
        ratio = dem / np.maximum(cap, 1e-6); inside = cap >= 0
        print(f"\n{f}: signal layers {r['sig']}, {r['nets']} signal nets, half-perimeter sum {r['hpwl']:.0f} mm")
        print("  free share per signal layer:", {k.split('.')[0]: round(v, 2) for k, v in r["per_layer"].items()})
        print("  signal track drawn, mm per layer:", {k.split('.')[0]: round(v) for k, v in r["used"].items()})
        print(f"  capacity {cap.sum() * CELL * CELL:.0f} mm of track, demand {dem.sum() * CELL * CELL:.0f} mm, board ratio {dem.sum() / cap.sum():.3f}")
        qs = np.quantile(ratio, [0.5, 0.9, 0.99]); print(f"  cell ratio: median {qs[0]:.2f}, 90th {qs[1]:.2f}, 99th {qs[2]:.2f}, max {ratio.max():.2f}; cells over 0.5: {(ratio > 0.5).sum()}, over 1: {(ratio > 1).sum()} of {ratio.size}")
        tot = cut.sum()
        if tot > 0:
            order = np.argsort(-ratio.ravel()); c = cut.ravel()[order]
            for share in (0.1, 0.2, 0.3):
                k = int(share * ratio.size); print(f"  plane cut {tot:.0f} mm: {c[:k].sum() / tot * 100:.0f} % lies in the {int(share * 100)} % most loaded cells")
            from numpy import corrcoef
            print(f"  correlation of cell ratio with cut length: {corrcoef(ratio.ravel(), cut.ravel())[0, 1]:.2f}")

