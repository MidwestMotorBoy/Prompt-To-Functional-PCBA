"""at.py cu.json x,y [r=0.6]: every copper item within r of the point, per layer (fills by point-in-polygon, tracks, vias, pads)."""
import json, sys, math
from matplotlib.path import Path
d = json.load(open(sys.argv[1]))
for a in sys.argv[2:]:
    if ',' not in a: continue
    x, y = [float(v) for v in a.split(',')[:2]]; r = float(a.split(',')[2]) if a.count(',') > 1 else 0.6
    out = []
    for f in d['fills']:
        for pts, hs in f['polys']:
            if Path(pts).contains_point((x, y)) and not any(Path(h).contains_point((x, y)) for h in hs): out.append((f['l'], 'fill', f['net'].split('/')[-1], 0))
    def dseg(t):
        ax, ay, bx, by = t['x1'], t['y1'], t['x2'], t['y2']; L2 = (bx - ax) ** 2 + (by - ay) ** 2
        u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2)); return math.hypot(x - ax - u * (bx - ax), y - ay - u * (by - ay)) - t['w'] / 2
    for t in d['tracks']:
        g = dseg(t)
        if g < r: out.append((t['l'], 'trk', t['net'].split('/')[-1], round(g, 3)))
    for v in d['vias']:
        g = math.hypot(v['x'] - x, v['y'] - y) - v['d'] / 2
        if g < r: out.append(('all', 'via (%.3f,%.3f)' % (v['x'], v['y']), v['net'].split('/')[-1], round(g, 3)))
    for p in d['pads']:
        for L, poly in p['L'].items():
            if poly:
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                g = max(min(xs) - x, x - max(xs), min(ys) - y, y - max(ys))
                if g < r: out.append((L, 'pad %s.%s' % (p['ref'], p['n']), p['net'].split('/')[-1], round(g, 3)))
    print('(%.3f,%.3f) r %.2f:' % (x, y, r), sorted(set(out)))
