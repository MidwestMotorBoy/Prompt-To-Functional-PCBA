"""Team D worker `tw`: hand routes for the open connections at x < 100, y < 104 on g2.
   python3 tw.py drop   -> tw_drop.json (removals only; apply g2 -> tw1)
   python3 tw.py        -> tw.json (drops + routes, built against tw1; apply to g2 for the final board)"""
import sys, json; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'
OUTD = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
DROPS = [
    ('IRQ_N', None, [81.8, 84.2, 84.5, 88.6]),                    # U501.10 escape via sits under SCL pin 9: re-laid
    ('/USB Port 2/BTST1', 'F.Cu', [83.6, 104.7, 86.7, 106.72]),   # BTST1 F diagonal between C512.2 and U503.28: moved to In2
    ('GND', None, [84.9, 84.35, 85.2, 84.9]),                      # U501.12 GND via: pin necked into the exposed pad instead
    ('IRQ_N', 'In2.Cu', [81.9, 88.1, 95.0, 90.8]),                 # old IRQ_N In2 detour west: replaced by a direct In2 run
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'g2')
    for d in DROPS: h.drop(*d)
    h.save(OUTD + 'tw_drop.json'); sys.exit()

h = HR(D, 'tw1')
for d in DROPS: h.drop(*d)
def T(label, r): print('%-14s %s' % (label, r))

# --- GND: U501 pins 36 and 31 necked into the exposed pad; R532.2 F pour island to the planes
T('U501.36', h.seg('GND', 'F.Cu', [(84.00, 80.38), (84.00, 81.2)], w=0.15))
T('U501.31', h.seg('GND', 'F.Cu', [(86.00, 80.38), (86.00, 80.9), (85.85, 81.1)], w=0.15))
T('R532 via', h.via('GND', 78.96, 64.54)); T('R532 stub', h.seg('GND', 'F.Cu', [(78.86, 64.54), (78.96, 64.54)]))

# --- 3V3: In3 pour lobe round U501.38 is cut off from the main pour; bridge it on B.Cu where the two come closest
T('3V3 viaL', h.via('3V3', 92.5, 82.3)); T('3V3 viaM', h.via('3V3', 94.6, 85.8))
T('3V3 bridge', h.auto('3V3', 'B.Cu', (92.5, 82.3), (94.6, 85.8), clr=0.15, margin=2))
T('3V3 viaU', h.via('3V3', 82.1, 80.1)); T('3V3 viaS', h.via('3V3', 92.0, 80.1))      # the U501.38 lobe itself is walled off by
T('3V3 lobe', h.auto('3V3', 'In2.Cu', (82.1, 80.1), (92.0, 80.1), clr=0.15, margin=2))  #   LDO_3V3 In3 tracks: In2 under U501

# --- U501 S side: GND pin 12 into the pad; SCL pin 9 and IRQ_N pin 10 each to a via, both In2 east
T('GND p12', h.seg('GND', 'F.Cu', [(85.2, 84.22), (85.2, 83.45)], w=0.15))
T('SCL viaU', h.via('SCL', 84.0, 85.2)); T('SCL stubU', h.seg('SCL', 'F.Cu', [(84.0, 84.22), (84.0, 85.2)]))
T('IRQ viaU', h.via('IRQ_N', 84.75, 85.15)); T('IRQ stubU', h.seg('IRQ_N', 'F.Cu', [(84.4, 84.22), (84.4, 84.8), (84.75, 85.15)]))
T('SCL via401', h.via('SCL', 105.72, 85.6)); T('SCL stub401', h.seg('SCL', 'F.Cu', [(105.79, 84.31), (105.72, 84.6), (105.72, 85.6)], w=0.15))
T('SCL in2a', h.auto('SCL', 'In2.Cu', (84.0, 85.2), (85.0, 90.0), clr=0.15, margin=2))
T('SCL in2b', h.auto('SCL', 'In2.Cu', (85.0, 90.0), (105.72, 85.6), clr=0.15, margin=4))
T('IRQ in2', h.auto('IRQ_N', 'In2.Cu', (84.75, 85.15), (95.725, 87.275), clr=0.15, margin=3))

# --- HG1 port 2: Q501.1 via -> In2 -> via in R544.2
N = '/USB Port 2/HG1'
T('HG1 via', h.via(N, 87.02, 102.47)); T('HG1 in2', h.auto(N, 'In2.Cu', (83.86, 98.825), (87.02, 102.47)))

# --- C_CC2 port 2: J501.B5 via (small notch in the VBUS pour edge) -> In2 -> via by U505.5
N = '/USB Port 2/C_CC2'
T('CC2 viaJ', h.via(N, 91.75, 69.95)); T('CC2 stubJ', h.seg(N, 'F.Cu', [(91.75, 69.17), (91.75, 69.95)]))
T('CC2 viaU', h.via(N, 94.75, 76.27)); T('CC2 stubU', h.seg(N, 'F.Cu', [(94.95, 76.52), (94.75, 76.27)]))
T('CC2 in2', h.auto(N, 'In2.Cu', (91.75, 69.95), (94.75, 76.27), clr=0.15, margin=5))

# --- SW1 / BTST1 port 2: BTST1 F diagonal replaced by a via + In2; SW1 C512.2 -> U503.28 on F along the freed corridor
#     (the checker still sees the AC_SNS_N pour of tw1 there, which refilled into the dropped BTST1 corridor)
B = '/USB Port 2/BTST1'
T('BTST via', h.via(B, 85.4, 105.3)); T('BTST F', h.seg(B, 'F.Cu', [(86.625, 106.674), (85.4, 105.45), (85.4, 105.3)]))
T('BTST in2', h.auto(B, 'In2.Cu', (85.4, 105.3), (82.525, 105.374), margin=1.5))
N = '/USB Port 2/SW1'
T('SW1 F', h.seg(N, 'F.Cu', [(83.635, 103.705), (84.1, 104.17), (84.5, 104.57), (84.5, 107.1), (85.2, 107.8), (85.56, 108.11)]))
# Not done: C512.2 / U503.28 to the Q501 SW1 pour. No via spot on this track clears the DRV9_OFF In3 track by the
# 0.25 mm HighCurrent rule, and In2 from a via at (86.31, 100.6) in the pour finds no path.

h.save(OUTD + 'tw.json')
