# Round 2 review (strict reviewer, before this round's changes)

Method: `./make.sh` (NETLIST OK, 0 lint on every sheet), then every page opened at 100 dpi and re-rendered at 130 to
150 dpi in tiles so that all text was readable. Scores are 0-5 per criterion; 5 means "as good as a careful human drawing".
The two USB sheets are one score (port 2 differs from port 1 only in the ADCIN1 strap).

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.5 | 3.5 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.0 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 3.5 |
| 5 Space | 3.0 | 3.0 | 3.0 | 3.0 |
| 6 Recognisable circuits | 4.0 | 4.0 | 4.0 | 4.0 |
| 7 Annotation | 4.0 | 4.5 | 4.5 | 4.0 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 3.5 |
| Mean | 3.9 | 3.9 | 4.1 | 3.6 |

## Why points were lost

3V3 Rail
* Space: buck box is half empty below the IC; pin-number cluster (4/11/1/6) at the bottom of U204 looks cramped.
* The VOS wire runs parallel to the SW wire for 30 mm before it joins the output; correct, but not how a person draws it.

Cells and Gauge
* Space: 325 x 340 mm page, bottom right quarter (right of the protector, above the title block) is empty and the
  thermistor box is a tall narrow column with large gaps; J117/J118 text is stacked tightly.
* The FET pair is an arch over a gap in the main line with C110/C111 in the line; correct, but a quick reader may take
  the capacitors for series parts of the path.

MCU
* Space: empty block to the right of the connector box above the title block; module box has an empty lower left.

USB Port (the lowest score)
* Wires vs labels: the input-window divider R409 to R411 is 30 mm away from ACUV/ACOV and tied to them by labels only;
  the FB divider R418/R419 stands 50 mm right of the FB/FBG pins and is tied by labels only; the PD controller's LDO
  caps C404/C405 are in a row far below the LDO pins, tied by labels only; "P1_LDO_3V3" is written eight times in the
  PD section (three pull-up arrows, flags, caps).
* Grouping: the three items above are not next to the pin they serve.
* Space: 410 x 405 mm. Empty top-left of the connector box (VBUS rail alignment), empty lower left of the PD box, empty
  strip under the charger. The PD box is wider than it needs to be because of the EEPROM at the far right.
* Clutter: stacked ground pads on U401 and U405 print overlapping pin numbers (symbol issue), a "(15)" pin box beside
  DRAIN.

## Five changes that would raise the lowest scores most (priority order)

1. USB charger: draw the input-window divider hanging from the PPHV wire at the VAC pin with its taps wired into ACUV
   and ACOV (no labels), and move the FB divider next to the FB/FBG pins with wired taps. Removes 6 labels/flags, makes
   both dividers read as dividers at their pins, narrows the charger section.
2. USB PD controller: one LDO_3V3 supply rail wired from the LDO_3V3 pin (and the ADCIN1 strap on port 1) with the
   three I2C pull-ups hanging from it, C404 on the rail at the pin and C405 wired to LDO_1V5, EEPROM moved under the
   pull-up block. Removes the support row, 5 repeated rail labels, and shrinks the section in both directions.
3. Space on the USB sheet: re-pack after 1 and 2 (narrower charger and PD boxes, shorter PD box) so that the page
   shrinks and the holes (under the charger, right of the PD box) go away.
4. Space on Cells and Gauge: re-pack the sections so that the empty bottom right closes (move the notes block and the
   thermistor box into the free area), and give the thermistor column tighter, even spacing.
5. Space on MCU and 3V3 Rail: fill or remove the dead zones (MCU: move the notes under the module box's right side or
   widen the module box content; Rail: shorten the buck box below the IC and drop the page height).

# After round 2 (same strict reader, after this round's changes)

Method: `./make.sh` ends with NETLIST OK (285 shared parts, 168 nets, 0 differences); 0 lint on all five sheets. Every page
was opened again at 100 dpi, and the changed regions were re-rendered at 130 to 400 dpi and read in tiles.

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.5 | 4.0 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.5 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 4.0 |
| 5 Space | 3.0 | 3.5 | 3.5 | 3.5 |
| 6 Recognisable circuits | 4.0 | 4.0 | 4.0 | 4.0 |
| 7 Annotation | 4.0 | 4.5 | 4.5 | 4.0 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 4.0 |
| Mean | 3.9 | 4.0 | 4.2 | 3.9 |

Change against the "before" table: 3V3 Rail 3.9 to 3.9, Cells and Gauge 3.9 to 4.0, MCU 4.1 to 4.2, USB Port 3.6 to 3.9.

## What was done about the five items

1. USB charger dividers (done). The input window divider hangs from the PPHV wire at the VAC pin and its taps are wired
   into ACUV and ACOV; the FB divider stands beside the FB/FBG pins with wired taps. Six labels/flags are gone and the
   charger section is about 25 mm narrower and 8 mm shorter.
2. USB PD controller supply (done). One LDO_3V3 rail runs from the pin: C404 on it at the pin, the ADCIN1 strap wired to
   it (port 1), the three I2C pull-ups hanging from it, the EEPROM under the pull-ups. C405 is wired to LDO_1V5. The
   support row and five repeated rail labels are gone. The section is about 20 mm shorter and 30 mm narrower.
3. USB sheet space (partly). 410 x 405 became 400 x 375 mm. Frames of one row now share a bottom edge and the two
   right-hand sections share a right edge; the notes are set in two columns of about 100 characters. Remaining: a 23 mm
   strip under the charger frame and a 70 x 38 mm corner at the top left of the connector frame.
4. Cells and Gauge space (done). The sections were re-ordered: pack path with the notes at its right, the gauge with the
   thermistor inputs at its right (they feed its TS pins), the protector below. The pack path was shortened by about 18
   mm. 325 x 340 became 305 x 330 mm; the large hole at the bottom right is now a smaller one above the title block.
5. MCU and 3V3 Rail space (MCU done, Rail small). MCU: notes and the connector box now stand in the right-hand column
   above the title block: 305 x 175 became 295 x 170 and the 105 x 65 mm hole is gone. Rail: notes narrowed, 270 to 265.

Also done: stacked duplicate pins are hidden in the embedded symbol (the KiCad convention for stacked pads), which
removes the overlapping pin numbers on U405 (TPD6S300); RPD_G1/RPD_G2 are wired to their CC lines instead of labels; the
EEPROM supply arrow no longer sits under the IRQ line; the text resolver now prefers positions that keep 0.6 mm clear
of wires.

## Where points are still lost

* 3V3 Rail, Space: ten parts on a 265 x 135 mm page; the buck frame has empty areas left and right of the IC and the
  title block is close to the bulk-capacitor frame. A page this small cannot be filled without scattering parts.
* Cells and Gauge, Space: a 107 x 62 mm hole above the title block (right of the protector). Every re-ordering of the
  five blocks I tried moves the hole instead of removing it. The bare PACK- return line is long (RS101 sits in the middle).
* MCU, Space: 74 x 35 mm hole right of the antenna match and the empty lower left of the module frame.
* USB, Wires vs labels: the EEPROM is tied to the I2C lines by labels (a wire would cross the IRQ line twice). The
  CC1/CC2 lines from the protector to the PD controller and the REGN pull-up of the thermistor divider are label ties
  over 60 to 110 mm.
* USB, Grouping: C405 stands at the far end of the 80 mm LDO_1V5 line because the 3V3 rail runs 2.54 mm below it from
  the neighbouring pin, so a drop at the pin would cross the rail.
* Clutter: KiCad draws the stacked pad numbers of U401 (GND "11 12 14 31 39", DRAIN "15, 30") as a tight stack, and the
  pin-number boxes of U204 (4, 11, 1, 6) touch. Both are symbol issues.
