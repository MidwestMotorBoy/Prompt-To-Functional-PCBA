"""Lead closing pass: every net whose copper is still in separate pieces gets each piece joined to the largest one
with the multi-layer search (tools/mroute.py).   python3 lead_close.py <dir> <board> <out.json> [net regex]"""
import sys, re, json, time; sys.path.insert(0, '../tools')
from mroute import MR
d, board, out = sys.argv[1:4]; rx = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
m = MR(d, board)
if len(sys.argv) > 5 and "nostrapB" in sys.argv[5]:           # give the signals B.Cu as a second crossing layer under the pack strap
    m.rip_tracks("PACK_P", "B.Cu", (100.0, 106.0, 120.0, 119.5)); print("pulled the PACK_P strap on B.Cu", flush=True)
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and kind not in ("keepout",) and n not in ("GND", "<keepout>")})
W = {"HighCurrent": (0.8, 0.5, 0.3), "Power": (0.4, 0.25, 0.2), "GateDrive": (0.3, 0.2), "Kelvin": (0.2, 0.15)}
order = {"HighCurrent": 0, "Power": 1}
import copy
from shapely.strtree import STRtree
from shapely.ops import unary_union
left = []; rips = [0]
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
def simple(net):
    """join all pieces of a net without pulling anything; True when it is one piece"""
    for k in range(12):
        cs = m.clusters(net)
        if len(cs) < 2: return True
        if not direct(net, cs[-1], cs): return False
    return False
def close(net):
    for k in range(12):
        cs = m.clusters(net)
        if len(cs) < 2: return True
        small = cs[-1]; n0 = len(cs); s0 = snap()
        if direct(net, small, cs):
            if len(m.clusters(net)) < n0: print("   joined", flush=True); continue
            restore(s0); print("   (a join that did not merge the pieces was undone)", flush=True)
        banned = set(); done = False
        for attempt in range(4):
            cand = {n for n in nets if n != net and n not in banned and m.cls(n) in ("Default", "Kelvin", "GateDrive") and m.npads(n) <= 8}
            r = m.join(net, small, cs[0], w=W.get(m.cls(net), (0.2, 0.15))[-1], margin=9.0, quiet=True, ghost=cand)
            if not r or r[0] != "RIP" or not r[1]: break
            s = snap()
            for v in r[1]: m.rip(v)
            good = direct(net, m.clusters(net)[-1], m.clusters(net)) if len(m.clusters(net)) > 1 else True
            good = good and len(m.clusters(net)) < n0 and all(simple(v) for v in r[1])
            if good: print("   joined after pulling and re-laying", r[1], flush=True); done = True; rips[0] += 1; break
            restore(s); banned |= set(r[1]); print("   pulling", r[1], "did not work out, put back", flush=True)
        if not done:
            b = unary_union([g for gs in small.values() for g in gs]).bounds
            print("   NOT JOINED: piece at (%.1f, %.1f)-(%.1f, %.1f)" % b, flush=True); return False
    return len(m.clusters(net)) < 2
queue = [n for n in sorted(nets, key=lambda n: (order.get(m.cls(n), 2), n)) if (not rx or rx.search(n)) and len(m.clusters(n)) > 1]
print(len(queue), "nets in pieces:", queue, flush=True)
for net in queue:
    print("%s (%s)" % (net, m.cls(net)), flush=True)
    if not close(net): left.append(net)
for net in list(left):                                        # second chance: the board has changed
    print("again: %s" % net, flush=True)
    if close(net): left.remove(net)
if len(sys.argv) > 5 and "nostrapB" in sys.argv[5]:           # put a strap back on B.Cu round the new signals, as wide as fits
    for w in (1.5, 1.2, 1.0, 0.8, 0.6):
        if m.strap("PACK_P", (100.8, 116.3), (119.0, 106.8), w, "B.Cu") is not None: print("PACK_P strap back on B.Cu at %.1f mm" % w); break
    else: print("no PACK_P strap fits on B.Cu any more")
m.ok = not left; m.save(out); print("left:", left)
