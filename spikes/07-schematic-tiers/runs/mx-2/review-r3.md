# Round 3 review (strict reviewer, before this round's changes)

Method: `./make.sh` (NETLIST OK, 0 lint on every sheet), then every page opened at 100 dpi and the dense parts re-rendered
at 110 to 260 dpi in tiles so that all text was readable. New this round: I ran KiCad's own ERC on the generated sheets
(`kicad-cli sch erc` in the same docker image as `make.sh`, helper `_scratch/erc.sh`) and scripts that list long
wires, plain wire crossings and frame rectangles. Scores are 0-5 per criterion; 5 means "as good as a careful human
drawing". The two USB sheets are one score (port 2 differs from port 1 only in the ADCIN1 strap). I graded harder than in
round 2: the holes and the one thing the ERC found cost more than I charged for them last time.

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.5 | 4.0 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.5 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 3.5 |
| 5 Space | 3.0 | 3.0 | 3.0 | 3.5 |
| 6 Recognisable circuits | 4.0 | 4.0 | 4.0 | 4.0 |
| 7 Annotation | 4.0 | 4.5 | 4.5 | 4.0 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 4.0 |
| Mean | 3.9 | 3.9 | 4.1 | 3.8 |

(Round 2 "after" table was 3.9 / 4.0 / 4.2 / 3.9. The drops are re-grading, not changes to the drawing: Space on Cells and
MCU from 3.5 to 3.0, Clutter on USB from 4.0 to 3.5.)

## Why points were lost

3V3 Rail
* Space: 265 x 135 mm with two frames at the left and the notes top right. Roughly half of the page is margin and the
  title block. No big hole, but nothing balances the left-heavy content either. I could not find a packing that is
  better (see "What I tried and rejected").
* The four pin-number boxes on the bottom of U204 (4, 11, 1, 6) touch (symbol library, not fixable in the drawing).

Cells and Gauge
* Space: a 107 x 62 mm hole above the title block, right of the protector; a 54 x 34 mm hole under the notes; the
  thermistor box is a tall narrow column. The 36 mm gap between PACK+ and PACK- is more than the parts need.
* Recognisable circuits: the two protection FETs Q101/Q102 are yellow rectangles with G/D/S pin names (library symbol
  AGM404AP1), while Q103/Q104 on the same sheet are transistors. A reader takes the boxes for ICs.
* The two wide frames differ by 0.1 mm at their left and right edges, invisible but sloppy.

MCU
* Space: a 74 x 35 mm hole between the antenna match and the title block; the module frame is empty at its lower left.
  The antenna note stands in the notes column at the top right, 100 mm from the circuit it describes.
* The module and antenna frames differ by 1.3 mm at the left edge.

USB Port (the lowest score)
* Clutter / Reviewability, found by the ERC and not by my lint: three wire ends stick out 2.5 to 3.8 mm past the
  capacitor they feed (C452 and C451 in the connector section, C403 in the PD controller section); KiCad reports them as
  "unconnected wire endpoint" on both USB sheets. Anyone who clicks on them in KiCad sees a dangling end.
* Recognisable circuits: the four-switch power stage is drawn with four yellow rectangles (SiZ240DT, two dual FETs as
  four units). The textbook half bridge, inductor, half bridge picture is there, but the switches are boxes.
* Wires vs labels: the EEPROM U402 is tied to the I2C lines by labels (SDA/SCL), and C405 stands 80 mm from its LDO_1V5
  pin. The CC, SBU_FLT, DRV9_OFF, I2C and driver signals between sections are labels, as they should be (long, between
  sections).
* Space: 400 x 375 mm. The connector frame is empty in its upper left (the VBUS rail is as high as the PD controller's
  VBUS pins) and lower right; the PD frame is empty at its lower left; a 159 x 29 mm strip lies under the charger frame
  because the 9 V and 5 V frames stacked beside it are taller than the charger.
* Frame edges: the charger frame starts 0.9 mm right of the frames above and below it, the 5 V frame 0.5 mm right of the
  9 V frame.

## Five changes that would raise the lowest scores most (priority order)

1. Cells and MCU, Space: put the notes that describe one circuit next to that circuit (Cells notes 4 and 5 beside the
   protector, in the hole; MCU antenna note beside the antenna frame, in the hole) instead of one block at the top right;
   close the 36 mm PACK+ to PACK- gap on Cells; give frames in one column exactly one left edge.
2. USB, Clutter and Reviewability: remove the three dangling wire ends the ERC reports, and make the drawing code refuse
   them (a lint rule: every wire end must hold a pin, a power symbol, a label or another wire).
3. Cells and USB, Recognisable circuits: draw the MOSFET boxes (AGM404AP1, SiZ240DT) as transistors. Eight FETs on
   two sheets; this was not on my open list but it is worth more than items 4 and 5.
4. USB PD controller, Wires vs labels: C405 near its pin instead of 80 mm away; the EEPROM wired instead of labelled.
5. 3V3 Rail, Space: a packing with a better fill. (Items 4 and 5 are the open items from round 2; I tried both and
   report below why I did not keep a change.)

# After round 3

Method: `./make.sh` ends with NETLIST OK (285 shared parts, 168 nets, 0 differences); 0 lint on all five sheets; the ERC
no longer reports any `unconnected_wire_endpoint` (what remains is the environment noise `footprint_link_issues` /
`lib_symbol_issues` on the root, and `power_pin_not_driven` on a few supply pins, which is what any sheet gets that has no
PWR_FLAG symbols). Every page was opened again at 100 dpi and the changed regions at 110 to 260 dpi.

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.5 | 4.0 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.5 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 4.0 |
| 5 Space | 3.0 | 3.5 | 3.5 | 3.5 |
| 6 Recognisable circuits | 4.0 | 4.5 | 4.0 | 4.5 |
| 7 Annotation | 4.0 | 4.5 | 4.5 | 4.0 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 4.0 |
| Mean | 3.9 | 4.1 | 4.2 | 3.9 |

Change against the "before" table of this round: Rail 3.9 to 3.9, Cells 3.9 to 4.1, MCU 4.1 to 4.2, USB 3.8 to 3.9.

## What was done about the five items

1. Notes and holes (`lay_cells.py`, `lay_mcu.py`, `patterns.notes_block(first=)`). Cells notes 1 to 3 stay at the top
   right; notes 4 and 5 ("Notes, continued") stand beside the protector in the hole above the title block. On MCU the
   antenna note is last in the block file (the order of the notes is a drawing hint) and stands beside the antenna
   frame; the numbering still follows the reading order. The Cells hole is now a 100 x 40 mm blank above the title block
   instead of 107 x 62, the MCU page lost 5 mm of height (295 x 165). PACK- on Cells moved 8 mm closer to PACK+ and the
   page is 10 mm shorter (305 x 320). `Sec.max_x0` (new) lets a layout stretch a frame to the left, so the frames in one
   column now share one left edge on Cells, MCU and USB (and `min_x1` makes the two wide Cells frames share a right edge).
2. Dangling wire ends (`lay_usb1.py`, `lay_usb2.py`, `sch.lint`): the three rails now end on the capacitor. The lint has a
   new rule, "dangling wire end", checked by temporarily lengthening one wire (it reported the end at once).
3. MOSFET glyph (`sch.fet_glyph`): a library symbol described as an N-MOSFET and drawn as the plain 7.62 mm box with G left,
   D upper right, S lower right gets the transistor drawing in the box's place (gate plate, three-piece channel, body arrow
   tied to the source) and its pin names hidden, because the glyph says them. Pins, pin numbers and connectivity are those
   of the library; the netlist comparison is unchanged. It applies to AGM404AP1 (Q101/Q102 on Cells) and SiZ240DT
   (Q401/Q402, Q501/Q502 on the USB sheets), including the mirrored right-hand half bridge.
4. C405 and the EEPROM: not changed, see below.
5. 3V3 Rail packing: not changed, see below.

Also this round: one more annotation on the USB PD controller ("Unused GPIOs tied to GND" at the GPIO ground bar, which
also takes up some of the empty lower left of that frame).

## What I tried and rejected

* C405 close to its pin. The LDO_1V5 and LDO_3V3 pins are 2.54 mm apart, so any capacitor that hangs below the 1V5 line
  stands on the 3V3 line, and one that hangs above it hits the DRAIN tie and C407. I drew the most promising variant:
  LDO_3V3 only a short stub with its flag and C404, each I2C pull-up with its own supply arrow instead of the
  shared 3V3 bar, C405 at 37 mm. It put C405 half as far from the pin but made the I2C lines 28 mm longer, put three
  repeated "P1_LDO_3V3" labels at three heights above the pull-ups and made the pull-ups stand 50 mm from the IC. Worse as
  a drawing than the shared bar with an 80 mm 1V5 line, so I went back to the previous version. The honest fix is a symbol
  with the two LDO pins apart or a horizontal capacitor symbol.
* EEPROM wired to the I2C lines. The pull-up staircase (shortest line on top) leaves the lines ending at their pull-ups.
  A riser from SCL or SDA down to the EEPROM crosses the IRQ line, and the pins of the EEPROM run SDA above SCL while the
  lines run SCL above SDA, so the pair would also have to cross each other. Two or three plain crossings are worse than two
  labels that name the same nets on both ends. Kept as is.
* 3V3 Rail packing. The width of the page (265 mm) is the bulk-capacitor frame (137 mm) plus the title block (112 mm) plus
  margins. I tried on paper (areas and positions of the frames) the buck and bulk side by side, notes below, the six bulk
  capacitors in two rows of three with notes beside them, and everything in one column. All of them end between 34000 and
  41000 mm2 against 35775 mm2 for the current page and leave a blank of the same size somewhere else. The page stays.
* USB holes. The strip under the charger (159 x 29 mm) comes from the 9 V plus 5 V column being 25 mm taller than the
  charger. Moving the notes into it only moves the blank to the bottom left of the page (the title block is fixed in the
  lower right corner); making the charger frame as tall as the column turns the strip into an empty framed area.
  Moving the connector's U405 left by 24 mm would shorten the VBUS wire but only moves the blank into the PD frame.
* ERC `power_pin_not_driven` (13 warnings over the five sheets): silencing it needs PWR_FLAG symbols on the sheets, which
  is a circuit change and not a drawing one. Left alone.
