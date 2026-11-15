"""Lead power repair after the worker tier: the In2 PACK_P island that feeds the Port 2 5 V buck (U504, top-left) is
cut off by In2 signal tracks along y 80. Search for a chain island via -> (track on In3/B/F) -> stepping-stone via ->
... -> via in the main pour.   python3 lead_packp4.py <dir> <board>  -> lead_packp4.json"""
import sys, io, contextlib, math, heapq; sys.path.insert(0, '../tools'); sys.path.insert(0, '../../../../tools/copper')
from obst import HR
from dc_score import load_copper
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
d, board = sys.argv[1], sys.argv[2]
h = HR(d, board); Z, T, V = load_copper('%s/%s.kicad_pcb' % (d, board))
pc = [Polygon(z['pts']).buffer(0) for z in Z if z['net'] == 'PACK_P' and z['layer'] == 'In2.Cu' and len(z['pts']) > 2]
main = max(pc, key=lambda p: p.area); isl = [p for p in pc if p is not main and p.area > 5][0]; ii, mi = isl.buffer(-0.35), main.buffer(-0.35)
box = (78.7, 70.0, 96.0, 88.0); N = []
x = box[0]
while x <= box[2]:
    y = box[1]
    while y <= box[3]:
        if not h.via_ok('PACK_P', x, y): N.append((round(x, 2), round(y, 2), 'I' if ii.contains(Point(x, y)) else ('M' if mi.contains(Point(x, y)) else '-')))
        y += 0.5
    x += 0.5
print(len(N), 'via spots:', sum(n[2] == 'I' for n in N), 'island,', sum(n[2] == 'M' for n in N), 'main')
def edge(a, b):
    for L in ('In3.Cu', 'B.Cu', 'F.Cu'):
        hh = h.J["routes"][:]; it = {k: v[:] for k, v in h.items.items()}
        with contextlib.redirect_stdout(io.StringIO()): r = h.auto('PACK_P', L, a[:2], b[:2], w=0.4, margin=2)
        h.J["routes"] = hh; h.items = it; h.tree[L] = STRtree([q[0] for q in h.items[L]])    # trial only: nothing is kept
        if r: return L, r
    return None
pq = [(0, i, None, None) for i, n in enumerate(N) if n[2] == 'I']; seen = {}; goal = None; tried = 0
while pq and tried < 2500:
    c, i, par, how = heapq.heappop(pq)
    if i in seen: continue
    seen[i] = (par, how)
    if N[i][2] == 'M': goal = i; break
    for j, n in enumerate(N):
        if j in seen or n[2] == 'I': continue
        dist = math.hypot(n[0] - N[i][0], n[1] - N[i][1])
        if dist > 4.5: continue
        tried += 1; e = edge(N[i], n)
        if e: heapq.heappush(pq, (c + dist + 2, j, i, e))
print('autos tried', tried, 'goal', goal)
if goal is not None:
    i = goal
    while seen[i][0] is not None:
        par, (L, r) = seen[i]; h.via('PACK_P', N[i][0], N[i][1]); h.seg('PACK_P', L, r, 0.4); print('  ', N[par][:2], '->', N[i][:2], L); i = par
    h.via('PACK_P', N[i][0], N[i][1])
h.save('lead_packp4.json')
