"""Second hand pass, on the board built from hand_a (HB=h4): the DRC error, the 3V3 pour pieces, the ground island,
then the pack straps go back as wide as still fits.   HB=h4 python3 hand_b.py"""
from hand_lib import *
from shapely.ops import unary_union
# 1. IRQ_N via too close to the FET_MID track
FM = '/Cells and Gauge/FET_MID'; st(FM)
rip_box(FM, (101.2, 121.0, 103.0, 124.2), layers=('F.Cu',), vias=False); st(FM); joinall(FM, w=0.5, margin=6.0) ; joinall(FM, w=0.3, margin=6.0)
# 2. 3V3 pieces (the In3 pour is cut by the new tracks)
for k in range(8):
    cs = m.clusters('3V3'); print('3V3 pieces:', [tuple(round(v, 1) for v in unary_union([g for gs in c.values() for g in gs]).bounds) for c in cs[1:]])
    if len(cs) < 2: break
    if not any(m.join('3V3', c, cs[0], w=w, margin=9.0) is not None for c in reversed(cs[1:]) for w in (0.3, 0.2)): break
why('3V3', margin=9.0)
# 3. the F ground island in the top-left corner: one via down to the ground planes
isl = [g for g, n, k, nm in m.items['F.Cu'] if n == 'GND' and k == 'pour' and g.distance(Point(78.86, 64.54)) < 0.05]
print('GND island:', [(round(g.area, 2), [round(v, 2) for v in g.bounds]) for g in isl])
for g in isl:
    b = g.bounds; ss = [p for p in via_sites('GND', (b[0], b[1], b[2], b[3])) if g.buffer(-0.3).contains(Point(p))]
    print('  via sites inside:', ss[:6])
    if ss: x, y = ss[len(ss) // 2]; m.J['vias'].append({'net': 'GND', 'x': x, 'y': y}); m.vias.append((x, y, 0.45, 'GND')); [m._add(l, Point(x, y).buffer(0.225), 'GND', 'via') for l in SIG]
# 4. pack strap back on In2: find the least-disturbing line, pull what it crosses there, lay the strap, re-lay the crossers round it
A, B = (100.8, 116.3), (119.0, 106.8); BB = (94, 100, 125, 123)
at = lambda p: {L: [geo for geo, n, kind, name in m.items[L] if n == 'PACK_P' and kind in ('via', 'pad') and geo.distance(Point(p)) < 0.03] for L in SIG}
G = set(nets) - {'PACK_P'}
def strap_in(L, w):
    s0 = snap()
    r = m._search('PACK_P', BB, at(A), at(B), w, layers=(L,), quiet=True, ghost=G)
    if not r: print('strap %s %.1f: no line at all' % (L, w)); return False
    vs = sorted(r[1]); print('strap %s %.1f displaces %s' % (L, w, vs))
    for v in vs: m.rip(v) if False else None
    # first a trial with the crossers gone entirely, to get the strap's line
    s1 = snap()
    for v in vs: m.rip(v)
    path = m._search('PACK_P', BB, at(A), at(B), w, layers=(L,), quiet=True)
    restore(s1)
    if not path: print('  no line even with them gone'); restore(s0); return False
    line = LineString([(p[1], p[2]) for p in path]).buffer(w / 2)
    for v in vs: rip_hit(v, line, layers=(L,))
    if m._search('PACK_P', BB, at(A), at(B), w, layers=(L,), quiet=True) is None: print('  strap does not fit after the pull'); restore(s0); return False
    for v in vs: joinall(v, margin=9.0)
    bad = [v for v in vs if not one(v)]
    if bad:
        for v in bad: why(v, margin=9.0)
        restore(s0); print('  undone, could not re-lay', bad); return False
    print('  strap %s %.1f mm in, crossers re-laid' % (L, w)); return True
for L in ('In3.Cu', 'B.Cu'):
    for w in (2.5, 2.0, 1.5, 1.0):
        if strap_in(L, w): break
m.save('hand_b.json')
