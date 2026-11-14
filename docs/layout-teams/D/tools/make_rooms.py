"""make_rooms.py - the lead's floorplan as data: writes ../rooms/<room>.spec.json and a legal starting master.json
(hand placement, with every part that the floorplan moves to another room parked at a free spot inside its room)."""
import json, os
from dlib import Board
from room import ROOMS, MASTER
b = Board(); comps = b.net['comps']
def sec(block, key): return [r for r, c in comps.items() if c['block'] == block and key in c['section']]
def port(n):
    P = f'USB Port {n}'; h = '4' if n == 1 else '5'
    d = dict(conn=sec(P, 'USB-C connector'), pd=sec(P, 'USB PD controller'), buck=sec(P, '5 V buck'), nine=sec(P, '9 V gate'),
             ctl=sec(P, 'BQ25756'), prog=sec(P, 'Charger programming'), stage=sec(P, 'Four-switch'))
    d['buck'] += [f'C{h}44', f'C{h}46']; d['stage'] = [r for r in d['stage'] if r not in d['buck']]
    return d, h
p1, _ = port(1); p2, _ = port(2)
rooms = {
 'p1_top': dict(boxes=[[99.9, 67.8, 121.5, 79.3], [95.6, 79.3, 121.5, 87.7], [113.2, 63.9, 121.5, 67.8]],
     parts=p1['conn'] + [r for r in p1['pd'] if r != 'C409'] + ['R424'] + [r for r in p1['nine'] if r != 'D410'],
     keep_free=[[99.4, 79.3, 101.0, 87.7, 'PP5V from the 5 V buck below, 1.5 A, comes up here']]),
 'p2_top': dict(boxes=[[78.5, 67.8, 99.8, 79.3], [78.5, 79.3, 95.5, 87.7], [78.5, 63.9, 86.9, 67.8]],
     parts=p2['conn'] + [r for r in p2['pd'] if r != 'C509'] + ['R524', 'R555'] + p2['buck']),
 'p1_stage': dict(boxes=[[101.1, 87.8, 121.5, 102.4], [107.6, 102.4, 121.5, 104.5], [116.5, 104.5, 121.5, 107.2]], parts=p1['stage'] + ['R427']),
 'p2_stage': dict(boxes=[[78.5, 87.8, 99.3, 102.5], [78.5, 102.5, 94.0, 104.5]], parts=p2['stage'] + ['R527']),
 'p1_chg': dict(boxes=[[94.0, 102.6, 99.3, 104.6], [101.1, 102.4, 107.6, 104.6], [94.0, 104.6, 116.4, 115.9], [116.4, 107.3, 121.5, 113.3]],
     parts=[r for r in p1['ctl'] if r not in ('R424', 'R427')] + p1['prog'] + ['C409', 'D410'] + p1['buck']),
 'p2_chg': dict(boxes=[[78.5, 104.6, 93.9, 116.0], [78.5, 116.0, 92.4, 121.2]],
     parts=[r for r in p2['ctl'] if r not in ('R524', 'R527')] + p2['prog'] + ['C509'] + [r for r in p2['nine'] if r != 'R555']),
 'pack_gauge': dict(boxes=[[92.4, 116.0, 110.8, 118.5], [92.4, 118.5, 109.1, 124.0], [88.6, 121.2, 92.4, 124.0], [93.4, 124.0, 111.3, 137.1],
                           [115.0, 126.8, 121.5, 132.2], [111.4, 128.7, 115.0, 134.3], [115.0, 132.2, 116.5, 134.3], [83.5, 131.6, 93.4, 137.1]],
     parts=sec('Cells and Gauge', 'Protection FETs') + sec('Cells and Gauge', 'Second-level') + sec('Cells and Gauge', 'BQ40Z50') +
           sec('Cells and Gauge', 'Current sense') + sec('Cells and Gauge', 'Gauge interrupt') + ['R314']),
 'sys': dict(boxes=[[78.5, 121.3, 88.6, 131.5], [88.6, 124.0, 93.3, 131.5], [108.6, 115.9, 121.6, 118.5], [109.2, 118.5, 110.95, 127.0]],
     parts=sec('3V3 Rail', 'TPS62177') + [r for r in sec('MCU', 'CC2340') + sec('MCU', 'Antenna') + sec('MCU', 'Pull-ups') if r != 'R314']),
}
owner = {}
for n, s in rooms.items():
    s['parts'] = sorted(set(s['parts']), key=lambda r: (r[0], int(''.join(ch for ch in r if ch.isdigit()))))
    for r in s['parts']: assert r not in owner, r; owner[r] = n
    xs = [v for bx in s['boxes'] for v in (bx[0], bx[2])]; ys = [v for bx in s['boxes'] for v in (bx[1], bx[3])]
    s['box'] = [min(xs), min(ys), max(xs), max(ys)]
un = [r for r in b.fp if r not in owner and not b.fixed(r)]; print('unowned movable parts:', un)
def inside(c, boxes, tol=0.0):
    boxes = [[B[0]-tol, B[1]-tol, B[2]+tol, B[3]+tol] for B in boxes]
    a = sum(max(0, min(c[2], B[2]) - max(c[0], B[0])) * max(0, min(c[3], B[3]) - max(c[1], B[1])) for B in boxes)
    return a > (c[2]-c[0]) * (c[3]-c[1]) - 0.02
def clash(r, c, placed):
    for o in placed:
        if o == r or b.fp[o]['side'] != b.fp[r]['side']: continue
        C = b.court(o)
        if min(c[2], C[2]) - max(c[0], C[0]) > 0.05 and min(c[3], C[3]) - max(c[1], C[1]) > 0.05: return True
    return False
out = [r for r, n in owner.items() if not b.fixed(r) and r != 'L402' and not inside(b.court(r), rooms[n]['boxes'], 0.45)]
placed = set(b.fp) - set(out); parked = []
for r in sorted(out, key=lambda r: -(b.court(r)[2]-b.court(r)[0]) * (b.court(r)[3]-b.court(r)[1])):
    x0, y0 = b.fp[r]['x0'], b.fp[r]['y0']; best = None
    for B in rooms[owner[r]]['boxes']:
        x = B[0]
        while x <= B[2]:
            y = B[1]
            while y <= B[3]:
                b.P[r] = [x, y, 0]; c = b.court(r)
                if inside(c, rooms[owner[r]]['boxes']) and not clash(r, c, placed):
                    d = abs(x-x0) + abs(y-y0)
                    if best is None or d < best[0]: best = (d, x, y)
                y += 0.25
            x += 0.25
    if best is None: print('NO ROOM to park', r, 'in', owner[r]); b.P[r] = [x0, y0, 0]; continue
    b.P[r] = [round(best[1], 2), round(best[2], 2), 0]; placed.add(r); parked.append((r, owner[r], round(best[0], 1)))
print('parked:', parked)
os.makedirs(ROOMS, exist_ok=True)
for n, s in rooms.items(): json.dump(s, open(os.path.join(ROOMS, n + '.spec.json'), 'w'), indent=1)
json.dump(b.P, open(MASTER, 'w'), indent=0)
import collections
for n, s in rooms.items():
    A = sum((bx[2]-bx[0]) * (bx[3]-bx[1]) for bx in s['boxes']); fixedA = 0
    for r in b.fp:
        if b.fixed(r) and b.fp[r]['side'] == 'F.Cu':
            c = b.court(r); fixedA += sum(max(0, min(c[2], B[2]) - max(c[0], B[0])) * max(0, min(c[3], B[3]) - max(c[1], B[1])) for B in s['boxes'])
    pa = sum((b.court(r)[2]-b.court(r)[0]) * (b.court(r)[3]-b.court(r)[1]) for r in s['parts'] if not b.fixed(r))
    print(f'{n:11s} {len(s["parts"]):3d} parts  {pa:5.0f} mm2 of parts in {A-fixedA:5.0f} mm2 free  = {100*pa/(A-fixedA):.0f} %')
pr = [p for p in b.check() if not (p.startswith('OVERLAP') and float(p.split()[-2]) < 0.1)]; print(pr)
b.render(os.path.join(ROOMS, 'floorplan.png'), rats=False, label=True, scale=20, boxes={n: bx for n, s in rooms.items() for bx in [s['box']]})
