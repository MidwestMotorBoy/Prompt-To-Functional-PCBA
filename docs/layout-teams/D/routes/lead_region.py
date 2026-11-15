"""Lead closing pass 2: region re-route. Where a pin stays walled in, every small signal net with copper in a box
round it is pulled and the whole group is laid again, the stuck nets first, in several orders; the result is kept
only if every net of the group ends up in one piece.   python3 lead_region.py <dir> <board> <out.json>"""
import sys, json, time, copy, random; sys.path.insert(0, '../tools')
from mroute import MR
from shapely.geometry import box as sbox
from shapely.strtree import STRtree
d, board, out = sys.argv[1:4]
m = MR(d, board)
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and n not in ("GND", "<keepout>")})
W = {"HighCurrent": (0.5, 0.3), "Power": (0.4, 0.25, 0.2), "GateDrive": (0.3, 0.2), "Kelvin": (0.2, 0.15)}
def snap(): return ({L: list(v) for L, v in m.items.items()}, list(m.vias), copy.deepcopy(m.J))
def restore(s):
    m.items = {L: list(v) for L, v in s[0].items()}; m.vias = list(s[1]); m.J = copy.deepcopy(s[2])
    for L in m.items: m.tree[L] = STRtree([i[0] for i in m.items[L]])
def simple(net):
    for k in range(12):
        cs = m.clusters(net)
        if len(cs) < 2: return True
        n0 = len(cs); ok = False
        for w in W.get(m.cls(net), (0.2, 0.15)):
            for margin in (4.0, 9.0):
                for target in cs[:2]:
                    if target is cs[-1]: continue
                    if m.join(net, cs[-1], target, w=w, margin=margin, quiet=True) is not None: ok = True; break
                if ok: break
            if ok: break
        if not ok or len(m.clusters(net)) >= n0: return False
    return False
REGIONS = [("U403 south and east pins", (108.0, 108.0, 119.0, 116.5), ["/USB Port 1/CE_N", "/USB Port 1/CHG_INT", "Net-(U403-FB)"]),
           ("U401 south pins", (103.5, 83.5, 110.5, 88.5), ["/USB Port 1/I2CC_SDA"]),
           ("U503 north pins", (83.5, 109.5, 90.0, 115.5), ["/USB Port 2/I2CC_SDA"]),
           ("U501 south pins", (85.5, 83.5, 93.5, 88.0), ["/USB Port 2/CHG_INT"]),
           ("MCU and gauge crossing", (100.0, 112.0, 114.0, 128.5), ["/Cells and Gauge/CELL_P", "IRQ_N", "SDA", "3V3"])]
left = []
for name, bx, stuck in REGIONS:
    stuck = [n for n in stuck if len(m.clusters(n)) > 1]
    if not stuck: print(name, ": nothing open"); continue
    B = sbox(*bx)
    vic = sorted({n for L in m.items for geo, n, kind, _ in m.items[L] if kind in ("track", "via") and n not in stuck and n in nets
                  and m.cls(n) in ("Default", "Kelvin", "GateDrive") and m.npads(n) <= 8 and geo.intersects(B)})
    print("%s: stuck %s, group of %d nets" % (name, stuck, len(vic)), flush=True); s0 = snap(); done = False; t0 = time.time()
    for attempt in range(8):
        restore(s0)
        for v in vic: m.rip(v)
        order = list(vic); random.Random(attempt).shuffle(order)
        if attempt % 2: order = stuck + order                 # stuck nets first on odd tries, last on even ones
        else: order = order + stuck
        bad = [n for n in order if not simple(n)]
        print("   try %d: %s (%.0f s)" % (attempt, "all joined" if not bad else "failed " + str(bad[:6]), time.time() - t0), flush=True)
        if not bad: done = True; break
    if not done:                                                # keep the best partial: the original state
        restore(s0); left += stuck
m.ok = not left; m.save(out); print("left:", left)
