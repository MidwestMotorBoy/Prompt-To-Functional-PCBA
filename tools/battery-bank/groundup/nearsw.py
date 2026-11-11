"""nearsw.py cu.json victim_regex aggressor_regex [dmax=0.8]: where a victim net runs near aggressor copper.
Same layer: edge distance. Other layers: plan overlap/nearness where no ground or supply plane copper lies between them."""
import json, sys, re, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
d = json.load(open(sys.argv[1])); V = re.compile(sys.argv[2]); A = re.compile(sys.argv[3]); dmax = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
LAY = ['F', 'In1', 'In2', 'In3', 'In4', 'B']; Z = dict(F=0, In1=0.2, In2=0.5, In3=0.89, In4=1.19, B=1.39)
x0, y0, x1, y1 = 78, 63, 123, 138; h = 0.05; nx = int((x1 - x0) / h); ny = int((y1 - y0) / h)
def P(x, y): return ((x - x0) / h, (y - y0) / h)
def raster(pred, L):
    im = Image.new('1', (nx, ny), 0); dr = ImageDraw.Draw(im)
    for f in d['fills']:
        if f['l'] == L and pred(f['net']):
            for pts, hs in f['polys']:
                dr.polygon([P(*p) for p in pts], fill=1)
                for hh in hs: dr.polygon([P(*p) for p in hh], fill=0)
    for t in d['tracks']:
        if t['l'] == L and pred(t['net']):
            w = max(1, int(round(t['w'] / h))); dr.line([P(t['x1'], t['y1']), P(t['x2'], t['y2'])], fill=1, width=w)
            for q in ((t['x1'], t['y1']), (t['x2'], t['y2'])):
                c = P(*q); r = t['w'] / 2 / h; dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
    for p in d['pads']:
        if L in p['L'] and p['L'][L] and pred(p['net'] or ''): dr.polygon([P(*q) for q in p['L'][L]], fill=1)
    for v in d['vias']:
        if pred(v['net']): c = P(v['x'], v['y']); r = v['d'] / 2 / h; dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
    return np.array(im, dtype=bool)
ag = {L: raster(lambda n: bool(A.search(n)), L) for L in LAY}
pl = {L: raster(lambda n: n in ('GND', 'PACK_P', '3V3') or n.endswith('/PACK_P'), L) for L in LAY}
dist = {L: ndi.distance_transform_edt(~ag[L]) * h for L in LAY}
rows = []
for t in d['tracks']:
    if not V.search(t['net']) or A.search(t['net']): continue
    Lv = t['l']; n = max(2, int(math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1']) / 0.1) + 1)
    for k in range(n):
        x = t['x1'] + (t['x2'] - t['x1']) * k / (n - 1); y = t['y1'] + (t['y2'] - t['y1']) * k / (n - 1); i, j = int((y - y0) / h), int((x - x0) / h)
        for La in LAY:
            dd = dist[La][i, j] - (t['w'] / 2 if La == Lv else 0)
            if dd > (dmax if La == Lv else 0.3): continue
            a, b = sorted((LAY.index(Lv), LAY.index(La)))
            if any(pl[LAY[m]][i, j] for m in range(a + 1, b)): continue      # a plane lies between
            rows.append((t['net'].split('/')[-1], Lv, La, round(x, 2), round(y, 2), round(max(dd, 0), 2)))
# merge runs
out = {}
for net, Lv, La, x, y, dd in rows: out.setdefault((net, Lv, La), []).append((x, y, dd))
for (net, Lv, La), pts in sorted(out.items()):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    print(f"{net:14s} on {Lv:3s} near aggressor on {La:3s}: {len(pts)*0.1:5.1f} mm, x {min(xs):.1f}..{max(xs):.1f} y {min(ys):.1f}..{max(ys):.1f}, min gap {min(p[2] for p in pts):.2f}, mean {sum(p[2] for p in pts)/len(pts):.2f}")
