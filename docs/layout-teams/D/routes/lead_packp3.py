"""Lead power repair after the worker tier: join PACK_P pour islands on In2 that hold a terminal back to the main
pour with a track (0.8 mm, narrower if nothing else fits) on any layer.  python3 lead_packp3.py <dir> <board>"""
import sys, io, contextlib; sys.path.insert(0, '../tools'); sys.path.insert(0, '../../../../tools/copper')
from obst import HR
from dc_score import load_copper
from shapely.geometry import Polygon, Point
d, board = sys.argv[1], sys.argv[2]
h = HR(d, board); Z, T, V = load_copper('%s/%s.kicad_pcb' % (d, board))
pieces = [Polygon(z['pts']).buffer(0) for z in Z if z['net'] == 'PACK_P' and z['layer'] == 'In2.Cu' and len(z['pts']) > 2]
vias = [(v['x'], v['y']) for v in V if v['net'] == 'PACK_P']
main = max(pieces, key=lambda p: p.area); mv = [v for v in vias if main.buffer(0.1).contains(Point(v))]
print('In2 PACK_P pieces', len(pieces), 'main area %.0f mm2 with %d vias' % (main.area, len(mv)))
for p in pieces:
    if p is main: continue
    pv = [v for v in vias if p.buffer(0.1).contains(Point(v))]
    if not pv or p.area < 5: continue          # tiny scraps round a Kelvin tap via must stay separate
    print('  island %.1f mm2 at (%.1f, %.1f) vias %s' % (p.area, p.centroid.x, p.centroid.y, pv[:3]))
    done = False
    for w in (0.8, 0.5, 0.3):
        for a in pv[:3]:
            for b in sorted(mv, key=lambda q: (q[0]-a[0])**2 + (q[1]-a[1])**2)[:4]:
                for L in ('In3.Cu', 'B.Cu', 'In2.Cu'):
                    with contextlib.redirect_stdout(io.StringIO()): r = h.auto('PACK_P', L, a, b, w=w, margin=4)
                    if r: print('    joined on', L, 'w', w, a, '->', b); done = True; break
                if done: break
            if done: break
        if done: break
    if not done: print('    NOT JOINED')
h.ok = True; h.save('lead_packp3.json')
