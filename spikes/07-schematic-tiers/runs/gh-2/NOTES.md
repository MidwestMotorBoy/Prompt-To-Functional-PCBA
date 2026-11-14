# NOTES

State: `./make.sh` ends with `NETLIST OK` (285 parts, 168 nets, 0 differences) and the layout lint is at 0 for all
five sheets. Renders are in `out/render/page-2..6.png` (2 3V3 Rail, 3 Cells and Gauge, 4 MCU, 5 and 6 USB Port 1 and 2).
Page 1 (root) is unchanged.

## What was changed

General (toolkit, reused by every sheet)
- `design/hand.py` (new): a small hand-drawing toolkit. A sheet layout places parts and draws wires pin to pin, the way a
  person draws; the toolkit does orientation, text placement, junctions, labels, no-connect flags, paper size and a lint pass.
  - placement: `ic`, `two`, `one`
  - wiring: `w`, `lab`, `stub`, `tie`, `drop`, `tapdown`, `gnd`, `nc`
  - patterns: `lane` (series parts straight out of a pin), `hang` (a part hanging from or standing on a rail)
  - notes and frames: `note`, `title`, `group` (dashed titled frame)
  - checks: `finish` and the lint (symbol on symbol, wire through a body, text on text/wire/symbol, overlapping frames)
  - pins nobody wired get an automatic label, ground or NC flag, so a forgotten pin cannot silently float.
- `design/symlib.py`: `respace(lib, name, {pin: y})` redraws a library symbol with other vertical pin positions (the body grows).
  Drawing only: pin names and numbers are untouched. This is what makes ladders possible: with pin rows 7.62 mm apart a
  vertical capacitor or resistor has its two ends exactly on two pin rows (cell filter ladder, SRP/SRN filter, BQ25756 FB
  divider, window divider, bootstrap cap between BST and SW).
- `design/draw.py`: `draw_hand` hooks the layouts in (`design/layouts/__init__.py` maps block name to layout), text
  justification follows rotation and mirror, paper size comes from the drawn content (plus room for the title block).
- Net names in two blocks (`blocks/cells_gauge.py`, `blocks/mcu.py`) were renamed from KiCad auto names (`Net-(U101-VC3)`)
  to readable ones (`VC3`, `FET_MID`, `ANT_MID`, ...). Net names are not compared, only pin groupings.

Per sheet (these are hand layouts and are per-case by nature)
- 3V3 Rail: buck as the datasheet draws it (PACK_P in, 2.2u at the pin, EN strapped to VIN, SW - L - 3V3, 22u out, VOS after
  the inductor, FB to ground), bulk bank as its own titled group, notes.
- Cells and Gauge: three groups. Gauge: BAT diode and R, cell ladder (R in series, caps between the nodes, one to CELL_1N),
  SRP/SRN filter with the shunt RS101 between the two lanes, PACK, NTC lanes, thermistor connector pairs, SMBus resistors,
  BTP_INT interrupt FET. Power path: fuse, back-to-back FETs with drains joined, gate networks, ESD caps in series across both
  FETs, bulk caps, test points. Protector: BQ294700 with its own cell ladder, supply filter, fuse driver FET.
- MCU: supply rail with reset pull-up and decoupling, reset cap, RF pi match in line (RFIO - C313 - node - R321 - ANT_IN), pull-ups
  standing up to 3V3, signal labels, the two Tag-Connect headers in their own frame, notes.
- USB Port 1 and 2 (one layout, parameterised by the reference base): connector, VBUS TVS and caps on one rail, CC lines straight
  into the protector and on to the PD controller, EEPROM and I2C pull-ups; the four-switch stage as one rail left to right
  (sense resistor, 7 input caps, half bridge, inductor with bootstrap parts, mirrored half bridge, output caps, RBAT, PACK_P);
  BQ25756 with its Kelvin filters, window divider, programming resistors, TS network and FB divider; 9 V gate-drive supply;
  5 V buck.

## Baseline vs final (my strict grading, 0 to 5)

Order: flow / grouping / wires vs labels / clutter / space / recognisable / annotation / reviewability.
Baseline numbers are from rendering the original `design/` (kept at `/tmp/gh2_design_orig`, outside the folder) and looking at it.

| sheet | baseline | final |
|---|---|---|
| 3V3 Rail | 2 / 2 / 3 / 4 / 2 / 3 / 2 / 3 | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 |
| Cells and Gauge | 1 / 2 / 1 / 3 / 1 / 1 / 2 / 1 | 4 / 4 / 4 / 4 / 3 / 4 / 3 / 4 |
| MCU | 1 / 2 / 2 / 3 / 1 / 2 / 2 / 2 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 |
| USB Port 1 | 1 / 2 / 1 / 2 / 1 / 1 / 2 / 1 | 4 / 4 / 4 / 3 / 3 / 4 / 3 / 3 |
| USB Port 2 | same as port 1 | same as port 1 |

## Checks done
- `make.sh` gate: NETLIST OK. Run after every batch of changes; it caught real wiring mistakes (lane orientation with a short
  net name, missing labels on SW1/SW2/AC_SNS_N/BAT_SNS_P/C_CC1/C_CC2, a label not joined to the resistor lane on CHG/DSG).
- Lint in `hand.py` at 0 on all five sheets. Every page was inspected in crops at 1.0 to 1.7x, not only in overview.
- Assumptions tested: net names are not compared (renaming auto nets and using labels passes); respaced symbols do not change
  the netlist (they pass); stacked/hidden pins move with their visible pin (verified on U403, U401).

## Still imperfect (stated plainly)
- USB sheets are very large (about 405 x 530 mm). This holds the `space` score down: a lot of blank area right of the front group and the stage
  frame is wide with little in it between the two half bridges. A tighter arrangement (charger left, 9 V and 5 V under it, stage
  across the top) was not tried.
- The SiZ240DT symbol is narrow: pin names `SW` and `G2` run together inside the body ("SWG2"). That is the library symbol; I did not
  redraw the body.
- The two-unit FET shows its reference twice (Q401A, Q401B, same for Q402) as KiCad does; fine but a little busy.
- C_CC1/C_CC2 are shown by labels next to the J401 to U405 lines because the RPD_G pins would have to cross a line to be wired;
  the labels sit close to each other and the RPD_G labels. Readable, not elegant.
- Q409, Q103, Q104: pin numbers on the small FET symbols crowd the body; the ground symbols are close to them.
- Annotation: notes exist on 3V3, MCU and the USB power stage and charger, but not on the cell inputs, the protector or the 9 V and
  5 V groups; the notes are 1.0 mm text, small. Values and net names are everywhere.
- The thermistor value text (TH101, TH104) touches the symbol.
- The layouts are hand coordinates: a changed circuit needs the layout edited (the unplaced-part check and the netlist gate will say so,
  but the repair is manual). Nothing was added to make the generic layout engine better; the older generic engine is unchanged and
  unused for these five sheets.

## Next
- Re-arrange the USB sheet to a more compact grid and re-grade.
- Add notes on the cell ladder (why 100R + 0.1u, the Kelvin 4P/1N wires), the protector and the buck/LDO groups.
- Draw a better SiZ240DT symbol (wider body) with `symlib.respace` plus a width option.
- Give `lane` and `hang` a text-collision retry so fewer text positions are chosen by hand.

## Blockers
None open. Nothing outside the folder was changed, `make.sh`, `tools/` and the frozen netlist are untouched, and no `.kicad_sch` was edited by hand.

Helper files added in the folder root: `dev.sh` (build and render without the netlist gate) and `crop.py` (crop a region of a render by mm).

## Round 2 (review and improve)
Strict re-grade before and after, and what changed, are in `review-r2.md`. Scores before this round (per sheet, total /40): 3V3 Rail 30,
Cells and Gauge 27, MCU 28, USB 27. After: 33, 30, 31, 31. `make.sh` still ends with NETLIST OK and the lint is 0 on all sheets.
New in the toolkit: `symlib.widen` (wider body, side pins move out), note lines at a 2.54 mm pitch (text snaps to a 1.27 grid, a smaller pitch overlapped),
lint messages now carry coordinates. Notes are 1.27 mm and every group has one.
Remaining weaknesses: USB page is still large (about 405 x 550 mm) with blank areas; Cells wires-vs-labels (many CELL_1N labels);
C_CC1/C_CC2 labels on the USB front end; small FET pin numbers; all layouts are hand coordinates.

## Round 3
Scores before round 3 (total /40): 3V3 33, Cells 29, MCU 31, USB 30. After: 33, 31, 31, 31. Details in `review-r3.md`.
USB: RPD_G pins wired straight to the CC lines (TPD6S300 respaced), C_CC labels removed, 9 V and 5 V groups moved left, cap pitch 13.97.
Cells: CELL_1N bus on the right of the gauge, C105/PTCEN and TH104/PTC joined by wire (labels 11 to 7).
MCU: shorter label stubs. make.sh: NETLIST OK, lint 0.
Open: USB page still about 395 x 550 mm with a blank block right of the front group; two NTC return labels; hand coordinates.

## Round 4
Scores before round 4 (total /40): 3V3 32, Cells 31, MCU 31, USB 31. After: 33, 31, 32, 31. Details in `review-r4.md`.
Changes: the paper-height rule in `draw.py` is group-aware (only frames reaching the title-block columns add height); 3V3 bulk bank is a group beside
the buck; MCU note moved inside the module frame; Cells path rail shortened; USB sheets get a "Sheet interface" box (nets that leave the sheet,
power flow) in the former blank top-right block and the lower rows move up. Fixed a duplicate: C407 was drawn twice on each USB sheet.
make.sh ends with NETLIST OK, lint 0 on every sheet, every page opened and cropped.
Remaining: Cells blank bottom right; USB page still tall (about 410 x 500 mm); two NTC return labels; AO3400 pin numbers crowd the symbol; hand coordinates.
