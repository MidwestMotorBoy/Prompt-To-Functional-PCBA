"""Team D worker `te3`: hand routes for the open connections of p2 at y < 104, x >= 100.
   python3 te3.py drop   -> te3_drop.json (removals only; apply p2 -> te3a)
   python3 te3.py        -> te3.json (drops + routes, built against te3a; apply to p2 for the final board)"""
import sys, json; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'
R = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
DROPS = [
    # GND stitch via between U401.38 and C403.1 and its B.Cu chain to the C403.2 via: room for the U401.38 3V3 via
    ('GND', None, [103.0, 79.2, 105.2, 80.8]),
    # CC2 B.Cu track under U401.37: re-laid further north so DRV9_OFF gets a via above its pin
    ('/USB Port 1/CC2', 'B.Cu', [101.6, 75.8, 108.4, 79.55]),
    # C_CC1 F arch round the U405 CC2 corner pins: re-laid as vias + B.Cu
    ('/USB Port 1/C_CC1', 'F.Cu', [101.4, 71.8, 103.06, 73.51]),
    # I2CC_SCL In2 vertical + jog that box the HG1 via in Q401.1: re-laid west of the via
    ('/USB Port 1/I2CC_SCL', 'In2.Cu', [106.3, 90.1, 107.6, 99.4]),
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'p2')
    for d in DROPS: h.drop(*d)
    h.save(R + 'te3_drop.json'); sys.exit()

h = HR(D, 'te3b')
for d in DROPS: h.drop(*d)
def T(label, r): print('%-14s %s' % (label, r))

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

# --- Net-(Q409-D): R454.1 east under the REGN via (0.15 neck), up the gap beside C457.2 to Q409.3
N = 'Net-(Q409-D)'
T('Q409-D a', h.seg(N, 'F.Cu', [(115.475, 86.735), (115.55, 86.63), (116.42, 86.63)], w=0.15))
T('Q409-D b', h.seg(N, 'F.Cu', [(116.42, 86.63), (116.42, 84.6)]))

# --- DRV9_OFF: U401.37 via -> In3 -> via on the R455.2 - Q409.1 track
N = '/USB Port 1/DRV9_OFF'
T('DRV9 viaR', h.via(N, 114.83, 82.55))
T('DRV9 in3', h.auto(N, 'In3.Cu', (105.39, 79.95), (114.83, 82.55), margin=4, clr=0.15))

# --- /P1_LDO_3V3: R455.1 and R441.1 each to a via, joined on In3 to the R404.1 via (108.525, 87.4245);
#     the R441 via sits in the AC_SNS_N finger tip (dead end, refills) and keeps 0.25 from the In3 PPHV diagonal
N = '/P1_LDO_3V3'
T('LDO via455', h.via(N, 114.705, 81.235)); T('LDO stub455', h.seg(N, 'F.Cu', [(114.805, 81.535), (114.705, 81.235)]))
T('LDO via441', h.via(N, 109.85, 87.08)); T('LDO stub441', h.seg(N, 'F.Cu', [(110.472, 87.225), (109.85, 87.08)]))
T('LDO 455-441', h.auto(N, 'In3.Cu', (114.705, 81.235), (109.85, 87.08), margin=3, clr=0.25))
T('LDO 441-404', h.auto(N, 'In3.Cu', (109.85, 87.08), (108.525, 87.4245), margin=2))

# --- SBU_FLT: U401.19 via (109.925, 84.4745) -> In2 -> via beside U405.9
N = '/USB Port 1/SBU_FLT'
T('SBU via405', h.via(N, 101.25, 73.9)); T('SBU stub405', h.seg(N, 'F.Cu', [(102.05, 74.3), (101.45, 74.3), (101.25, 74.1), (101.25, 73.9)]))
T('SBU in2', h.auto(N, 'In2.Cu', (101.25, 73.9), (109.925, 84.4745), margin=3))

# --- I2CC_SCL In2 re-laid west of the HG1 via (it used to box the via in from the east and south)
N = '/USB Port 1/I2CC_SCL'
T('SCLc relay', h.seg(N, 'In2.Cu', [(107.525, 90.2245), (107.525, 97.3), (106.325, 98.5), (106.325, 99.3245)]))

# --- HG1: existing via in Q401.1 -> In2 -> via at the top of R444.2's pad
N = '/USB Port 1/HG1'
T('HG1 via', h.via(N, 110.54, 102.17))
T('HG1 stub', h.seg(N, 'F.Cu', [(110.44, 102.47), (110.54, 102.17)]))
T('HG1 in2', h.auto(N, 'In2.Cu', (106.96, 98.825), (110.54, 102.17), margin=2))

# --- C_CC1 / C_CC2 at J401 / U405. In3 carries EN_5V2 (y 71.77) and CELL3 (y 70.13) right across, so the vias sit
#     in the F gap between the two VBUS blobs (x 105.3 - 107.4, y 70.6 - 71.3) or inside the old C_CC1 arch.
N = '/USB Port 1/C_CC2'
T('CC2 viaU', h.via(N, 101.8, 72.3))
T('CC2 stubU', h.seg(N, 'F.Cu', [(102.65, 72.5), (102.45, 72.3), (101.8, 72.3)]))
T('CC2 viaJ', h.via(N, 105.75, 70.85))
T('CC2 stubJ', h.seg(N, 'F.Cu', [(104.75, 69.17), (104.75, 69.95), (105.45, 69.95), (105.75, 70.25), (105.75, 70.85)]))
T('CC2 in2', h.auto(N, 'In2.Cu', (105.75, 70.85), (101.8, 72.3), margin=2))
N = '/USB Port 1/C_CC1'
T('CC1 viaJ', h.via(N, 106.5, 70.9))
T('CC1 A5-via', h.seg(N, 'F.Cu', [(107.75, 69.17), (107.75, 69.95), (107.45, 69.95), (106.5, 70.9)]))
T('CC1 via-pin4', h.seg(N, 'F.Cu', [(106.5, 70.9), (105.93, 71.47), (103.05, 71.47), (103.05, 72.5)]))
T('CC1 viaB', h.via(N, 101.15, 73.05)); T('CC1 stubB', h.seg(N, 'F.Cu', [(102.05, 73.5), (101.6, 73.5), (101.15, 73.05)]))
T('CC1 B', h.auto(N, 'B.Cu', (101.15, 73.05), (106.5, 70.9), margin=2))

h.save(R + 'te3.json')
