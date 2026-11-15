"""Sixth hand pass, on board f1: the long GND track on In2 (x 98.3-99.6, y 96.8-113.5) joins two GND vias that both
already sit on the In1 / In4 planes, and it cuts the In2 pack pour off from the Port 2 feed vias (R527 saw 98 mOhm).
Remove the track, keep its vias.   HB=f1 python3 hand_h.py"""
from hand_lib import *
from hand_lib import SIG
import math
win = sbox(97.9, 96.6, 101.0, 113.7); keep = []; k = 0
for it in m.items['In2.Cu']:
    geo, n, kind, name = it
    if n == 'GND' and kind == 'track' and win.contains(geo):
        P, A = geo.length, geo.area; w = (P / 2 - math.sqrt(max(P * P / 4 - math.pi * A, 0))) / (math.pi / 2); b = geo.bounds
        m.J['drop'].append({'net': 'GND', 'layer': 'In2.Cu', 'box': [b[0] + w / 2 - 0.01, b[1] + w / 2 - 0.01, b[2] - w / 2 + 0.01, b[3] - w / 2 + 0.01], 'tracks_only': True}); k += 1; print('  drop', [round(v, 2) for v in b]); continue
    keep.append(it)
m.items['In2.Cu'] = keep; m.tree['In2.Cu'] = STRtree([i[0] for i in keep]); print('dropped', k)
m.save('hand_h.json')
