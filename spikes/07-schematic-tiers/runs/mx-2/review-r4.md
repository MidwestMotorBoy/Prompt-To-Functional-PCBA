# Round 4 review (strict reviewer, before this round's changes)

Method: `./make.sh` (NETLIST OK, 285 shared parts, 168 nets, 0 differences; 0 lint on all five sheets), then every
`out/render/page-*.png` opened at 100 dpi and every region of the dense sheets re-rendered at 150 to 450 dpi with
`_scratch/zoom.sh` (poppler through PIL crops): pack path, gauge, protector and thermistors on Cells; module, antenna
and connectors on MCU; connector, PD controller (both ports, the straps differ), charger, 9 V and 5 V frames and both
halves of the power stage on USB; buck and bulk frame on the Rail. I graded as a harsh outside reviewer who checks the
render for things a careful person would not leave: misaligned frame titles, garbled text at zoom, blank corners, long
lines, label-tied parts. The two USB pages are one score (port 2 differs from port 1 only in the ADCIN1 strap).

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.0 | 4.0 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.5 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 3.5 |
| 5 Space | 3.0 | 3.5 | 3.5 | 3.5 |
| 6 Recognisable circuits | 4.0 | 4.5 | 4.0 | 4.5 |
| 7 Annotation | 4.0 | 4.5 | 4.5 | 4.0 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 4.0 |
| Mean | 3.9 | 4.1 | 4.1 | 3.9 |

(End of round 3 was 3.9 / 4.1 / 4.2 / 3.9. Two re-gradings after this round's zoom pass, no drawing change: MCU Grouping
4.5 to 4.0 and USB Clutter 4.0 to 3.5, for the two things found below that no earlier check looked for.)

## Why points are still lost

New findings of this pass (none of them is caught by the lint, the ERC or the netlist check)
* Frame titles are not at the corner of their frame. A title is placed when the section starts; when a layout later
  stretches the frame to the left (`max_x0`, used to give a column one left edge) or the content reaches further left, the
  frame moves and the title stays. Measured on the five sheets (`_scratch/secs.py`): 12 of 21 frames have the title
  further in than the 3 mm the others have, 8 of them by 2.5 mm or more. Worst: the USB "9 V gate-drive supply" frame,
  whose title starts 10.7 mm to the right of the "5 V buck" title directly below it. A reviewer sees two stacked frames
  with differently indented headings.
* The PD controller's GND pad (pins 11, 12, 14, 31, 39, U401 and U501) is one library pin with the stacked number
  `[11,12,14,31,39]`. KiCad draws such a number as a row of five rotated numbers inside brackets, about 1.3 mm apart; at
  100 dpi it is a red smudge under the IC, at 450 dpi it is readable but cramped. It is the ugliest glyph on the two
  largest pages.
* The LDO_1V5 line (U401 pin 4 to C405) is 80 mm long, runs 2.5 mm above the LDO_3V3 line, and carries no name anywhere
  except the pin name inside the IC. A reviewer cannot tell what the line is without following it.

Still open from round 3, structural
* USB, Space: the connector frame is empty over its whole upper band (183 x 26 mm above the VBUS rail), the strip under the
  charger frame is 159 x 29 mm, the PD frame is empty at its lower left (43 x 22 mm). All the notes stand together at the
  bottom of the page, 150 to 250 mm from the circuits they describe.
* USB, Wires vs labels: C405 at the far end of the 1V5 line, EEPROM tied to the I2C lines by labels. Analysed in round 3:
  the pins LDO_1V5 and LDO_3V3 are 2.54 mm apart and the I2C pull-up staircase cannot continue to the EEPROM without
  two or three crossings.
* Rail, Space: both frames at the left, notes top right, a 90 x 34 mm blank between the notes and the title block. The two
  frames end at different right edges (161 and 137 mm).
* Cells and MCU, Space: a blank of 118 x 41 mm right of the protector (Cells), the module frame's lower left (MCU). The
  structure (title block in one corner, three stacked frames) leaves these; I found no packing that is better.

## Five changes that would raise the lowest scores most (priority order)

1. USB (both pages), Space, Grouping, Annotation: put the notes next to the circuit they describe, as was done on Cells
   and MCU in round 3: the CC protector note into the empty band of the connector frame, the charger-input and gate-drive
   notes into the strip under the charger. The overview and the PD-controller note stay in the bottom band, left of the
   title block. Numbering follows the reading order.
2. All sheets, Grouping and Clutter: the title and the one-line description of a frame follow the frame's top-left corner
   (3 mm in), whatever stretched the frame.
3. USB, Clutter: replace the five-number stacked pad on U401/U501 by one visible pad number and hidden coincident pads, as
   KiCad's own libraries do for exposed pads (pins stay, the net list is unchanged).
4. Rail, Space and Grouping: the bulk-capacitor note beside the bulk frame, in the blank under the notes, and one right
   edge for the two frames.
5. USB, Wires vs labels and Annotation: name the long LDO_1V5 line with a net label next to the pin, so that the 80 mm
   line reads as a named net with one load (C405).

# After round 4

Method: `./make.sh` ends with NETLIST OK (285 shared parts, 168 nets, 0 differences); 0 lint on all five sheets (the lint
has one more rule, see below); KiCad ERC unchanged (only the environment noise on the root and the same 13
`power_pin_not_driven`, no new violation type from the expanded pads). Every page was opened again at 100 dpi and every
changed region at 150 to 300 dpi.

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4.0 | 4.0 | 4.0 | 4.0 |
| 2 Grouping | 4.0 | 4.0 | 4.5 | 4.5 |
| 3 Wires vs labels | 4.0 | 4.0 | 4.0 | 3.5 |
| 4 Clutter | 4.0 | 4.0 | 4.5 | 4.0 |
| 5 Space | 3.0 | 3.5 | 3.5 | 4.0 |
| 6 Recognisable circuits | 4.0 | 4.5 | 4.0 | 4.5 |
| 7 Annotation | 4.5 | 4.5 | 4.5 | 4.5 |
| 8 Reviewability | 4.0 | 4.0 | 4.5 | 4.0 |
| Mean | 3.9 | 4.1 | 4.2 | 4.1 |

Change against the "before" table of this round: Rail 3.9 to 3.9 (Annotation up, 3.88 to 3.94 unrounded), Cells 4.1 to 4.1,
MCU 4.1 to 4.2, USB 3.9 to 4.1. These are small steps: the structure of the pages is what it was after round 3.

## What was done about the five items

1. USB notes beside their circuits (`lay_usb.py`, the note order in `blocks/usb_port.py`). The CC-protector note stands in
   the empty band over the VBUS rail of the connector frame; the charger-input and gate-drive notes stand side by side in
   the 159 x 29 mm strip under the charger frame; the power-path overview and the PD-controller note stay at the foot of
   the page. Numbered 1 to 5 in reading order. The page is 5 mm shorter (400 x 370) because the foot block is only two
   notes tall now. The blank that remains: the right half of the connector band, the PD frame's lower left (43 x 22 mm), and
   the foot of the page between the two notes and the title block.
2. Frame titles at the frame corner (`Scene.retitle`, `Sec.hdr`). The title and the description line are remembered when a
   section begins and moved to the left edge the frame finally got. All 21 frames now have the title exactly 3.0 mm in
   (`_scratch/secs.py` lists them).
3. Stacked pad numbers (`sch.expand_stacked`, `symlib.stack_numbers`). A stacked number with more than two pads is embedded
   as one visible pad number plus hidden passive pins at the same point (KiCad draws `[11,12,14,31,39]` as a smudge). Only
   U401 and U501 are affected (GND, pads 11 12 14 31 39); `[15,30]` stays. The pads connect by geometry, the net list is
   unchanged, and the ERC shows no new violation. A text "GND pads 11, 12, 14, 31, 39" next to the ground symbol keeps the
   information that the number no longer carries.
4. Not done as planned. One right edge for the two Rail frames makes the bulk frame reach under the title block, which pushes
   the page from 135 to 160 mm (tried, reverted). The bulk-capacitor note has no room beside its frame: the notes column ends
   4 mm above the title block, and a note under the frame costs 6 mm of page height. Done instead: the buck frame on the
   Rail and the module frame on the MCU sheet had no description line, every other frame has one, so both got one;
   plus net names on the nets that were drawn but not named: VBUS (rail in the connector frame), AC_SNS_N and BAT_SNS_P
   (the rails either side of the half bridges), CELL_P (fuse output on the Cells sheet).
5. LDO_1V5 is named (a label above the first 5 mm of the line). The line is still 80 mm long: I tried the capacitor lying
   horizontally at the pin, 21 mm out, with its far end on a ground symbol. The pins are 2.54 mm apart, so the line has to
   step up 2.54 mm, and then the capacitor's text meets C407 (hanging from the PP5V line right above) or the PD_DRAIN
   label; with the text below it meets the 3V3 line. Reverted.

Found by a new scan (`_scratch/near.py`, texts of different parts within 1.2 mm), not in the list: the two gate resistors of
the high-side half bridge on each USB sheet (R444 / R445) printed their texts facing each other (four lines in a column
between the resistors); both are below their resistor now. The Cells sense filter R107 and R108 printed their texts on the side
of C106's text; they are on the outer sides now. Forcing the text side of R444 above the resistor put "R444" over C420's ground
symbol, which the lint did not report; `sch.lint` has a new rule "text on ground symbol" (checked by forcing the bad position
once: it reports it).
