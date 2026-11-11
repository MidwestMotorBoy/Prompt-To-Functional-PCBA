"""zoomf.py cu.json out.png x0,y0,x1,y1 [layer=F]: one-layer close-up with pad refs, courtyard-free. Bigger than zoom.py."""
import json, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
d = json.load(open(sys.argv[1])); x0, y0, x1, y1 = [float(v) for v in sys.argv[3].split(',')]; L = sys.argv[4] if len(sys.argv) > 4 else 'F'
fig, ax = plt.subplots(figsize=(14, 14 * (y1 - y0) / (x1 - x0)))
import zlib
col = lambda n: plt.cm.tab20(zlib.crc32(n.encode()) % 20)
for f in d['fills']:
    if f['l'] != L: continue
    for poly in f['polys']:
        ax.add_patch(Polygon(poly[0], closed=True, fc=col(f['net']), ec='none', alpha=0.18))
for t in d['tracks']:
    if t['l'] == L: ax.plot([t['x1'], t['x2']], [t['y1'], t['y2']], color=col(t['net']), lw=t['w'] / (x1 - x0) * 14 * 72 * 0.78, solid_capstyle='round', alpha=0.8)
for p in d['pads']:
    if L in p['L'] and x0 - 1 < p['x'] < x1 + 1 and y0 - 1 < p['y'] < y1 + 1:
        ax.add_patch(Polygon(p['L'][L], closed=True, fc=col(p['net']), ec='k', lw=0.6)); ax.text(p['x'], p['y'], f"{p['ref']}.{p['n']}\n{p['net'].split('/')[-1][:12]}", fontsize=5.5, ha='center', va='center')
for v in d['vias']:
    if x0 < v['x'] < x1 and y0 < v['y'] < y1:
        ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc='w', ec=col(v['net']), lw=2)); ax.text(v['x'], v['y'] - 0.3, v['net'].split('/')[-1][:10], fontsize=4.5, ha='center')
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.grid(True, lw=0.3); ax.set_xticks([x0 + 0.5 * i for i in range(int((x1 - x0) / 0.5) + 1)]); ax.set_yticks([y0 + 0.5 * i for i in range(int((y1 - y0) / 0.5) + 1)]); ax.tick_params(labelsize=6)
ax.set_title(L); fig.savefig(sys.argv[2], dpi=110, bbox_inches='tight')
