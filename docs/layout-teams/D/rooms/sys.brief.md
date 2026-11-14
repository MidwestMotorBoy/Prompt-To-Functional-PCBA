# Room sys: the always-on 3.3 V buck and the small parts round the MCU module

Room area: 3.3 V buck: x 78.5-88.6, y 121.3-131.5 and x 88.6-93.3, y 124.0-131.5 (H101 and TP301 are fixed inside).
MCU parts: x 108.6-121.6, y 115.9-118.5 (the strip between the tag-connect J301 and the module U301) and x 109.2-110.95,
y 118.5-127.0 (the strip along the module's west side). U301 itself is fixed.
Some of your parts are parked at meaningless spots in the starting picture (R302, C304, R313 near TP301): place all afresh.

## 3.3 V buck (U204, L201, C206, C207)
- Hot loop "HL_3V3": C206 between U204 pad 2 (VIN = PACK_P; pad 3 is also PACK_P) and pad 1 (PGND), pads right at the
  pins. Limit 27.5 nH, hand board 1.33.
- U204 pad 9 SW -> L201 pad 1; L201 pad 2 -> C207 -> 3V3. PACK_P arrives through an inner-layer pour: room for a via within
  1.5 mm of C206's PACK_P pad. 3V3 leaves on an inner layer to the far side of the board: via room at C207.
- 3V3_SLEEP (U204 pad 8) goes to the MCU (U301 pad 15) and R313.
- The room is larger than the buck needs. Put the buck where its PACK_P via and its 3V3 exit are least hemmed in, and
  keep it compact; the lower-left corner region was fine on the hand board.

## MCU parts
- C301, C302, C303 at U301 VDDS pads 6/7 (north side of the module); C304 and R302 at RSTN pad 14 (west side);
  pull-ups R304 (SCL, pad 9), R305 (SDA, pad 10), R313 (3V3_SLEEP, pad 15).
- Antenna match C313, C314, C315, R321 between U301 pads 4 (RFIO) and 3 (ANT_IN) on the module's north side: keep the
  hand arrangement of these four unless something forces a change (it is RF: shortest possible, in line).
- On the hand board the 3V3 pads of R313, R302 and R305 had no path to the 3V3 copper, and C304's GND pad none to ground:
  give each a free spot for a via.

## Numbers to report
HL_3V3 (one run without --no-hot), blocked connections in your room.
