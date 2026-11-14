# Round 3 self-review (before this round's changes)

All six renders opened and cropped at full resolution (make.sh: NETLIST OK; lint 0 on every sheet, MCU 1 false positive).

| Sheet | Flow | Group | Wires vs labels | Clutter | Space | Recognisable | Annotation | Review | Mean |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 3.9 |
| Cells and Gauge | 3 | 4 | 3 | 4 | 3 | 4 | 3 | 3 | 3.4 |
| MCU | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 3.8 |
| USB Port (1 and 2) | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 3 | 3.6 |

Main faults seen:
- Cells: seven nested staircase wires (SRP..TS4 fan) running 40 mm down the left of the gauge, crossing the cell-filter
  stairs; the pads J117-J120 and RS101 hang off those wires; the lower right of the page and the area below the
  protector are empty while the left column is tall.
- USB: A2 sheet, content about 70 % of the width; charger FSW/ICHG/ILIM/TS fan is a 50 mm staircase tower that makes the
  charger the tallest group; EEPROM far right on the pull-up rail; gate-drive supply has a lonely C410/D410 row below it.
- MCU: pull-up resistors on long rails; lower third empty besides two connectors.
- 3V3: right half of the A4 sheet is empty.

## Five changes ranked by expected gain
1. Cells: replace the SRP..TS4 staircase by label stubs on the gauge and draw "Current sense and pack sense" and
   "Thermistors" as their own wired groups under the gauge (fills the empty lower area, removes the nested wires).
2. Cells: rebalance the page (move the thermistor/pad groups, bring the protector closer, keep the page A3).
3. USB: charger configuration pins (FSW, ICHG, ILIM_HIZ, TS) to label stubs with a compact "charger configuration"
   row of resistors in place of the 50 mm tower.
4. USB: EEPROM above the I2C rail in the PD controller group (shorter row); look again at A3: needs 380 x 241 mm of
   drawing against 419 x 284 now, which three stacked rows (110 + 78 + 100 mm) cannot reach without splitting the power stage.
5. MCU / 3V3: shorten pull-up rails, move notes and bulk caps so the empty halves are used.

## After round 3
Done: change 1 (Cells staircase replaced by label stubs and three wired groups under the gauge: "Pack current sense" with a
Kelvin-filtered RS101, "Pack sense and thermistors" with R113, TH101, TH104 and the TS2/TS3 wire pads; this also fills the
bottom of the sheet and the area under the protector). Lint 0 on Cells, NETLIST OK.

Not done, with reasons:
- USB on A3: needs <= 380 x 241 mm of drawing; it is 419 x 284. Its three stacked rows (about 110 + 78 + 100 mm) and the 400 mm
  wide bottom row (charger 124, supply 137, buck 133) cannot lose 40 x 43 mm without splitting the power stage into two
  columns or dropping parts of the groups; a redesign of the sheet, not a tweak. Stays A2.
- Charger FSW/ICHG/ILIM/TS: kept as a wired ladder (a label-bus version only saves about 9 mm and moves four local
  resistors onto labels, which the rubric counts against "wires vs labels").
- EEPROM: wiring SDA/SCL to it needs the two lines to cross (pin order is reversed), so it stays on labels.

| Sheet | Mean before | Mean after |
|---|---|---|
| 3V3 Rail | 3.9 | 3.9 |
| Cells and Gauge | 3.4 | 3.8 |
| MCU | 3.8 | 3.8 |
| USB Port (1 and 2) | 3.6 | 3.6 |
