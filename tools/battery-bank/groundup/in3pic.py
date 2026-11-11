"""in3pic.py cu.json out.png [layer=In3] [net=3V3]: one layer, the plane net's fill pieces each in its own colour, tracks of other nets in black with labels."""
import json, sys
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
d = json.load(open(sys.argv[1])); L = sys.argv[3] if len(sys.argv) > 3 else 'In3'; N = sys.argv[4] if len(sys.argv) > 4 else '3V3'
fig, ax = plt.subplots(figsize=(22, 36)); cm = plt.get_cmap('tab20'); k = 0
for f in d['fills']:
    if f['l'] != L or f['net'] != N: continue
    for pts, hs in f['polys']:
        ax.add_patch(Polygon(pts, closed=True, fc=cm(k % 20), ec='k', lw=0.3, alpha=0.5)); k += 1
        for hh in hs: ax.add_patch(Polygon(hh, closed=True, fc='white', ec='none'))
seen = set()
for t in d['tracks']:
    if t['l'] != L: continue
    c = 'red' if t['net'] == N else 'k'
    ax.plot([t['x1'], t['x2']], [t['y1'], t['y2']], color=c, lw=1.6, solid_capstyle='round')
    key = (t['net'], round((t['x1'] + t['x2']) / 6), round((t['y1'] + t['y2']) / 6))
    if key not in seen and abs(t['x1'] - t['x2']) + abs(t['y1'] - t['y2']) > 1.5:
        seen.add(key); ax.text((t['x1'] + t['x2']) / 2, (t['y1'] + t['y2']) / 2, t['net'].split('/')[-1][:12], fontsize=6, color='blue')
for v in d['vias']:
    ax.plot(v['x'], v['y'], 'o', ms=3, color='red' if v['net'] == N else '#888888')
ax.set_xlim(78, 122); ax.set_ylim(138, 62); ax.set_aspect('equal'); ax.grid(lw=0.2)
ax.set_xticks(range(78, 123, 2)); ax.set_yticks(range(62, 139, 2))
fig.savefig(sys.argv[2], dpi=70, bbox_inches='tight'); print(k, 'pieces')
