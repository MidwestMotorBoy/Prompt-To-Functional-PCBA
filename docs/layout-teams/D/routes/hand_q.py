"""Thirteenth hand pass, on board p1: the single pack via at (100.05, 112.67) carries about 2.8 A of the Port 2 feed between
the In2 pour and the B / F pours. Add pack vias beside it wherever a legal site lies inside both pours.   HB=p1 python3 hand_q.py"""
from hand_lib import *
def pour(L): return unary_union([g for g, n, k, nm in m.items[L] if n == 'PACK_P' and k == 'pour'])
P2, PB = pour('In2.Cu'), pour('B.Cu')
got = []
for x, y in via_sites('PACK_P', (98.4, 111.0, 101.2, 114.2), 0.05):
    g = Point(x, y).buffer(0.3)
    if P2.contains(g) and PB.contains(g) and all(math.hypot(x - a, y - b) >= 0.8 for a, b in got):
        got.append((x, y)); m.J['vias'].append({'net': 'PACK_P', 'x': x, 'y': y}); m.vias.append((x, y, 0.45, 'PACK_P'))
print('added', got)
m.save('hand_q.json')
