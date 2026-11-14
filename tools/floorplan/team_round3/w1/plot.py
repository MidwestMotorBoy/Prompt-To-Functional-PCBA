"""plot.py <dump> <fill placement> <out.png> [nets to draw, comma]  quick view of both sides"""
import json, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.path.insert(0, "/home/claude/work/team/w1"); from metrics import pads_at, rot
d = json.load(open(sys.argv[1])); cl = json.load(open("/home/claude/work/hp/q7s2_fz_clusters.json")); fill = {r: k for k, v in cl.items() for r in v}
P = {r: v for r, v in json.load(open(sys.argv[2])).items() if r in fill}; B = json.load(open("/home/claude/work/team/w1/bodies.json")); ri = {r: i for i, r in enumerate(B["refs"])}
fp = json.load(open("/home/claude/work/bfp7/floorplan_2.json"))["blocks"]
fig, axs = plt.subplots(1, 2, figsize=(16, 14))
secs = sorted(set(fill.values())); cmap = plt.get_cmap("tab20")
pads = pads_at(d, P)
for ax, s in zip(axs, ("F.Cu", "B.Cu")):
    ax.set_title(s); box = B["box"]; ax.add_patch(Rectangle((box[0], box[1]), box[2] - box[0], box[3] - box[1], fill=False))
    for kb, f, b in B["KO"]:
        if (f and s == "F.Cu") or (b and s == "B.Cu"): ax.add_patch(Rectangle((kb[0], kb[1]), kb[2] - kb[0], kb[3] - kb[1], color="#ddd", lw=0))
    for name, bx in fp.items():
        if name.endswith(s) and name in cl: ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=False, ec=cmap(secs.index(name) % 20), ls="--", lw=1))
    for f in d["fps"]:
        if f["side"] != s: continue
        r = f["ref"]; b = B["bbx"][ri[r]] if r in ri else None
        if b is None: continue
        if r in P: x, y, a = P[r]; k = int(a) // 90
        else: x, y, k = f["x"], f["y"], 0
        c1 = rot(b[0], b[1], k); c2 = rot(b[2], b[3], k); x0 = x + min(c1[0], c2[0]); y0 = y + min(c1[1], c2[1]); w = abs(c2[0] - c1[0]); h = abs(c2[1] - c1[1])
        col = cmap(secs.index(fill[r]) % 20) if r in P else "#555"
        ax.add_patch(Rectangle((x0, y0), w, h, color=col, alpha=0.6 if r in P else 0.5, lw=0))
        if w * h > 4 or r in P: ax.text(x, y, r, fontsize=4 if w * h < 9 else 6, ha="center", va="center")
    ax.set_xlim(box[0] - 1, box[2] + 1); ax.set_ylim(box[3] + 1, box[1] - 1); ax.set_aspect("equal")
if len(sys.argv) > 4:
    for n in sys.argv[4].split(","):
        q = [(p["x"], p["y"]) for p in pads if p["net"] == n]
        for ax in axs: ax.plot([a for a, _ in q], [b for _, b in q], "r.-", lw=0.6, ms=3)
plt.tight_layout(); plt.savefig(sys.argv[3], dpi=110)
