"""edges.py drc.json [box] : list router edges (unconnected items) touching / crossing a box x0,y0,x1,y1"""
import json, sys, re
from shapely.geometry import LineString, box as B
d = json.load(open(sys.argv[1]))
bx = B(*map(float, sys.argv[2].split(','))) if len(sys.argv) > 2 else None
out = []
for u in d['unconnected_items']:
    it = u['items']
    if len(it) < 2: continue
    a, b = it[0], it[1]
    net = re.search(r'\[(.*?)\]', a['description']).group(1)
    if net in ('GND', 'PACK_P', '3V3'): continue
    pa, pb = (a['pos']['x'], a['pos']['y']), (b['pos']['x'], b['pos']['y'])
    ra = re.sub(r'.*\] of (\S+).*', r'\1', a['description']); rb = re.sub(r'.*\] of (\S+).*', r'\1', b['description'])
    if bx is not None:
        L = LineString([pa, pb]) if pa != pb else LineString([pa, (pa[0]+1e-3, pa[1])])
        if not L.intersects(bx): continue
        ina = bx.contains(LineString([pa,pa]).centroid); inb = bx.contains(LineString([pb,pb]).centroid)
        tag = 'IN' if (ina and inb) else ('END' if (ina or inb) else 'CROSS')
    else: tag = ''
    out.append((tag, net, ra, pa, rb, pb, round(((pa[0]-pb[0])**2+(pa[1]-pb[1])**2)**.5, 1)))
for o in sorted(out): print(*o)
print(len(out), 'edges')
