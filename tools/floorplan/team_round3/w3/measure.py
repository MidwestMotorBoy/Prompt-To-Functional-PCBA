"""measure.py <fill.json> [log]: parts within 2.5 mm (courtyard gap, same side) of U403 U503 U401 U501, and the repaired count"""
import json, sys, collections
D = json.load(open('/home/claude/work/hp/q7s2_fz_dump.json'))
def boxes(pl, dump):
    out = {}
    for f in dump['fps']:
        r = f['ref']; c = f.get('court')
        if not c: continue
        if pl is not None and r in pl:
            x, y, a = pl[r][:3]; k = (int(a) // 90) % 4
        else:
            x, y, k = f['x'], f['y'], 0
        pts = [(c[0] - f['x'], c[1] - f['y']), (c[2] - f['x'], c[3] - f['y'])]
        for _ in range(k): pts = [(-v[1], v[0]) for v in pts]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        out[r] = (x + min(xs), y + min(ys), x + max(xs), y + max(ys), f['side'])
    return out
def near(B, ic, g=2.5):
    a = B[ic]; n = 0
    for r, b in B.items():
        if r == ic or b[4] != a[4]: continue
        cx = (b[0] + b[2]) / 2; cy = (b[1] + b[3]) / 2      # part centre within g of the IC courtyard
        dx = max(0, cx - a[2], a[0] - cx); dy = max(0, cy - a[3], a[1] - cy)
        if (dx * dx + dy * dy) ** 0.5 <= g: n += 1
    return n
pl = json.load(open(sys.argv[1])) if sys.argv[1] != 'hand' else None
dump = D if pl is not None else json.load(open('/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/board_dump.json'))
B = boxes(pl, dump)
print("NEAR", {ic: near(B, ic) for ic in ('U403', 'U503', 'U401', 'U501')})
if len(sys.argv) > 2:
    for l in open(sys.argv[2]):
        if '"repaired"' in l:
            p = json.loads(l)['parts']; c = collections.Counter(p)
            print("REPAIRED", len(p), "distinct", len(c), "top", c.most_common(8))
