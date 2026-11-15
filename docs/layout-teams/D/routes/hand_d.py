"""Hand pass on board c1 (strap kept): the lines that have to cross the pack strap.   HB=c1 python3 hand_d.py"""
from hand_lib import *
P1 = '/USB Port 1/'; G = '/Cells and Gauge/'
def multi(stuck, rips, margin=12.0):
    s = snap(); print('multi', stuck, [(v.split('/')[-1], bx) for v, bx in rips], flush=True)
    for v, bx in rips: rip_box(v, bx)
    vs = list(dict.fromkeys(v for v, bx in rips))
    joinall(stuck, margin=margin)
    for v in vs: joinall(v, margin=margin)
    if one(stuck) and all(one(v) for v in vs): return True
    why(stuck, margin=margin)
    for v in vs: why(v, margin=margin)
    restore(s); print('  undone'); return False
def around(p, r=3.0): return (p[0] - r, p[1] - r, p[0] + r, p[1] + r)
multi('IRQ_N', [(G + 'DSG_G', around((94.0, 117.6)))])
piecewise('3V3')
# ground island in the top-left corner
isl = [g for g, n, k, nm in m.items['F.Cu'] if n == 'GND' and k == 'pour' and g.distance(Point(78.86, 64.54)) < 0.05]
for g in isl:
    b_ = g.bounds; pads = [(nm, [round(v, 2) for v in q.bounds]) for q, n, k, nm in m.items['F.Cu'] if n == 'GND' and k == 'pad' and q.intersects(g.buffer(0.05))]
    ss = [p for p in via_sites('GND', (b_[0] - 0.3, b_[1] - 0.3, b_[2] + 0.3, b_[3] + 0.3)) if g.buffer(0.05).contains(Point(p))]
    print('GND island', [round(v, 2) for v in b_], 'pads', pads, 'via sites', ss[:8])
    if ss:
        x, y = ss[len(ss) // 2]; m.J['vias'].append({'net': 'GND', 'x': x, 'y': y}); m.vias.append((x, y, 0.45, 'GND')); [m._add(l, Point(x, y).buffer(0.225), 'GND', 'via') for l in SIG]; print('  GND via at', x, y)
for n in (G + 'CELL_P', '3V3', 'IRQ_N', 'SDA', P1 + 'CE_N', P1 + 'CHG_INT'): st(n)
m.save('hand_d.json')
