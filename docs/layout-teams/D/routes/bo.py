"""bo: hand routes for team D region y > 104 on board g2 (g2_open items with both ends at y >= 104 + U101 clearance fixes).
Stage 1 (bo_drop.json, applied to g2 -> bo1): drops + re-lays that free space.  Stage 2 (bo.json, applied to bo1 -> bo2)."""
import sys, math; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR, load_copper
from shapely.geometry import Polygon, Point
D = '/home/claude/runs/r2_route'; R = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
STAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 2

if STAGE == 1:
    h = HR(D, 'g2')
    # U101 clearance (CELL_1N HighCurrent needs 0.25 to small-signal tracks): drop the stub from the pad centre,
    # start from the far end of the pad instead.
    h.drop('/Cells and Gauge/TS1', 'F.Cu', [98.0, 129.25, 98.2, 129.64])
    h.seg('/Cells and Gauge/TS1', 'F.Cu', [(98.12, 129.55), (98.125, 129.6245)])
    h.drop('/Cells and Gauge/BTP_INT', 'F.Cu', [100.0, 129.25, 100.2, 129.64])
    h.seg('/Cells and Gauge/BTP_INT', 'F.Cu', [(100.12, 129.55), (100.125, 129.6245)])
    h.drop('Net-(U101-SMBD)', 'F.Cu', [100.95, 128.3, 101.34, 128.45])
    h.seg('Net-(U101-SMBD)', 'F.Cu', [(101.27, 128.4), (101.325, 128.3745)])
    # SS_5V went C439.1 -> via -> In2 -> via -> round U404.1; that via walls in U404.1 (GND). Re-lay it on F directly.
    h.drop('/USB Port 1/SS_5V', None, [100.5, 109.1, 102.2, 112.4])
    h.seg('/USB Port 1/SS_5V', 'F.Cu', [(101.115, 109.455), (101.115, 110.0), (101.83, 110.0), (102.075, 110.245), (102.075, 110.585)], w=0.15)
    h.save(R + 'bo_drop.json')
    raise SystemExit

h = HR(D, 'bo1')
Z, T, VV = load_copper(D + '/bo1.kicad_pcb')

def tryauto(net, layers, a, b, w=0.2, clrs=(0.2, 0.15), margin=3):
    for c in clrs:
        for L in layers:
            p = h.auto(net, L, a, b, w=w, clr=c, margin=margin)
            if p: print('  ok', net, L, a, b, 'clr', c); return L
    return None

def pour(net, layer, pt):
    for z in Z:
        if z['net'] == net and z['layer'] == layer:
            p = Polygon(z['pts']).buffer(0)
            if p.distance(Point(pt)) < 0.05: return p
    print('  no pour of', net, layer, 'at', pt)

def bridge(net, A, B, mid, r=2.0, layers=('In2.Cu', 'B.Cu', 'F.Cu'), w=0.2):
    """two new vias, one on In3 pour A and one on In3 pour B, joined on another layer"""
    fv = h.free_vias(net, mid[0], mid[1], r, n=40)
    ca = [(d, x, y) for d, x, y in fv if A.buffer(-0.3).contains(Point(x, y))]
    cb = [(d, x, y) for d, x, y in fv if B.buffer(-0.3).contains(Point(x, y))]
    pairs = sorted(((math.hypot(a[1] - b[1], a[2] - b[2]), a, b) for a in ca for b in cb))
    for dd, a, b in pairs[:12]:
        if dd < 0.6: continue
        for L in layers:
            p = h.auto(net, L, (a[1], a[2]), (b[1], b[2]), w=w, clr=0.2, margin=1.5)
            if p:
                h.via(net, a[1], a[2]); h.via(net, b[1], b[2]); print('  bridge', net, L, a, b); return True
    print('  bridge FAILED', net, mid, len(ca), len(cb)); return False

G, V3, CP, SCL = 'GND', '3V3', '/Cells and Gauge/CELL_P', 'SCL'

# --- GND U404.1: the SS_5V via that walled it is gone (stage 1); a GND via west of the pad
fv = h.free_vias(G, 100.95, 111.7, 0.7); print('GND vias', fv)
for d, x, y in fv:
    if tryauto(G, ['F.Cu'], (101.575, 112.065), (x, y), clrs=(0.2, 0.15), margin=1): h.via(G, x, y); break

# --- 3V3 islands on In3 (the board is too full for new vias on both sides: use the islands' own vias)
main = pour(V3, 'In3.Cu', (98.625, 115.1745))
V3vias = [(v['x'], v['y']) for v in VV if v['net'] == V3]
mainv = [p for p in V3vias if main.buffer(-0.1).contains(Point(p))]
def island(srcs, r=6.0, layers=('In2.Cu', 'B.Cu')):
    tg = sorted(((math.hypot(s[0] - t[0], s[1] - t[1]), s, t, False) for s in srcs for t in mainv if math.hypot(s[0] - t[0], s[1] - t[1]) < r))
    for s in srcs:
        for d, x, y in h.free_vias(V3, s[0], s[1], r, n=60):
            if main.buffer(-0.3).contains(Point(x, y)): tg.append((d + 0.5, s, (x, y), True))
    tg.sort()
    for d, s, t, new in tg[:14]:
        for L in layers:
            if h.auto(V3, L, s, t, margin=2, clr=0.2):
                if new: h.via(V3, t[0], t[1])
                print('  island', s, '->', t, L, 'new via' if new else ''); return True
    print('  island FAILED', srcs, len(tg)); return False
def padvia(net, x0, x1, y0, y1):
    best = None
    for i in range(int((x1 - x0) / 0.02) + 1):
        for j in range(int((y1 - y0) / 0.02) + 1):
            x, y = round(x0 + i * 0.02, 3), round(y0 + j * 0.02, 3); bad = h.via_ok(net, x, y)
            m = min([b[0] for b in bad] + [9]); m2 = min([b[0] for b in bad if b[1] in ('track', 'via')] + [9])
            if best is None or min(m2, m + 0.03) > best[0]: best = (min(m2, m + 0.03), x, y, bad)
    print('  padvia', net, best); return best
# island() runs (slow) gave: 92 scrap (R517.2 via) -> new via on the main pour at (87.775, 113.675) on In2;
# nothing for the C207 scrap (no free via spot on either side within 8 mm), the 94 scrap (via 110.225,118.87; CHG/WAKE
# vias cut its neck to the main pour at (106.4, 115.34); In2/B paths blocked) or the R314 group.
if tryauto(V3, ['In2.Cu'], (87.725, 114.9745), (87.775, 113.675), margin=2, clrs=(0.2,)): h.via(V3, 87.775, 113.675)
# R302.1 / R313.1: via inside each pad at the padvia() spot farthest from the In3 tracks under them (the CELL_P pour
# refills round it), joined on In2, then B.Cu to the 3V3 via (110.225, 118.8745) of the R305 group.
h.via(V3, 109.61, 123.6); h.via(V3, 109.63, 125.25)
tryauto(V3, ['In2.Cu', 'B.Cu'], (109.63, 125.25), (109.61, 123.6))
tryauto(V3, ['B.Cu', 'In2.Cu'], (109.61, 123.6), (110.225, 118.8745))

# --- CELL_P: R118.1 and R110.2 have PACK_P / EN_5V1 tracks under them on In2/B (no via); try F into the pour
# tried: auto F w 0.3 from each pad to Q101.3: NO PATH (vias, tracks and the FET_MID pour in the way)

# --- SCL: R115.2 to J302.6 on F (stub north out of the Tag-Connect pad); no free via spot within 2 mm of J302.6
# tried: 0.15 stub north out of J302.6 + auto F (clr 0.15) to R115.2: NO PATH (not kept)

# --- Net-(C313-Pad2): C313.1 (RFIO) blocks F; no via spot in or near C313.2 / C314.1 / R321.1 (In2/In3 tracks under)
h.save(R + 'bo.json')
