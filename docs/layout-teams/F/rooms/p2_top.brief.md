# Room p2_top: Port 2 connector protection, PD controller, input shunt, and the Port 2 5 V buck

Room area: x 78.5-99.8 for y 67.8-79.3; x 78.5-95.5 for y 79.3-87.7; the corner x 78.5-86.9, y 63.9-67.8.
Fixed inside: J501 (USB-C, pads at y 69.2: VBUS at x 91.1 and 95.9, CC1 A5 at 94.75, CC2 B5 at 91.75), hole H102, J109 (a
cell wire pad), TP512 (GND). The 5 V buck parts were elsewhere on the hand board, so the hand picture does not show them, and the starting
placement parks them at meaningless spots: place everything afresh.

## The lead's change to the floorplan
On the hand board the Port 2 5 V buck sat at the far bottom-left of the board and its 1.5 A output PP5V ran 46 mm up the
board edge to U501. The buck now lives in this room, next to the PD controller it feeds.

## Power flow you must make work (top-layer copper, straight and wide)
1. VBUS, 5 A: J501 VBUS pads -> D501 (TVS), C506 (bulk), C550 -> U501 pad 23 (large pad, east side, upper).
2. PPHV, 5 A: U501 pad 20 (large pad, east side, lower) -> R524 pad 1. C549 at pad 20.
3. AC_SNS_N, 5 A: R524 pad 2 -> leaves through the bottom edge at about x 81-85, y 87.7: directly below, the stage room
   puts its input capacitor column (x about 80.9-84.2, from y 87.9). R524 pad 2 within about 2 mm of that crossing, clear
   strip at least 2.5 mm wide. R524 is a shunt with two long sense taps: room for two vias beside it.
4. 5 V buck (U504, L502, C539-C543, R532-R534, C544, C546): U504 pad 5 SW -> L502 pad 1; L502 pad 2 -> output capacitors
   C541-C543 -> PP5V, 1.5 A, to U501 pad 34 (north side) and C507, top layer, clear strip at least 1.2 mm wide. Pad 34 sits
   between pads 36/37 on its left and VBUS pad 32 on its right: PP5V has to arrive from the north or north-west of U501.
   - Hot loop "USB Port 2/HL_5V": C546 (first, 0.1 uF) then C544 (22 uF) between U504 pad 3 (VIN = PACK_P) and pad 4 (GND).
     C546's pads right at those two pins.
   - PACK_P reaches U504 pad 3 / C546 / C544 through an inner-layer pour: leave room for two vias within 1.5 mm of the
     PACK_P pads (the hand board failed exactly here: "no room for a via").
   - EN_5V2 (U504 pad 2, R532) arrives on an inner layer from the far corner of the board: via room.
   - C540 boot capacitor between pads 6 and 5; C539 at pad 7; divider R533/R534 at pad 8 (FB, sensitive: short, away from L502).
   The top-left corner and the left edge are free for the buck. You may move U501 (keep its north side facing the
   connector and within about 10 mm of the connector's CC pins) if the room works better that way.
5. R555 (pull-up of DRV9_OFF, U501 pad 37, to /P2_LDO_3V3 at pads 1/2) sits at U501. DRV9_OFF then leaves on an inner layer
   down the left edge: via room.

## Signals
- CC: J501 A5/B5 -> U505 (pads 4/7 both C_CC1, 5/6 both C_CC2) -> U505 pads 12/11 -> U501 pads 28/29; C501, C502; C551 at
  U505 pad 3, C552 at U505 pad 10; SBU_FLT U505 pad 9 -> U501 pad 19 (R541).
- U501 south side: SDA 8, SCL 9, IRQ_N 10 leave on inner layers (via room below the pins); I2CC 16/17 and CHG_INT 18 go to
  U502, pull-ups R502-R504 and on to the charger chip below the stage.
- LDO capacitors: C503 at pad 38, C504 at pads 1/2, C505 at pad 4, C508 at U502 pad 8.

## What failed here on the hand board (connections with no path)
C_CC1 and C_CC2 J501-U505, U505 pad 7 to pad 4; CC2 U501-U505; I2CC_SDA R502-U501; IRQ_N, SDA, SCL at U501; GND at three
U501 pads and at C549. Aim for none of these.

## Numbers to report
VBUS, PPHV, PP5V resistances from dc.log; whether PACK_P is joined at U504; HL_5V inductance (run qs.sh once without
--no-hot at the end and read hot_gate.log; limit 6.98 nH, hand board 1.17); blocked connections in your room.
