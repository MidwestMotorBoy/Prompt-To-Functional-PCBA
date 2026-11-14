"""Lead power repair on the routed board: PACK_P straps (hard tracks) from the Q102 via field to the R427/J113 via
field, as many as fit on B, In3 and In2 round the signal routes.  python3 lead_packp2.py <dir> <board> -> lead_packp2.json"""
import sys; sys.path.insert(0, '../tools')
from obst import HR
h = HR(sys.argv[1], sys.argv[2]); got = []
A = [(100.8, 116.3), (101.5, 116.5), (101.3, 117.3), (100.5, 117.3), (102.5, 113.3), (104.0, 111.3)]
B = [(119.0, 106.8), (118.8, 106.0), (119.5, 106.2), (120.3, 106.2), (119.5, 105.4)]
for L in ('B.Cu', 'In3.Cu', 'In2.Cu', 'B.Cu', 'In3.Cu', 'In2.Cu'):
    done = False
    for w in (2.0, 1.5, 1.0, 0.6):
        for a in A:
            for b in B:
                if (L, a, b) in [(g[0], g[2], g[3]) for g in got]: continue
                import io, contextlib
                with contextlib.redirect_stdout(io.StringIO()): p = h.auto('PACK_P', L, a, b, w=w, margin=5)
                if p: got.append((L, w, a, b, round(sum(((p[i][0]-p[i+1][0])**2+(p[i][1]-p[i+1][1])**2)**.5 for i in range(len(p)-1)), 1))); done = True; break
            if done: break
        if done: break
h.ok = True
for g in got: print(g)
h.save('lead_packp2.json')
