"""Tenth hand pass, on board m1: rejoin the 3V3 piece the pour refill cut off (gauge side <-> R313).   HB=m1 python3 hand_n.py"""
from hand_lib import *
st('3V3'); why('3V3', w=0.2, margin=8.0)
piecewise('3V3', w=0.2, margin=8.0); st('3V3')
print([r for r in m.J['routes']], m.J['vias'])
m.save('hand_n.json')
