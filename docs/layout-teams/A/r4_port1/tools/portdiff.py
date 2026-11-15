"""portdiff.py bare.json : compare port 1 (4xx) and port 2 (5xx) poses relative to anchors (U401/U501, J401/J501, L401/L501, U403/U503)."""
import json, sys, re
d = json.load(open(sys.argv[1]))
fp = {f['ref']: f for f in d['fps']}
anch = ['U401', 'J401', 'L401', 'U403']
def rel(r, a):
    f, g = fp[r], fp[a]
    return (round(f['x'] - g['x'], 2), round(f['y'] - g['y'], 2), f['rot'] % 360, f['layer'][0])
rows = []
for r in sorted(fp):
    m = re.match(r'^([A-Z]+)4(\d\d)$', r)
    if not m: continue
    r2 = m.group(1) + '5' + m.group(2)
    if r2 not in fp: rows.append((r, '-', 'no twin')); continue
    best = None
    for a in anch:
        a2 = a.replace('4', '5', 1)
        p1, p2 = rel(r, a), rel(r2, a2)
        dd = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])
        if best is None or dd < best[0]: best = (dd, a, p1, p2)
    dd, a, p1, p2 = best
    if dd > 0.05 or p1[2] != p2[2] or p1[3] != p2[3]:
        rows.append((r, r2, 'vs %s: p1 %s p2 %s  |d|=%.2f' % (a, p1, p2, dd)))
for x in rows: print(*x)
print('anchors:', {a: (fp[a]['x'], fp[a]['y'], fp[a]['rot']) for a in anch + [a.replace('4', '5', 1) for a in anch]})
