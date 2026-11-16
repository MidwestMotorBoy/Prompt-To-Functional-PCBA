import sys, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
from dc_score import load_copper
b, keep, x, y, r = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
Z, T, V = load_copper(b); Zk, Tk, Vk = load_copper(keep)
kt = {(t['net'], t['layer'], tuple(t['a']), tuple(t['b'])) for t in Tk}; kv = {(v['net'], round(v['x'],3), round(v['y'],3)) for v in Vk}
def dseg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p; dx, dy = bx-ax, by-ay; L = dx*dx+dy*dy
    t = 0 if L == 0 else max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/L)); return math.hypot(px-ax-t*dx, py-ay-t*dy)
for t in T:
    d = dseg((x, y), t['a'], t['b'])
    if d <= r: print('T %-6s %-28s w%.2f %s -> %s d %.2f %s' % (t['layer'], t['net'], t['w'], t['a'], t['b'], d, 'PLAN' if (t['net'], t['layer'], tuple(t['a']), tuple(t['b'])) in kt else ''))
for v in V:
    d = math.hypot(v['x']-x, v['y']-y)
    if d <= r: print('V %-28s %.3f,%.3f d %.2f %s' % (v['net'], v['x'], v['y'], d, 'PLAN' if (v['net'], round(v['x'],3), round(v['y'],3)) in kv else ''), {k: v[k] for k in v if k not in ('net','x','y')})
