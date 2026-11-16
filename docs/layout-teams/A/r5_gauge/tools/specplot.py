"""specplot.py <spec.json> <bare.json> <out.png> x0,y0,x1,y1 [nets regex]: quick matplotlib view of planned copper
(F solid, B hatched outline) plus pads, for checking a planner rule before the scorecard."""
import sys, json, re
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP, Circle
s = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2])); x0, y0, x1, y1 = map(float, sys.argv[4].split(','))
rx = re.compile(sys.argv[5]) if len(sys.argv) > 5 else re.compile('.')
fig, ax = plt.subplots(figsize=(12, 12 * (y1 - y0) / (x1 - x0)))
cols = {}
def col(n):
    if n not in cols: cols[n] = plt.cm.tab20(len(cols) % 20)
    return cols[n]
for z in s['zones']:
    if z['layer'] not in ('F.Cu', 'B.Cu') or not rx.search(z['net']): continue
    for p in z['polys']:
        ring = p['ring'] if isinstance(p, dict) else p[0] if isinstance(p[0][0], (list, tuple)) else p
        if z['layer'] == 'F.Cu': ax.add_patch(MP(ring, closed=True, fc=col(z['net']), alpha=0.45, ec='none'))
        else: ax.add_patch(MP(ring, closed=True, fill=False, ec=col(z['net']), hatch='//', lw=1.2))
for t in s['tracks']:
    if not rx.search(t['net']): continue
    ax.plot([t['a'][0], t['b'][0]], [t['a'][1], t['b'][1]], '-' if t['layer'] == 'F.Cu' else '--', color=col(t['net']), lw=max(1, t['w'] * 20))
for v in s['vias']:
    if x0 <= v['x'] <= x1 and y0 <= v['y'] <= y1: ax.add_patch(Circle((v['x'], v['y']), 0.225, fc='k' if rx.search(v['net']) else 'gray'))
for p in b['pads']:
    if not (x0 - 1 <= p['x'] <= x1 + 1 and y0 - 1 <= p['y'] <= y1 + 1): continue
    for L, rs in p['shapes'].items():
        if L != 'F.Cu': continue
        for r in rs: ax.add_patch(MP(r['ring'], closed=True, fill=False, ec='k', lw=0.6))
    if p.get('npth') or p.get('drill'): ax.add_patch(Circle((p['x'], p['y']), p['drill'] / 2, fill=False, ec='r'))
    ax.text(p['x'], p['y'], f"{p['ref']}.{p['num']}", fontsize=5, ha='center')
for n, c in cols.items(): ax.plot([], [], color=c, label=n[-20:])
ax.legend(fontsize=6, loc='upper right'); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal')
plt.savefig(sys.argv[3], dpi=110, bbox_inches='tight')
