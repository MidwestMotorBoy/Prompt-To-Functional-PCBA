import sys; sys.path.insert(0, '../tools')      # cd rooms && python3 p2_top.py
from room import Room
rm = Room('p2_top')

# ---------------- PD controller (north side faces the connector)
rm.put('U501', 85.6, 82.3, 0)

# ---------------- 5 V buck: L502 across the top-left, U504 + input caps in the corner above it, output caps below it
rm.put_court('L502', rot=270, left=78.55, bottom=72.85)        # pad 1 SW west, pad 2 PP5V east
rm.put_court('U504', rot=180, left=80.6, top=64.0)              # SW pad 5 at SE corner, VIN/GND on W side
rm.beside('C546', 'U504.3', 'W', gap=0.15, rot=270)
rm.beside('C540', 'U504.6', 'E', gap=0.15, rot=180, pad=1)
rm.put_court('R534', rot=90, left=84.65, top=63.95)
rm.put_court('R533', rot=90, left=85.78, top=63.95)
rm.put_court('C539', rot=90, left=84.75, top=66.0)
rm.put_court('R532', rot=0, left=78.6, top=63.95)        # EN pull-down
rm.put_court('C541', rot=0, left=80.85, top=72.95)
rm.put_court('C542', rot=180, left=85.3, top=70.45)

# ---------------- U501 support (west column: C503, C504, then C544 at the bottom-left; R555 + C507 north)
rm.put_court('C543', rot=0, left=78.55, top=75.15)               # PP5V pad N
rm.put_court('C503', rot=270, right=82.05, top=79.9)            # 3V3 pad E -> pin 38
rm.put_court('C504', rot=90, right=82.05, top=81.5)             # LDO_3V3 pad E -> pin 1
rm.put_court('C544', rot=0, left=78.55, bottom=87.7)            # PACK_P bulk (HL_5V second cap)
rm.put_court('C505', rot=0, left=82.1, top=85.15)               # LDO_1V5, SW corner of U501
rm.put_court('C507', rot=90, left=84.2, top=75.25)              # PP5V pad S, east of the PP5V drop (r2: 1.1 W, frees pins 28-31)
rm.put_court('R555', rot=0, right=83.95, bottom=79.75)
rm.beside('C550', 'U501.23', 'E', rot=90)
rm.beside('C549', 'U501.20', 'E', rot=270)
# r2: R524 stands upright right under U501 pad 20 (PPHV pad N, AC_SNS_N pad S at the room edge): the PPHV copper stays a
#     short stub west of x 90.5 (further east, the copper planner finds a 0.3 mm PPHV path round the stage to C509 that
#     walls in the charger's north side), and the strip under pins 15-19 is left to the pull-ups
rm.put_court('R524', rot=90, left=89.0, bottom=87.7)
rm.put_court('U502', rot=180, left=91.1, top=82.3)
rm.beside('C508', 'U502.8', 'N')
# r2: the SDA / SCL pull-ups lie flat under pins 13-18 (SCL pad 2 under pin 17, SDA pad 2 under pin 15): their pad rings
#     keep the AC_SNS_N / PPHV pour out of the strip under pins 15-19, so pins 16-18 get via spots
rm.put('R503', 87.52, 85.7, 270)                                # pad 2 SCL W (x 87.2), pad 1 LDO_3V3 E
rm.put_court('R502', rot=90, right=rm.court('R503')[0] - 0.1, top=rm.court('R503')[1])   # pad 1 LDO_3V3 W, pad 2 SDA E
rm.put_court('R504', rot=0, left=91.7, top=85.2)
# r2: SBU_FLT pull-up lies flat under J501 B7/A5: its pad rings keep the VBUS pour out from under A5 (via spot for C_CC1)
rm.put_court('R541', rot=90, left=93.76, top=70.5)

# ---------------- connector side
rm.put('D501', 98.35, 71.42, 0)
rm.put_court('C506', rot=90, left=89.85, top=75.35)       # VBUS pad N, keeps the branch east (pad 32 anchor)
rm.put('U505', 96.35, 77.32, 0)                              # r2: 0.9 E, via room west of pins 6-10
rm.beside('C551', 'U505.3', 'N', rot=270, shift=0.65)
rm.beside('C552', 'U505.10', 'W', rot=90, shift=0.5)
# r2: CC caps over U501 pins 29 / 28, CC pads down (0.99 mm above the pins: via spots between)
rm.put_court('C502', rot=0, left=85.9, bottom=79.3)
rm.put_court('C501', rot=0, left=86.95, bottom=79.3)
rm.done()
