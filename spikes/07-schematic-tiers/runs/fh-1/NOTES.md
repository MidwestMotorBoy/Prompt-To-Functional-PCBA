# Notes on the sheet drawing

State: `./make.sh` ends with "NETLIST OK" (285 parts, 168 nets, 0 differences). The lint in
`out/sheets/lint.txt` is empty (no overlapping text, symbols or wires, no shorts). KiCad's ERC on the result
reports only the library-link messages and 13 "power pin not driven" that belong to the circuit; nothing dangling.

| Sheet | Labels before | Labels now | Page before (mm) | Page now (mm) |
|---|---|---|---|---|
| 3V3 Rail | 5 | 1 | 297 x 210 | 180 x 160 |
| Cells and Gauge | 104 | 28 | 500 x 520 | 370 x 260 |
| MCU | 32 | 19 | 460 x 210 | 220 x 175 |
| USB Port (each) | 112 | 64 | 470 x 730 | 425 x 365 |

(Labels = local plus global labels. Ground and supply symbols are not counted.)

## What I changed

All of it is under `design/`. The circuit is untouched: the block files only gained drawing hints and notes.

**`design/draw.py` (rewritten) and `design/sch.py` (new).** `sch.py` is the canvas: figures that can be measured,
moved and joined, the KiCad writer, and the lint. `draw.py` decides what is drawn where. The old generator placed
every part in a cell and tied it with labels; the new one draws the way a person does:

- Every part with three or more pins is drawn once, and what belongs to a pin is wired to that pin.
  Decoupling and filter parts hang from the pin's wire to ground. Pull-ups stand on it. Series parts and
  inductors lie in line. A part between two pins of the same side (bootstrap capacitor, divider, cell-filter
  ladder) stands between their wires. A chain from one pin back to another (the antenna pi network) runs along one
  wire and a wire closes it.
- Where neighbouring pins need more room than the pin pitch, their wires move to lanes. A small solver picks the
  lanes with the least wire and the fewest bends. This is what removed most of the "down wire".
- Pull-ups on neighbouring pins stand side by side and their leads cross the wires in between, so the bus wires
  stay straight (I2C pull-ups on the MCU and the PD controller).
- A power path is drawn left to right from a hint in the block: wire pad, fuse, charge FET, discharge FET, load
  pad. Gate parts sit at the gate, the ESD capacitors arc over the FETs, the fuse-heater FET hangs under the fuse.
  The sense path (pack minus, shunt, Kelvin filter, ground) is drawn the same way.
- The four-switch stage is one path: shunt with Kelvin filter, input capacitors, half bridge with gate resistors,
  inductor, half bridge, output capacitors, shunt.
- Ground is a ground symbol, and ground pins next to each other share one. The gauge's own ground (CELL_1N) has
  its own symbol with its name. Supplies with a top-level name
  (PACK_P, 3V3, P1_LDO_3V3) are arrows pointing up.
- A label is used only where a net leaves the figure. A wire pad on that net is drawn at the end of its wire
  (cell sense wires at the cell filter, NTC wires at TS2/TS3, test points on their rail).
- A small transistor driven from one pin is drawn at the end of that pin's wire (Q103 on BTP_INT, Q409 on the
  LDO enable).
- Text widths are measured from KiCad's font, so reference and value text no longer overlap.
- A part with several units (the half bridges) is drawn unit by unit when no template draws it.
- Sections are packed onto a page sized to the drawing and kept clear of the title block. Section order may change
  where that fills the page better.
- KiCad does not always connect a pin or power symbol that sits in the middle of a wire, so wires are cut at every
  such point when the sheet is written. Junction dots are worked out from the result.

**`design/kernel.py`: four drawing hints, none of which touch the circuit.**

- `draw_as("path", ...)`: a power path through the listed elements, with `dock` to hang a part under a pin.
- `draw_net(net, style="supply" | "ground")`: how a net is shown.
- `draw_hint(ref, at="U405.~{FLT}")`: draw a part at a named pin.
- `note(...)`: short notes under a section title.

**Block files (hints only).**

- `cells_gauge.py`: CELL_1N as a ground of its own, the pack-plus path and the sense path, four notes.
- `usb_port.py`: LDO_3V3, REGN, DRV_SUP and V9 are supplies; R441 at the FLT pin; C457 and C407 left out of the
  5 V buck hint so they are drawn at the pins they serve; notes with the programmed values, taken from the
  `expect(...)` lines.
- `rail_3v3.py`: only C206 is the buck's input capacitor; the six bulk capacitors are a bank in their own section.
- `mcu.py`: one note.

Without hints the generic rules still draw every sheet. I checked this by building with all hints, `serves` and
Kelvin declarations removed (`scratch/nohint.sh`): the netlist still matches and the lint is still empty. Those
sheets are plainer (the four-switch stage is two half bridges with labels, REGN and DRV_SUP are followed like
signals), so a new board gets a usable drawing first and the hints then add the power paths and the supplies.

## What I would do next

1. **Wire two parts that face each other.** Nets between two multi-pin parts are still labels. The clear case is
   the USB connector's CC pins to the TPD6S300 next to it. It needs the second part drawn at the end of the first
   part's wires, with the lane solver keeping those wires together. I started thinking it through and stopped: it
   is the largest remaining item.
2. **Supply arrows for supplies local to a block** (REGN, DRV_SUP, PPHV, PP5V). They are local labels on top of
   the pull-ups today, because a power symbol is global and the block is used twice. It needs unique names per
   block instance.
3. **Straps that cross.** Where two pin-to-pin straps interleave (C_CC1/RPD_G1 and C_CC2/RPD_G2 on U405) each pin
   gets a label. One crossing would wire them.
4. **Lint of pin names and numbers.** The lint knows symbol bodies, text, labels and wires, but not the pin text
   drawn by the symbol. I checked those by eye.
5. **Section order.** The packer trades reading order against page fill with one weight. A hint to pin a section
   first would be cheap.
6. **The root sheet** is still five boxes. It could show the nets between the blocks.

## What blocked me

Nothing blocked the work. Two things cost time and are worth knowing:

- KiCad's rule for pins in the middle of a wire (above). The first build had every bottom ground pin of the 3V3
  buck off the ground net until the wires were cut at pins.
- A multi-line text with a raw newline makes `kicad-cli` refuse the whole sheet with "Failed to load schematic";
  newlines must be written as `\n`.

## Files

- `design/draw.py`, `design/sch.py`, `design/kernel.py`, `design/blocks/*.py`: the change.
- `scratch/`: my working files. `scratch/design_orig/` is the design folder as I found it,
  `scratch/out_baseline/` its output, `scratch/render.sh` renders the sheets even when the netlist check fails,
  `scratch/crop.sh` cuts a region out of a page for a close look, `scratch/nohint.sh` builds without hints into
  `scratch/nohint/`.
