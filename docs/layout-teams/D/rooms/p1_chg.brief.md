# Room p1_chg: Port 1 charger controller, its programming and sense filters, and the Port 1 5 V buck

Room area: x 94.0-116.4, y 104.6-115.9; x 116.4-121.5, y 107.3-113.3; x 94.0-99.3, y 102.6-104.6; x 101.1-107.6, y 102.4-104.6.
Fixed inside: J113 (PACK_P wire pad, x 117.6-121.3, y 107.3-110.6), TP113, TP412 (GND), the corner of J301. On the BOTTOM
side under x 96-106, y 103-112 sit the six pack-rail bulk capacitors (PACK_P to GND); the copper planner drops vias for
them wherever the top side is free, so do not pave that area solid: leave a few 1 mm gaps.
This is the fullest room (73 %). The stage room is above (its gate resistors at about y 102.5-104.5, x 108-117), the pack
FETs below (from y 116).

## Charger controller U403 (keep its north side facing the stage; the hand position, centre (111.4, 110.4), is fine)
- North side pins, left to right: SW1, HIDRV1, BTST1, LODRV1, REGN, DRV_SUP, GND, LODRV2, BTST2, HIDRV2: they connect to
  the stage room above. Keep the strip between U403's north side and y 104.6 free of anything but C410 (REGN), C411
  (DRV_SUP) and D410 (REGN -> DRV_SUP), and leave gaps so ten nets can pass.
- West side: ACN_F 29, ACP_F 30 (sense filter R425, R426, C414, C415, C416; R425 pad 1 and R426 pad 1 are the two sense
  taps of the input shunt R424, which is 25 mm away at about (109, 85): they leave on inner layers, via room at each),
  PPHV 32/33 (C409; R409 divider), ACUV 34, ACOV 35 (R409, R410, R411), FSW 36 (R412).
- South side: I2CC SCL 1, SDA 2, CHG_INT 3 (from the PD controller at the top of the board, inner layers: via room),
  CE_N 7 (R417, R435; CHG_INH from the MCU), TS 8 (R415, R416; thermistor TH401 is fixed up at the inductor, (111.3, 97.3)),
  ICHG 9 (R413), ILIM 10 (R414).
- East side: SW2 18, SRP_F 14, SRN_F 13 (filter R428, R429, C417, C418, C419; R428 pad 1 and R429 pad 1 are the sense taps
  of the battery shunt R427, which the stage room puts at the right edge just above J113), FB 12, FBG 11 (R418, R419).

## 5 V buck (U404, L402, C439-C443, R432-R434, C444, C446) in the west part of the room
- U404 pad 5 SW -> L402 pad 1; L402 pad 2 -> C441-C443 -> PP5V, 1.5 A, leaves north through the reserved lane
  x 99.4-101.0 at y 104.6 (it runs 25 mm up the board to the PD controller). Give it a clear top-layer strip at least
  1.2 mm wide from the output capacitors to (100.2, 104.6).
- Hot loop "USB Port 1/HL_5V": C446 (first) then C444 between U404 pad 3 (VIN = PACK_P) and pad 4 (GND), pads right at the
  pins. Limit 6.98 nH, hand board 0.92.
- PACK_P at U404 pad 3 / C446 / C444: room for two vias within 1.5 mm (the hand board had none).
- EN_5V1 (U404 pad 2, R432) comes from the MCU module to the lower right: it had no path on the hand board.
- FB divider R433/R434 at pad 8, short, away from L402 and the SW node.

## What failed here on the hand board (connections with no path)
ACP_F C415-U403; HIDRV1 at U403; ACUV R410-U403; EN_5V1 U404-R432 and U301-U404; TS U403-TH401; the sense taps at R425,
R428; PACK_P at R429. Aim for none of these.

## Numbers to report
PP5V and PACK_P-at-U404 status and resistance (dc.log), HL_5V (one run without --no-hot at the end), blocked connections.
