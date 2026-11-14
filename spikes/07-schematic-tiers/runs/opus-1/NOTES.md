# NOTES: readable Monolith sheets

`make.sh` passes: it ends with "NETLIST OK" and reports 285 shared parts, 168 nets and 0 differences. The lint shows no text overlaps on any sheet. Its only remaining lines are "pin on the middle of a wire (joined to it)", and each of those is a deliberate T joint.

## What changed

The sheets are now drawn by a layout script for each block, written the way an engineer draws one. The old generic placer is kept only as a fallback.

- **`design/sheetkit.py` (new): a small drawing kit.**
  - A `Kit` places parts (`place`, `two`) and gives each placed pin's exact position and direction. The kit follows KiCad's rotate-then-mirror order.
  - It draws orthogonal wires (`w`, `hv`, `vh`), ground symbols, named grounds (`gref`, for example CELL_1N), rail symbols (`rail`, for 3V3, PACK_P and P1/P2_LDO_3V3), labels, no-connect markers, titles and notes.
  - `finish()` closes every pin the script left open, so a script only states the wires a reader should see.
    - Each open pin gets the right ground, rail, named-ground symbol, label or no-connect marker.
    - Wires are split at every pin, wire end and label, so that T joints really connect.
    - Junction dots are added where three or more items meet.
  - `lint()` reports what a reader would trip on. It checks text overlapping text, text on part bodies, wires running through bodies or text, and pins landing on the middle of a wire. Its output goes to stderr during the build.
  - Field placement modes: `right`, `left`, `above`, `below`, `line`, `linebelow` and `top` (for ICs), or exact coordinates.
- **`design/layouts.py` (new): reusable drawing patterns and one layout per block.**
  - Patterns:
    - `hang`: a part hanging from a rail.
    - `bank`: a row of parts on one wire.
    - `series_h`: a part lying in a line.
    - `vpart`: a part standing between two rows.
    - `pullup`: a pull-up with its rail symbol on top.
    - `chain`: series parts along a row.
    - `fanout`: spreads an IC's pins onto their own rows with ordered jogs, so wires never cross.
    - `kelvin_shunt`: a shunt with its Kelvin RC filter drawn above it.
    - `part_notes`: turns each part's Notes field into a numbered note on the sheet.
  - **3V3 Rail (A4):**
    - The power path runs on one line: PACK_P → C206 → U204 → L201 → C207 → 3V3.
    - EN is tied to VIN, the four bottom pins share one ground, and VOS is shown sensing after the inductor.
    - The bulk capacitor bank sits in its own section, with notes below.
  - **MCU (A4, previously A3 and mostly empty):**
    - The 3V3 rail runs across the top into VDDS, with the decoupling capacitors hanging from it.
    - The reset RC is drawn on its own.
    - The antenna match is drawn as a pi network under the module.
    - Each I2C, sleep or IRQ line has its pull-up standing on it.
    - The debug connectors have their own section, and the notes sit on the right.
  - **Cells and Gauge:**
    - The pack power path runs along the top: PACK+ → F102 → CELL_P → Q101/Q102 back to back → PACK_P. The ESD capacitors bridge the FETs, and the gate networks hang below.
    - The BQ2947 protector, its input RC ladder and Q104 sit directly under the F102 heater pin.
    - On the BQ40Z50 gauge:
      - The left side is fanned out into the VC RC ladder.
      - The Kelvin filter and RS101 stand in the current path.
      - The thermistors connect by wire.
      - CHG and DSG are wired up to the gate resistors.
    - The pack-wire solder pads have their own section.
  - **USB Port 1/2 (one layout for both ports, refs derived from the J ref).** The sheet has four bands:
    - **A: connector and PD controller.** J401 → TVS and VBUS capacitors → TPD6S300 → TPS25751D. The CC capacitors lie flat. The SBU fault line is wired with its pull-up, and unused GPIOs are grounded. The local I2C is fanned out to its pull-ups, and the EEPROM is shown.
    - **B: four-switch power stage.** It reads left to right: PPHV → RAC with its Kelvin filter → input capacitors → Q401 half bridge → L401 → Q402 half bridge → output capacitors → RBAT with its Kelvin filter → PACK_P. Both bootstrap diodes are fed from one DRV_SUP point.
    - **C: BQ25756 controller.**
      - Every programming pin is fanned out to its own part: the ACUV/ACOV divider, the CE pull-up, the FSW/ICHG/ILIM resistors as a staircase, the TS divider with the thermistor, and the FB divider.
      - Next to it are the REGN/9 V diode-OR into DRV_SUP and the 9 V LDO with its enable FET.
    - **D: 5 V buck.** It sits in the space to the right of the controller.

    The sheet is now about 155 by 125 grid units, down from 180 by 150.
- **`design/draw.py`:**
  - `draw_layout()` runs a block's layout script and then `finish()`. It sizes the paper automatically unless the layout sets a size, draws any part the script did not place with the old placer (with a warning, which no current sheet triggers), and prints the lint.
  - `Sheet.symbol` gained raw field placement; `Sheet.text` gained bold text and no longer snaps.
  - Paper can be a named size or a custom size.
  - The old template, lane and auto-placement path is untouched. A block without a layout still uses it.

## What I would do next

- **Turn the hand-written coordinates into rules.** The layouts are explicit per-block scripts. They reuse patterns, but the coordinates are chosen by hand. The patterns are general enough to drive an automatic placer: classify each pin's neighbourhood (pull-up, divider, decoupling capacitor, series element, RC ladder, bridge leg) and emit the same patterns. That would carry over to a new board without a script per block.
- **Strengthen the lint.** It could check text against the paper border, check wires that run collinear and close together, and count labels used where a short wire would do. It could also run as a test that fails on any overlap.
- **USB Port polish:**
  - The top right of band A and the lower left of band C still have some free space.
  - The 9 V LDO's enable FET (Q409) and its pull-up reach lower than strictly needed.
- **Cells and Gauge:** the notes column is long and narrow. A two-column notes block would make the page less wide.
- **Fix the symbols that draw stacked pin numbers on top of each other.** This happens on the TPD6S300 GND pins and the TPS25751 bottom pins. Those symbols should show one pin number. This is a library or `symlib` fix, not a layout fix.

## Blockers

None. Docker and KiCad worked throughout. The quickest way to iterate is to rerun only the Python step, which also prints the lint:

`(cd design && SYMBOL_DIRS=... python3 draw.py ...)`

Then run `make.sh` for the netlist proof and the renders.
