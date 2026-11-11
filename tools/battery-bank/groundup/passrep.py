"""passrep.py cu.json router.log out.png "title": whole-board picture of one routing pass, open connections in red."""
import json, sys, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, PathPatch
from matplotlib.path import Path
import rc
d = json.load(open(sys.argv[1])); log = open(sys.argv[2]).read(); out, title = sys.argv[3], sys.argv[4]
fails = [tuple(map(float, m)) for m in re.findall(r"FAILED .*? (-?[\d.]+),(-?[\d.]+) \(.*?\) -> (-?[\d.]+),(-?[\d.]+) \(", log)]
x0, y0, x1, y1 = 78.5, 63.5, 122.5, 137.5
layers = tuple(sys.argv[5].split(',')) if len(sys.argv) > 5 else ('F', 'In2', 'In3', 'B'); names = {'F': 'Front', 'In1': 'Inner 1 (ground plane)', 'In2': 'Inner 2 (PACK+ plane, vertical signals)', 'In3': 'Inner 3 (3V3 plane, horizontal signals)', 'In4': 'Inner 4 (ground plane, slow signals added in the fix pass)', 'B': 'Back'}
scale = 15; n = len(layers)
W, H = (x1 - x0) * scale / 100 * n, (y1 - y0) * scale / 100 + 0.6
fig = plt.figure(figsize=(W, H), dpi=100)
fig.text(0.5, 1 - 0.3 / H, title, ha='center', va='center', fontsize=15)
for i, L in enumerate(layers):
    ax = fig.add_axes([i / n, 0, 1 / n, 1 - 0.6 / H]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.axis('off')
    ax.text(x0 + 0.5, y0 + 1.6, names[L], fontsize=10, color='k')
    for f in d['fills']:
        if f['l'] != L: continue
        for pts, hs in f['polys']:
            verts = list(pts) + [pts[0]]; codes = [Path.MOVETO] + [Path.LINETO] * (len(pts) - 1) + [Path.CLOSEPOLY]
            for h in hs:
                verts += list(h) + [h[0]]; codes += [Path.MOVETO] + [Path.LINETO] * (len(h) - 1) + [Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts, codes), fc=rc.col(f['net']), ec='none', alpha=0.4))
    for t in d['tracks']:
        if t['l'] == L: ax.plot([t['x1'], t['x2']], [t['y1'], t['y2']], color=rc.col(t['net']), lw=max(t['w'] * scale * 0.72, 0.6), solid_capstyle='round')
    for p in d['pads']:
        if L in p['L'] and p['L'][L]: ax.add_patch(Polygon(p['L'][L], fc=rc.col(p['net']), ec='k', lw=0.15))
    for v in d['vias']:
        ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc=rc.col(v['net']), ec='k', lw=0.15))
    if i == 0:
        for a, b, c, e in fails:
            ax.plot([a, c], [b, e], color='red', lw=1.0, alpha=0.9)
            ax.plot([a, c], [b, e], 'o', color='red', ms=2.2)
fig.savefig(out); plt.close(fig)
