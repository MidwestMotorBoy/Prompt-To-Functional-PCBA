# NOTES: readable Monolith sheets (mx-1)

State at hand-over (after round 4): `./make.sh` ends with `NETLIST OK` (285 parts, 168 nets, 0 differences). The generator's own
clutter lint reports 0 findings on all five sheets, the tight lint 3 benign findings on the gauge and on each USB page (a thermistor next
to its ground symbol, labels that rest on their own junction), the independent PDF lint (`scratch/lint_pdf.py`) no text on text and only the
known false positives (pin numbers next to NC crosses or stacked numbers), and runs with different `PYTHONHASHSEED` values (1, 777, 31337)
give byte-identical `.kicad_sch` files.
Sheet sizes: 3V3 Rail 165x138 mm, Cells and Gauge 411x242, MCU 311x137, USB Port 1 579x247, USB Port 2 579x247.
`review-r2.md`, `review-r3.md` and `review-r4.md` have the strict reviews (scores per criterion, the five changes of the round) and the result of each round.

## What I changed

The drawing code is now a small set of modules under `design/` (the circuit files are unchanged except for drawing hints and
notes). Everything is still generated; no `.kicad_sch` is edited by hand.

* `sch.py` writer and checker. Every item is recorded with an exact bounding box, all positions snap to the 1.27 mm grid, junctions
  are added automatically, UUIDs are derived from names (deterministic). `lint()` finds symbol overlaps, text on symbols, wires
  through text or symbols, text on text, wires touching pins of another net and crossing wires of different nets. It is printed for
  every sheet ("0 lint findings").
* `ctx.py` decides which small part belongs to which IC (templates and hints, `serves`, neighbours on non-rail nets, chains,
  section) so support parts are drawn at the pin they serve.
* `parts.py` places small parts with their texts beside them: texts follow the real body width, a lopsided body (diode, FET) is
  mirrored so its light side faces the texts, banks of three or more shunts get vertical texts, pads/test points sit at a ground
  or label, ground and supply symbols show a name only when it is not plain GND.
* `lanes.py` is the lane engine (a wire runs out of each IC pin; along it: shunts to ground or supply, rung capacitors between two
  neighbouring pins (cell filter ladders, dividers), series parts, then the end). New in this round:
  * **Pinned rows.** A pin that is only a stub to a label, a ground or a supply symbol stays on its pin instead of being pushed
    away by the lanes around it; the wires that pass it are moved out by whole columns so they clear its label
    (`pinned_rows`). This removed the 30 to 50 mm "down wires" to labels and ground symbols (REGN, DRV_SUP, PGND, HIDRV/LODRV,
    SCL/SDA/IRQ_N, SWDIO/SWCLK/GND, PTCEN/PTC) and shrank several sections.
  * **Long loops become two labels.** A lane wired back to the neighbouring pin (pi match RFIO/ANT_IN, the PPHV input filter) is only
    kept as a wire loop while it is short (`JOIN_MAX`); a long loop is drawn as a label at each end.
  * Lane joins (a regulator output and the top of its feedback divider meet in one wire), staircase of shunts beside short lanes,
    weighted least-squares row positions (`pava`), fan-out columns with nested corners (no crossings), ground stubs that are long
    enough for a ground name.
* `layout.py` clusters, sections (dashed frame, bold title, wrapped note), and page packing: every cut of a section's items into
  rows is tried, sections are packed by skyline, neighbour-swap orders are tried, the page is sized to the content and clears the
  title block (a page is now only as tall as the lowest section over the title block needs, not a whole title block taller).
* `templates.py` textbook drawings: `bridge4` (four-switch buck-boost stage, FET pairs, inductor in the middle, gate resistors, input
  and battery capacitor banks) and `fetpair` (back-to-back protection FETs with ESD capacitors and bypass).
* `kernel.py` drawing hints: `draw_ground`, `draw_supply`, `draw_alias`, `draw_near`, `note`, `draw_wide`, `draw_as`. The block
  files use them (see below).
* `blocks/*.py`: section notes on every functional section, `draw_ground(CELL_1N, GNDREF)`, aliases for two long net names,
  `draw_near("F102", "Q104")`, `draw_as("fetpair" ...)`, `draw_as("bridge4" ...)`, `draw_supply` for REGN/DRV_SUP and the PD
  controller's LDO.
* `draw.py` wraps it all; the root sheet now lists each page with the titles of its sections.

### Round 2 (review, then the five changes)

* **Early join of a regulator output and its feedback.** A lane that ends in a join (a pair of lanes on one net such as the output and the
  feedback divider, or a loop back to the pin beside it such as VOS) and that has capacitors on its end net is joined right behind its last
  series part (`pair_joins`, `place_joins` in `lanes.py`); the output capacitors and the end symbol stand beyond the join wire. U404's
  feedback resistor R433 now joins the output right behind L402 (26 mm of wire from the resistor to the output node, was 69 mm); the TPS62177 VOS
  return joins behind the inductor too (14 mm run instead of 19) and no longer runs through the value text of C207.
* **Tight clearance lint** (`LINT_TIGHT=1`, `scratch/tight.sh`): the same checks with negative margins and power symbols included. What it
  found was fixed in the engine: the name of a supply or ground symbol at the end of a lane clears the text of the last series part
  (`end_tail` in `parts.py`, also used by the four-switch template, R113/R427 with PACK_P); a shunt that stands beyond another lane clears it
  by 3.81 mm (`STAIR_CLEAR`); the shunt reach now includes the text zone of the next lane; an IC's reference and value take the first of
  seven places that is clear of wires, labels and symbols (`text_clashes`, `draw_anchor`; U402's value was crowding a label). What is left
  in the tight list is benign: label boxes that touch at pin pitch (SCL/SDA/IRQ_N), a label that rests on its own junction (SW1/SW2,
  FET_MID) and the arrow marks of the thermistor symbol next to its ground symbol.
* **Pads.** A wire pad on a lane that has other parts shows reference and value on one line (no more pad text sitting on the next
  lane's label); stacked pins that are all shown and have one name become one KiCad stacked pin `[8,13,18,21]` (`symlib._stack`), so U405's
  GND and N.C. numbers are readable blocks and not overprinted digits.
* **Staircases.** Three or more neighbouring rows that each carry one shunt (R412..R414 of the charger, the pull-ups on the PD controller's
  I2C pins, TS1..TS4 of the gauge) get vertical texts (`mark_stairs`), so the steps are 10 mm wide instead of 20 to 25 mm; the gauge
  section is 15 mm narrower and the longest TS wire is 20 mm shorter (71 mm to 51 mm). Vertical text on a symbol turned 90 or 270 degrees now has the right angle.
* **Page packing.** Section orders with up to three inversions of the block file's order are tried (1.5 % of page area per inversion),
  instead of single neighbour swaps; the USB page area is 2 % smaller (4 % with the diode OR below).
* **Row fit.** Lanes that are only the decoupling of their pin count twice as much as other lanes when rows are fitted to their pins
  (`fit_weight`): C105 of the gauge stands 6 mm closer to PBI, wire length of all sheets is 1 to 2 % lower.
* **Diode OR (twin).** D410 and D411 (REGN and V9_DRV into DRV_SUP) were two diodes tied by two DRV_SUP labels, D410 drawn in a leftover
  list under the 9 V section. A diode whose cathode net also has a second diode (anode on a net that ends in a label) now carries it as a
  `twin` (`Att.twin`, `find_twin`, `draw_twin` in `lanes.py`): the upright diode of the lane ends in a node, the twin lies beside that node
  (cathodes joined), its anode net ends in a label (REGN), the end net (DRV_SUP) leaves the node on the other side, and the twin's reference
  and value stand on one line above it (`hpart(text="line")`; text anchors snap to the 1.27 grid, so the gap between the two texts is
  rounded up). The leftover list is gone, the 9 V section is 7 mm lower and the USB pages are 332 mm high (were 339). Nothing else in the design
  matches the rule (two diodes with one cathode net), so no other sheet changed.
* Gauge note says what CELL_1N (hollow ground) is.

Measured effect of the round on the wires (`scratch/wirelen.py`): total length fell on the gauge (1892 to 1852 mm) and the USB sheets (3043 to 3010),
rose slightly on MCU (427 to 432); segments over 50 mm: gauge 4 to 3, USB 4 to 7, MCU 0 to 1 (the charger section got 2 to 5 mm wider and several
48 mm wires crossed the line; the longest wire, 73.7 mm, is the charger's PPHV input and did not change).

Things I tried and dropped: one-line texts for series parts (the shunts, not the texts, set the lane pitch: 1 mm per lane at best);
a weight of 8 for decoupling lanes (longer wires overall); full permutation search of the section order (8 % smaller page but the
connector section moves behind the charger; reading order matters more).

### Round 3 (review, then the structural change)

`review-r3.md` has the scores before and after. The one structural change of the round is that an IC side may be drawn with its pins where its
lanes are.

* **Stretched symbols.** The old picture of the gauge (U101: 16 left pins at 2.54 mm pitch, lanes that need 6 to 10 mm each) was a bundle of
  14 parallel wires, every lane reaching its pin through a jog of up to 56 mm. A person draws such a part with room between the pins. Now an IC
  side whose lanes stand `STRETCH_MIN` (1 mm, `lanes.py`) or more from their pins gets its pins moved to the lanes: same order, same names and
  numbers, the body rectangle grows with them, every lane is a straight wire from its pin and the parts stand at the pin they serve.
  * `plan_stretch` / `_move_pins` (`layout.py`): the IC is drawn into a scratch sheet with its normal pins, `vertical()` logs the rows (`_vlog`,
    `Row.ys` = where the lane stands), the pins are moved to the row positions, and that is repeated (4 times at most) until the lanes stand on
    their pins. A row of several pins keeps its lane at their middle, the pins keep the 2.54 pitch below the first one, and a pin that prints
    several numbers (KiCad stacked pin `[15,30]`, `Dp.nvis`) leaves one text line of room per extra number above it (U401's DRAIN no longer prints
    over the PP5V pin). `LaneMixin.gaps` is the least distance between the first pins of neighbouring rows (what the lanes need, and the pins of
    the upper row).
  * The result is a plan `((((x, y_old), new_y), ...), (top, bottom))`, a hashable value in `Block.plans[ref]`, handed to `symlib.flat/pins`,
    `sch.geo`, `Sheet.lib/symbol` and `PartMixin._geo/put`. The sheet's `lib_symbols` entry for the lib_id is written with the moved pins and
    the longer rectangle (`symlib._restretch`); the library files are not touched and the pins keep their numbers, so the netlist proof is
    unchanged. Only plain symbols qualify (`symlib.plain_body`: one unit, one rectangle, nothing else drawn); connectors with a pictogram
    (the USB-C receptacle J401/J501) keep their pins. `NO_STRETCH=1` switches it off, `STRETCH_MIN=8` gives the first version (only the gauge, the charger,
    U301's left side).
  * Effect (sum of lane-to-pin distances before, 0 after on every stretched side): U101 left 464 mm (up to 56 mm for one lane), U403 357 mm,
    U301 left 80 mm, U401 right 84 mm. Wire length (`scratch/wirelen.py`): 3V3 201 to 156 mm, Cells and Gauge 1852 to 879, MCU 432 to 338, USB
    3010 to 1722 mm; segments over 50 mm: Cells 3 to 2, USB 7 to 3, MCU 1, 3V3 1. What is left is rails and one lane: the PACK_P bank rail of the 3V3 sheet
    (69 mm), the PPHV rail along the input capacitors of the power stage (74 mm) and the VBUS rail of the connector section (55 mm), the
    CELL_P source rail of the protection FETs (51 mm), the TS1 line of the gauge (52 mm), the RFIO loop of the pi match (53 mm) and the
    I2Cc_IRQ lane of the PD controller to its pull-up (57 mm).
  * The bucks now are the textbook picture on their own: SW straight into the inductor, the feedback returns to the node behind it, output
    capacitors beyond (U204 on the 3V3 sheet, U404/U504 on the USB pages).
* **Page packing.** (1) The first section of a block (where the signal comes in: the connector, the gauge) stays top left: only orders that
  start with it are tried, and the "tall first" order competes with the cost of three swaps (it had a 25 % penalty, which hid good layouts).
  (2) Strict columns (`pack_cols`, `cuts`): every cut of an order into columns is tried; the frames of a column share left and right edge;
  a column layout gets a 3 % bonus (`COLUMN_BONUS`) and is sized with its own (equalised) widths, because a column that reaches over the title
  block corner makes the page taller. USB pages are now `[USB-C, PD controller | power stage, 9 V, 5 V | charger]` with aligned frames and
  balanced column heights (579x247). `DEBUG_LAYOUT=1` prints the best skyline and the best column score per sheet.
* **Left as it was:** the gauge page is still the skyline layout (columns would make the middle column reach over the title block and the
  page 32 mm taller); F102 stands beside Q104 and is tied to it by two FUSE_HTR labels (50 mm apart); a wire would be clearer (see below).

Things I tried and dropped this round: `STRETCH_MIN` 15 (`snap23`) and 8 (`snap24`): only the big sides get straight and the 1 to 4 mm kinks
stay (U102's V1 to V4, U301's SCL/SDA/IRQ_N lanes, U405's CC lines, U401's I2C pull-ups); 1 mm removes all of them and costs nothing visible.
A creep in the planner (U401's pins drifted down 1.27 mm per iteration) was a rows-of-two-pins bug: the pins were put below the lane instead of
around it.

### Round 4 (short)

* **Linked ICs.** Two ICs named by `draw_near` whose only common net (not a supply or ground) runs from a bottom pin of the first to a top pin of the
  second are drawn as one item (`Block.link_item`): the first above the second, the stubs of the two pins meet in one wire (`LINK_LEN` 0 mm
  between the stub ends), no label at either end (`link_nets` makes `end_v` record the stub end in `stubs` instead of drawing a label). F102 (fuse)
  now sits above Q104 (its heater FET) with a 12 mm wire; before, the net FUSE_HTR was two labels 50 mm apart. Only the gauge sheet has such a
  pair. The gauge page is 411x242 now (the packer re-ordered the sections for the new item: protection FETs, protector with fuse, wire pads).
* `scratch/snap26` is the design after this round.

## Tools I left (inside this folder, not needed by make.sh)

* `scratch/quick.sh` redraws and renders without the netlist proof (about 10 s); `scratch/crop.py PAGE X0 Y0 X1 Y1 [DPI]` crops the PDF in
  mm (page coordinates, so the page must be that big) to `scratch/crop.png`; `scratch/tiles.py PAGE COLS ROWS [DPI] [OVERLAP_MM]` cuts a page
  into `scratch/tile_<row>_<col>.png`; `scratch/lint_pdf.py out/render/sheets.pdf 2 3 4 5 6` is an independent text/wire overlap check on the
  PDF (it still reports pin numbers next to wires, stacked-pin numbers and the labels FET_MID/CHG_INH as hits; those are false positives).
* `scratch/tight.sh` lists the tight-clearance findings (`LINT_TIGHT=1`, `LINT_MAX=n` for how many per sheet); `scratch/wirelen.py DIR` prints
  wire count and length per sheet and how many segments are longer than 30 and 50 mm (a quick measure for "too much down wire");
  `scratch/perm_eval.py` shows how much a full permutation search of the section order would gain.
* `DEBUG_ROWS=U101 DEBUG_SIDE=L` prints the row profiles of one IC side; `DEBUG_MOVED=1` lists rows moved off their pin and rows pinned.
* `scratch/ref_round1/sheets/` holds the five sheets as they were at the end of round 1 (regenerated from snap15), for before/after numbers: `python3 scratch/wirelen.py scratch/ref_round1/sheets`.
* `scratch/own.py BLOCK REF...` prints which IC owns a small part and why (the net roles) when a part lands in the wrong place.
* `scratch/disp.py` prints, for every IC side, how far each lane stands from its pin (also for the planner's dry runs; the last line per side is the
  real one); `DEBUG_ROWS=U401 DEBUG_SIDE=R python3 scratch/disp.py` adds the row profiles. `scratch/symgfx.py` shows what a library symbol draws
  (rectangles, other graphics, pin ranges: which symbols are plain enough to stretch). `scratch/cands.py "USB Port 1" [N]` lists the best
  page-packing candidates of a block. `scratch/refpdf/` has the pages of the hand-drawn reference PDF as PNG.
* `scratch/snap1 ... snap25` are copies of `design/` at milestones (snap15 = end of round 1, snap21 = round 2 before the diode OR, snap22 = final
  state of round 2, snap23/snap24 = stretched symbols with a 15 / 8 mm threshold, snap25 = final state of round 3).

## What I would do next

1. (Done in round 4: F102 is tied to Q104 with a wire, see `link_item`.) A second use of the same rule would be any pair of anchors that
   share one net between a bottom and a top pin.
2. The I2C pull-up stair of the PD controller has a 57 mm lane (each pull-up stands in its own column, 22 mm apart, because of the net labels and
   rotated texts): a compact stair with the labels on the far side of the column would shorten that.
3. Section frames are wider than their content where a long note sets the width (PD controller, charger): offer the packer two or three widths
   per section (the note wraps narrower) and let it choose; the USB page would lose about 40 mm of width.
4. A rubric lint in make.sh (max wire length to a label or ground symbol, count of labels per pin) so regressions show up in the gate;
   `make.sh` is not mine to edit, so the checks live in `draw.py` and `sch.py` only.
5. Read the `wide` hint (`draw_wide`) and the empty `order` entry of the drawing constraints in the layout, so a block author can
   keep a part out of a bank or fix the order of sections; the kernel records them, the layout does not use them yet.
6. Library symbols: the protection FETs and the half bridges are rectangles with pin names, not FET symbols; a symbol swap would change the
   library and is outside what the drawing code may do.

## Blockers

None. Notes for whoever continues: `make.sh` deletes `out/` each time; the netlist proof needs the docker KiCad image (it worked with
`sudo docker`). KiCad draws stacked pins (several pin numbers at one spot) as one bracketed number list, one line per number, upward from the
pin; the drawing code only leaves room for it (`Dp.nvis`) on stretched sides. A no-connect cross sits on the end of its pin and touches the pin
number beside it (U301 DIO20/DIO12, U405 SBU1/SBU2, U101 LEDCNTLx): that is KiCad's rendering, and the PDF lint reports these as hits.
