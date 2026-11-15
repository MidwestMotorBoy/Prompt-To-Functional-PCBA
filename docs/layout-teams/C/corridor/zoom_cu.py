"""zoom_cu.py <scorecard outdir> <out.png> [x0 y0 x1 y1] [net substrings, comma separated]
F.Cu power copper of a scorecard run (spec.json) with the F.Cu pads (cu.json); pads of nets matching the substrings
are labelled REF.PAD. For looking at why plan_copper.py left a terminal to the router."""
import sys, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
d = sys.argv[1]; out = sys.argv[2]; w = [float(v) for v in sys.argv[3:7]] if len(sys.argv) > 6 else [78, 62, 122, 95]
keys = (sys.argv[7] if len(sys.argv) > 7 else "VBUS,PP5V,PPHV").split(",")
cu = json.load(open(d + "/cu.json")); S = json.load(open(d + "/spec.json"))
nets = sorted({z["net"] for z in S["zones"]}); cm = plt.get_cmap("tab20"); col = {n: cm(i % 20) for i, n in enumerate(nets)}
fig, ax = plt.subplots(figsize=(13, 13 * (w[3] - w[1]) / (w[2] - w[0]) + 0.5))
for z in S["zones"]:
    if z["layer"] != "F.Cu": continue
    for p in z["polys"]: ax.add_patch(MP(p["ring"], closed=True, fc=(*col[z["net"]][:3], 0.5), ec="none"))
    ax.plot([], [], color=col[z["net"]], lw=6, label=z["net"])
for t in S.get("tracks", []):
    if t.get("layer") == "F.Cu" and t["net"] in col: ax.plot([t["a"][0], t["b"][0]], [t["a"][1], t["b"][1]], color=col[t["net"]], lw=1)
for p in cu["pads"]:
    for r in p["shapes"].get("F.Cu", []): ax.add_patch(MP(r["ring"], closed=True, fc="none", ec="k" if p["net"] in col else "0.55", lw=0.5))
    if w[0] < p["x"] < w[2] and w[1] < p["y"] < w[3] and p["net"] and any(k in p["net"] for k in keys): ax.text(p["x"], p["y"], f'{p["ref"]}.{p["num"]}', fontsize=6)
ax.legend(fontsize=6, loc="lower right"); ax.set_xlim(w[0], w[2]); ax.set_ylim(w[3], w[1]); ax.set_aspect("equal"); fig.tight_layout(); fig.savefig(out, dpi=90)
