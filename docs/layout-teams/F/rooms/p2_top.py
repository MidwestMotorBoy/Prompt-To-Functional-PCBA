import sys; sys.path.insert(0, '../tools')      # run from the rooms folder: cd rooms && python3 p2_top.py
from room import Room
rm = Room('p2_top')

# ---------------- PD controller, low on the left: VBUS drops straight down the gap between J109 and H102 onto pad 23,
# PPHV (pad 20) -> C549 -> R524 (upright) -> AC_SNS_N leaves along the bottom edge towards x 83-87, y 87.7
UX, UY = 84.0, 82.6
rm.put('U501', UX, UY, 0)
# west column: LDO capacitors at pads 1 and 4
rm.put_court('C504', rot=0, right=80.4, top=80.05)          # LDO_3V3 pad north, level with pad 1
rm.put_court('C505', rot=90, right=80.4, top=83.2)         # LDO_1V5
# fence along the bottom edge: keeps the AC_SNS_N copper out of the via band (y 85.1-86.1) under the south pins
rm.put_court('C503', rot=0, left=78.6, top=84.35)            # 3V3 bulk, 3V3 pad south (its copper stays out of the via band)
rm.put('R532', 82.4, 86.95, 90)              # EN_5V2 pull-down (EN arrives on an inner layer): fence under pins 8-10
for r, x in (('R502', 84.8), ('R503', 85.6), ('R504', 86.4), ('R541', 87.2)): rm.put(r, x, 86.95, 0)   # pull-ups under pins 16-19, signal pad north
# north row (2 mm band under the inductor): pull-up at pad 37, VBUS cap at pad 32; PP5V channel x 82.4-83.6 stays free
rm.put_court('R555', rot=0, left=81.5, bottom=79.95)
rm.put_court('C550', rot=0, left=83.45, bottom=79.95)
rm.put_court('C502', rot=90, left=84.5, top=78.0)            # CC2 cap as a lid: CC2 pad over pin 29, keeps PP5V/VBUS copper out of the via pocket
rm.put_court('C501', rot=0, left=86.5, bottom=80.05)         # CC1 cap as the east wall of the pocket (CC1 pad south)
# PPHV side
rm.put('R524', 88.75, 84.2, 90)                              # pad 1 level with pad 20, pad 2 straight down to the edge
rm.put('C549', 90.3, 82.81, 180)                             # PPHV pad south, beside R524 pad 1; Kelvin vias fit below it

# ---------------- 5 V buck, top-left: input caps (top) -> U504 -> L502 -> PP5V straight down to pad 34
rm.put('L502', 83.8, 74.55, 0)                               # SW pad north, PP5V pad south
rm.put('U504', 82.3, 69.6, 180)                              # E side: FB, SS, BST, SW(bottom); W side: GND, EN, VIN, GND
rm.put('C540', 84.3, 70.3, 180)                              # boot: BST north at pin 6, SW south on the inductor pad
rm.put('C546', 80.33, 70.1, 270)                             # hot loop: PACK north / GND south at pins 3 / 4
rm.put_court('C544', rot=270, left=78.5, top=63.96)          # bulk
rm.put('R534', 84.35, 67.7, 0)                               # FB divider above the chip, away from L502
rm.put('R533', 84.35, 66.6, 180)
rm.put('C539', 86.3, 67.55, 180)                             # soft start
rm.put_court('C543', rot=0, left=78.5, top=75.2)             # output cap beside L502 pad 2
rm.put('C507', 90.8, 78.1, 0)                                # no room at pad 34 (2 mm band): parked under H102

# ---------------- connector side: protection chip under the CC pins, TVS and bulk on the east VBUS pads
rm.put('U505', 95.8, 73.9, 0)
rm.put('C551', 96.44, 71.2, 0)                               # VBIAS pad over pad 3, clear of the CC1 drop into pad 4
rm.put('C552', 92.9, 70.9, 180)                              # under the pins: its pads keep the west VBUS copper off the C_CC2 escape; LDO pad east
rm.put('D501', 98.45, 78.0, 0)
rm.put('C506', 94.7, 78.1, 180)

# ---------------- lower right: EEPROM, pull-ups, and the output capacitors that do not fit at the inductor
rm.put('U502', 93.55, 80.85, 0)
rm.put('C508', 92.5, 82.52, 0)
rm.put('C541', 91.95, 85.33, 0)
rm.put('C542', 94.35, 85.33, 0)
rm.done()
