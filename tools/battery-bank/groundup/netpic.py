"""netpic.py out.png NET "x0,y0,x1,y1[;x0,y0,x1,y1...]" before.json after.json [title_before] [title_after]
Before / after picture of one net from two copper dumps (dumpcu.py): the net in full colour by layer, everything
else dimmed. One row per box. Run with the venv python."""
import json, sys, math
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Circle
out, NET, boxes = sys.argv[1], sys.argv[2], [[float(v) for v in b.split(',')] for b in sys.argv[3].split(';')]
D = [json.load(open(sys.argv[4])), json.load(open(sys.argv[5]))]; T = (sys.argv[6:8] + ['before', 'after'])[:2] if len(sys.argv) > 6 else ['before', 'after']
COL = dict(F='#e25555', In2='#f0b43c', In3='#4fc27a', B='#4f8fe8'); ORD = ['B', 'In3', 'In2', 'F']
def stats(d):
    t = [s for s in d['tracks'] if s['net'] == NET]; v = [s for s in d['vias'] if s['net'] == NET]
    return sum(math.hypot(s['x2'] - s['x1'], s['y2'] - s['y1']) for s in t), len(t), len(v), len({s['l'] for s in t})
fig, axs = plt.subplots(len(boxes), 2, figsize=(15, sum(7.2 * (b[3] - b[1]) / (b[2] - b[0]) for b in boxes) + 0.9), squeeze=False,
                        gridspec_kw=dict(height_ratios=[(b[3] - b[1]) / (b[2] - b[0]) for b in boxes]))
for r, (x0, y0, x1, y1) in enumerate(boxes):
    for c, d in enumerate(D):
        ax = axs[r][c]; ax.set_facecolor('#10151c'); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal')
        ppmm = 7.2 * 72 / (x1 - x0)                       # points per mm at this panel width (approx.)
        inb = lambda x, y, m=1.0: x0 - m < x < x1 + m and y0 - m < y < y1 + m
        for L in ORD:
            segs = [[(s['x1'], s['y1']), (s['x2'], s['y2'])] for s in d['tracks'] if s['l'] == L and s['net'] != NET and (inb(s['x1'], s['y1']) or inb(s['x2'], s['y2']))]
            lw = [s['w'] * ppmm for s in d['tracks'] if s['l'] == L and s['net'] != NET and (inb(s['x1'], s['y1']) or inb(s['x2'], s['y2']))]
            ax.add_collection(LineCollection(segs, linewidths=lw, colors=COL[L], alpha=0.22, capstyle='round'))
        pads = [p for p in d['pads'] if inb(p['x'], p['y'], 3)]
        for L in ('B', 'F'):
            ax.add_collection(PolyCollection([p['L'][L] for p in pads if p['L'].get(L) and p['net'] != NET], facecolors=COL[L], alpha=0.25, edgecolors='none'))
        for v in d['vias']:
            if v['net'] != NET and inb(v['x'], v['y']): ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc='#6b7480', ec='none', alpha=0.55))
        for L in ORD:
            mine = [s for s in d['tracks'] if s['l'] == L and s['net'] == NET]
            ax.add_collection(LineCollection([[(s['x1'], s['y1']), (s['x2'], s['y2'])] for s in mine], linewidths=[s['w'] * ppmm for s in mine], colors=COL[L], alpha=0.95, capstyle='round', zorder=5))
        for p in pads:
            if p['net'] == NET:
                for L in ('B', 'F'):
                    if p['L'].get(L): ax.add_collection(PolyCollection([p['L'][L]], facecolors=COL[L], edgecolors='white', linewidths=1.0, alpha=0.9, zorder=4))
                ax.text(p['x'], p['y'] - 0.55, p['ref'], color='white', fontsize=9, ha='center', va='bottom', zorder=8)
        for v in d['vias']:
            if v['net'] == NET: ax.add_patch(Circle((v['x'], v['y']), v['d'] / 2, fc='#f4f0e6', ec='#222', lw=0.8, zorder=6)); ax.add_patch(Circle((v['x'], v['y']), v['drill'] / 2, fc='#10151c', ec='none', zorder=7))
        ax.tick_params(colors='#555', labelsize=7)
        if r == 0:
            l, n, nv, nl = stats(d); ax.set_title(f"{T[c]}:  {l:.1f} mm, {n} segments, {nv} vias, {nl} layers", fontsize=13, loc='left')
h = [plt.Line2D([], [], color=COL[L], lw=5, label={'F': 'F.Cu', 'B': 'B.Cu', 'In2': 'In2.Cu', 'In3': 'In3.Cu'}[L]) for L in ('F', 'In2', 'In3', 'B')]
fig.legend(handles=h, loc='lower center', ncol=4, frameon=False, fontsize=11)
fig.suptitle(NET.split('/')[-1] + ' in colour, all other copper dimmed', fontsize=11, x=0.01, ha='left', y=0.995, color='#444')
fig.tight_layout(rect=(0, 0.035, 1, 0.985)); fig.savefig(out, dpi=110)
