"""lfree.py cu.json net fromlayer tolayer[,tolayer]: along the net's tracks on fromlayer, where would the same line be legal on tolayer
(0.2 mm track, 0.15 mm to other nets' tracks, vias and holes; plane pours ignored)? Prints blocked stretches and what blocks them."""
import json, sys, math
d = json.load(open(sys.argv[1])); net = sys.argv[2]; FL = sys.argv[3]
def dseg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p; vx, vy = bx - ax, by - ay; L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / L2)); return math.hypot(px - ax - t * vx, py - ay - t * vy)
S = [t for t in d['tracks'] if t['net'] == net and t['l'] == FL]
for TL in sys.argv[4].split(','):
    T = [t for t in d['tracks'] if t['l'] == TL and t['net'] != net]; V = [v for v in d['vias'] if v['net'] != net]
    H = [p for p in d['pads'] if p['hole'] > 0 and p['net'] != net]
    tot = 0; bad = 0; runs = []
    for s in S:
        L = math.hypot(s['x2'] - s['x1'], s['y2'] - s['y1']); n = max(1, int(L / 0.1))
        for i in range(n + 1):
            p = (s['x1'] + (s['x2'] - s['x1']) * i / n, s['y1'] + (s['y2'] - s['y1']) * i / n); why = None
            for t in T:
                if abs(t['x1'] - p[0]) > 30 and abs(t['x2'] - p[0]) > 30: continue
                if dseg(p, (t['x1'], t['y1']), (t['x2'], t['y2'])) < 0.1 + t['w'] / 2 + 0.15: why = 'trk ' + t['net']; break
            if not why:
                for v in V:
                    if math.hypot(v['x'] - p[0], v['y'] - p[1]) < 0.1 + 0.225 + 0.15: why = 'via ' + v['net']; break
            if not why:
                for h in H:
                    if math.hypot(h['x'] - p[0], h['y'] - p[1]) < 0.1 + h['hole'] / 2 + 0.35: why = 'hole ' + h['ref']; break
            tot += L / (n + 1)
            if why:
                bad += L / (n + 1)
                if runs and runs[-1][2] == why and math.hypot(runs[-1][1][0] - p[0], runs[-1][1][1] - p[1]) < 0.5: runs[-1][1] = p
                else: runs.append([p, p, why])
    print('%s -> %s: %.1f mm, blocked %.1f mm in %d stretches' % (FL, TL, tot, bad, len(runs)))
    for a, b, w in runs: print('   (%.2f,%.2f)-(%.2f,%.2f) %s' % (a[0], a[1], b[0], b[1], w))
