import sys, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
d = json.load(open(sys.argv[1])); lay = sys.argv[3]; net = sys.argv[4]
import os; Z = float(os.environ.get("Z", 1))
box = [float(v) for v in sys.argv[5].split(',')] if len(sys.argv) > 5 else [77, 61.5, 123, 138.5]
fig, ax = plt.subplots(figsize=((box[2] - box[0]) / 46 * 14 * Z, (box[3] - box[1]) / 46 * 14 * Z))
cols = plt.cm.tab20.colors; k = 0
for l, n, pts in d['z']:
    if l != lay: continue
    ax.add_patch(Polygon(pts, closed=True, fc=cols[k % 20] if n == net else '#dddddd', ec='none', alpha=0.8)); k += 1
for l, n, x0, y0, x1, y1, w in d['t']:
    if l != lay: continue
    ax.plot([x0, x1], [y0, y1], color='red' if n == net else 'black', lw=max(w * 14 * 72 / 46 * 0.9 * Z, 0.3), solid_capstyle='round')
for n, x, y in d['v']:
    if box[0] < x < box[2] and box[1] < y < box[3]:
        ax.plot([x], [y], 'o', ms=0.45 * 14 * 72 / 46 * Z, color='red' if n == net else '#3060ff', mec='none')
ax.set_xlim(box[0], box[2]); ax.set_ylim(box[3], box[1]); ax.set_aspect('equal'); ax.grid(True, lw=0.2)
ax.set_title('%s %s (pieces coloured; black = other-net tracks on this layer, red = own net; dots = vias, red own net)' % (lay, net), fontsize=8)
fig.savefig(sys.argv[2], dpi=110, bbox_inches='tight')
