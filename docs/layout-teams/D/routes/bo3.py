"""bo3: team D region y > 104 on board p2 (p2_open items with both ends at y >= 104 + U101 clearance fixes).
   python3 bo3.py drop -> bo3_drop.json (apply p2 -> bo3a);  python3 bo3.py -> bo3.json (built on bo3a; apply to bo3a)"""
import sys, math; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'; R = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
TS1, BTP, SMBD = '/Cells and Gauge/TS1', '/Cells and Gauge/BTP_INT', 'Net-(U101-SMBD)'
DROPS = [
    # U101 small-signal stubs that run from the pad centre past the CELL_1N (HighCurrent, 0.25 mm) pads/tracks
    (TS1, 'F.Cu', [98.0, 128.95, 98.2, 129.35]),
    (BTP, 'F.Cu', [100.0, 129.25, 100.2, 129.64]),
    (SMBD, 'F.Cu', [100.95, 128.3, 101.34, 128.45]),
    # SCL In3 jog under R302.1 (3V3 pad that needs a via in the pad): re-laid 0.4 mm further north
    ('SCL', 'In3.Cu', [108.4, 122.9, 111.3, 123.6]),
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'p2')
    for d in DROPS: h.drop(*d)
    # re-lay each from the far end of its pad (the end toward its via / track)
    h.seg(TS1, 'F.Cu', [(98.12, 129.05), (98.125, 128.9745)])
    h.seg(BTP, 'F.Cu', [(100.12, 129.55), (100.125, 129.6245)])
    h.seg(SMBD, 'F.Cu', [(101.27, 128.4), (101.325, 128.3745)])
    h.seg('SCL', 'In3.Cu', [(111.225, 123.4745), (111.225, 123.0745), (108.525, 123.0745)])
    h.save(R + 'bo3_drop.json'); sys.exit()

# ---------------- stage 2: built on bo3a (p2 + bo3_drop.json) ----------------
import fnmatch
from shapely.geometry import Polygon, Point
from obst import load_copper, SIG
h = HR(D, 'bo3a')
Z, T, VV = load_copper(D + '/bo3a.kicad_pcb')
G, V3, CP, SCL, CE = 'GND', '3V3', '/Cells and Gauge/CELL_P', 'SCL', '/USB Port 1/CE_N'
# real DRC is 0.15 mm (0.25 HighCurrent copper to Default-class copper); the HR checker uses 0.2: a relaxed via check
HCP = ['PACK_P', 'CELL_N', '/Cells and Gauge/CELL*', '/Cells and Gauge/FET_MID', '*/VBAT_SYS', '*/PPHV', '*/VBUS', '*/SW1', '*/SW2', '*/AC_SNS_N', '*/BAT_SNS_P']
OTH = ['*/ACP_F', '*/ACN_F', '*/SRP_F', '*/SRN_F', '/Cells and Gauge/SRP', '/Cells and Gauge/SRN', 'Net-(U101-*', '3V3', '*/3V3_*', '*/SW_3V3', '*/PACK_LP',
       '*/LDO_IN', '*/PP5V', '*/5V_IN', '*/SW_5V', '*/REGN', '*/LDO_3V3', '/P1_LDO_3V3', '*/5V_AMP', 'GND', '*/HG1', '*/HG2', '*/LG1', '*/LG2', '*/HIDRV*', '*/LODRV*', '/Cells and Gauge/*_G']
def cls(n): return 'HC' if any(fnmatch.fnmatchcase(n, p) for p in HCP) else ('O' if any(fnmatch.fnmatchcase(n, p) for p in OTH) else 'D')
def rvia(net, x, y):
    g = Point(x, y).buffer(0.225); bad = []
    if not h.outline.contains(g.buffer(0.3)): return [(0, 'edge')]
    for L in SIG:
        for i in h.tree[L].query(g.buffer(0.4)):
            gg, n, kind, name = h.items[L][int(i)]
            if n == net or (kind == 'pour' and n in h.soft): continue
            need = 0.26 if kind != 'pad' and {cls(net), cls(n)} == {'HC', 'D'} else 0.16
            if g.distance(gg) < need: bad.append((round(g.distance(gg), 3), kind, name, L))
    for vx, vy, s, n in h.vias:
        d = math.hypot(vx - x, vy - y)
        if 1e-6 < d < (0.5 if n == net else 0.61): bad.append((round(d, 3), 'via spacing', n))
    return bad
def rfree(net, x, y, r=1.5, n=8, inside=None):
    c = []; k = int(r / 0.05)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            px, py = round(x + i * 0.05, 3), round(y + j * 0.05, 3); d = math.hypot(px - x, py - y)
            if d <= r and (inside is None or inside.contains(Point(px, py))) and not rvia(net, px, py): c.append((d, px, py))
    c.sort(); out = []
    for d, px, py in c:
        if all(math.hypot(px - q[1], py - q[2]) > 0.3 for q in out): out.append((round(d, 2), px, py))
        if len(out) >= n: break
    return out
def pour(net, L, pt):
    for z in Z:
        if z['net'] == net and z['layer'] == L and len(z['pts']) > 2:
            p = Polygon(z['pts']).buffer(0)
            if p.distance(Point(pt)) < 0.05: return p
def tryauto(net, layers, a, b, clrs=(0.2, 0.15), w=0.2, margin=2):
    for c in clrs:
        for L in layers:
            p = h.auto(net, L, a, b, w=w, clr=c, margin=margin)
            if p: print('  ok', net, L, a, '->', b, 'clr', c); return L
    print('  FAILED', net, a, '->', b); return None
def via(net, x, y):
    bad = rvia(net, x, y)
    if bad: print('  rvia PROBLEM', net, x, y, bad)
    h.via(net, x, y, quiet=True)
from shapely.strtree import STRtree
def guard(L, on):
    """HighCurrent copper needs 0.25 mm from Default-class tracks: inflate it by 0.1 on layer L while routing with clr 0.15"""
    h.items[L] = [i for i in h.items[L] if i[1] != 'HCGUARD']
    if on: h.items[L] += [(g.buffer(0.1), 'HCGUARD', 'track', 'HCGUARD') for g, n, k, nm in h.items[L] if cls(n) == 'HC' and k in ('track', 'via', 'pour')]
    h.tree[L] = STRtree([i[0] for i in h.items[L]])
def hop(net, src, targets, layers=('In2.Cu', 'B.Cu'), clrs=(0.2, 0.15), margin=2):
    """src via -> first target (x, y, new_via) reachable on one layer"""
    for t in targets:
        for c in clrs:
            for L in layers:
                if h.auto(net, L, src, (t[0], t[1]), clr=c, margin=margin):
                    if t[2]: via(net, t[0], t[1])
                    print('  hop', net, src, '->', t, L, c); return t
    print('  hop FAILED', net, src); return None

main = pour(V3, 'In3.Cu', (110.875, 116.9745))          # the big In3 3V3 pour (main group)
mainI = main.buffer(-0.35)

# --- GND U404.1: walled-in F GND island; a via at the pad corner to the In1/In4 planes
via(G, 101.3, 112.5); h.seg(G, 'F.Cu', [(101.575, 112.065), (101.3, 112.5)])

# --- 3V3 scrap round via (104.125, 115.17): In3 track into the main pour, else a hop to a new via on it
src = (104.125, 115.1745)
cand = sorted(((Point(src).distance(Point(x, y)), x, y) for x in [103 + 0.1 * i for i in range(40)] for y in [113 + 0.1 * j for j in range(40)]
               if mainI.contains(Point(x, y))))[:60:6]
if not any(h.auto(V3, 'In3.Cu', src, (x, y), clr=0.15, margin=1.5) and print('  scrap92 In3 ->', x, y) is None for d, x, y in cand):
    hop(V3, src, [(x, y, True) for d, x, y in rfree(V3, 104.1, 115.2, 2.5, n=12, inside=mainI)])

# --- 3V3 scrap at U301.6 (via 115.425, 118.82): In3 into the main pour, else hop
src = (115.425, 118.8245)
cand = sorted(((Point(src).distance(Point(x, y)), x, y) for x in [113.5 + 0.1 * i for i in range(40)] for y in [116.5 + 0.1 * j for j in range(40)]
               if mainI.contains(Point(x, y))))[:60:6]
if not any(h.auto(V3, 'In3.Cu', src, (x, y), clr=0.15, margin=1.5) and print('  scrap95 In3 ->', x, y) is None for d, x, y in cand):
    hop(V3, src, [(x, y, True) for d, x, y in rfree(V3, 115.4, 118.8, 2.5, n=12, inside=mainI)])

# --- 3V3 R302.1 / R313.1: a via in each pad (SCL moved off R302.1 in stage 1), joined, then a hop to the main pour
print('R302 vias', rvia(V3, 109.6, 123.6), rvia(V3, 109.65, 125.25))
via(V3, 109.6, 123.6); via(V3, 109.65, 125.25)
tryauto(V3, ['In2.Cu', 'B.Cu'], (109.65, 125.25), (109.6, 123.6), clrs=(0.2, 0.15))
hop(V3, (109.6, 123.6), [(x, y, True) for d, x, y in rfree(V3, 110.0, 121.0, 3.0, n=14, inside=mainI)] + [(110.875, 116.9745, False)])

# --- 3V3 R314.1 group (In3 scrap round via 103.875, 126.02): hop from that via to the main pour or to the R313.1 via
src = (103.875, 126.0245)
S94 = pour(V3, 'In3.Cu', (101.0, 125.6)); print('scrap94', S94 and S94.bounds)
srcs = [(103.875, 126.0245, False)] + [(x, y, True) for d, x, y in rfree(V3, 98.5, 126.0, 5.0, n=12, inside=S94.buffer(-0.25))]
tgts = [(x, y, True) for d, x, y in rfree(V3, 100.5, 122.0, 6.0, n=16, inside=mainI)]
print('srcs', srcs); print('tgts', tgts)
def hop2(net, srcs, tgts, layers=('In2.Cu', 'B.Cu'), clrs=(0.2, 0.15)):
    pairs = sorted((math.hypot(s[0] - t[0], s[1] - t[1]), s, t) for s in srcs for t in tgts)
    for d, s, t in pairs[:40]:
        for c in clrs:
            for L in layers:
                if h.auto(net, L, (s[0], s[1]), (t[0], t[1]), clr=c, margin=1.5):
                    for v in (s, t):
                        if v[2]: via(net, v[0], v[1])
                    print('  hop2', net, s, '->', t, L, c); return True
    print('  hop2 FAILED', net); return False
# (no free via spot on either side: the group sits between the FET_MID and CELL_P F pours; not closed)

# --- CELL_P R118.1 / R110.2: not closed. R118.1 has one via spot (110.8, 117.6) but it is boxed in on every inner layer
# by the 3V3 via (110.875, 116.97) and the TS4 / EN_5V1 / GAUGE_FUSE vias; R110.2 + C110.1 sit over the 3 mm In2 and 1.5 mm
# B.Cu PACK_P power tracks (no via possible) and are walled on F by the CHG track, R109 and the FET_MID pour.

# --- CE_N U403.7: not closed. Pin stub + F to a via at (111.45, 114.4) works, but the only In3 corridor west to R435.2 needs a
# 0.15 mm track that passes 0.15 mm from a PPHV via (HighCurrent: 0.25 needed) and its loop cuts an island out of the In3
# 3V3 pour (which the scrap-92 hop above lands on); with the 0.25 guard there is no path on In3, In2 or B.Cu.

# --- SCL R115.2: via beside the pad, In3 north-east past the blue PACK track's via and between the 3V3 via (103.875, 126.02)
# and the IRQ_N via (104.775, 125.87) (0.46 mm gap: 0.15 mm track) to the SCL In3 track at y 124.67
print('R115 via', rvia(SCL, 102.52, 127.76))
via(SCL, 102.52, 127.76); h.seg(SCL, 'F.Cu', [(102.215, 127.815), (102.52, 127.76)])
h.seg(SCL, 'In3.Cu', [(102.52, 127.76), (103.5, 127.2), (104.325, 126.375), (104.325, 124.6745)], w=0.15)

# --- SCL J302.6: not closed. A 0.15 F neck between J302.3/.4 and .5 reaches the one legal via spot (108.7, 133.0), but from
# there no layer reaches SCL copper (R115.2 via, In3 SCL track, SCL vias at 115.475, 123.42): boxed in on In2/In3/B.Cu.

h.save(R + 'bo3.json')
