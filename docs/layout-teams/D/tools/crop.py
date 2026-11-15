"""crop.py <dir> <board> x0 y0 x1 y1 out.png [net to highlight ...]: the four signal layers of a window side by side,
pads / tracks / vias / pours with short net names, for deciding a hand route. Highlighted nets are drawn red."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
from shapely.geometry import box as sbox
from mroute import MR
from obst import SIG
d, board = sys.argv[1:3]; x0, y0, x1, y1 = map(float, sys.argv[3:7]); out = sys.argv[7]; hl = set(sys.argv[8:])
m = MR(d, board); win = sbox(x0, y0, x1, y1)
COL = {"pad": "#c9a227", "track": "#2a6fdb", "via": "#444444", "pour": "#b8e0b8", "hole": "#000000"}
fig, axs = plt.subplots(2, 2, figsize=(22, 22 * (y1 - y0) / (x1 - x0)))
for ax, L in zip(axs.flat, SIG):
    seen = set()
    for kind_pass in ("pour", "pad", "track", "via", "hole"):
        for i in m.tree[L].query(win):
            geo, n, kind, name = m.items[L][int(i)]
            if kind != kind_pass: continue
            g = geo.intersection(win)
            for q in (g.geoms if hasattr(g, "geoms") else [g]):
                if q.is_empty or q.geom_type != "Polygon": continue
                c = "#e02020" if n in hl and kind != "pour" else ("#f5b0b0" if n in hl else ("#d9c6e8" if kind == "pour" and n != "GND" else COL.get(kind, "#999")))
                ax.add_patch(MP(list(q.exterior.coords), closed=True, fc=c, ec="k" if kind != "pour" else "none", lw=0.3, alpha=0.55 if kind == "pour" else 0.9))
                if kind == "pour" and n == "GND": continue
                p = q.representative_point(); short = n.split("/")[-1].replace("Net-(", "").replace(")", "")
                key = (short, round(p.x), round(p.y)) if kind in ("track", "pour") else (name or short, round(p.x, 1), round(p.y, 1))
                if key in seen: continue
                seen.add(key)
                ax.text(p.x, p.y, (name + ":" if kind == "pad" and name else "") + short, fontsize=5.5 if kind != "pour" else 7, ha="center", va="center", color="k")
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal"); ax.set_title(L); ax.grid(True, lw=0.2)
    ax.set_xticks([x0 + i for i in range(int(x1 - x0) + 1)]); ax.set_yticks([y0 + i for i in range(int(y1 - y0) + 1)])
plt.tight_layout(); plt.savefig(out, dpi=110)
