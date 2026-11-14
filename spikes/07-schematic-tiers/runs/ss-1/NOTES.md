# Notes: readability pass on the generated Monolith sheets

## What changed
- `design/hand.py` (new): a small helper for drawing a section the way a person does. Parts are placed on a 2.54 mm
  grid by reference, wires are polylines between pins or points, labels and grounds are put on pins, junctions are
  added automatically where a wire ends on another wire or a pin, and every pad of every placed part is checked to be
  wired, labelled or marked no-connect (warnings are printed as `WARN`).
- `design/layouts.py` (new): hand layouts per block and section title (`LAYOUTS[block][section]`). Used for the small,
  recognisable circuits: wire pads and test points in tidy columns, current sense (shunt with Kelvin taps and filter
  cap), back-to-back protection FETs as a power path with gate networks and the series ESD caps, fuse and heater driver,
  gauge interrupt level shifter, BAT feed diode, the antenna pi network, the Tag-Connect connectors, the USB-C
  connector with VBUS rail, TVS, CC protector and its decoupling, and the EEPROM with the I2C pull-up bank.
  Sections that name a layout are removed from the automatic cell/zone analysis, the rest is still drawn by `draw.py`.
- `design/draw_util.py` (new): `snap` and `rot` shared by `draw.py` and `hand.py`.
- `draw.py`:
  - page packing now tries every page width and keeps the one whose A-series-shaped page is smallest, instead of a
    fixed 594 mm width (balanced sheets, no long single column); the minimum page size is smaller so short sheets
    (3V3 rail) are not mostly empty;
  - cell-to-IC assignment weights nets by how private they are (a net shared by many pins no longer pulls a part to the
    wrong IC; the protector caps now sit with the protector);
  - a resistor chain is only detected when the middle node has exactly two pins (stops two unrelated resistors that
    share a cell tap from being drawn as a divider);
  - pin labels get a short wire stub so the net name no longer sits on the pin number.
- `blocks/cells_gauge.py`, `blocks/mcu.py`, `blocks/usb_port.py`: nets that only had auto names (`Net-(U101-VC1)`) now
  have meaningful names (`VC1`, `PV3`, `FUSE_G`, `ANT_MID` ...; names are not part of the netlist gate); sections were
  re-cut so every hand-drawn group owns its parts (pads, fuse path, BAT feed, EEPROM and pull-ups).

## Round 2
Graded all pages (see review-r2.md). Added hand layouts for the USB 9 V LDO enable group and the 5 V enable
pull-down with its ground test point, moved the TVS ahead of the VBUS caps so nothing overlaps the CC labels, and fixed
pull-up bank labels. USB score 20 -> 24 (of 40) by my own count.

## Round 3
Gauge section is now a hand layout: cell pads, series resistors and caps in a ladder with the turns kept left of the
pin labels, BAT diode and R105 on a lane, R106 and the PBI cap on lanes, outputs and SMBus series resistors on the right.
MCU module is a hand layout: decoupling at VDDS, reset RC at RSTN, I2C and sleep pull-ups on their lines (IRQ_N pull-up
hangs down). Scores in review-r3.md (Gauge 24 -> 29.5, MCU 26 -> 30.5, USB 24 -> 25).

## Not done / next
- USB port sheets: the BQ25756 controller section (long wires, many labels), the 9 V gate-drive supply (Q409, R454,
  R455 float) and the 5 V buck (R432 pull-down and TP412 float) are still the automatic drawing.
  (Round 2 fixed the 9 V enable parts and the 5 V pull-down and test point.) They want hand
  layouts like the ones above (`usb_c(n)` in `layouts.py` is the pattern, written once for both ports).
- The BQ25756 charger is still the automatic lane drawing (needs lanes both above and below the IC).
- Intended general feature: let `section()` take a hand-layout key so a layout can live next to the part definitions.
- No short notes on the sheets beyond section titles and a few hand notes; a `note()` hint in the block files would help.

## Blockers
- None. The hand layout engine needed explicit pin-on-wire junctions (KiCad does not join a pin that only touches the
  middle of a wire); `Hand.finish()` adds them.

## Round 4
- Added SECTION_NOTES (design/layouts.py): a wrapped one/two-line note under each section title, drawn by draw.py (note_lines) for both auto and hand sections, including the 3V3 rail. Sections shift down to make room.
- make.sh ends NETLIST OK; all pages re-checked.
- Still open: BQ25756 charger as a hand layout (lanes need space above and below the IC; C416 shunt cap clears the divider taps only with an up-pointing ground), long wires on the charger programming block, sparse pad column on Cells and Gauge.
