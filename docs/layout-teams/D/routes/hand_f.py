"""Fourth hand pass, on board e1: the CELL_P sense tap (R110 / C110) threaded between the pads of R109 by hand.
   HB=e1 python3 hand_f.py"""
from hand_lib import *
CP = '/Cells and Gauge/CELL_P'
stub(CP, [(107.3, 117.45), (107.68, 117.825), (108.75, 117.825), (109.3, 117.4), (109.95, 117.4)], w=0.15, via=False); st(CP)
m.save('hand_f.json')
