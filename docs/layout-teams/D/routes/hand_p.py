"""Twelfth hand pass, on board o1: the last DRC 'unconnected' item is an F-layer GND pour island at x 79.2-81.6, y 68.8-83.1
that holds the ground pads of the Port 2 5 V capacitors (the item's printed position is the zone's corner, not the island).
The In2 pack track and the B-side 5 V pour leave no free via site in the pour itself, so the two vias sit in the
ground pad of C543 (via-in-pad, flagged in the report).   HB=o1 python3 hand_p.py"""
from hand_lib import *
isl = [g for g, n, k, nm in m.items['F.Cu'] if n == 'GND' and k == 'pour' and sbox(79.0, 68.5, 81.8, 83.4).contains(g.centroid)][0]
for x, y in ((79.45, 78.7), (79.45, 79.3)):
    g = Point(x, y).buffer(0.225); bad = []
    for l in SIG: bad += viol('GND', g, l)
    print((x, y), 'inside island:', isl.contains(g), 'problems:', bad)
    m.J['vias'].append({'net': 'GND', 'x': x, 'y': y})
m.save('hand_p.json')
