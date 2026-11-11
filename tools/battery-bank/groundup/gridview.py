"""gridview.py dump.npz out.png netregex: what the router sees for one net (white free, green own, grey other, black shared halo; red dots = via sites)"""
import sys, re, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = np.load(sys.argv[1]); rx = re.compile(sys.argv[3])
net = [int(c) for n, c in d["nets"] if rx.search(n)][0]
x0, y0, G = d["box"]; g, gv, cu = d["grid"], d["gridv"], d["copper"]
fig, axs = plt.subplots(1, 4, figsize=(4 * g.shape[2] / 25, g.shape[1] / 25 + 0.3), dpi=100)
for li, ax in enumerate(axs):
    im = np.zeros(g[li].shape + (3,)); a = g[li]
    im[a == -1] = (1, 1, 1); im[(a != -1) & (a != net)] = (0.75, 0.75, 0.75); im[a == -2] = (0.2, 0.2, 0.2); im[a == net] = (0.6, 1, 0.6)
    im[(cu[li] == net) & (a == net)] = (0, 0.7, 0)
    ok = np.logical_and.reduce([(v == -1) | (v == net) for v in gv])
    ext = (x0, x0 + G * a.shape[1], y0 + G * a.shape[0], y0)
    ax.imshow(im, extent=ext, interpolation="nearest"); ys, xs = np.nonzero(ok[::2, ::2] & (a[::2, ::2] == -1))
    ax.plot(x0 + xs * 2 * G, y0 + ys * 2 * G, ".", color="red", ms=1.2); ax.set_title("F In2 In3 B".split()[li], fontsize=8); ax.tick_params(labelsize=6)
fig.tight_layout(); fig.savefig(sys.argv[2])
