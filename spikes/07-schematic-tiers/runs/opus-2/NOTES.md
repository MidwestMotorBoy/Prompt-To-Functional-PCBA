# Schematic drawing rework: notes

`./make.sh` passes ("NETLIST OK": 285 parts, 168 nets, 0 differences). The built-in drawing lint reports 0 issues on every sheet.

## What changed

### `design/draw.py` (rewritten)

**Circuit-shaped drawing instead of a pin fan-out**

- Each IC's support parts are grown into trees that follow private nets out from the pin. The trees are drawn the way an engineer would draw them:
  - series parts lie in line;
  - decoupling and pull-downs hang straight down to a ground symbol;
  - pull-ups rise to a supply arrow;
  - test points sit on the wire;
  - dividers stack.
- Two-pad parts sitting between adjacent pins become vertical "bridges" between the two rows. Examples: boot caps, and the cell-ladder caps between VCx taps.
- Rows go on lanes beside the IC, with short jogs when a tree is taller than the pin pitch. A staircase indent lets tall rows tuck past their neighbours. The lane spacing allows for text and power-symbol overhang.

**Templates selected by the existing `draw_as` hints**

- `buck`: input caps on VIN, the inductor in line with SW, then the output caps and the FB divider.
- `bridge4` (BQ25756 four-switch stage) is drawn as one left-to-right power path:
  - input shunt with its Kelvin RC filter;
  - input caps;
  - input half bridge;
  - inductor;
  - output half bridge;
  - output caps;
  - battery shunt with its filter.
- `pack_path` (new, Cells and Gauge):
  - the pack+ wire, fuse and back-to-back CHG/DSG FETs with their gate networks;
  - the ESD caps across the pair;
  - the fuse-heater FET;
  - below it, the pack- return with the sense shunt and its Kelvin filter.

**Nets, labels and power symbols**

- Power symbols are used for supplies and grounds. Nets that never leave the sheet use local power symbols.
- Global labels are used only for nets that leave the sheet; local labels otherwise.
- Same-net label pairs that are close are turned into real wires, but only when a clean route exists (no bodies, no text, at most one crossing).

**Layout and sheet output**

- Each section gets a title and optional notes. Sections are skyline-packed toward an A-series page shape, and the packer tries several orders.
- Text-collision fallbacks:
  - a horizontal part's text moves below when the text above would hit a neighbour's text;
  - an in-line part starts after the room reserved for a bridge's text.
- The page size fits the content (minimum 180×120 mm).
- A lint pass (`DRAW_LINT=1`) checks text overlaps, wires through text or bodies, and shorts.

### Drawing hints

- **`design/kernel.py`**: added `note(text)` (section annotation) and `ground_symbol(*nets)` (draw a local reference net such as CELL_1N as a named ground).
- **Block files** (hints only; no circuit change):
  - `cells_gauge.py`: `draw_as("pack_path", ...)`, `kelvin(RS101)` and `ground_symbol(CELL_1N)`, plus one note.
  - `mcu.py`, `rail_3v3.py` and `usb_port.py`: one or two `note()` lines each.

## What I would do next

- **Charger right side**: the BQ25756 gate-drive and bootstrap rows (HIDRV/BTST/SW/LODRV × 2) still fan out with long jogs. A small "gate drive" template would fix it, with the boot diode and cap stacked beside each HG/LG resistor.
- **MCU antenna match**: draw the pi network as a real pi (series part on a line, shunt caps down from each end) instead of the current U-shaped loop.
- **Packing on the USB sheets**: there is still empty space. The four-switch stage is very wide (7 input caps in a row). Splitting the cap bank into two rows, or packing sections in columns, would tighten it.
- **Gauge cell-input ladder**: lane jogs still cross once (CELL_4P feeding both BAT and VC4).
- **Local power marker**: KiCad draws a small marker before local power names, which looks like "@". It is correct KiCad 10 behaviour, but some readers may find it odd. Plain local labels would be the alternative.

## Blockers

None. Everything is generated from code and no `.kicad_sch` files are hand-edited. `make.sh` and `tools/` are untouched.
