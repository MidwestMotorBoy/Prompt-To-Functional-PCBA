# Round 3 review (strict outside reviewer, state = end of round 2, snap22)

Method: `./make.sh` (NETLIST OK), every `out/render/page-*.png` read at 100 dpi and then cropped with PIL at 130 to 260 dpi, region by region;
the reference PDF `ref/hand_drawn_vs_generated.pdf` looked at again for how a person draws a buck and a big IC; generator lint (0 findings),
tight lint (3 to 5 benign findings), independent PDF lint (only the known false positives) and wire statistics (`scratch/wirelen.py`,
`scratch/disp.py`: how far every lane stands from its pin).
Scores are 0-5 per criterion, half points between levels. They are lower than the estimates I wrote at the end of round 2 for the same
state: there I counted wire length and long segments; a strict reader looks at how far every support part stands from the pin it serves and
at bundles of parallel wires between a lane and its pin, which is exactly the owner's "way too much down wire".

## Scores before this round's changes

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port 1/2 |
|---|---|---|---|---|
| 1 Flow | 3.5 | 3.5 | 4.5 | 4 |
| 2 Grouping | 4 | 3 | 4.5 | 3.5 |
| 3 Wires vs labels | 3.5 | 2.5 | 4 | 3 |
| 4 Clutter | 4 | 3.5 | 4 | 3.5 |
| 5 Space | 3.5 | 3 | 3.5 | 3.5 |
| 6 Recognisable circuits | 3.5 | 4 | 4.5 | 4.5 |
| 7 Annotation | 4 | 4.5 | 4.5 | 4.5 |
| 8 Reviewability | 4 | 3 | 4.5 | 3.5 |
| mean | 3.75 | 3.38 | 4.25 | 3.81 |

### What cost the points

* **Cells and Gauge (3.38).** U101's left side is 16 rows of lanes (BAT, VCC, PBI, the cell ladder, SRP/SRN, PACK, TS1 to TS4) whose
  parts need 104 mm of height, while the 16 pins stand 48 mm apart. Every lane therefore reaches its pin through a jog: BAT, VCC and PBI
  stand 35 to 56 mm above their pins, TS1 to TS4 40 to 46 mm below, 14 parallel wires of 20 to 56 mm form a bundle 36 mm wide, and the
  reader has to follow each wire to see which RC filter belongs to which pin (sum of lane-to-pin displacements 464 mm). 3 segments are
  longer than 50 mm and the sheet is wide (471 mm) because of the bundle. Parts do not "sit next to the pin they serve".
* **USB Port 1/2 (3.81).** The same effect on the charger U403: left lanes up to 51 mm and right lanes up to 29 mm away from their pins
  (sum 357 mm), U401's right side 19 mm; 7 segments over 50 mm; R412 to R414, the input window divider and the bootstrap parts are not at
  their pins. Page 451x332 with one column 35 mm shorter than the other.
* **3V3 Rail (3.75).** The buck is not drawn like a buck: the inductor is lifted 23 mm to the output level (the SW wire jogs up), and the
  VOS wire detours 20 mm below and around (48 mm path) instead of running straight back to the node behind the inductor. The hand drawn
  reference has the inductor in line with SW. The other U204 and U404 (TPS62933) have the same jog.
* **MCU (4.25).** U301's left lanes are 27 to 36 mm from their pins (3V3 decoupling, RSTN network, RFIO pi match); the IRQ_N wire is 52 mm.

## The five changes that raise the lowest scores most (in order)

1. **Move the pins of a crowded IC side to their lanes (structural).** An IC side whose lanes stand 8 mm or more from their pins is drawn like
   a person draws a part with a lot around its pins: same order, names and numbers, but the pins stand where their lanes stand and the body
   grows with them (the symbol is written with moved pins, not edited in the library). Every lane is then a straight wire from its pin: no
   jogs, no bundles, the parts sit at the pin. Hits Wires, Grouping, Space, Reviewability on Cells, USB and MCU.
2. **Buck converters as the textbook picture (Recognisable circuits, Flow; 3V3, USB U404/U504).** Follows from 1 for the regulators: SW straight
   to the inductor in line, output node behind it, the feedback (VOS, FB divider) back to that node, output capacitors beyond.
3. **Page packing for the new shapes (Space; USB, Cells).** Sections change width and height when pins move to lanes; the packer has to
   be re-run on them (column widths, aspect), and the unequal column heights of the USB page should go.
4. **Check every pin side that is not moved (Clutter, Annotation).** Pins at 2.54 mm pitch next to stretched sides: label boxes that touch,
   pin numbers that crowd, the IC texts over a taller body; the tight lint is the tool.
5. **Staircases and pads in the new frame (Wires; Cells TS1 to TS4, U401 pull-ups).** With lanes on their pins the stairs only need their
   own rows; check they still read as a stair and that pads stay beside their ground symbols.

## Result of round 3 (state = snap25; `./make.sh` ends with NETLIST OK, 0 generator lint findings, 0 text-on-text in the PDF lint)

### What was done with the five changes

1. **Pins of a crowded IC side moved to their lanes: done, and wider than planned.** The first version (threshold 8 mm) straightened the gauge,
   the charger and the MCU module's left side; at that point the 1 to 4 mm kinks that were left (U102's V1 to V4, the SCL/SDA/IRQ_N lanes of the
   module, the CC lines of U405, the I2C pull-up lanes of U401) were now the most visible flaw, so the threshold is 1 mm. Every lane of every
   plain IC symbol stands on its pin (`scratch/disp.py`: of 48 IC sides, 42 have displacement 0; the 6 others stand 1.3 mm off in one stub row, a label or ground stub
   on U401/U501's two sides, and on the USB-C receptacle J401/J501, whose symbol carries a drawing and is not stretched). Two planner bugs were fixed on the way: rows
   of two pins were put below their lane (the pins crept down 1.27 mm per iteration on U401) and a pin that prints two numbers (`[15,30]`)
   overprinted the pin above it.
2. **Textbook bucks: done as a consequence.** TPS62177 (3V3 sheet) and both TPS62933 (USB pages): SW straight into the inductor, feedback back to
   the node behind it, output capacitors beyond. The 3V3 sheet is 165x138 (was 186x128).
3. **Page packing: done.** The first section stays top left, "tall first" no longer carries a 25 % penalty, and strict column layouts compete with
   the skyline. The USB pages are `[USB-C, PD controller | power stage, 9 V, 5 V | charger]` with aligned frames, 579x247 (were 451x332 with
   unequal columns); the gauge page stays the skyline layout, 420x226 (was 471x219), because columns would make it 32 mm taller.
4. **Unmoved sides: checked.** Tight lint: 3 benign findings on the gauge and on each USB page (thermistor next to its ground symbol, SW1/SW2 and
   FET_MID labels resting on their junction), none on 3V3 and MCU (the SCL/SDA/IRQ_N label boxes no longer touch). What is left that I cannot
   change from the drawing code: no-connect crosses touch the pin number beside them (U101, U301, U405) and KiCad prints stacked pin numbers
   as a bracketed list.
5. **Staircases and pads: checked, nothing to change.** TS1 to TS4, the charger's R412 to R414 and the pull-up stair of U401 still read as
   stairs; the pads stand beside their ground symbols; with straight lanes the stair columns are the only place where a wire is longer than it
   needs to be (the I2Cc_IRQ lane is 57 mm).

### Scores after this round's changes (same harsh reading, every page re-read at 130 to 400 dpi)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port 1/2 |
|---|---|---|---|---|
| 1 Flow | 4.5 | 4 | 4.5 | 4 |
| 2 Grouping | 4 | 4 | 4.5 | 4 |
| 3 Wires vs labels | 4.5 | 4 | 4.5 | 4 |
| 4 Clutter | 4.5 | 4 | 4 | 4 |
| 5 Space | 3.5 | 3.5 | 3.5 | 3.5 |
| 6 Recognisable circuits | 4.5 | 4.5 | 4.5 | 4.5 |
| 7 Annotation | 4 | 4.5 | 4.5 | 4.5 |
| 8 Reviewability | 4.5 | 4 | 4.5 | 4 |
| mean | 4.25 | 4.06 | 4.31 | 4.06 |

Before: 3.75 / 3.38 / 4.25 / 3.81 (the table at the top). Largest gains: Cells Wires 2.5 to 4, Reviewability 3 to 4, Grouping 3 to 4;
USB Wires 3 to 4, Grouping 3.5 to 4, Clutter 3.5 to 4; 3V3 Recognisable 3.5 to 4.5, Wires 3.5 to 4.5, Flow 3.5 to 4.5.

### Numbers

| | before (snap22) | after (snap25) |
|---|---|---|
| page sizes (mm) | 3V3 186x128, Cells 471x219, MCU 337x124, USB 451x332 | 165x138, 420x226, 311x137, 579x247 |
| wire length (mm) | 201 / 1852 / 432 / 3010 | 156 / 879 / 338 / 1722 |
| segments over 50 mm | 1 / 3 / 1 / 7 | 1 / 2 / 1 / 3 |
| lane-to-pin distance, sum over the IC sides | U101 left 464, U403 357, U301 left 80, U401 right 84 | 0 on every stretched side |

### What still costs points

* **Space (3.5 everywhere).** Frames are wider than their content where a long note sets the width (PD controller, charger, the gauge interrupt
  section); the 3V3 page has an empty lower left third; the MCU debug section is half empty. A frame with a narrower wrapped note would help;
  the packer does not offer two widths per section yet.
* **Cells and Gauge.** F102 stands beside Q104 and is tied to it by two FUSE_HTR labels 50 mm apart (a wire would be clear: Wires, Grouping);
  U101 is a 150 mm tall box with its right-hand pins bunched in the middle; the parking sections for pads and test points hold six small
  parts in two large frames.
* **USB pages.** The page is wide (579x247); the PD controller frame is half empty to the right of U401; the I2Cc_IRQ lane is 57 mm because each
  pull-up of the stair stands in its own 22 mm column.
* **Library limits.** The protection FETs and half bridges are rectangles with pin names, not FET symbols; KiCad's NC crosses touch the pin
  numbers beside them and stacked numbers print one line per number; the TC2030 connector symbol prints VCC over RESET.

Next in line (for a round 4): tie F102 to Q104 with a wire (a small template), two frame widths per section for the packer, a compact stair for
the I2C pull-ups.
