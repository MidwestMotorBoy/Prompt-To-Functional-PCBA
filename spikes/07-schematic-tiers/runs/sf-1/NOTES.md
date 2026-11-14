# Readability pass: notes (round 2)

make.sh ends with NETLIST OK (285 parts, 168 nets, 0 differences). draw.py prints, per sheet, the page size, the fill ratio and a
collision count; the pairs are written to out/sheets/<sheet>.kicad_sch.collisions.txt.


# Current state (final round)

## Checks. Two, and the PDF one is the truth
- `design/pdfcheck.py` (run `python3 design/pdfcheck.py out/render/sheets.pdf` after make.sh) reads word boxes from the rendered PDF
  with pdftotext -bbox, so it measures what KiCad drew. Last run: page 2: 3, page 3: 1, page 4: 1, pages 5 and 6: 10 each (25 total).
  Of these, 8 per USB page are pin-number stacks (11/12/14/31/39 and 13/16/17/18/21): rotated pin numbers on the 2.54 mm pitch bottom
  pins of U405/U401, which pdftotext reports as flat boxes; the crops need checking before calling them real. Real ones: C410 value
  under D410 value (USB pages), F102 pin 2 on FUSE_HTR (page 3), RESET on VCC inside J301 (page 4, library symbol), U204 bottom pin
  names (page 2, library symbol), R113 on SRN (page 3: not visible in the page-3 render at 100 dpi, so possibly a false hit).
- `Sheet.collisions` (estimate, draw.py) still prints per sheet. Its counts are not proof: it tracks where text was meant to go. Last
  counts: 3V3 0, Cells 1 (R113 field), MCU 0, USB 1 each (the EN_5V label over its own stub wire: a label sitting on its stub is
  deliberate but a global-shape label over the wire looks heavy). Do not tune its constants further; the PDF check supersedes it.
Neither check makes make.sh fail; non-zero counts are unfinished work.

## What changed in the last two rounds
- Packer keeps reading order (no random orders). Fill: 3V3 0.45, Cells 0.46, MCU 0.52, USB 0.56 (page 654 x 471 mm).
- MCU: duplicate 3V3 label at VDDS removed (all pins at the same point as a wired pin count as wired).
- Template ICs (U404 buck) now keep single parts on their other pins inline: C439 is back on SS, R432 is on EN (text below when a
  connected pin is just above). Inline stub labels of global nets are drawn in global shape, which keeps the netlist equal.
- Ladders, pin-label stubs, inline vs lanes, pad grid, USB front-end sketch, pack/Kelvin/antenna sketches: as in the earlier notes below.

## Not done (open work, in priority order)
1. Lone parts: U402 EEPROM (needs to sit on the I2CC lanes of U401), Q409/R455 (onto U406 EN beside R454), TP412, TP301 and the
   cell pads at the end of a wire of their net. A general "attach leftover cell at a drawn wire end of its net" has not been written.
2. Lane runs on U101 left and U403 are still long; R418/R419 (FB divider) and R417/R435 (CE divider) are still far from their lanes
   (R417/R435 draw text over their bodies: field justification of rotated parts is not set explicitly in symbol()).
3. Ground stacks on U401 and U204 are not joined in draw_anchor.
4. MCU pull-up order and TP301 unchanged. Fill still below 0.6; sections are bounding boxes.
5. D410/D411/C458 text overlaps and R415 on TH401 (page 5) remain.

## Earlier notes (rounds 1 and 2), kept for the record
## Changes this round
1. Pin labels: every pin label now sits at the end of a 2.54 mm stub (pin_label), no more "31CHG" against the pin number.
2. Inline vs lanes (draw_anchor): a part is drawn inline only when no neighbouring pin on that side is connected (or is a rung end
   of a ladder); otherwise it goes to a lane. Inline parts start beyond the labels of neighbouring pins, and ref/value sit above (or
   below if a labelled pin is above) the part, not after the end label. Lanes use a variable pitch (10.16 for series-only lanes,
   7.62 for bare pins, 15.24 with caps). Series parts in lanes and inline can continue into a second part (BAT -> R105 -> D101).
3. Ladders: a part whose two nets are the nets of two neighbouring lanes is drawn upright between the lanes with junctions
   (U101 cell inputs R101..R104/C101..C104, U102 R119..R122/C112..C115, charger ACP/ACN filter).
4. Pads: single-pad parts (wire pads, test points) are drawn in a grid, net label on a stub at the left of each pad, ref and
   description at its right (pad_grid). Not done: putting a pad at the end of the wire it belongs to.
5. USB front end is a sketch (usb_front in design/sketches.py, both ports): receptacle, VBUS up and across with bulk caps and TVS,
   CC lines straight into the protector, D+/D- strapped, protector supply caps on buses above it, one ground symbol for its
   ground pins. Sketches can now apply to several blocks (applies/refs_of).
6. Page packing: skyline packer plus 150 random section orders per sheet (reading order gets a 4 % bonus), width searched
   200..900 mm, score = area x aspect penalty. Fill ratios (printed by make.sh): 3V3 0.45, Cells 0.58, MCU 0.52, USB 0.61 (was
   0.46 / 0.46 / 0.52 / 0.61 at larger sizes). Sections are bounding boxes of what they contain, so fill below 1.0 is partly
   unavoidable. Note the random order can put sections out of reading order (USB sheet: 5 V buck top right).
7. Fixed: field text of upright parts drawn at angle 180 sat on the body (symbol() default justification); gate resistors of the
   four-switch stage now stay on the charger pins; inline text no longer trails off after the end label.

