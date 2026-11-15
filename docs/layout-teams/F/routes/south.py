"""Region south (y 112..137): close the open items left by the router. Re-run from the top on board g1."""
import sys, math; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/tools')
from ml import ML
from shapely.geometry import Point, box
h = ML('/home/claude/runs/c_south', 'g1')
EN_VC = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
CN = '/Cells and Gauge/CELL_1N'; TS1 = '/Cells and Gauge/TS1'; BTP = '/Cells and Gauge/BTP_INT'; SMBD = 'Net-(U101-SMBD)'

# ---- 4. gauge U101: HighCurrent CELL_1N stubs vs small-signal stubs. Both tracks ran side by side over their own
# pads (0.4 mm pitch); shorten each so that they end inside their pad at opposite ends.
h.drop(CN, 'F.Cu', [97.9, 130.3, 98.3, 130.6]);  h.force(CN, 'F.Cu', [(98.025, 130.4745), (98.10, 130.465)], w=0.2)
h.drop(TS1, 'F.Cu', [98.4, 130.0, 98.7, 130.6]); h.force(TS1, 'F.Cu', [(98.55, 130.125), (98.56, 130.25)], w=0.2)
h.drop(SMBD, 'F.Cu', [101.10, 129.50, 101.50, 129.60]); h.force(SMBD, 'F.Cu', [(101.125, 129.5245), (101.25, 129.535)], w=0.2)
h.drop(CN, 'F.Cu', [101.40, 129.90, 102.00, 130.00]); h.force(CN, 'F.Cu', [(101.70, 129.96), (101.975, 129.9745)], w=0.15)
h.drop(BTP, 'F.Cu', [100.50, 130.10, 100.65, 130.50]); h.force(BTP, 'F.Cu', [(100.575, 130.1245), (100.573, 130.25)], w=0.2)
h.drop(CN, 'F.Cu', [100.90, 130.40, 101.05, 131.10]); h.force(CN, 'F.Cu', [(100.97, 130.65), (100.975, 131.0745)], w=0.15)

# ---- 1. EN_5V1. U404 pad 2 is walled in by GND (pad 1, C439.2, R432.2 and its via) and the PACK_P via field.
# The only legal way on F.Cu: south out of the pin, round the east and south side of R432.2 (GND) between that pad
# and the PACK_P vias at (101.15, 115.975) / (100.15, 115.975), up into R432.1. 0.15 mm, exact points.
h.force('EN_5V1', 'F.Cu', [(101.75, 113.9), (101.75, 114.33), (101.2, 114.88), (101.2, 115.12), (100.93, 115.455),
                           (100.693, 115.51), (100.413, 115.475), (100.203, 115.399), (100.1, 115.15)], w=0.15)
# U301 pad 12 sits in a pocket closed on every layer (B.Cu: CELL_P + SDA + IRQ_N; In2: CHG_INH + TS4; In3: SDA +
# TS2; F: pads), and the PACK_P island of item 3 is cut off only by SDA's In2 trunk. So SDA is re-laid: its detour
# U301 -B- via(110.775,115.92) -F- via(109.525,114.67) -In2- (106.675,114.82) .. (101.425,128.72) -In3- via(104.025,
# 129.32) is dropped and replaced by a new route from the gauge end to the MCU end. EN_5V1 then takes the B.Cu
# corridor beside the CELL_P track up to a via at (110.45, 117.25), squeezes on In3 between the WAKE via and the
# CELL_P via (0.15 mm) and runs on In3 to a via at R432.1.
for L in ('In2.Cu', 'In3.Cu'): h._add(L, box(111.5, 111.5, 114.0, 118.5), '__scl_reserve__', 'track')   # not saved: keeps my routes out
h.drop('SDA', 'B.Cu', [109.4, 115.7, 111.6, 120.25])
h.drop('SDA', 'F.Cu', [109.3, 114.4, 111.0, 116.15])
h.drop('SDA', 'In2.Cu', [101.2, 114.4, 109.75, 128.95])
h.drop('SDA', 'In3.Cu', [102.1, 128.5, 104.25, 129.65])
for x, y in ((111.375, 120.0245), (110.775, 119.8245)): h.via('SDA', x, y)     # the drops took these vias too
h.via('EN_5V1', 110.45, 117.25)
u = h.pad('U301', 12)
print('EN south', h.route('EN_5V1', (u[0], u[1]), (110.45, 117.25), layers=('F.Cu', 'B.Cu'), margin=3))
r = h.pad('R432', 1)
# west on In2 (free now that SDA's trunk is gone); In3 here would cut the neck of the 3V3 pour that feeds the MCU
ew = h.route('EN_5V1', (110.45, 117.25), (r[0], r[1]), layers=('F.Cu', 'In2.Cu', 'In3.Cu'), margin=5, via_cost=EN_VC)
print('EN west', ew)

# ---- 3. PACK_P island (D103.2 + via 103.45/128.175 + In2 pour piece): hard track on In2 to the Q101/Q102 via field
pk = None
for w in (0.3, 0.25, 0.2):
    pk = h.route('PACK_P', (103.45, 128.175), (103.15, 117.174), w=w, margin=4, layers=('In2.Cu',), quiet=True)
    if pk: break
print('PACK_P', w, pk)
# SDA again: gauge end (via 106.325/130.32, F to R116.2 and J302.1) to the MCU end. The old gauge-side via
# (104.025, 129.32) and its F stub to R116.2 are not needed any more (R116.2 keeps its F track to via 106.325).
h.drop('SDA', 'F.Cu', [103.2, 129.15, 104.2, 130.27])
sd = None
for b in ((111.375, 120.0245), (110.775, 119.8245), (106.725, 120.0745), (104.975, 119.4745)):
    for w in (0.2, 0.15):
        sd = h.route('SDA', (106.325, 130.3245), b, w=w, margin=5, quiet=True)
        if sd: break
    if sd: break
print('SDA', b, w, sd)

# ---- 2. 3V3
# R417.2: dangling stub -> drop it; with SDA's F link gone the pad reaches C303.1 on F
h.drop('3V3', 'F.Cu', [110.3, 114.9, 111.0, 115.6])
a = h.pad('R417', 2)
c = h.pad('C303', 1)
print('R417', h.route('3V3', (a[0], a[1]), (c[0], c[1]), layers=('F.Cu',)) or h.try_route('3V3', (a[0], a[1]), (110.775, 118.9745)))
# J301.1 (Tag-Connect pin 1): LEFT OPEN, see report (no via spot, F walled by Net-(C313-Pad2) / C314.1 / RFIO / CELL_1N via)
# U301 pins 6/7 (via 114.325/120.125) <-> R314 branch (In3 track at y 121.27)
print('U301.6', h.route('3V3', (114.325, 120.1245), (115.3, 121.2745), layers=('In3.Cu',)))
# C207.1 (buck output capacitor) sits on an F pour piece without a via
a = h.pad('C207', 1); print('C207 plane', h.plane('3V3', (a[0], a[1]), w=0.3))

h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/routes/south.json')
if len(sys.argv) > 2:
    sys.path.insert(0, '/home/claude/runs/c_south'); import pred; print('3V3 In3 pour components at 4 vias:', pred.pred(h, h.J))
