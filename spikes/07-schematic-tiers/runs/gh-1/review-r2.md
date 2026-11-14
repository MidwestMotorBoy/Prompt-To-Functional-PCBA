# Round 2 self-review (strict outside reviewer, after re-reading every page at zoom)

Order: flow, grouping, wires vs labels, clutter, space, recognisable circuits, annotation, reviewability.

## Before (harsh re-grade of the round 1 result)
| sheet | F | G | W | C | S | R | A | V |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| Cells and Gauge | 3 | 4 | 3 | 3 | 3 | 4 | 4 | 3 |
| MCU | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| USB Port | 3 | 4 | 3 | 4 | 3 | 4 | 3 | 3 |

Evidence: Cells TS2/TS3 return ground symbols and "CELL_1N" text ran into the next TS row (clutter 3); gauge frame half empty, frames
with 20+ mm dead margins (space 3); USB had almost no notes and the power path jumps between frames (flow 3, annotation 3,
reviewability 3); the gate, sense and SW nets between the charger and the power stage are labels only (wires vs labels 3).

## Five changes that would raise the lowest scores most
1. Cells: give the TS rows room so grounds and text do not touch other rows (clutter). DONE (TS2/TS3/TS4/PTC pitches, columns pulled 18 mm closer).
2. USB annotation: say what sets each number (input window, limits, 500 kHz, 16.8 V, 5.15 V, 9 V gating, address strap) with refs from the port base. DONE (notes in charger, power stage, buck, 9 V, PD groups).
3. USB flow: a one-line power path under the title so a reader can follow VBUS to PACK_P across frames. DONE (title note). A real fix (power stage to the right of the charger) makes the page about 750 mm wide; judged worse for space. Not done.
4. Wires vs labels: gate and sense links by wire. Not done (labels carry short names, frames are 100+ mm apart; a wire would be a long detour).
5. Space: auto-pack frames and trim dead margins (gauge frame, 3V3 frames, MCU connector frame). Not done; needs a packer in `Lay`.

## After
| sheet | F | G | W | C | S | R | A | V |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| Cells and Gauge | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 |
| MCU | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| USB Port | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 |
