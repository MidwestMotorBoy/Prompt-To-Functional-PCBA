"""zoom.py cu.json out.png x0,y0,x1,y1 [netregex]: 4-layer close-up from a dumpcu.py JSON, nets labelled (matching nets in red)."""
import json, sys, re, hashlib
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
d = json.load(open(sys.argv[1])); x0, y0, x1, y1 = [float(v) for v in sys.argv[3].split(',')]
rx = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
sn = lambda n: n.split('/')[-1]
def col(n):
    if rx and rx.search(n): return '#e00000'
    if n == 'GND': return '#909090'
    h = hashlib.md5(n.encode()).digest(); return '#%02x%02x%02x' % (40 + h[0] % 150, 40 + h[1] % 150, 60 + h[2] % 160)
inb = lambda x, y, m=0.3: x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m
W = x1 - x0; H = y1 - y0; sc = 9.0 / W
fig, axs = plt.subplots(1, 4, figsize=(36, H * sc + 0.6))
for ax, L in zip(axs, ('F', 'In2', 'In3', 'B')):
    ppu = 9.0 * 72 / W
    for f in d['fills']:
        if f['l'] != L: continue
        for pts, hs in f['polys']:
            if any(inb(x, y, 3) for x, y in pts[::5]): ax.add_patch(Polygon(pts, closed=True, fc=col(f['net']), ec='none', alpha=0.13))
    for p in d['pads']:
        if L in p['L'] and p['L'][L] and inb(p['x'], p['y'], 1):
            ax.add_patch(Polygon(p['L'][L], closed=True, fc=col(p['net']), ec='k', lw=0.3, alpha=0.55))
            ax.text(p['x'], p['y'], '%s.%s\n%s' % (p['ref'], p['n'], sn(p['net'])[:10]), fontsize=4.5, ha='center', va='center')
    seen = set()
    for t in d['tracks']:
        if t['l'] != L or not (inb(t['x1'], t['y1']) or inb(t['x2'], t['y2'])): continue
        ax.plot([t['x1'], t['x2']], [t['y1'], t['y2']], color=col(t['net']), lw=t['w'] * ppu, solid_capstyle='round', alpha=0.85)
        k = (t['net'], round((t['x1'] + t['x2']) / 2), round((t['y1'] + t['y2']) / 2))
        if k not in seen and abs(t['x1'] - t['x2']) + abs(t['y1'] - t['y2']) > 0.25:
            seen.add(k); ax.text((t['x1'] + t['x2']) / 2, (t['y1'] + t['y2']) / 2, sn(t['net'])[:12], fontsize=4.5, color='k', ha='center', va='center')
    for v in d['vias']:
        if inb(v['x'], v['y']):
            ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc=col(v['net']), ec='k', lw=0.5)); ax.add_patch(Circle((v['x'], v['y']), v['drill'] / 2, fc='w', ec='none'))
            ax.text(v['x'], v['y'] - 0.3, sn(v['net'])[:10], fontsize=4, ha='center', color='#333333')
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.set_title(L, fontsize=9); ax.grid(True, lw=0.2); ax.tick_params(labelsize=6)
    import matplotlib.ticker as mt
    ax.xaxis.set_major_locator(mt.MultipleLocator(0.5)); ax.yaxis.set_major_locator(mt.MultipleLocator(0.5))
fig.savefig(sys.argv[2], dpi=100, bbox_inches='tight')
