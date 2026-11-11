"""pathfill.py cu.json spec.json: which pour each new track of a handadd spec runs through (per layer, mm per net)."""
import json, sys
from matplotlib.path import Path
d = json.load(open(sys.argv[1])); spec = json.load(open(sys.argv[2]))
F = {}
for f in d['fills']:
    for poly in f['polys']: F.setdefault(f['l'], []).append((f['net'], Path(poly[0]), [Path(h) for h in poly[1]] if len(poly) > 1 else []))
for s in spec:
    if 'pts' not in s: continue
    tot = {}
    for a, b in zip(s['pts'], s['pts'][1:]):
        n = max(2, int(((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5 / 0.1)); L = ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5 / n
        for i in range(n):
            x = a[0] + (b[0]-a[0]) * (i + .5) / n; y = a[1] + (b[1]-a[1]) * (i + .5) / n; hit = 'none'
            for net, p, hs in F.get(s['layer'], []):
                if p.contains_point((x, y)) and not any(h.contains_point((x, y)) for h in hs): hit = net; break
            tot[hit] = tot.get(hit, 0) + L
    print(s['net'].split('/')[-1], s['layer'], {k: round(v, 1) for k, v in tot.items()})
