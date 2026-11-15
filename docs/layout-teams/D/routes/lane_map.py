"""lane_map.py: a text map of one net's free lanes, one character per 0.2 mm, per signal layer (. free, o via, letter = first letter of the\nnet in the way). Used to find the In3 lane for SDA.   HB=<board> python3 lane_map.py"""
from hand_lib import *
import numpy as np
def row(L, y, x0, x1, step=0.2):
    s = ''
    x = x0
    while x < x1:
        v = viol('SDA', LineString([(x, y), (x + step, y)]).buffer(0.075), L)
        s += '.' if not v else (v[0][2][:1] if v[0][1] != 'via' else 'o'); x += step
    return s
for L in ('In3.Cu', 'In2.Cu', 'B.Cu'):
    print(L, 'x 92..112 step 0.2')
    y = 112.0
    while y <= 126.01:
        print('%6.2f %s' % (y, row(L, y, 92.0, 112.0))); y += 0.25
