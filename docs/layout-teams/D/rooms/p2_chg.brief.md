# Room p2_chg: Port 2 charger controller, its programming and sense filters, and the Port 2 9 V gate-drive supply

Room area: x 78.5-93.9, y 104.6-116.0; x 78.5-92.4, y 116.0-121.2.
The 9 V supply parts are not in the hand picture (on the hand board they were at the top of the
board, 25 mm from the chip they feed) and start parked at meaningless spots: place everything afresh. The stage room is above (its gate resistors at about
y 102.5-104.5, x 85-94).

## Charger controller U503 (keep its north side facing the stage; the hand position, centre (88.4, 110.5), is fine)
- North side pins, left to right (x 86.2 to 90.7, y 108.1): SW1, HIDRV1, BTST1, LODRV1, REGN, DRV_SUP, GND, LODRV2, BTST2,
  HIDRV2: they connect to the stage room above. Keep the strip between U503's north side and y 104.6 free of anything but
  C510 (REGN), C511 (DRV_SUP) and D510 (REGN -> DRV_SUP), with gaps so ten nets can pass.
- West side: ACN_F 29, ACP_F 30 (filter R525, R526, C514, C515, C516; R525 pad 1 and R526 pad 1 are the sense taps of the
  input shunt R524, 25 mm away near (86, 85): inner layers, via room at each), PPHV 32/33 (C509; R509), ACUV 34, ACOV 35
  (R509, R510, R511), FSW 36 (R512).
- South side: I2CC SCL 1, SDA 2, CHG_INT 3 (from the PD controller at the top: via room), CE_N 7 (R517, R535), TS 8 (R515,
  R516; thermistor TH501 fixed at (88.3, 97.3)), ICHG 9 (R513), ILIM 10 (R514).
- East side: SW2 18, SRP_F 14, SRN_F 13 (filter R528, R529, C517, C518, C519; R528 pad 1 and R529 pad 1 are the sense taps
  of the battery shunt R527, which the stage room puts near x 96-99, y 98-104), FB 12, FBG 11 (R518, R519).

## 9 V gate-drive supply (U506, Q509, C557, C558, D511, R552, R553, R554) in the lower part of the room
- U506 pad 8 IN and C557 take PACK_P from an inner-layer pour: room for a via within 1.5 mm of each.
- U506 pad 1 OUT -> C558, R552/R553 divider (FB pad 2) -> D511 -> DRV_SUP, which goes to U503 pad 23 / C511 and to the
  boot diodes in the stage room above (around y 103). Put D511's DRV_SUP pad on the side facing U503.
- Q509 (pad 1 gate = DRV9_OFF, arriving on an inner layer down the left board edge from the PD controller: via room;
  pad 3 drain -> U506 pad 5 EN, with R554 from REGN).

## What failed here on the hand board (connections with no path)
ACP_F U503-C514; LODRV2 and HIDRV1 at U503; REGN C510-U503 and U503-R515; BTST2 U503-C513; DRV_SUP at U503; ACUV
R510-U503; TS U503-TH501; the sense taps at R525, R526, R528; PACK_P at R529; GND at Q509. Aim for none of these.

## Numbers to report
Blocked connections in your room, and whether PACK_P is joined at U506 (dc.log / plan.log).
