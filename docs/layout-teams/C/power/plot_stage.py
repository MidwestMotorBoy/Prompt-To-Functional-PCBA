"""plot_stage.py <dump.json> <placement.json> <out.png> [x0,y0,x1,y1]
Quick look at a placement without KiCad: courtyards (grey), pads coloured by net (supply/return/switch/other), part
names. Only for looking at the stage shapes between scorecard runs; the scorecard renders are what count."""
import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def rot(x, y, k):
    for _ in range(k % 4): x, y = -y, x
    return x, y

def rbox(b, k):
    a = rot(b[0], b[1], k); c = rot(b[2], b[3], k); return min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])

d = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])); win = [float(v) for v in sys.argv[4].split(",")] if len(sys.argv) > 4 else d["box"]
fp = {f["ref"]: f for f in d["fps"]}
def pose(r):
    f = fp[r]; v = P.get(r)
    if v is None: return f["x"], f["y"], 0, False
    return v[0], v[1], int(v[2]) // 90, len(v) > 3 and (v[3] == "F") != (f["side"] == "F.Cu")
col = lambda n: "red" if not n else ("#2a7" if n == "GND" else "#c30" if "PACK_P" in n or "AC_SNS" in n or "BAT_SNS" in n else "#36c" if "SW" in n else "#a6c" if "PP5V" in n or "3V3" in n else "#999")
fig, ax = plt.subplots(figsize=(12, 12 * (win[3] - win[1]) / (win[2] - win[0])))
for f in d["fps"]:
    x, y, k, fl = pose(f["ref"])
    if not (win[0] - 5 < x < win[2] + 5 and win[1] - 5 < y < win[3] + 5) or "court" not in f: continue
    c = f["court"]; b = (c[0] - f["x"], c[1] - f["y"], c[2] - f["x"], c[3] - f["y"])
    if fl: b = (-b[2], b[1], -b[0], b[3])
    b = rbox(b, k); onB = (f["side"] == "B.Cu") != fl
    ax.add_patch(Rectangle((x + b[0], y + b[1]), b[2] - b[0], b[3] - b[1], fill=False, ec="#88f" if onB else "#444", lw=0.6, ls="--" if onB else "-"))
    ax.text(x, y, f["ref"], fontsize=6, ha="center", va="center", color="#00a" if onB else "k")
for p in d["pads"]:
    f = fp[p["ref"]]; x, y, k, fl = pose(p["ref"])
    if not (win[0] - 5 < x < win[2] + 5 and win[1] - 5 < y < win[3] + 5): continue
    b = (p["box"][0] - f["x"], p["box"][1] - f["y"], p["box"][2] - f["x"], p["box"][3] - f["y"])
    if fl: b = (-b[2], b[1], -b[0], b[3])
    b = rbox(b, k); onB = ("B.Cu" in p["layers"]) != fl and "*.Cu" not in p["layers"]
    ax.add_patch(Rectangle((x + b[0], y + b[1]), b[2] - b[0], b[3] - b[1], color=col(p["net"]), alpha=0.25 if onB else 0.7, lw=0))
ax.set_xlim(win[0], win[2]); ax.set_ylim(win[3], win[1]); ax.set_aspect("equal"); ax.grid(alpha=0.2)
plt.savefig(sys.argv[3], dpi=110, bbox_inches="tight")
