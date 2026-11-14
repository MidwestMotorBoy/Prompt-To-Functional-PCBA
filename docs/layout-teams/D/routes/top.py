"""Team D worker `top`: hand routes for the open connections at y < 104.
   python3 top.py drop   -> top_drop.json (removals only; apply k2 -> top1)
   python3 top.py        -> top.json (drops + routes, built against top1; apply to k2 for the final board)"""
import sys, json; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'
DROPS = [
    ('/USB Port 1/C_CC1', 'In3.Cu', [102.2, 69.8, 107.85, 70.8]),      # CC1 inner track under J401.B5: re-laid
    ('/USB Port 1/C_CC1', 'F.Cu', [101.4, 70.67, 103.06, 73.51]),      # CC1 arch round the U405 CC2 corner pins: re-laid
    ('/USB Port 1/SW1', 'In3.Cu', [109.5, 101.25, 114.73, 102.23]),    # SW1 / BTST1 under R444.2: re-laid either side
    ('/USB Port 1/BTST1', 'In3.Cu', [109.0, 102.7, 113.33, 102.98]),   #   of a new HG1 via
    ('SCL', None, [84.0, 84.2, 85.25, 86.13]),                          # U501 S-side fan-out: SCL, SDA, IRQ_N vias re-spaced
    ('GND', None, [84.9, 84.35, 85.2, 84.9]),                           #   (pin 12 GND via moves into the exposed pad)
    ('SCL', None, [104.25, 84.6, 105.8, 85.45]),                        # U401 SCL escape crossed under SDA pin 8: re-laid
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'k2')
    for d in DROPS: h.drop(*d)
    h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/top_drop.json'); sys.exit()

h = HR(D, 'top2')
for d in DROPS: h.drop(*d)
def T(label, r): print('%-14s %s' % (label, r))

# --- GND pins: short necks into the exposed pads, and vias to the C*38 caps
T('U501.3', h.seg('GND', 'F.Cu', [(82.67, 82.10), (83.6, 82.10)]))
T('U501.36', h.seg('GND', 'F.Cu', [(84.00, 80.38), (84.00, 81.2)], w=0.15))
T('U401.36', h.seg('GND', 'F.Cu', [(105.79, 80.46), (105.79, 81.2)], w=0.15))
T('C538', h.seg('GND', 'F.Cu', [(90.15, 97.17), (90.94, 97.35)]))
T('C438', h.seg('GND', 'F.Cu', [(113.25, 97.17), (114.04, 97.35)]))

# --- 3V3 U401.38 up into the F 3V3 pour at C403
T('U401.38', h.seg('3V3', 'F.Cu', [(104.88, 80.42), (104.88, 79.9), (104.53, 79.55), (104.35, 79.55)]))

# --- C_CC2 / C_CC1 at U405: CC2 corner pins -> via -> In2 -> via under J401.B5; CC1 pins 4 and 7 each to a via, joined on In3
T('CC2 viaU0', h.via('/USB Port 1/C_CC2', 101.8, 72.2))   # placed first so the CC1 bottom track keeps clear
N = '/USB Port 1/C_CC1'
T('CC1 viaA', h.via(N, 103.0, 71.6)); T('CC1 stubA', h.seg(N, 'F.Cu', [(103.05, 72.5), (103.0, 71.6)]))
T('CC1 viaB', h.via(N, 100.9, 73.5)); T('CC1 stubB', h.seg(N, 'F.Cu', [(102.05, 73.5), (100.9, 73.5)]))
T('CC1 B-A', h.auto(N, 'B.Cu', (103.0, 71.6), (100.9, 73.5), margin=5))
T('CC1 viaJ', h.via(N, 107.725, 69.9245))   # J401.A5 via, removed with the old inner track
T('CC1 A-J', h.auto(N, 'In3.Cu', (103.0, 71.6), (107.725, 69.9245)))

N = '/USB Port 1/C_CC2'
T('CC2 viaB5', h.via(N, 104.75, 69.9))
T('CC2 stubB5', h.seg(N, 'F.Cu', [(104.75, 69.17), (104.75, 69.9)]))
T('CC2 stubU', h.seg(N, 'F.Cu', [(102.65, 72.5), (102.35, 72.2), (101.8, 72.2)]))
T('CC2 in2', h.auto(N, 'In2.Cu', (101.8, 72.2), (104.75, 69.9)))
# --- HG1: Q401.1 via -> In2 -> via in R444.2; SW1 and BTST1 In3 re-laid either side of it
T('HG1 via', h.via('/USB Port 1/HG1', 110.44, 102.47))
T('HG1 in2', h.auto('/USB Port 1/HG1', 'In2.Cu', (106.96, 98.82), (110.44, 102.47)))
T('BTST1 via', h.via('/USB Port 1/BTST1', 113.325, 102.9745))
T('BTST1 in3', h.seg('/USB Port 1/BTST1', 'In3.Cu', [(113.325, 102.9745), (112.33, 101.98), (109.85, 101.98), (109.85, 102.5), (109.6, 102.75), (109.025, 102.7245)]))
T('SW1 via', h.via('/USB Port 1/SW1', 109.525, 101.2745))
T('SW1 in3', h.auto('/USB Port 1/SW1', 'In3.Cu', (109.525, 101.2745), (114.725, 102.2245)))

# --- Net-(Q409-D): R454.1 up to Q409.3
T('Q409-D', h.seg('Net-(Q409-D)', 'F.Cu', [(115.47, 86.73), (116.45, 86.73), (116.45, 84.9), (116.72, 84.44)]))

# --- /P1_LDO_3V3: R403 via -In3- R404 via -In2- R441 via -In2- R455 via
N = '/P1_LDO_3V3'
T('R403-R441', h.seg(N, 'F.Cu', [(106.87, 87.22), (108.67, 87.22), (110.47, 87.22)]))   # along the pad row, through AC_SNS_N finger tips


# --- 3V3: the In3 pour lobe round U501.38 is cut off from the main pour; bridge it on In2 with a via in each
T('3V3 viaL', h.via('3V3', 81.7, 79.5)); T('3V3 viaM', h.via('3V3', 88.9, 79.2))
T('3V3 bridge', h.auto('3V3', 'In2.Cu', (81.7, 79.5), (88.9, 79.2), margin=3))

# --- C504.2 GND pour island: via to the planes
T('C504 via', h.via('GND', 80.4, 82.2)); T('C504 stub', h.seg('GND', 'F.Cu', [(79.75, 82.28), (80.4, 82.2)]))

# --- U501 S side: SDA (pin 8) left, SCL (pin 9) straight down, IRQ_N (pin 10) right; GND pin 12 into the pad
T('GND p12', h.seg('GND', 'F.Cu', [(85.2, 84.22), (85.2, 83.45)], w=0.15))
T('SDA viaU', h.via('SDA', 83.3, 85.0)); T('SDA stubU', h.seg('SDA', 'F.Cu', [(83.6, 84.22), (83.6, 84.7), (83.3, 85.0)]))
T('SCL viaU', h.via('SCL', 84.0, 85.35)); T('SCL stubU', h.seg('SCL', 'F.Cu', [(84.0, 84.22), (84.0, 85.35)]))
T('SCL in3', h.auto('SCL', 'In3.Cu', (84.0, 85.35), (85.225, 86.1245)))
T('IRQ viaU', h.via('IRQ_N', 84.85, 85.15)); T('IRQ stubU', h.seg('IRQ_N', 'F.Cu', [(84.4, 84.22), (84.4, 84.85), (84.7, 85.15), (84.85, 85.15)]))
# --- U401 S side: SCL pin 9 straight down to a new via, SDA pin 8 down to its own via
T('SDA via401', h.via('SDA', 105.2, 85.25))
T('SCL via401', h.via('SCL', 105.8, 85.75))
T('SCL stub401', h.seg('SCL', 'F.Cu', [(105.775, 84.6245), (105.775, 85.5), (105.8, 85.75)]))
T('SCL in2 401', h.auto('SCL', 'In2.Cu', (105.8, 85.75), (104.275, 85.4245)))
T('SDA stub401', h.seg('SDA', 'F.Cu', [(105.39, 84.31), (105.39, 85.06), (105.2, 85.25)], w=0.15))

# --- IRQ_N and SDA, U501 -> U401: In2 to vias at x 98.3, then one lane each (IRQ_N on B.Cu, SDA on In3) along y 85.4
T('IRQ via98', h.via('IRQ_N', 98.3, 84.75)); T('SDA via98', h.via('SDA', 98.3, 86.0))
T('IRQ in2', h.auto('IRQ_N', 'In2.Cu', (84.85, 85.15), (98.3, 84.75), margin=6))
T('SDA in2', h.auto('SDA', 'In2.Cu', (83.3, 85.0), (98.3, 86.0), margin=6))
T('IRQ lane', h.seg('IRQ_N', 'B.Cu', [(98.3, 84.75), (98.95, 85.4), (104.0, 85.4)]))
T('IRQ end', h.auto('IRQ_N', 'B.Cu', (104.0, 85.4), (106.37, 85.02), margin=3))
T('SDA lane', h.seg('SDA', 'In3.Cu', [(98.3, 86.0), (98.9, 85.4), (104.3, 85.4)]))
T('SDA end', h.auto('SDA', 'In3.Cu', (104.3, 85.4), (105.2, 85.25), margin=3))
T('DRV9 via', h.via('/USB Port 1/DRV9_OFF', 105.39, 79.92))
T('DRV9 stub', h.seg('/USB Port 1/DRV9_OFF', 'F.Cu', [(105.39, 80.46), (105.39, 79.92)]))
T('DRV9 viaQ', h.via('/USB Port 1/DRV9_OFF', 114.85, 83.49))
T('DRV9 in2', h.auto('/USB Port 1/DRV9_OFF', 'In2.Cu', (105.39, 79.92), (114.85, 83.49), margin=8))

h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/top.json')
