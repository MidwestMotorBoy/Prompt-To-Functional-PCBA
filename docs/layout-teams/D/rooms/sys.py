import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('sys')

# ---------------- 3.3 V buck (box 0, lower-left; TP301 / H101 fixed) ----------------
# Row along the bottom: C206 | U204 | L201, with C207 lifted to sit north of U204/L201 beside the 3V3 test pad TP301,
# so the 3V3 node (L201.2 top end, TP301, C207.1) is one compact cluster with open board north of it for the 3V3 exit vias.
UC = 128.35                                   # U204 centre y; pin 9 (SW) = UC-0.5 lands near the top of L201 pad 1
rm.put('U204', 82.38, UC, 0)                  # W pins: 1 PGND, 2/3 PACK_P, 4/5 GND; E pins: 10 VOS, 9 SW, 8 SLEEP, 7 nc, 6 GND
# C206 turned 180: PACK_P pad (south) level with pins 2/3, GND pad (north) just above pin 1 (PGND). The PACK_P pad edge
# facing pin 2 is where the planner puts U204's own PACK_P via (C206's via goes in its pad centre, >= 0.75 mm away).
rm.put_court('C206', rot=180, right=rm.court('U204')[0] - 0.15, top=UC - 1.2 - 1.75)
# L201 0.6 mm clear of U204 so VOS (pin 10, north) and SLEEP (pin 8, south) escape through the gap beside the SW link;
# its top edge just clears TP301.
rm.put_court('L201', rot=0, left=rm.court('U204')[2] + 0.6, top=rm.court('TP301')[3] + 0.1)
# C207 turned 180: 3V3 pad east next to TP301, GND pad west above U204.
rm.put_court('C207', rot=180, right=rm.court('TP301')[0] - 0.1, bottom=rm.court('U204')[1] - 0.15)

# ---------------- MCU: VDDS decoupling + SCL pull-up (box 2, west of J301) ----------------
C3T = rm.court('U301')[1] + 0.04              # bottom row may touch the module courtyard by < 0.1 mm
rm.put_court('C303', rot=0, right=113.92, bottom=C3T)          # 3V3 pad east, nearest pin 7
rm.put_court('C302', rot=0, right=113.92, bottom=rm.court('C303')[1] - 0.0)
rm.put_court('C301', rot=0, right=114.36, top=115.9)           # 4.7 uF, 3V3 pad east (to J301.1 and the caps below)
rm.put_court('R304', rot=0, right=rm.court('C303')[0] - 0.12, bottom=C3T)   # SCL pad south at pin 9, 3V3 north
# (x 110.8-111.5 west of R304 and y 116.1-116.9 above it are left free for the SCL and 3V3 vias)

# ---------------- antenna match (box 2 under J301): hand row kept, C313 turned so RFIO meets pin 4 ----------------
RY = 118.015
rm.put('C314', 114.8868, RY, 0)               # GND W | node E
rm.put('C313', 116.7592, RY, 180)             # node W | RFIO E (RFIO pad right above U301.4)
rm.put('R321', 118.618, RY, 0)                # node W | ANT_IN E (ANT_IN pad right above U301.3)
rm.put('C315', 120.5236, RY, 0)               # ANT_IN W | GND E

# ---------------- west strip of the module (box 3) ----------------
# R305 upright against the module (SDA pad south at pin 10, 3V3 pad north) so its 3V3 pad reaches a via spot at
# about (110.4, 118.8) without crossing the pack_gauge CELL_P pour that fills x < 109.7 here.
rm.put_court('R305', rot=90, right=110.76, bottom=rm.pad('U301.10')[1] + 0.32 + 0.43)
# y 120.5-123.2 left free for the escapes of pins 11-13 (CHG_INH, EN_5V1, EN_5V2)
for r, y in (('R302', 123.58), ('C304', 124.48), ('R313', 125.38)):     # between pin 13 trace and H103
    rm.put_court(r, rot=0, left=109.2, top=y - 0.4)
rm.done()
