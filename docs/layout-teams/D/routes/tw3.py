"""Team D worker `tw3`: hand routes for the open connections at x < 100, y < 104 on p2.
   python3 tw3.py drop   -> tw3_drop.json (removals only; apply p2 -> tw3a)
   python3 tw3.py        -> tw3.json (drops + routes, built against tw3a; apply to p2 for the final board)"""
import sys, json; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
D = '/home/claude/runs/r2_route'
OUTD = '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/routes/'
DROPS = [
    ('GND', None, [84.9, 84.35, 85.2, 84.9]),          # U501.12 GND via: pin is already tied to the pad copper (frees the IRQ_N escape)
    ('GND', 'F.Cu', [106.6, 84.4, 107.2, 85.2]),       # U401.11 GND track + via: pin necked into the exposed pad instead (frees IRQ_N at U401.10)
    ('/USB Port 2/C_CC1', 'F.Cu', [94.2, 75.2, 96.0, 77.0]),    # CC1 F loop round U505.5/6 (and its via): re-laid round a CC2 via
    ('/USB Port 2/C_CC1', 'In2.Cu', [94.7, 69.8, 94.9, 76.0]),  # CC1 In2 drop to that via: re-laid shorter
    ('/USB Port 2/BTST1', 'F.Cu', [83.6, 104.7, 86.7, 106.72]), # BTST1 F diagonal between C512.2 and U503.28: moved to In2
]
if sys.argv[1:] == ['drop']:
    h = HR(D, 'p2')
    for d in DROPS: h.drop(*d)
    h.save(OUTD + 'tw3_drop.json'); sys.exit()

h = HR(D, 'tw3b')
for d in DROPS: h.drop(*d)
def T(label, r): print('%-14s %s' % (label, r))

# --- GND: U501 pins 36 and 31 necked into the exposed pad 39; R532.2 F pour island to the planes
T('U501.36', h.seg('GND', 'F.Cu', [(84.00, 80.38), (84.00, 81.2)], w=0.15))
T('U501.31', h.seg('GND', 'F.Cu', [(86.00, 80.38), (86.00, 80.9), (85.85, 81.1)], w=0.15))
T('R532 via', h.via('GND', 78.96, 64.54)); T('R532 stub', h.seg('GND', 'F.Cu', [(78.86, 64.54), (78.96, 64.54)]))

# --- 3V3: the F pour island on U501.38 gets a via on its own track into the In3 3V3 pour (no In2 bridge)
T('3V3 via', h.via('3V3', 82.87, 79.95))

# --- U501 S side: SDA 8, SCL 9, IRQ_N 10 each to a via under the pin row, In2 south-east round the PACK_P pour
#     (west ends free, no fence) to three vias at x 95-96.5 clear of the AC_SNS_N pours, then In3 east to U401
W = {'SDA': (83.25, 84.95), 'SCL': (84.0, 85.0), 'IRQ_N': (84.75, 85.15)}
E = {'IRQ_N': (95.05, 86.1), 'SCL': (95.75, 86.75), 'SDA': (96.5, 87.5)}
T('IRQ viaW', h.via('IRQ_N', *W['IRQ_N'])); T('IRQ stubW', h.seg('IRQ_N', 'F.Cu', [(84.4, 84.22), (84.4, 84.6), (84.75, 84.95), (84.75, 85.15)], w=0.15))
T('SCL viaW', h.via('SCL', *W['SCL'])); T('SCL stubW', h.seg('SCL', 'F.Cu', [(84.0, 84.22), (84.0, 85.0)], w=0.15))
T('SDA viaW', h.via('SDA', *W['SDA'])); T('SDA stubW', h.seg('SDA', 'F.Cu', [(83.6, 84.22), (83.6, 84.6), (83.25, 84.95)], w=0.15))
for n in ('IRQ_N', 'SCL', 'SDA'): T(n + ' viaE', h.via(n, *E[n]))
for n in ('IRQ_N', 'SCL', 'SDA'): T(n + ' In2', h.auto(n, 'In2.Cu', W[n], E[n], clr=0.15, margin=3))
T('SDA viaU', h.via('SDA', 105.15, 85.45))                                                 # U401.8 escape
T('SDA stubU', h.seg('SDA', 'F.Cu', [(105.39, 84.31), (105.39, 84.6), (105.15, 84.84), (105.15, 85.45)], w=0.15))
T('U401.11', h.seg('GND', 'F.Cu', [(106.59, 84.31), (106.59, 83.6)], w=0.15))                 # GND pin into U401's pad
T('IRQ viaU', h.via('IRQ_N', 106.45, 85.6))                                                # U401.10 escape
T('IRQ stubU', h.seg('IRQ_N', 'F.Cu', [(106.19, 84.31), (106.25, 84.69), (106.45, 85.15), (106.45, 85.6)], w=0.15))
T('SDA In3', h.auto('SDA', 'In3.Cu', E['SDA'], (105.15, 85.45), clr=0.15, margin=3))
T('SCL In3', h.auto('SCL', 'In3.Cu', E['SCL'], (103.17, 85.57), clr=0.15, margin=3))     # to the existing SCL via by U401
T('IRQ In3', h.auto('IRQ_N', 'In3.Cu', E['IRQ_N'], (106.45, 85.6), clr=0.15, margin=8))     # south round the P1 I2CC_SDA hairpin

# --- C_CC2 port 2: CC2 via in the corner of U505 (where the CC1 via was), In3 to a via by J501.B5 (F stub through
#     the VBUS pour fringe east of the pad); CC1 re-laid round it from a via 0.9 mm further north on its In2 drop
C1 = '/USB Port 2/C_CC1'
T('CC1 viaJ', h.via(C1, 94.78, 69.92)); T('CC1 viaU', h.via(C1, 94.78, 74.85))
T('CC1 In2', h.seg(C1, 'In2.Cu', [(94.78, 69.92), (94.78, 74.85)]))
T('CC1 loop', h.seg(C1, 'F.Cu', [(94.95, 76.92), (94.53, 76.92), (94.33, 76.72), (94.33, 75.5), (94.56, 75.27), (95.72, 75.27), (95.92, 75.47), (95.95, 75.92)]))
T('CC1 stubV', h.seg(C1, 'F.Cu', [(94.78, 74.85), (94.78, 75.27)]))
N = '/USB Port 2/C_CC2'
T('CC2 viaU', h.via(N, 94.9, 75.85)); T('CC2 stubU', h.seg(N, 'F.Cu', [(94.9, 75.85), (94.95, 75.95), (94.95, 76.52)]))
T('CC2 viaJ', h.via(N, 92.65, 71.55)); T('CC2 stubJ', h.seg(N, 'F.Cu', [(91.75, 69.17), (91.75, 69.75), (92.65, 70.65), (92.65, 71.55)]))
T('CC2 In3', h.auto(N, 'In3.Cu', (92.65, 71.55), (94.9, 75.85), clr=0.15))

# --- SW1 / BTST1 port 2: BTST1 F diagonal replaced by a via + In3; SW1 C512.2 -> U503.28 on F along the freed corridor
#     (the checker still sees the AC_SNS_N pour of tw3b there, which refilled into the dropped BTST1 corridor)
B = '/USB Port 2/BTST1'
T('BTST via', h.via(B, 86.75, 105.45)); T('BTST F', h.seg(B, 'F.Cu', [(86.53, 106.77), (86.45, 106.6), (86.45, 105.75), (86.75, 105.45)]))
T('BTST In3', h.auto(B, 'In3.Cu', (86.75, 105.45), (82.525, 105.374), margin=1.5))
N = '/USB Port 2/SW1'
T('SW1 F', h.seg(N, 'F.Cu', [(83.635, 103.705), (84.1, 104.17), (84.5, 104.57), (85.3, 105.37), (85.5, 105.57), (85.5, 107.75), (85.56, 107.85), (85.56, 108.11)]))
# --- HG1 port 2: via in R544.2's pad, In2 to the via in Q501.1's pad
N = '/USB Port 2/HG1'
T('HG1 via', h.via(N, 87.02, 102.47)); T('HG1 In2', h.auto(N, 'In2.Cu', (83.86, 98.83), (87.02, 102.47), clr=0.15))


#     ... and C512.2 / U503.28 to the Q501 SW1 pour: via on the new track, In2 north round the west end of HG1, via in the pour
N = '/USB Port 2/SW1'
T('SW1 viaT', h.via(N, 85.5, 106.3)); T('SW1 viaP', h.via(N, 86.6, 97.0))
T('SW1 In2', h.auto(N, 'In2.Cu', (85.5, 106.3), (86.6, 97.0), clr=0.25, margin=4))

h.save(OUTD + 'tw3.json')
