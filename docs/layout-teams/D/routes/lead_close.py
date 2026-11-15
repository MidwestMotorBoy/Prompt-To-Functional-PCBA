"""Lead closing pass: every net whose copper is still in separate pieces gets each piece joined to the largest one
with the multi-layer search (tools/mroute.py).   python3 lead_close.py <dir> <board> <out.json> [net regex]"""
import sys, re, json, time; sys.path.insert(0, '../tools')
from mroute import MR
d, board, out = sys.argv[1:4]; rx = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
m = MR(d, board)
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and kind not in ("keepout",) and n not in ("GND", "<keepout>")})
W = {"HighCurrent": (0.8, 0.5, 0.3), "Power": (0.4, 0.25, 0.2), "GateDrive": (0.3, 0.2), "Kelvin": (0.2, 0.15)}
order = {"HighCurrent": 0, "Power": 1}
left = []
for net in sorted(nets, key=lambda n: (order.get(m.cls(n), 2), n)):
    if rx and not rx.search(net): continue
    cl = m.clusters(net)
    if len(cl) < 2: continue
    print("%s (%s): %d pieces" % (net, m.cls(net), len(cl)), flush=True)
    for k in range(1, len(cl)):
        cs = m.clusters(net)                                  # pieces change as they are joined
        if len(cs) < 2: break
        small = cs[-1]; done = False; t0 = time.time()
        for w in W.get(m.cls(net), (0.2, 0.15)):
            for margin in (4.0, 9.0):
                for target in cs[:-1][:2]:
                    r = m.join(net, small, target, w=w, margin=margin, quiet=True)
                    if r is not None: done = True; print("   joined at w %.2f (%.0f s)" % (w, time.time() - t0), flush=True); break
                if done: break
            if done: break
        if not done:
            from shapely.ops import unary_union
            b = unary_union([g for gs in small.values() for g in gs]).bounds
            print("   NOT JOINED: piece at (%.1f, %.1f)-(%.1f, %.1f)" % b, flush=True); left.append((net, [round(v, 1) for v in b])); break
m.ok = not left; m.save(out); print("left:", left)
