"""Ninth hand pass, on board k1: SDA (PD chips <-> MCU), laid in forced pieces so it does not wall the In2 pack pour:
   In2 down the board centre with a B hop past the Port 2 pack-feed vias, the In2 crossing at the strap's west end
   (TS4 and CHG pulled locally and re-laid), a via at (101.6, 119.3), then an In3 lane north of 3V3_SLEEP east to the MCU-side piece.   HB=k1 python3 hand_m.py"""
from hand_lib import *
CG = '/Cells and Gauge/'; TS4 = CG + 'TS4'; CHG = CG + 'CHG'
def cl_at(net, x, y):
    for c in m.clusters(net):
        if unary_union([g for gs in c.values() for g in gs]).distance(Point(x, y)) < 0.05: return c
def J(a, b, margin, **kw):
    r = m.join('SDA', cl_at('SDA', *a), cl_at('SDA', *b), w=0.15, margin=margin, quiet=True, **kw); print('  join', a, b, 'ok' if r is not None else 'FAILED', flush=True)
    if r is None:
        g = m.join('SDA', cl_at('SDA', *a), cl_at('SDA', *b), w=0.15, margin=margin, quiet=True, ghost=set(nets) - {'SDA'}); print('     in the way:', g[2] if g else 'WALLED')
    return r is not None
# TS4 and CHG moved a few tenths by hand so SDA can come down beside them at the strap's west end
rip_box(TS4, (97.8, 112.4, 99.0, 114.5), layers=('In2.Cu',), vias=False)
stub(TS4, [(97.855, 112.416), (98.0, 112.56), (98.0, 114.32), (97.855, 114.466)], L='In2.Cu', via=False); st(TS4)
rip_box(CHG, (97.3, 115.6, 97.45, 121.4), layers=('In2.Cu',), vias=True)
stub(CHG, [(97.325, 121.375), (97.325, 116.6), (97.33, 116.3)], L='In2.Cu')
stub(CHG, [(97.549, 115.597), (97.33, 115.82), (97.33, 116.3)], L='In3.Cu', via=False); st(CHG)
stub('SDA', [(110.02, 121.8), (107.7, 121.8), (106.1, 120.2), (102.5, 120.2), (101.6, 119.3)], L='In3.Cu')   # In3 lane into the MCU-side piece, via V3 at (101.6, 119.3)
stub('SDA', [(99.4, 101.2), (99.4, 100.6), (100.3, 99.7), (100.3, 97.5)], L='B.Cu')     # B hop past the Port 2 pack-feed vias, so the In2 pour stays open there
# In2 down the pocket west of the SS_5V column (x 98.4), so the pack pour still reaches its via at (100.05, 112.67)
stub('SDA', [(97.79, 117.6), (97.79, 116.017), (98.957, 114.85), (98.957, 113.307), (98.4, 112.75), (98.4, 103.0), (99.4, 102.0), (99.4, 101.2)], L='In2.Cu')
st('SDA')
AV = [(98.5, 98.0, 101.6, 101.0)]
ok = J((100.3, 97.5), (97.52, 87.45), 3.0, avoid=AV) or J((100.3, 97.5), (97.52, 87.45), 6.0, avoid=AV)
ok = (J((97.79, 117.6), (101.6, 119.3), 2.0) or J((97.79, 117.6), (101.6, 119.3), 4.0)) and ok
st('SDA')
print('OPEN NETS', [v for v in nets if not one(v)])
print([r for r in m.J['routes'] if r['net'] == 'SDA'])
m.save('hand_m.json')
