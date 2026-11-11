"""in4cross.py out.json tag=cu.json ...: for each board, the signal tracks cut into the In4 ground plane: how many nets on B and In3
cross a slot (their return has to step round it), how much runs within 3 mm of a board edge, and how much lies under or over
sense-pair copper or switching copper on the two neighbouring layers (In3, B)."""
import json, sys, math, re
SENSE = re.compile(r'(SRP|SRN|ACP|ACN)(_F)?$|SNS_[PN]$'); SWN = re.compile(r'/SW[12]$|SW_5V$|SW_3V3$|BTST[12]$|BST_5V$|HIDRV[12]$|/HG[12]$')
def ccw(a, b, c): return (c[1]-a[1])*(b[0]-a[0]) - (b[1]-a[1])*(c[0]-a[0])
def X(p1, p2, p3, p4): return ccw(p1, p3, p4) * ccw(p2, p3, p4) < 0 and ccw(p1, p2, p3) * ccw(p1, p2, p4) < 0
def dseg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p; vx, vy = bx - ax, by - ay; L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / L2)); return math.hypot(px - ax - t * vx, py - ay - t * vy)
out = {}
for arg in sys.argv[2:]:
    tag, f = arg.split('='); d = json.load(open(f))
    sl = [t for t in d['tracks'] if t['l'] == 'In4' and t['net'] != 'GND']; res = {}
    for L in ('B', 'In3'):
        for t in d['tracks']:
            if t['l'] != L or t['net'] == 'GND': continue
            for s in sl:
                if s['net'] != t['net'] and X((t['x1'], t['y1']), (t['x2'], t['y2']), (s['x1'], s['y1']), (s['x2'], s['y2'])): res.setdefault((L, t['net']), set()).add(s['net'])
    xs = [p['x'] for p in d['pads']]; ys = [p['y'] for p in d['pads']]; ex0, ex1, ey0, ey1 = 78.6, 122.4, 63.6, 137.4
    edge = sens = sw = tot = 0.0; near = {}
    adj = [t for t in d['tracks'] if t['l'] in ('In3', 'B') and (SENSE.search(t['net']) or SWN.search(t['net']))]
    for s in sl:
        n = max(2, int(math.hypot(s['x2'] - s['x1'], s['y2'] - s['y1']) / 0.1) + 1); step = math.hypot(s['x2'] - s['x1'], s['y2'] - s['y1']) / (n - 1)
        for k in range(n):
            x = s['x1'] + (s['x2'] - s['x1']) * k / (n - 1); y = s['y1'] + (s['y2'] - s['y1']) * k / (n - 1); w = step * (0.5 if k in (0, n - 1) else 1); tot += w
            if min(x - ex0, ex1 - x, y - ey0, ey1 - y) < 3.0: edge += w
            for t in adj:
                if dseg((x, y), (t['x1'], t['y1']), (t['x2'], t['y2'])) < t['w'] / 2 + s['w'] / 2 + 0.1:
                    if SENSE.search(t['net']): sens += w; near.setdefault('sense', set()).add((s['net'].split('/')[-1], t['net'].split('/')[-1], t['l']))
                    else: sw += w; near.setdefault('sw', set()).add((s['net'].split('/')[-1], t['net'].split('/')[-1], t['l']))
                    break
    out[tag] = len(res); out[tag + '_detail'] = dict(total=round(tot, 1), edge=round(edge, 1), over_sense=round(sens, 1), over_switching=round(sw, 1), near={k: sorted(v) for k, v in near.items()},
                                                    crossing=sorted(f"{L} {n.split('/')[-1]}" for L, n in res))
    print(tag, len(res), 'crossing nets; total %.1f mm, edge %.1f, over sense %.1f, over switching %.1f' % (tot, edge, sens, sw), {k: sorted(v) for k, v in near.items()})
out['edge'] = out['fix_detail']['edge']
json.dump(out, open(sys.argv[1], 'w'), indent=1)
