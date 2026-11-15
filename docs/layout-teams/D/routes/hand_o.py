"""Eleventh hand pass, on board n1: join the two 3V3 pieces with a track between hard copper (via / pad / track ends), not
between pours, because a pour-to-pour link can be cut again by the next refill.   HB=n1 python3 hand_o.py"""
from hand_lib import *
pour_ids = {id(g) for L in SIG for g, n, k, nm in m.items[L] if k == 'pour'}
cs = m.clusters('3V3'); print(len(cs), 'pieces')
hard = [{L: [g for g in gs if id(g) not in pour_ids] for L, gs in c.items()} for c in cs]
for margin in (3.0, 6.0, 10.0):
    r = m.join('3V3', hard[1], hard[0], w=0.2, margin=margin, quiet=True)
    if r is not None: break
print('joined' if r is not None else 'FAILED', margin); st('3V3')
if r is None:
    CI = '/Cells and Gauge/CHG_INH' if '/Cells and Gauge/CHG_INH' in nets else 'CHG_INH'
    for rr in (1.0, 2.0):
        s0 = snap()
        with contextlib.redirect_stdout(io.StringIO()): rip_hit(CI, Point(108.5, 123.1).buffer(rr), layers=SIG, clr=0.0)
        r = m.join('3V3', hard[1], hard[0], w=0.2, margin=10.0, quiet=True)
        ok = r is not None and (cross2(CI, depth=2, chain=frozenset({'3V3', 'SDA'}), margin=12.0) or cross2(CI, depth=3, chain=frozenset({'3V3', 'SDA'}), margin=12.0, r=2.0))
        print('with CHG_INH pulled r', rr, r is not None, ok)
        if ok: break
        restore(s0)
st('3V3'); print('OPEN NETS', [v for v in nets if not one(v)])
print([q for q in m.J['routes'] if q['net'] == '3V3'], m.J['vias'])
m.save('hand_o.json')
