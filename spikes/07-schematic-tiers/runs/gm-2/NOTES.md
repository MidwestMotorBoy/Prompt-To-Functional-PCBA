# NOTES: gm-2 (hand-drawn look for the generated Monolith sheets)

## What changed (all under design/, nothing in make.sh, tools/ or outside)
General, reusable:
- `design/lay.py` (new): a small canvas (`Cv`) on top of `Sheet`. Places a symbol by pin, mirror applied after rotation (as KiCad does),
  wires orthogonally, splits wires at pins, adds junctions, and runs a lint (text over text, text on wire, wire through a body, parts not drawn).
  Helpers: `vp` / `hp` (vertical / in-line two-pad parts), `chain`, `lanes` (fan pins out to lanes without crossings), `bank` (parallel caps on a rail),
  `pwr`, `end`, `gnd_side` (sideways ground, no height), `one` (test points and pads), `frame` (dashed titled block), `note`.
  Net aliases for the auto names (`Net-(Q104-G)` and so on) so labels read as names.
- `design/draw.py`: dispatches to a hand layout when one is registered for the sheet (the old generic drawer stays as the fallback),
  per-sheet paper size, centred/right text on symbols, deterministic `#PWR` refs.
- `design/layouts.py`, `design/layout_usb.py` (new): one composed picture each for 3V3 Rail, Cells and Gauge, MCU and (one function, base 400 / 500) USB Port 1 and 2.
Per-case (hand placement): every sheet is a set of titled, dashed blocks; inside each block the signal runs left to right, supplies are arrows up,
grounds down, support parts sit on the pin they serve (boot cap between BTST and SW, divider tapping FB, pull-ups to a rail, decoupling hung on the rail).
Where a net could not be drawn as a short wire without crossing, it is a local label on both ends (gate nets, ACUV/ACOV, I2C on the charger).
Supply names on the USB sheets are per port (`P1_PPHV`, `P2_PPHV`, ...) because a power symbol is global in KiCad.

## Check
`./make.sh` ends with `NETLIST OK` (285 parts, 168 nets, 0 differences).
Lint left: one (`J113` text touches the PACK_P rail on Cells and Gauge).

## Scores (0-5 per rubric item, averaged; honest, my own reading of the renders)
| sheet | baseline | final |
|---|---|---|
| 3V3 Rail | 2.0 | 4.0 |
| Cells and Gauge | 1.5 | 3.0 |
| MCU | 2.0 | 3.5 |
| USB ports (both) | 1.5 | 3.5 |
Weakest items now: Cells and Gauge clutter and space (dense left block, many long fan-out lanes, empty lower right); MCU space (empty left half of the module block);
USB wires-vs-labels (gate, ACUV/ACOV, I2C nets use labels); Q101/Q102/Q401/Q402 are box symbols, not textbook FET glyphs (symbol library, not touched).

## Next
- Shorten the Cells and Gauge lanes (move the cell filter ladder next to the lanes), tighten the left block, shrink the empty lower right.
- Draw the BQ25756 gate nets as wires by putting the controller and the bridge on one band (needs a wider paper).
- Pull the MCU module block left to remove the empty left half; same for the second-level protector block.
- Make `lanes` choose spacing from the parts that hang on the lane, so the lane heights are not hand-set.
## Blocked / learned
- No blockers. KiCad connects a wire to a pin only at a wire end, so wires must be split where they pass a pin (done in `finish`).
- Power symbols are global: two USB sheets must not share a supply symbol value.

## Round 2
Reviewed all pages (scores in review-r2.md). Changed on Cells and Gauge: CELL_1N grounds are symbols (hidden value plus a note) instead of boxed global labels,
sideways grounds where a lane runs below, gate labels on stubs, J113/TP106 and Kelvin note moved. `gnd_side` now takes a net. Lint: one (J113 text on the rail).
Not done: the space and lane-length work on Cells and Gauge, MCU and 3V3 empty areas, USB label-tied nets.

## Round 3
3V3 Rail narrowed (paper 210 wide). Other open items listed in review-r3.md.

## Round 4
Cells and Gauge protector block centred under the pack-path frame. Open items in review-r4.md.
