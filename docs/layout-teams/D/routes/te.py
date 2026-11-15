"""Team D worker `te`: hand routes for the open connections of g2 at y < 104, x >= 100.
   python3 te.py drop   -> te_drop.json (removals only; apply g2 -> te1)
   python3 te.py        -> te.json (drops + routes, built against te1; apply to g2 for the final board)"""
import sys, json; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'
R = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
DROPS = [
    # GND stitch via north of U401.37/38 and its B.Cu tails: makes room for the U401.38 3V3 escape; the EP keeps its own vias
    ('GND', None, [104.40, 79.95, 105.03, 80.0]),
    ('GND', 'B.Cu', [103.8, 79.95, 106.25, 81.18]),
    # CC2 B.Cu track under U401.37: re-laid further north so DRV9_OFF gets a via above its pin
    ('/USB Port 1/CC2', 'B.Cu', [101.6, 75.8, 108.4, 79.55]),
    # C_CC1 F arch round the U405 CC2 corner pins: re-laid as vias + B.Cu
    ('/USB Port 1/C_CC1', 'F.Cu', [101.4, 71.8, 103.06, 73.51]),
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'te1')
    for d in DROPS: h.drop(*d)
    h.save(R + 'te_drop.json'); sys.exit()

h = HR(D, 'te2')
for d in DROPS: h.drop(*d)
def T(label, r): print('%-14s %s' % (label, r))

# --- restore the GND via + B tail that the B.Cu box also caught (EP corner via at 105.125, 81.1745)
T('GND via EP', h.via('GND', 105.125, 81.1745)); T('GND via F', h.via('GND', 104.475, 80.8745))

# --- GND pins 36 / 31 of U401: short necks straight down into the exposed pad (U401.39)
T('U401.36', h.seg('GND', 'F.Cu', [(105.79, 80.46), (105.79, 81.25)], w=0.15))
T('U401.31', h.seg('GND', 'F.Cu', [(107.8, 80.46), (107.8, 81.4), (107.6, 81.4)], w=0.15))

# --- 3V3 U401.38: via where the GND stitch via was, into the In3 3V3 pour (and the F pour at C403)
T('3V3 via38', h.via('3V3', 104.45, 80.1))
T('3V3 stub38', h.seg('3V3', 'F.Cu', [(104.675, 80.4245), (104.45, 80.2), (104.45, 80.1)]))

# --- CC2 B.Cu re-laid north of the DRV9_OFF via
N = '/USB Port 1/DRV9_OFF'
T('DRV9 via', h.via(N, 105.39, 79.95))
T('DRV9 stub', h.seg(N, 'F.Cu', [(105.392, 80.464), (105.39, 79.95)], w=0.15))
T('CC2 vias', (h.via('/USB Port 1/CC2', 108.375, 79.5245), h.via('/USB Port 1/CC2', 101.625, 75.8745)))
T('CC2 B', h.auto('/USB Port 1/CC2', 'B.Cu', (108.375, 79.5245), (101.625, 75.8745), margin=2))

# --- Net-(Q409-D): R454.1 up to Q409.3
T('Q409-D', h.seg('Net-(Q409-D)', 'F.Cu', [(115.475, 86.735), (115.55, 86.68), (116.42, 86.68), (116.42, 84.6)]))

# --- DRV9_OFF: U401.37 via -> In3 -> via beside R455.2
T('DRV9 viaR', h.via(N, 114.83, 82.55))          # on the R455.2 - Q409.1 track
T('DRV9 in3', h.auto(N, 'In3.Cu', (105.39, 79.95), (114.83, 82.55), margin=3))

# --- /P1_LDO_3V3: R455.1 and R441.1 each to a via, joined on In3 to the R404.1 via (108.525, 87.4245)
N = '/P1_LDO_3V3'
T('LDO via455', h.via(N, 114.855, 81.185)); T('LDO stub455', h.seg(N, 'F.Cu', [(114.805, 81.535), (114.855, 81.185)]))
T('LDO via441', h.via(N, 109.922, 87.075)); T('LDO stub441', h.seg(N, 'F.Cu', [(110.472, 87.225), (109.922, 87.075)]))
T('LDO 455-441', h.auto(N, 'In3.Cu', (114.855, 81.185), (109.922, 87.075), margin=3))
T('LDO 441-404', h.auto(N, 'In3.Cu', (109.922, 87.075), (108.525, 87.4245), margin=2))

# --- SBU_FLT: U401.19 via (109.925, 84.4745) -> In3 -> via beside U405.9
N = '/USB Port 1/SBU_FLT'
T('SBU via405', h.via(N, 101.25, 74.1)); T('SBU stub405', h.seg(N, 'F.Cu', [(102.05, 74.3), (101.45, 74.3), (101.25, 74.1)]))
# In2, north of the I2CC_SDA loop, through the gap between its 45-degree corner and the GND via at (108.55, 78.075)
T('SBU in2 a', h.auto(N, 'In2.Cu', (101.25, 74.1), (107.669, 77.967), margin=3))
T('SBU in2 gap', h.seg(N, 'In2.Cu', [(107.669, 77.967), (108.569, 78.867)]))
T('SBU in2 b', h.auto(N, 'In2.Cu', (108.569, 78.867), (109.925, 84.4745), margin=3, clr=0.26))

# --- HG1: Q401.1 via-in-pad -> In2 -> via at the top of R444.2's pad (clear of the TS In2 and BTST1 In3 tracks)
T('HG1 via', h.via('/USB Port 1/HG1', 110.54, 102.17))
T('HG1 in2', h.auto('/USB Port 1/HG1', 'In2.Cu', (106.96, 98.825), (110.54, 102.17)))

# --- C_CC2: corner pins -> via -> In2 -> via under J401.B5 ; C_CC1: pins 4 and 7 each to a via, joined on B.Cu, In3 to J401.A5
N = '/USB Port 1/C_CC2'
T('CC2 viaU', h.via(N, 101.8, 72.2))
T('CC2 stubU', h.seg(N, 'F.Cu', [(102.65, 72.5), (102.35, 72.2), (101.8, 72.2)]))
T('CC2 viaB5', h.via(N, 104.75, 69.9))
T('CC2 stubB5', h.seg(N, 'F.Cu', [(104.75, 69.1745), (104.75, 69.9)]))
N = '/USB Port 1/C_CC1'
T('CC1 viaA', h.via(N, 103.0, 71.6)); T('CC1 stubA', h.seg(N, 'F.Cu', [(103.05, 72.5), (103.0, 71.6)]))
T('CC2 in2', h.auto('/USB Port 1/C_CC2', 'In2.Cu', (101.8, 72.2), (104.75, 69.9)))
T('CC1 viaB', h.via(N, 100.9, 73.5)); T('CC1 stubB', h.seg(N, 'F.Cu', [(102.05, 73.5), (100.9, 73.5)]))
T('CC1 B-A', h.auto(N, 'B.Cu', (103.0, 71.6), (100.9, 73.5), margin=5))
T('CC1 viaJ', h.via(N, 107.725, 69.9245))
T('CC1 stubJ', h.seg(N, 'F.Cu', [(107.75, 69.1745), (107.725, 69.9245)]))
T('CC1 A-J', h.auto(N, 'In3.Cu', (103.0, 71.6), (107.725, 69.9245)))

h.save(R + 'te.json')
