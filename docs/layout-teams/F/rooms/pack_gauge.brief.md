# Room pack_gauge: protection FETs, fuse, second-level protector, fuel gauge, current sense

Room area (several boxes, see the picture): the FET band x 92.4-110.8, y 116.0-118.5 and x 92.4-109.1, y 118.5-124.0; a
small box x 88.6-92.4, y 121.2-124.0; the gauge area x 93.4-111.3, y 124.0-137.1; the fuse corner x 115.0-121.5,
y 126.8-132.2 with x 111.4-116.5, y 128.7-134.3; and the shunt area x 83.5-93.4, y 131.6-137.1.
Fixed inside: wire pads J108 (CELL_N), J112 (CELL_P_RAW), J114 (GND load), J110, J115, J116, J119, J120, J117, J118 (cell
taps and thermistor wires), holes H103, the tag-connect J302, the MCU module U301 to the right.
With 54 parts this is the largest room; you may split it between sub-agents (FETs + fuse / gauge + second level).

## Power flow, all 10 A (this path carries the highest current on the board)
J112 (CELL_P_RAW, bottom right) -> F102 pad 1; F102 pad 2 -> CELL_P -> Q101 pads 1,2,3; Q101 -> FET_MID (pads 5-8 and the
tab) -> Q102; Q102 pads 1,2,3 -> PACK_P, which goes to J113 (fixed, right board edge at (119.5, 109), 10 A), to the two
battery shunts (R427 at the right edge above J113, R527 near (97, 101)) and to bulk capacitors under the board centre.
Return: J108 (CELL_N, bottom left) -> RS101 pad 1; RS101 pad 2 = GND.
- On the hand board CELL_P cost 1.4 milliohm (0.14 W): F102 far from Q101's CELL_P pads, path squeezed past H103 and J302.
  Make it short and wide.
- PACK_P from Q102 to J113 cost 2.1 milliohm (0.21 W), the largest single loss on the board: Q102's PACK_P pads faced the
  left, 27 mm from J113. If you can find a legal arrangement of the FET pair that brings Q102's PACK_P pads nearer to
  J113 and the shunts without lengthening CELL_P / CELL_P_RAW by more than it saves, do it and report what it cost and
  saved (dc.log: PACK_P terminals J113, R427, R527; CELL_P; CELL_P_RAW). If not, keep the hand arrangement of the pair.
- RS101 pad 2 is where every return current of the board enters (GND costs 0.34 W in all): leave free space for at
  least six vias round that pad.
- 10 A copper needs strips about 5 mm wide: keep small parts out from between the FET pads, F102 and the wire pads.

## Around the FETs
Gate parts: R109 (CHG -> CHG_G, Q101 pad 4), R110, R111 (DSG -> DSG_G, Q102 pad 4), R112, D103; C107/C108 (PACK_P - mid -
GND), C110/C111 (CELL_P - mid - PACK_P); R118 to WAKE (TP113 fixed).

## Gauge U101 and second-level protector U102
- U101 west side: cell inputs VC4..VC1 with filters R101-R104 / C101-C104, PBI (C105), SRN/SRP from the shunt filter
  (R107, R108, C106: R107 pad 1 and R108's tap are sense taps at RS101's inner pad edges, thin tracks, keep them reachable).
- U101 north: BAT (D101), CHG pad 31 -> R109, DSG pad 28 -> R111, PACK (R113 from PACK_P), VCC (R106 from FET_MID),
  GAUGE_FUSE pad 25 -> R126. East: SMBC/SMBD -> R115/R116 -> SCL/SDA (J302 pads 6/1 and the MCU). South: TS1-TS4, BTP_INT
  -> Q103 / R117 -> IRQ_N.
- Cell taps arrive from wire pads: CELL2 J110, CELL_4P J116, CELL_1N J115/J118/J120 are at the bottom edge; CELL1 (J109)
  and CELL3 (J111) come all the way from the top corners of the board on inner layers: via room at R101/R122 and R103/R120.
- U102 with R119-R123, C112-C117; its output drives Q104 (R124, R125, C118) which fires the fuse heater F102 pad 3; R126.
- R314 (pull-up of IRQ_N at U301 pad 21, south side of the module) is also yours.

## What failed here on the hand board (connections with no path)
SCL R115-J302; IRQ_N from Q103; the CELL_N sense tap at R107; PACK_P at C107; hand-board courtyard overlaps C108/Q103
(0.85 mm) and Q104/F102 (1.0 mm), which you must not repeat.

## Numbers to report
CELL_P, CELL_P_RAW, FET_MID, CELL_N, and PACK_P (per terminal) resistance and loss from dc.log; blocked connections.
