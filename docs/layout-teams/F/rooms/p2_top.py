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
# pack_x1 (the r3 placement inside another worker's run) showed: C550 walled in -> its VBUS came by a bottom-layer detour
# right under the via pocket, and the PP5V detours to C507/C541 ran under it too -> CC1, CC2, GND 26/27/31 had no via.
# Now: C550 lies directly above pads 32/31 (VBUS pad over pad 32, GND pad over pin 31) and gets its VBUS on the top layer
# along the top of the lid; lid (C502) and east wall (C501) shifted east so that strip is not pinched at L502's pad.
rm.put('C550', 88.45, 80.65, 90)     # in the VBUS corridor beside U501 pad 23 (brief: VBUS -> C550 -> pad 23); frees the pocket above pins 29-32
# NOT YET SCORED (next thing to try): rm.put('C502', 84.8, 79.6, 270) puts C502's GND pad over pin 31 and its CC2 pad over pin 29;
# it should clear the last two blocked edges there (the planner grows a VBUS island from pad 32 into that pocket, run stage_x2).
rm.put('C502', 86.23, 78.6, 90)                              # lid: CC2 pad west (pin 29 runs up past C550's end), GND pad over pins 26/27
rm.put('C501', 87.7, 79.095, 0)                              # east wall: CC1 pad south, GND pad north
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
rm.put_court('C507', rot=180, right=93.725, bottom=76.69)   # no room at pad 34 or L502: right under H102, PP5V pad west. Its bottom-layer link to L502 stays north of y 78.3
                                                             #   (clear of U501's via pocket); its GND pad closes the slot between H102 and U505 against VBUS copper

# ---------------- connector side: protection chip under the CC pins, TVS and bulk on the east VBUS pads
rm.put('U505', 95.8, 74.5, 0)                                # 0.6 lower: its south pads + the GND pads of D501/C506 below close the lane against the east VBUS copper
rm.put('C551', 96.44, 71.2, 0)                               # VBIAS pad over pad 3, clear of the CC1 drop into pad 4
rm.put('C552', 92.28, 70.86, 180)    # GND pad under B5 keeps VBUS copper off C_CC2; 0.88 mm lane above it for the C_CC2 track
# TVS west (VBUS pads on the west VBUS feed coming round H102), bulk east (VBUS pad under the east VBUS strip): only
# GND pads lie under U505's south side, so CC1/CC2 (pads 12/11) get via room there and the east VBUS pins cannot
# become the feed of U501 through the gap under U505 (they did in pack_x1: 19 mV, and U505 was flooded)
rm.put_court('D501', rot=0, left=92.36, bottom=79.3)
rm.put_court('C506', rot=180, right=99.8, bottom=79.29)

# ---------------- lower right: EEPROM, pull-ups, and the output capacitors that do not fit at the inductor
rm.put('U502', 93.05, 80.85, 180)    # signal pads face east, away from the VBUS corridor copper (no via room on the west side)
rm.put('C508', 92.5, 82.52, 0)
rm.put('C541', 91.95, 85.33, 180)                            # PP5V pads south: more than 10 mm from L502, so the copper planner draws no bottom-layer
rm.put('C542', 94.35, 85.33, 180)                            #   detour under U501 / R524's Kelvin vias (it did, and it took the via sites)
rm.done()
