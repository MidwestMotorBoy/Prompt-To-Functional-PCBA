"""Lead closing pass 3: like lead_close.py, but a net that was pulled to make room may itself pull others (depth-limited
rip-up and re-lay, every level undone as a whole when it does not work out).
   python3 lead_close3.py <dir> <board> <out.json> [depth=2] [net regex]"""
import sys, re, json, time, copy; sys.path.insert(0, '../tools')
from mroute import MR
from shapely.strtree import STRtree
from shapely.ops import unary_union
d, board, out = sys.argv[1:4]; DEPTH = int(sys.argv[4]) if len(sys.argv) > 4 else 2; rx = re.compile(sys.argv[5]) if len(sys.argv) > 5 else None
m = MR(d, board)
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and kind != "keepout" and n not in ("GND", "<keepout>")})
W = {"HighCurrent": (0.8, 0.5, 0.3), "Power": (0.4, 0.25, 0.2), "GateDrive": (0.3, 0.2), "Kelvin": (0.2, 0.15)}
ELIG = {n for n in nets if m.cls(n) in ("Default", "Kelvin", "GateDrive") and m.npads(n) <= 8}
def snap(): return ({L: list(v) for L, v in m.items.items()}, list(m.vias), copy.deepcopy(m.J))
def restore(s):
    m.items = {L: list(v) for L, v in s[0].items()}; m.vias = list(s[1]); m.J = copy.deepcopy(s[2])
    for L in m.items: m.tree[L] = STRtree([i[0] for i in m.items[L]])
def direct(net, small, cs):
    for w in W.get(m.cls(net), (0.2, 0.15)):
        for margin in (4.0, 9.0):
            for target in cs[:2]:
                if target is small: continue
                if m.join(net, small, target, w=w, margin=margin, quiet=True) is not None: return True
    return False
T0 = time.time()
def close(net, depth, chain, ind="  "):
    for k in range(12):
        cs = m.clusters(net)
        if len(cs) < 2: return True
        small = cs[-1]; n0 = len(cs); s0 = snap()
        if direct(net, small, cs):
            if len(m.clusters(net)) < n0: continue
            restore(s0)
        if depth == 0: return False
        banned = set(); done = False
        for attempt in range(3 if not chain else 2):
            cand = ELIG - chain - banned - {net}
            r = m.join(net, small, cs[0], w=W.get(m.cls(net), (0.2, 0.15))[-1], margin=9.0, quiet=True, ghost=cand)
            if not r or r[0] != "RIP" or not r[1]: break
            s = snap()
            for v in r[1]: m.rip(v)
            c2 = m.clusters(net)
            good = (len(c2) < 2 or direct(net, c2[-1], c2)) and len(m.clusters(net)) < n0
            if good:
                for v in r[1]:
                    if not close(v, depth - 1, chain | {net} | set(r[1]), ind + "  "): good = False; break
            if good: print("%s%s: joined after pulling and re-laying %s (%.0f s)" % (ind, net, r[1], time.time() - T0), flush=True); done = True; break
            restore(s); banned |= set(r[1]); print("%s%s: pulling %s did not work out" % (ind, net, r[1]), flush=True)
        if not done: return False
    return len(m.clusters(net)) < 2
order = {"HighCurrent": 0, "Power": 1}
queue = [n for n in sorted(nets, key=lambda n: (order.get(m.cls(n), 2), n)) if (not rx or rx.search(n)) and len(m.clusters(n)) > 1]
print(len(queue), "nets in pieces:", queue, flush=True); left = []
for rnd in range(2):
    left = []
    for net in queue:
        s = snap()
        if close(net, DEPTH, frozenset()): print("%s: closed" % net, flush=True)
        else:
            restore(s); left.append(net); b = [unary_union([g for gs in c.values() for g in gs]).bounds for c in m.clusters(net)[1:]]
            print("%s: NOT JOINED, pieces at %s" % (net, [tuple(round(v, 1) for v in x) for x in b]), flush=True)
    if not left or len(left) == len(queue): break
    queue = left
m.ok = not left; m.save(out); print("left:", left)
