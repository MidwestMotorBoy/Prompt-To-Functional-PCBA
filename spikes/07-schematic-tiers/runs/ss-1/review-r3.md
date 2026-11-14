# Round 3 review

Criteria order: Flow, Group, Wires, Clutter, Space, Recog, Annot, Review (0-5 each).

| Sheet | Flow | Group | Wires | Clutter | Space | Recog | Annot | Review | /40 |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail (before r3) | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 | 30 |
| Cells and Gauge (before r3) | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 24 |
| MCU (before r3) | 3 | 3.5 | 3 | 3.5 | 3 | 3.5 | 3 | 3.5 | 26 |
| USB ports (before r3) | 3 | 3.5 | 2.5 | 3 | 3 | 3 | 3 | 3 | 24 |
| Cells and Gauge (after) | 3.5 | 4 | 4 | 3.5 | 3 | 4 | 3.5 | 4 | 29.5 |
| MCU (after) | 4 | 4 | 4 | 4 | 3 | 4 | 3.5 | 4 | 30.5 |
| USB ports (after) | 3 | 3.5 | 2.5 | 3.5 | 3 | 3 | 3 | 3 | 25 |
| 3V3 Rail (after, unchanged) | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 | 30 |

Faults seen before the changes (all pages read at zoom):
- Gauge: BQ40Z50 cell-filter lanes ran as long parallel wires, cells tied by labels, supply parts floating.
- MCU: pull-ups were a bank hung from the rail and tied to their pins only by labels.
- USB: BQ25756 section still a fan of long wires; EEPROM ref text on the rail.
- Everywhere: little annotation inside the sheets, big empty areas on the gauge sheet next to the pad list.

Priority list:
1. Gauge cell-filter ladder drawn as a textbook circuit with the pads, series resistors and caps in order (done).
2. Gauge supply pins (BAT diode and R105, R106, PBI cap) on short lanes (done).
3. MCU module hand drawn, pull-ups on their lines, caps at the supply pin, reset RC at RSTN (done).
4. EEPROM text clear of the rail (done).
5. Open: BQ25756 charger hand layout (Kelvin filters and divider need lanes both up and down; I could not make the C416 shunt
   cap clear of the divider taps without a ground-up symbol), and in-sheet notes for the 3V3 rail and USB sections.
