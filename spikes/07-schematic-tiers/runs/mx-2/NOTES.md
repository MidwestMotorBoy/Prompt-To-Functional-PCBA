# Notes: Monolith schematic drawing

State at the end: `./make.sh` ends with `NETLIST OK` (285 shared parts, 168 nets, 0 differences). Every generated sheet
reports 0 lint messages, and KiCad's own ERC reports no dangling wire ends and no pin conflicts. Page sizes: 3V3 Rail
265 x 135 mm, Cells and Gauge 305 x 320, MCU 295 x 165, USB Port 1 and 2 400 x 370 each, root A4. Nothing in `out/` is hand
edited; every sheet is rebuilt from `design/`. My own scores (0-5, strict) are in `review-r2.md`, `review-r3.md` and
`review-r4.md`: the means (Rail / Cells / MCU / USB) were 3.9 / 3.9 / 4.1 / 3.6 before round 2, 3.9 / 4.0 / 4.2 / 3.9 after
round 2, 3.9 / 4.1 / 4.2 / 3.9 after round 3, 3.9 / 4.1 / 4.1 / 3.9 when I re-graded harder at the start of round 4, and are
3.9 / 4.1 / 4.2 / 4.1 at the end.

## What I changed

The five blocks no longer go through the template or lane drawer. Each block asks for a layout program with a hint
(`layout("usb_port", ...)` in the block file) and a short program places the parts the way a person would draw that
circuit. `draw.py` keeps the old template/lane code only as a fallback for a block without a hint.

* `design/sch.py` (new drawing kit). A `Scene` places symbols through `symlib`, draws 2-pad parts in either orientation
  (`two(ref, x, y, "v"|"h", first=net)` says which net is on the first pad), wires with their net, power arrows and
  grounds, no-connect marks, flags, titled dashed sections and notes. Reference and value text is placed by a small
  resolver that tries candidate positions and keeps the one that touches no wire, symbol or other text. Junctions are
  added automatically. `fit_page` sizes the page from the drawing and keeps section frames clear of the border and
  the title block.
* A lint pass inside the kit that fails loudly before KiCad is involved: text overlapping text or a symbol, wires
  through text or through a symbol body, a foreign wire touching a pin, overlapping symbol boxes, and connectivity
  re-derived from the drawn geometry and compared with the netlist. All sheets are at 0.
* `design/patterns.py`: the idioms. Parts hanging from a rail, a pull-up standing on its line with its own supply
  arrow, a bank of decoupling caps, tie bars for pins that share a net, a notes block, and `fit()` which draws a
  section on a scratch scene first so that it never protrudes left of its slot.
* Layout programs: `lay_rail.py`, `lay_mcu.py`, `lay_usb.py` (composer) with `lay_usb1..5.py` (connector, PD
  controller, charger controller, four-switch power stage, 9 V and 5 V supplies), `lay_cells.py` (composer) with
  `lay_cells1..3.py` (pack power path, gauge, thermistors, second-level protector), `lay_root.py` (root sheet).
* Drawing rules the programs follow:
  * Power reads left to right: the USB power stage is drawn as a path (PPHV, sense resistor, input caps, half bridge,
    inductor, half bridge, output caps, sense resistor, PACK_P) with the Kelvin filters hanging under the sense
    resistors. The pack path on the Cells sheet runs cells, fuse, FETs, load; low side below it. Supplies up, ground down.
  * Support parts sit on the pin they serve: decoupling caps hang from the supply wire at the pin, pull-ups stand on
    their line, gate and strap resistors are in line with the pin, dividers are vertical chains with taps.
  * Wires for local connections, flags only for nets that leave the section or the sheet. Pin rows 2.54 mm apart are
    fanned out with staircase jogs that do not cross (the line that travels farthest jogs nearest the IC).
  * Each sheet is a few titled, dashed sections with a one-line description under the title and a numbered notes block
    that says what the block does and why a part is there (`note()` in the block files).
* Block files: drawing hints only (`layout()`, `note()`, a `slot` for the root map, section names). I also gave
  readable names to 22 nets that were anonymous `Net-(...)` (for example `VC1..VC4`, `GAUGE_VCC`, `GAUGE_BAT`,
  `FUSE_HTR`, `FUSE_G`, `OV_OUT`, `U102_V1..4`, `RF_MID`, `ESD_MID`) so that flags and labels say something. Connectivity
  is unchanged; the comparison in `make.sh` looks at pin groups, not names. The gauge's signal ground `CELL_1N` is drawn
  with a named ground symbol (`power:GNDS`) so that it cannot be mistaken for GND.
* Root sheet: a map with the sheets in flow order (USB ports, pack and rail, MCU), the sections each sheet holds, a
  one-paragraph overview, and a table of the nets that run between sheets (for example `SDA, SCL, IRQ_N`: gauge, MCU,
  both USB ports) so a flag can be followed without searching.

## Round 2 (review, then fix)

I scored every page against RUBRIC.md as a strict reader (`review-r2.md`) and worked down my own list of five changes.

* USB charger (`lay_usb3.py`): the input window divider hangs from the PPHV wire at the VAC pin, its taps wired into
  ACUV and ACOV; the FB divider stands beside FB/FBG with wired taps. No labels for either.
* USB PD controller (`lay_usb2.py`): the LDO_3V3 rail runs from its pin as a wire with C404 at the pin, the ADCIN1 strap
  wired to it, the three I2C pull-ups hanging from it and a flag with the rail name where it leaves; C405 is on the
  LDO_1V5 line; the EEPROM stands under the pull-ups. Replaced a support row far below the IC and five repeated labels.
* USB connector (`lay_usb1.py`): RPD_G1/RPD_G2 are wired to their CC lines (one plain crossing) instead of labels.
* Page packing: `lay_cells.py` now puts the notes beside the pack path and the thermistor inputs beside the gauge;
  `lay_mcu.py` puts the notes and the connector box in a right-hand column above the title block; the pack path
  (`lay_cells1.py`) is about 18 mm shorter; the 9 V and 5 V frames and the 3V3 notes are tighter.
* Neat edges (`sch.py`, `Sec.min_x1/min_y1`): a layout can stretch a frame so that neighbours share an edge. The USB
  sheets use it for the bottoms of the first row and the right edge of the right-hand column; Cells for the second row.
* Notes (`patterns.notes_block(cols=2)`): the USB notes are set in two columns of about 100 characters instead of one
  line of 190.
* Symbols (`sch.hide_stacked`): pads that share a drawn pin position get `(hide yes)` on all but the first, as KiCad's
  own libraries do, unless the pin is a power pin (a hidden power-input pin would join the net of its name). Fixes the
  overlapping pin numbers of the TPD6S300 symbol. Connectivity still comes from the geometry; the netlist is identical.
* Text (`sch._Resolver.cost`): reference and value text now avoids positions within 0.6 mm of a wire when a clear
  position exists. `LINT_TEXT_WIRE=-0.6` (environment) makes the lint demand that clearance for every text, which is how
  I found the remaining tight spots (U405 value, R412 reference, the VPWR arrow text).

## Round 3 (review, then fix)

I re-graded every page (`review-r3.md`), ran KiCad's ERC for the first time, and worked down a new list of five.

* ERC found what my lint did not: three wire ends past a capacitor on each USB sheet (`lay_usb1.py`: C452 and C451
  rails, `lay_usb2.py`: C403 rail). Fixed, and `sch.lint` has a new rule: every wire end must hold a pin, a power symbol,
  a label or another wire ("dangling wire end"). `_scratch/erc.sh` runs the ERC and prints the counts per sheet.
* MOSFETs (`sch.fet_glyph`, called from `Scene.lib_key` after `hide_stacked`): a library symbol whose description says
  N-MOSFET and whose body is the plain 7.62 mm box (AGM404AP1 and SiZ240DT in `MonolithDev.kicad_sym`, which I cannot
  edit) is embedded with a transistor drawing in place of the box and its pin names hidden. Pins and pin numbers are the
  library's, so connectivity is untouched. The glyph mirrors with the part. A new board with other box-style FETs gets the
  same treatment as long as the description says N-MOSFET; a P-MOSFET would need its own glyph.
* Notes beside the circuit they describe (`patterns.notes_block(first=)`): Cells notes 4 and 5 stand beside the protector
  in the former hole, the MCU antenna note beside the antenna frame (the antenna note is now the last of the MCU notes in
  `design/blocks/mcu.py`, so numbering follows reading order). Cells 330 to 320 mm high (PACK- 8 mm closer to PACK+),
  MCU 170 to 165.
* Frame edges (`Sec.max_x0`, `Sec.min_x1`): sections in one column share one left edge (before, `fit` quantisation left
  0.5 to 1.3 mm steps), the two wide Cells frames share a right edge.
* Annotation: "Unused GPIOs tied to GND" at the PD controller's GPIO ground bar.
* Tried and not kept (details in `review-r3.md`): C405 next to its pin with the pull-ups on their own supply arrows;
  the EEPROM wired to the I2C lines; other packings of the 3V3 Rail page.

## Round 4 (review, then fix)

I graded every page again with zoom tiles (`review-r4.md`) and worked down a list of five. What changed:

* Frame titles follow the frame (`Scene.retitle`, `Sec.hdr`): a layout that stretches a frame to the left (`Sec.max_x0`)
  used to leave the title where it was written, up to 10.7 mm inside the left edge. All 21 frames now have it 3 mm in.
* USB notes beside the circuits (`lay_usb.py`; the order of the notes in `blocks/usb_port.py` is the hint): the CC protector
  note in the empty band of the connector frame, charger and gate-drive notes in the strip under the charger, two general
  notes at the foot. The page is 5 mm shorter.
* Stacked pad numbers (`sch.expand_stacked`): a library pin numbered `[11,12,14,31,39]` is drawn by KiCad as a smudge.
  It is embedded as one visible pad number and hidden passive pins at the same point; a text next to the ground symbol
  lists the pads. Two-pad stacks (`[15,30]`) are left alone.
* Annotation: description lines for the Rail buck frame and the MCU module frame (every other frame had one); net names
  for VBUS, LDO_1V5, AC_SNS_N, BAT_SNS_P and CELL_P (nets that were drawn but not named).
* Text placement found by a new scan (`_scratch/near.py`, different parts' texts closer than 1.2 mm): the gate resistors
  R444/R445 and the Cells sense filter R107/R108 print their texts on the outer sides. `sch.lint` has a new rule, "text on
  ground symbol" (a forced text side can sit on a ground symbol and nothing reported it).
* Tried and not kept (`review-r4.md`): one right edge for the Rail frames (page +25 mm, the frame reaches under the title
  block), the bulk-capacitor note beside its frame (no room), C405 lying horizontally at the LDO_1V5 pin (its text meets
  C407, the PD_DRAIN label or the 3V3 line).

## What I would do next

* C405 (LDO_1V5 cap of the PD controller) stands at the end of an 80 mm line. The LDO_1V5 and LDO_3V3 pins are 2.54 mm
  apart, so a capacitor hanging from the 1V5 line stands on the 3V3 line, and one hanging up hits the DRAIN tie and
  C407. I drew the pull-ups on their own supply arrows to free the space (worse, round 3) and the capacitor lying
  horizontally at the pin (its text collides with C407 and the PD_DRAIN label, round 4). A symbol with the two pins apart
  would fix it; the drawing code cannot. The line at least carries its name now.
* Make the layout programs data driven. The helpers (`hang`, `pullup`, `bank`, `tie`, jogs) carry over to a new board,
  the coordinates in `lay_*.py` do not. A placer that takes "pins on this side, support parts by `serves`" from the
  kernel would remove most of the hand coordinates.
* Put the root's "where does this flag go" table on every sheet next to the flags, and add sheet pins on the root.
* Remaining holes: Cells, 118 x 41 mm above the title block right of the protector, and 68 x 33 mm under the first notes;
  MCU, the module frame's lower left (50 x 42 mm); USB, the PD frame's lower left (43 x 22 mm), the right half of the
  connector band and the foot of the page between the two last notes and the title block; Rail, a 90 x 34 mm blank under
  the notes. Every re-ordering of sections I tried moved a hole instead of removing it. A packer that tries section orders
  and shapes (for example a narrower, taller protector) and keeps the smallest page is the general answer.
* The EEPROM on the USB sheets is tied to the I2C lines by labels: a wire crosses the IRQ line, and its SDA/SCL pin
  order is the reverse of the lines' order, so a wired version needs two or three crossings.
* ERC `power_pin_not_driven` (13 warnings): the rails come from regulator outputs and connectors, and KiCad wants a
  PWR_FLAG on them. That is a circuit change, so I left it.
* Look at the sheets printed at A2 or A3. I judged legibility from 100 dpi renders and 150 to 200 dpi crops.
* Symbol library issues that the drawing code cannot fix: the adjacent pin names `VC1` and `PRES/SHUTDN` sit close
  together on U101, and the four pin numbers on the bottom of U204 stand 2.54 mm apart. They need the symbol generator
  changed. (The stacked pad list of U401 is handled in `sch.expand_stacked`.)

## What blocked me

* Power symbols with a custom value are global in KiCad, so a per-sheet net can not be drawn as a rail arrow; those use
  wires and local labels, and arrows only for global or unique names.
* The 2.54 mm pin pitch next to 7.62 mm tall passives (see the LDO caps above) and the stacked pin numbers in the
  symbols limited how tidy some IC sides could get.
* The session had a hard output limit per message, so the programs are split into small modules.

Development helpers I used are in `_scratch/` (`dev.sh` builds and renders even when the comparison differs, `zoom.sh`
crops a page region in mm, `pins.py` prints a symbol's pins). They are not part of the build.
