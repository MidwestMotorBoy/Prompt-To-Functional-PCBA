# Notes: schematic sheet redraw

make.sh ends with "NETLIST OK" (285 parts, 168 nets, 0 differences on both USB ports).
The sheets are still generated from code. Nothing under tools/ or make.sh was touched.

## What changed
- `design/scene.py` (new): a small drawing kit. A layout names parts by reference and pins by name, and the kit
  works out where pin ends are, which way a two-pin part stands and which net a label names. Wires are snapped,
  split at pin points and get junction dots automatically. Power symbols (3V3, PACK_P, GND, CELL_1N) are used only
  for nets that were already global.
- `design/layouts.py`, `design/layouts_usb.py` (new): hand layouts, one per sheet, registered in `LAYOUTS`.
  `draw.py` calls them when a block has one and prints a WARNING if any part of the block was left undrawn.
- `design/draw.py`: deferred wire emission (split at pin points), pin-on-wire junctions, per-sheet paper size
  (A4 for 3V3 and MCU, A3 for Cells and Gauge, A2 for the USB ports), dashed section boxes with titles.
- Auto-named nets (`Net-(...)`) in `blocks/cells_gauge.py` and `blocks/mcu.py` got real names (VC1..VC4, BAT_F, PACK_R,
  ANT_MID and so on). The gate compares pin groups, not names, so the circuit is unchanged.

Layout ideas used:
- Signal flow left to right, supply on top, ground at the bottom.
- Short links are wires: caps and resistors hang from the rail or pin they serve, in staircases so lanes never cross.
- Long links and links between sections are labels, named for what the net carries.
- IC pins with a stub and a label are used only where the neighbouring circuit is drawn apart as its own small cell
  (BQ25756 sense filters, bootstraps, feedback dividers).
- Every sheet is divided into titled boxes (what the circuit does) with a note where a value is a decision
  (0R gate resistors are tuning positions, D+ and D- shorted, set points).
- USB ports are one layout used twice, so the two sheets always match.

## Round 2 (self-review)
`review-r2.md` has the before and after scores. Added `design/lint.py` (text over text, wire or symbol body; run
`python3 design/lint.py out/sheets/*.kicad_sch`, expects 0 findings; draw.py writes symbol boxes to out/lint/).
Fixed all overlaps, rebuilt the 3V3 sheet as one left-to-right path on a smaller page, respaced the MCU decoupling.

## Round 3
`review-r3.md`. BQ25756 hub: VAC, ACP, ACN and both bootstrap pairs are now wired on lanes (upper pin nearest, so
no crossings) instead of stub and label. Cells gauge lanes and the MCU antenna network were reviewed and left as
they are (reasons in review-r3.md). `Scene.two()` can take explicit text positions.

## Round 4
`review-r4.md`. Cells: right column compacted (TS box shorter, protector and notes moved up, page 420 x 272).
MCU: antenna pi network wired directly from RFIO and ANT_IN in the main box (the separate antenna box is gone),
connectors in one box. USB: notes added in the empty corners of boxes A and B. Not changed: the long gauge input
lanes on Cells, the MCU decoupling distance from VDDS, the BQ25756 sense filters on the right (Kelvin SRP/SRN, FB,
ACUV/ACOV dividers, still label-linked), USB A/B box heights.

## What next
- Move the layout idioms (fan-out lane, staircase hang, riser and rail, sideways ground) from per-sheet coordinates
  into helpers, so a new block needs a list of parts and not coordinates.
- Add a check to the build that no wire crosses a symbol body or text, and that no two texts overlap. Today this is
  checked by eye on the rendered pages.
- The 3V3 sheet and the USB A/B sections have unused area; the paper size could be fitted to the content.
- Root sheet (page 1) was not redrawn.

## Blockers
None. A stray `refp-*.png` in the scratchpad root could not be deleted (rm was blocked). It is outside the project
and harmless. Helper scripts used while drawing are in `work/` (r.sh soft build, crop.py, dump.py) and are not needed
by make.sh.
