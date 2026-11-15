"""Lead power interconnect: a hard PACK_P strap on B.Cu from the pack FET (Q102 via field) to the Port 1 battery
shunt / pack connector (R427, J113). The generated plan carries this 10 A path on the In2 pour, which the signal
router cuts into islands (found on the first hand-routed board: PACK_P open at J113 and R427). A track is hard for
the router, a pour of PACK_P is not.   python3 lead_packp.py <dir> <board>  -> lead_packp.json"""
import sys; sys.path.insert(0, '../tools')
from obst import HR
h = HR(sys.argv[1], sys.argv[2])
import io, contextlib
A = ((100.8, 116.3), (101.5, 116.5), (101.3, 117.3), (100.0, 116.5), (99.2, 116.3))
B = ((119.0, 106.8), (118.8, 106.0), (119.5, 106.2), (120.3, 106.2), (119.5, 105.4))
def strap(L, widths):
    for w in widths:
        for a in A:
            for b in B:
                with contextlib.redirect_stdout(io.StringIO()): p = h.auto('PACK_P', L, a, b, w=w, margin=5)
                if p: print(L, w, p); return True
    print(L, 'NO STRAP'); return False
r = [strap('In2.Cu', (3.0, 2.5, 2.0, 1.5)), strap('B.Cu', (2.0, 1.5, 1.0))]
# second strap: the Port 2 5 V buck (U504, top-left corner) hangs on the In2 pour by a long neck down the left edge;
# signal tracks along y 80 cut it off on the second routed board and no legal bridge was left afterwards
A = ((79.85, 65.575),); B = ((79.45, 83.975), (80.2, 83.975), (81.0, 83.975))
r.append(strap('In2.Cu', (1.5, 1.0, 0.8)))
h.ok = all(r)
h.save('lead_packp.json')
