"""sigpic.py out.png "x0,y0,x1,y1" dump1.json "title 1" [dump2.json "title 2" ...] [--nets=regex] [--h=inches]
The signal tracks of several boards side by side (copper dumps from dumpcu.py): every net that is routed as tracks
(no pour) in full colour by layer, pads and poured nets dimmed. With --nets only the matching nets are in colour.
Run with the venv python."""
import json, sys, math, re, collections
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Circle
a = [x for x in sys.argv[1:] if not x.startswith('--')]; OPT = dict(x[2:].split('=', 1) for x in sys.argv[1:] if x.startswith('--'))
out = a[0]; x0, y0, x1, y1 = [float(v) for v in a[1].split(',')]; D = [(json.load(open(a[i])), a[i + 1]) for i in range(2, len(a), 2)]
COL = dict(F='#e25555', In1='#9aa3ad', In2='#f0b43c', In3='#4fc27a', In4='#b98ae6', B='#4f8fe8'); ORD = ['B', 'In4', 'In3', 'In2', 'In1', 'F']
def area(pts): return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
H = float(OPT.get('h', 9)); Wd = H * (x1 - x0) / (y1 - y0)
fig, axs = plt.subplots(1, len(D), figsize=(Wd * len(D) + 0.3, H + 0.9), squeeze=False)
for ax, (d, title) in zip(axs[0], D):
    za = collections.Counter()
    for fl in d['fills']:
        for pts, hs in fl['polys']: za[fl['net']] += area(pts)
    sig = lambda n: bool(n) and za[n] < 3.0 and (re.search(OPT['nets'], n) is not None if 'nets' in OPT else True)
    ax.set_facecolor('#10151c'); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ppmm = 0.86 * Wd * 72 / (x1 - x0)
    inb = lambda x, y, m=1.0: x0 - m < x < x1 + m and y0 - m < y < y1 + m
    tr = [s for s in d['tracks'] if inb(s['x1'], s['y1']) or inb(s['x2'], s['y2'])]
    for L in ORD:
        o = [s for s in tr if s['l'] == L and not sig(s['net'])]
        ax.add_collection(LineCollection([[(s['x1'], s['y1']), (s['x2'], s['y2'])] for s in o], linewidths=[s['w'] * ppmm for s in o], colors='#5b6470', alpha=0.25, capstyle='round'))
    pads = [p for p in d['pads'] if inb(p['x'], p['y'], 3)]
    for L in ('B', 'F'):
        ax.add_collection(PolyCollection([p['L'][L] for p in pads if p['L'].get(L)], facecolors='#7c8794', alpha=0.30, edgecolors='none'))
    for L in ORD:
        m = [s for s in tr if s['l'] == L and sig(s['net'])]
        ax.add_collection(LineCollection([[(s['x1'], s['y1']), (s['x2'], s['y2'])] for s in m], linewidths=[max(s['w'] * ppmm, 0.6) for s in m], colors=COL[L], alpha=0.95, capstyle='round', zorder=5))
    for v in d['vias']:
        if inb(v['x'], v['y']) and sig(v['net']): ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc='#f4f0e6', ec='none', zorder=6))
    ax.set_title(title, fontsize=12, loc='left'); ax.tick_params(colors='#555', labelsize=7)
h = [plt.Line2D([], [], color=COL[L], lw=5, label=L + '.Cu') for L in ('F', 'In2', 'In3', 'In4', 'B')] + [plt.Line2D([], [], marker='o', color='none', markerfacecolor='#f4f0e6', markersize=7, label='via')]
fig.legend(handles=h, loc='lower center', ncol=6, frameon=False, fontsize=10)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out, dpi=int(OPT.get('dpi', 110)))
