"""bot: hand routes for team D region y > 104 (k2_open items + U101 clearance fixes)."""
import sys, math; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR, load_copper
from shapely.geometry import Polygon, Point
from shapely.ops import nearest_points
D = '/home/claude/runs/r2_route'
h = HR(D, 'k2')

def tryauto(net, layers, a, b, margin=3, w=0.2, clr=0.2):
    for L in layers:
        p = h.auto(net, L, a, b, w=w, margin=margin, clr=clr)
        if p: print('  ok', net, L, a, b); return p
    return None

# --- U101 clearance fixes (HighCurrent CELL_1N needs 0.25 to small-signal tracks): start the small-signal escapes
#     from the far end of their pad instead of the pad centre next to CELL_1N copper.
h.drop('/Cells and Gauge/TS1', 'F.Cu', [98.0, 128.95, 98.25, 129.35])
h.seg('/Cells and Gauge/TS1', 'F.Cu', [(98.12, 129.05), (98.125, 128.9745)])
h.drop('/Cells and Gauge/BTP_INT', 'F.Cu', [100.0, 129.25, 100.25, 129.65])
h.seg('/Cells and Gauge/BTP_INT', 'F.Cu', [(100.12, 129.55), (100.125, 129.6245)])
h.drop('Net-(U101-SMBD)', 'F.Cu', [100.95, 128.3, 101.34, 128.45])
h.seg('Net-(U101-SMBD)', 'F.Cu', [(101.27, 128.39), (101.325, 128.3745)])

# --- 3V3
V = '3V3'
Z, T, VV = load_copper(D + '/k2.kicad_pcb')
P = {i: Polygon(z['pts']).buffer(0) for i, z in enumerate(Z) if z['net'] == V and z['layer'] == 'In3.Cu'}
main = max(P.values(), key=lambda p: p.area)
# R417.2 group: via (101.125,115.1745) sits on a 1 mm2 scrap of the In3 plane; run In3 into the main plane
a, _ = nearest_points(main.buffer(-0.35), Point(101.125, 115.1745))
if not tryauto(V, ['In3.Cu'], (101.125, 115.1745), (round(a.x, 2), round(a.y, 2)), clr=0.16):
    for d, x, y in h.free_vias(V, 101.125, 115.1745, 3, n=12):
        if main.buffer(-0.2).contains(Point(x, y)):
            print('  R417 jumper via', x, y)
            h.via(V, x, y)
            if tryauto(V, ['F.Cu', 'B.Cu', 'In2.Cu'], (101.125, 115.1745), (x, y), clr=0.16): break
# C207 / TP301 scraps: B jumper to a new via on the main plane
h.via(V, 86.388, 122.649)
tryauto(V, ['B.Cu', 'In2.Cu'], (86.075, 124.4245), (86.388, 122.649))
tryauto(V, ['B.Cu', 'In2.Cu'], (89.075, 125.7245), (86.075, 124.4245))
# R302.1 / R313.1 walled by the CELL_P pour: via in each pad, B.Cu to the 3V3 via at (110.225,119.27)
h.via(V, 109.62, 123.58); h.via(V, 109.62, 125.38)
tryauto(V, ['In2.Cu', 'B.Cu'], (109.62, 125.38), (109.62, 123.58))
tryauto(V, ['B.Cu', 'In2.Cu'], (109.62, 123.58), (110.225, 119.2745))

# --- SCL: R115.2 to the nearest SCL copper of the main net (via 107.425,113.575) on In2
N = 'SCL'
h.via(N, 102.72, 127.81); h.seg(N, 'F.Cu', [(102.22, 127.81), (102.72, 127.81)])
tryauto(N, ['In2.Cu'], (102.72, 127.81), (107.425, 113.575))

# --- short ones on F
# SS_5V: C439.1 down between the C439.2 and U404.8 pads into U404.7 (0.15 neck, 0.175 to each pad)
h.seg('/USB Port 1/SS_5V', 'F.Cu', [(101.11, 109.45), (101.11, 110.0), (101.83, 110.0), (102.08, 110.25), (102.08, 110.58)], w=0.15)

# Not routed (see report): Net-(U403-FB) pin 12 is boxed by pins 11/13 and the SRN_F Kelvin track; C313-Pad2 to R321.1
# and SWDIO J301.2 to U301.20 found no legal path on any layer; SCL J302.6 (Tag-Connect) is boxed by its guide holes,
# the CELL_P pours and In2/In3 tracks; 3V3 R314.1 island (In3 scrap) has no free via spot or single/two-layer path.
h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/bot.json')
