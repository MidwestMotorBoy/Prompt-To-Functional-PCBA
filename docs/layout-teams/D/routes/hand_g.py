"""Seventh hand pass, on board i1: reshape the In2 pack strap under the charger's south pins (3 mm -> 2 mm, moved north)
so pins 3 and 7 get room for escape vias, then lay CE_N, CHG_INT and SDA.   HB=i1 python3 hand_g.py"""
from hand_lib import *
P1 = '/USB Port 1/'
segs = [(g, [round(v, 2) for v in g.bounds]) for g, n, k, nm in m.items['In2.Cu'] if n == 'PACK_P' and k == 'track' and g.intersects(sbox(98, 104, 121, 121))]
print('strap pieces:', [b for g, b in segs])
rip_hit('PACK_P', Point(111.95, 112.4).buffer(0.01), layers=('In2.Cu',), clr=0.0)
stub('PACK_P', [(108.8, 114.1), (108.8, 113.4), (110.2, 112.0), (113.8, 112.0), (114.3, 111.5)], w=2.0, L='In2.Cu', via=False)
stub('PACK_P', [(114.3, 111.5), (119.0, 106.8)], w=3.0, L='In2.Cu', via=False)
st('PACK_P')
CE, CI = P1 + 'CE_N', P1 + 'CHG_INT'
SDA1 = P1 + 'I2CC_SDA'   # move the pin 2 escape west so pin 3 can come straight out
rip_box(SDA1, (110.2, 112.9, 111.2, 114.6), layers=('F.Cu',), vias=False)
stub(SDA1, [(110.69, 113.0), (110.69, 113.75), (110.3, 114.14), (110.3, 114.5)], via=False); st(SDA1)
stub(CI, [(111.19, 113.0), (111.19, 113.35), (111.45, 113.6), (112.0, 113.6)])
stub(CE, [(113.19, 113.0), (113.19, 113.4), (113.45, 113.9)])
for n in (CI, CE, 'SDA'):
    cross2(n, depth=2) or cross2(n, depth=2, r=2.0)
for n in (CI, CE, 'SDA', 'PACK_P'): st(n); why(n, margin=12.0)
m.save('hand_g.json')
