"""plates_reference.py: independent reference for two parallel plates carrying equal and opposite current along x.
Each plate is cut into N filaments across its width; the current is free to crowd toward the edges (all filaments of a
plate are in parallel), so the answer is the high-frequency loop inductance. Filament mutuals use the exact finite-length
formula; a filament's own term uses the geometric mean distance of a thin tape. Also prints the 2-D parallel-strip
formula (Palmer) times the length, which ignores the two ends."""
import math, sys
import numpy as np
MU0 = 4e-7 * math.pi

def mpar(l, d):                      # mutual of two parallel filaments of length l (m) at distance d (m)
    return MU0 / (2 * math.pi) * l * (np.arcsinh(l / d) - np.sqrt(1 + (d / l) ** 2) + d / l)

def plates(l, w, sep, t_top, t_bot, n):
    dy = w / n; y = (np.arange(n) + 0.5) * dy; r = np.abs(y[:, None] - y[None, :])
    def same(t): rr = r.copy(); np.fill_diagonal(rr, 0.2235 * (dy + t)); return mpar(l, rr)
    lam = same(t_top) + same(t_bot) - 2 * mpar(l, np.hypot(r, sep))
    i = np.linalg.solve(lam, np.ones(n)); return 1 / i.sum(), i / i.sum()

def palmer(l, w, sep):
    k = w / sep; return MU0 * l / (k * (1 + (1 + math.log(2 * math.pi * k)) / (math.pi * k)))

if __name__ == "__main__":
    sep, tt, tb = 0.24375e-3, 0.07e-3, 0.0175e-3
    print("| length x width, mm | filaments, N = 200 / 400 / 800, nH | uniform current, nH | 2-D formula x length, nH |\n|---|---|---|---|")
    for l, w in ((18, 10), (19, 10), (20, 10), (17.75, 10.25), (17.5, 10.5)):
        v = [plates(l * 1e-3, w * 1e-3, sep, tt, tb, n)[0] * 1e9 for n in (200, 400, 800)]
        n = 400; dy = w * 1e-3 / n; y = (np.arange(n) + 0.5) * dy; r = np.abs(y[:, None] - y[None, :]); rr = r.copy(); np.fill_diagonal(rr, 0.2235 * dy)
        uni = (2 * mpar(l * 1e-3, rr) - 2 * mpar(l * 1e-3, np.hypot(r, sep))).sum() / n / n * 1e9
        print(f"| {l} x {w} | {v[0]:.4f} / {v[1]:.4f} / {v[2]:.4f} | {uni:.4f} | {palmer(l * 1e-3, w * 1e-3, sep) * 1e9:.4f} |")
