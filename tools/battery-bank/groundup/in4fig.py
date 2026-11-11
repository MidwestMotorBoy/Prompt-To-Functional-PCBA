"""in4fig.py out.png: signal tracks on the In4 ground plane, current board against the ground-up board after the fix pass."""
import json, sys, math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
BO = [('Current board', 'base/cubase.json'), ('Ground-up board after the fix pass', 'new/cus13_c.json')]
PAL = ['#2a78d6', '#d1495b', '#1b998b', '#e08e0b', '#7b4fbf', '#4d6a2a', '#b0387d', '#6b6f76']
x0, y0, x1, y1 = 78.5, 63.5, 122.5, 137.5; sc = 0.115
fig = plt.figure(figsize=((x1 - x0) * sc * 2 + 0.3, (y1 - y0) * sc + 0.9), dpi=150); fig.patch.set_facecolor('white')
W, Hh = fig.get_size_inches(); out = {}
for i, (title, f) in enumerate(BO):
    d = json.load(open(f)); ax = fig.add_axes([i / 2 + 0.01, 0.0, 0.48, (y1 - y0) * sc / Hh]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.axis('off')
    for fl in d['fills']:
        if fl['l'] != 'In4': continue
        for pts, hs in fl['polys']:
            verts = list(pts) + [pts[0]]; codes = [Path.MOVETO] + [Path.LINETO] * (len(pts) - 1) + [Path.CLOSEPOLY]
            for h in hs: verts += list(h) + [h[0]]; codes += [Path.MOVETO] + [Path.LINETO] * (len(h) - 1) + [Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts, codes), fc='#d9dbde' if fl['net'] == 'GND' else '#f2c9a0', ec='none'))
    nets = {}
    for t in d['tracks']:
        if t['l'] == 'In4' and t['net'] != 'GND': nets.setdefault(t['net'], []).append(t)
    order = sorted(nets, key=lambda n: -sum(math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1']) for t in nets[n])); tot = 0; rows = []
    for j, n in enumerate(order):
        L = sum(math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1']) for t in nets[n]); tot += L
        nm = n.replace('/USB Port 1/', 'Port 1 ').replace('/USB Port 2/', 'Port 2 ').lstrip('/')
        for t in nets[n]: ax.plot([t['x1'], t['x2']], [t['y1'], t['y2']], color=PAL[j % 8], lw=max(t['w'] * 6, 1.3), solid_capstyle='round')
        ax.plot([], [], color=PAL[j % 8], lw=2.5, label=f"{nm}  {L:.1f} mm"); rows.append([nm, round(L, 1), len(nets[n]), min(t['w'] for t in nets[n])])
    ax.legend(loc='upper left', fontsize=7.5, frameon=True, facecolor='white', edgecolor='#cccccc', framealpha=0.95, title=f"{tot:.0f} mm in {sum(len(v) for v in nets.values())} segments", title_fontsize=8)
    fig.text(i / 2 + 0.25, 1 - 0.3 / Hh, title, ha='center', va='center', fontsize=11, color='#1c1e21'); out[title] = dict(total=round(tot, 1), rows=rows)
fig.text(0.5, 1 - 0.62 / Hh, 'Inner layer 4, the ground plane next to the back side. Grey is ground copper, coloured lines are signal tracks cut into it.', ha='center', va='center', fontsize=8, color='#55595f')
fig.savefig(sys.argv[1]); json.dump(out, open(sys.argv[1].replace('.png', '.json'), 'w'), indent=1); print(json.dumps(out))
