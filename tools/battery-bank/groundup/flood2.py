"""flood2.py dump.npz netregex xa,ya xb,yb out.png (BOX env): two floods (A green, B blue) with the high-current spacing, one picture per layer."""
import sys, re, os, numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = np.load(sys.argv[1]); rx = re.compile(sys.argv[2])
net = [int(c) for n, c in d["nets"] if rx.search(n)][0]
x0, y0, G = d["box"]; g, gv = d["grid"], d["gridv"]
free = np.array([(a == -1) | (a == net) for a in g]) & np.array([(a == -1) | (a == net) for a in d["gridh"]])
via = np.logical_and.reduce([(v == -1) | (v == net) for v in gv]) & np.logical_and.reduce([(v == -1) | (v == net) for v in d["gridvh"]])
st = ndimage.generate_binary_structure(2, 2)
def flood(sx, sy):
    reach = np.zeros_like(free); cx, cy = int(round((sx - x0) / G)), int(round((sy - y0) / G)); reach[:, cy, cx] = free[:, cy, cx]
    for it in range(300):
        n0 = reach.sum()
        for li in range(4):
            lab, _ = ndimage.label(free[li], structure=st); ids = np.unique(lab[reach[li]]); ids = ids[ids > 0]; reach[li] = np.isin(lab, ids)
        anyv = reach.any(axis=0) & via
        for li in range(4): reach[li] |= anyv & free[li]
        if reach.sum() == n0: break
    return reach
A = flood(*[float(v) for v in sys.argv[3].split(",")]); B = flood(*[float(v) for v in sys.argv[4].split(",")])
BOX = [float(v) for v in os.environ["BOX"].split(",")]
names = {int(c): n for n, c in d["nets"]}; cu = d["copper"]
fig, axs = plt.subplots(2, 2, figsize=(24, 24 * (BOX[3] - BOX[1]) / (BOX[2] - BOX[0])), dpi=100)
for li, ax in enumerate(axs.flat):
    im = np.ones(free[li].shape + (3,)); im[~free[li]] = (0.72, 0.72, 0.72); im[(cu[li] >= 0) & (cu[li] != net) & ~free[li]] = (0.5, 0.5, 0.5)
    im[A[li]] = (0.6, 1, 0.6); im[B[li]] = (0.6, 0.8, 1); im[(A[li] | B[li]) & via] *= 0.8
    ax.imshow(im, extent=(x0, x0 + G * free.shape[2], y0 + G * free.shape[1], y0), interpolation="nearest")
    ax.set_title("F In2 In3 B".split()[li]); ax.tick_params(labelsize=7); ax.set_xticks(np.arange(78, 124, 0.5)); ax.set_yticks(np.arange(62, 140, 0.5)); ax.grid(True, lw=0.2)
    ax.set_xlim(BOX[0], BOX[2]); ax.set_ylim(BOX[3], BOX[1])
    cx0, cx1, cy0, cy1 = [int((v - o) / G) for v, o in ((BOX[0], x0), (BOX[2], x0), (BOX[1], y0), (BOX[3], y0))]
    sub = cu[li][cy0:cy1, cx0:cx1]
    for n in np.unique(sub):
        if n < 0: continue
        lab, k = ndimage.label(sub == n)
        for j in range(1, min(k, 6) + 1):
            yy, xx = np.nonzero(lab == j)
            if len(yy) < 30: continue
            m = len(yy) // 2; ax.text(BOX[0] + xx[m] * G, BOX[1] + yy[m] * G, names.get(int(n), "?").split("/")[-1][:10], fontsize=6, color="darkred")
fig.tight_layout(); fig.savefig(sys.argv[5]); print("A", int(A.sum()), "B", int(B.sum()))
