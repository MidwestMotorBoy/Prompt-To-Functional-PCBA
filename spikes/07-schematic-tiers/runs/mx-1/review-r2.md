# Round 2 review (strict outside reviewer, state = end of round 1)

Method: `./make.sh` (NETLIST OK), every `out/render/page-*.png` tiled and cropped with PIL at 130 to 500 dpi, every page read
region by region, plus the generator's own lint (0 findings) and the independent PDF lint (`scratch/lint_pdf.py`).
Scores are 0-5 per criterion; half points are used where a sheet is between two levels.

## Scores before this round's changes

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port 1/2 |
|---|---|---|---|---|
| 1 Flow | 4 | 3.5 | 4.5 | 4 |
| 2 Grouping | 4 | 3 | 4.5 | 4 |
| 3 Wires vs labels | 3 | 2.5 | 4 | 3.5 |
| 4 Clutter | 3 | 3 | 4 | 3.5 |
| 5 Space | 3.5 | 3 | 3.5 | 3 |
| 6 Recognisable circuits | 4 | 4 | 4.5 | 4 |
| 7 Annotation | 4 | 4.5 | 4.5 | 4.5 |
| 8 Reviewability | 4 | 3 | 4.5 | 3.5 |
| mean | 3.69 | 3.31 | 4.25 | 3.75 |

(The means of Cells and MCU were first written as 3.44 and 4.31; that was an addition error, the columns add up to 3.31 and 4.25.)

### What cost the points

* **3V3 Rail.** The value text of C207 sits on the wire that returns from the regulator's VOS pin (text-on-wire, the lane end ignores the
  text of the last part). That VOS wire runs 40 mm back along the output (a feedback loop drawn at the far end of the output rail,
  although the feedback node is at the inductor). The page is a thin strip (most of the area right of the IC is empty).
* **Cells and Gauge.** The gauge's left side is a bundle of parallel 30 to 90 mm wires: BAT, VCC and PBI lanes stand 30 to 55 mm above
  their pins, the TS lanes end in a staircase of 4 wide shunt texts that reaches 94 mm out. About 20 % of the page is empty (below
  the gauge, around the three small sections). Two pad parts (J117, J119) float at the end of the stairs. The pad texts crowd the
  next lane's label in two places.
* **MCU.** Clean and the best page. Loses a little on space (the connector section is much smaller than the module section next to it,
  the band under both is empty) and a little on wires (the 3V3 supply wires of U301 and the RSTN network run 20 to 25 mm).
* **USB Port 1/2.** U404's feedback divider (R433) is a lane of about 86 mm that runs from the output rail back to the FB pin under the IC.
  The U403 and U401 fan-outs are long (the longest wires are 40 to 60 mm). Space: the two columns of sections leave 20 % of the page empty (right column is shorter
  than the left one). The 9 V supply block shows D410/D411 as two diodes tied by labels instead of a diode-OR. Stacked pin numbers
  of U405 (GND 8/13/18/21, N.C. 16/17) print on top of each other and cannot be read. A few clearances are tight (value text 0.4 mm from
  a wire, ground symbol 0.8 mm from a capacitor).

## The five changes that raise the lowest scores most (in order)

1. **Early join of a feedback / output loop (Wires vs labels, Clutter; 3V3, USB).** A regulator output and its feedback divider are joined
   at the first node after the inductor, not at the far end of the output bank, and a lane end must clear the text of its last part.
   Fixes the C207 text-on-wire, shortens the U204 VOS loop from 40 mm and the U404 FB lane from 86 mm.
2. **Tight-clearance lint and the fixes it finds (Clutter, all sheets).** A second lint level (power symbols included, 0.8 mm symbol and
   0.5 mm text/wire margins) to find cramped spots; fix them in the engine (tap-pad texts on one line, staircase clearance that counts the
   capacitor body, label clear zone), not by hand. Also merge stacked pins of U405/U505 so their numbers print as one block.
3. **Better page packing (Space, all sheets).** Search all section orders for up to seven sections (today only neighbour swaps),
   with a small penalty per inversion so the reading order stays natural; try several column widths per order.
4. **Shorter staircases and pinned rows (Wires vs labels, Cells; USB).** Shunts with wide texts in a staircase get vertical texts (TS1 to TS4
   of the gauge: 94 mm to about 50 mm); pinned-row candidates are chosen again after the first pinning (I2CC_SCL, ICHG-like rows now
   displaced 5 mm) and the displacement threshold is lowered.
5. **Diode-OR and bootstrap pair drawn as the textbook circuit (Recognisable circuits, USB).** D410/D411 into DRV_SUP as one cathode node;
   D404/D405 with C411/C413 as the usual bootstrap pairs next to the driver pins.

## Result of round 2 (state = end of round 2, `./make.sh` ends with NETLIST OK, lint 0 on all sheets)

Status of the five changes:

1. **Early join of feedback / output loops: done.** Measured on the generated files: the TPS62177 VOS return now joins the output right behind the
   inductor (x = 149.9 mm) and not at the far end of the output bank (x = 154.9 mm): the horizontal run is 14 mm instead of 19 mm (whole path 48 mm
   instead of 53 mm), and the return wire no longer runs through the value text of C207 (the lint-visible fault). U404's feedback resistor R433
   joins the PP5V net right behind L402: its wire from the resistor to the output node is 26 mm instead of 69 mm (the whole loop from the FB
   pin about 62 mm instead of 105 mm). My review above said 40 mm and 86 mm; those figures were read off the render and were too high for VOS.
2. **Tight-clearance lint and the fixes it found: done.** `LINT_TIGHT=1` (`scratch/tight.sh`) lists cramped spots; the engine now keeps supply and
   ground symbol names clear of the last series part (`end_tail`), shunts beyond a lane clear it by 3.81 mm, one-line pad texts, an IC's
   reference and value try seven places, and stacked pins (U405, U505) print as one bracketed number list. The tight findings left (3 on the gauge sheet, 5 on each
   USB sheet, none on the other two) are benign: labels resting on their own wire or junction, label boxes touching at pin pitch, the
   thermistor's arrow marks.
3. **Page packing: done.** Section orders with up to three inversions are searched, widths per order; the USB page area is 2 % smaller
   (464x337 to 451x339) from this, 4 % with the diode OR (451x332).
4. **Shorter staircases: done.** Vertical texts for three or more shunts in a row (R412 to R414, the I2C pull-ups, TS1 to TS4): steps 10 mm wide
   instead of 20 to 25, gauge section 15 mm narrower, the longest TS wire 71 mm to 51 mm, longest wire of the gauge sheet 71 mm to 56 mm. Fitting rows with
   weights (supply pins 4, pure decoupling lanes 2) brought C105 6 mm closer to PBI. Choosing pinned rows again after the first pinning was
   tried and found unnecessary: the rows that stay displaced are GND rows blocked by the hang zone of a neighbour or by the PD_DRAIN label.
5. **Diode OR and bootstrap pairs: done.** D410 and D411 now share a cathode node (the twin attachment of the lane engine; D410 no longer sits in a
   leftover list, DRV_SUP leaves the node as one label, REGN ends D410's anode). The bootstrap pairs D404/C412 and D405/C413 already stood as
   the textbook pair (diode from DRV_SUP to BTST, capacitor from BTST down to SW) once the pinned rows were in place.

Sizes (mm): 3V3 183x128 to 186x128, Cells 475x219 to 471x219, MCU 335x124 to 337x124, USB Port 1 464x337 to 451x332, USB Port 2 462x337 to 451x332.
Wire length, sum of segments (mm): 3V3 203 to 201, Cells 1892 to 1852, MCU 427 to 432, USB Port 1 3043 to 3010. Segments longer than 50 mm: Cells 4 to 3,
**USB Port 1 and 2 4 to 7 and MCU 0 to 1** (not an improvement: the charger section is 2 to 5 mm wider than before, which pushed several wires of
48 mm to 50.8 to 53 mm; the MCU wire went from 49.5 to 52.1 mm). Segments of 30 to 50 mm on USB: 21 to 19. The longest wire is still 73.7 mm
(the PPHV input of the charger).

### Scores after the changes (my own estimate, same harsh reader)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port 1/2 |
|---|---|---|---|---|
| 1 Flow | 4 | 3.5 | 4.5 | 4 |
| 2 Grouping | 4 | 3.5 | 4.5 | 4.5 |
| 3 Wires vs labels | 4 | 3 | 4 | 3.5 |
| 4 Clutter | 4 | 3.5 | 4 | 4 |
| 5 Space | 3.5 | 3 | 3.5 | 3.5 |
| 6 Recognisable circuits | 4 | 4 | 4.5 | 4.5 |
| 7 Annotation | 4 | 4.5 | 4.5 | 4.5 |
| 8 Reviewability | 4 | 3.5 | 4.5 | 4 |
| mean | 3.94 | 3.56 | 4.25 | 4.06 |

### What would still cost points

* **Cells and Gauge** (still the lowest): the gauge's left side is a bundle of 14 parallel wires; BAT, VCC and PBI stand 30 to 45 mm above their
  pins and TS1 to TS4 about 50 to 60 mm below. Cause: 2.54 mm pin pitch against lanes 10 mm tall. A fix needs a different structure (labels at
  the pins for the lanes that would move far, with the part block beside the IC), not more tuning. About 15 % of the page is empty.
* **USB Port 1/2:** 7 wires longer than 50 mm (the charger's fan-out and the PPHV input; more than before the round, see above); the right
  column is 35 mm shorter than the left one.
* **3V3 Rail** is a thin strip; **MCU** has a connector section much smaller than the module section next to it.
