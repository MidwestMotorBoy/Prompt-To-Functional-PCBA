"""cudiff.py spec.json : planner copper per net/layer in port-1 boxes vs the same boxes shifted by -dx (port 2)"""
import json, sys, re
from shapely.geometry import Polygon, box, Point, LineString
from shapely.ops import unary_union
S = json.load(open(sys.argv[1])); DX = float(sys.argv[2]) if len(sys.argv) > 2 else 21.0
boxes = {'PD south (cluster, I2C exits)': (101, 82.5, 112, 92), 'PD north (CC/VBUS/PP5V)': (100, 74, 113, 79.5),
         'column PD->charger': (101, 92, 114, 112)}
def nn(n): return re.sub(r'USB Port [12]', 'P', n).replace('P1_LDO_3V3', 'LDO_3V3')
for name, b in boxes.items():
    for side, sh in (('p1', 0), ('p2', DX)):
        B = box(b[0] - sh, b[1], b[2] - sh, b[3]); acc = {}
        for z in S['zones']:
            for p in z['polys']:
                g = Polygon(p['ring'], [h for h in p.get('holes', [])]).buffer(0).intersection(B)
                if g.area > 0.01: acc.setdefault((nn(z['net']), z['layer'], 'zone'), [0])[0] += g.area
        for t in S['tracks']:
            g = LineString([t['a'], t['b']]).buffer(t['w'] / 2).intersection(B)
            if g.area > 0.001: acc.setdefault((nn(t['net']), t['layer'], 'trk'), [0])[0] += g.area
        for v in S['vias']:
            if B.contains(Point(v['x'], v['y'])): acc.setdefault((nn(v['net']), 'all', 'via'), [0])[0] += 1
        print('==', name, side, B.bounds)
        for k in sorted(acc): print('   %-28s %-6s %-4s %.2f' % (k[0], k[1], k[2], acc[k][0]))
