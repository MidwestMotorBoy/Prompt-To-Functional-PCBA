"""Third hand pass, on board d1: one DRC error, the corner ground island, a PACK_P neck and a 3V3 piece cut by the new routes.
   HB=d1 python3 hand_e.py"""
from hand_lib import *
FM = '/Cells and Gauge/FET_MID'
rip_box(FM, (101.2, 121.0, 103.0, 124.2), layers=('F.Cu',), vias=False); st(FM)
stub('GND', [(79.02, 64.4), (78.89, 65.14)], w=0.2)
piecewise('PACK_P', w=0.5); st('PACK_P')
piecewise('3V3'); st('3V3')
for n in ('/Cells and Gauge/CELL_P', 'SDA', '/USB Port 1/CE_N', '/USB Port 1/CHG_INT'): st(n)
m.save('hand_e.json')
