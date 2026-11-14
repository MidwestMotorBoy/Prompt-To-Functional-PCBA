# Notes on the schematic drawing work

State: `./make.sh` ends with `NETLIST OK` (285 parts, 168 nets, 0 differences) and prints no lint lines.
The circuit files (`design/top.py`, `design/kernel.py`, `design/blocks/*.py`), `make.sh` and `tools/` are unchanged.

## What changed

1. **`design/scene.py` (new): a small drawing toolkit.**
   A sheet is described in units of 2.54 mm relative to a titled, framed section. Every point carries its net
   from the netlist, so the toolkit can check the drawing while it is being made:
   - a wire between two different nets is refused;
   - a pin the view did not touch is finished automatically (ground symbol, rail arrow, no-connect, or a label on a short stub);
   - junction dots are placed by rule (three or more directions meet), then collinear wires are merged;
   - before KiCad runs, the drawing's connectivity is rebuilt and compared with the netlist (`_netcheck`),
     so a drawing mistake fails at once with the part and net named;
   - a lint pass reports text on text, text on a symbol, a wire through a symbol, anything off the page or in the title block.
   Helpers for the shapes that repeat: `bank` (capacitors hanging from a rail), `two` (part in line), `shunt` (part to ground),
   `kelvin` (sense resistor with its RC filter below it), `tie`, `pwr`, `gnd`, `label`, `note`, `section`.
2. **`design/views/*.py` (new): one layout per block**, written with the toolkit. `usb_port.py` serves both ports.
   Each view places the main power path left to right on a rail, hangs support parts at the pin they serve,
   uses wires inside a section and labels only between sections, and ends with a numbered NOTES block.
3. **`design/draw.py`**: calls the view for a block when one exists and falls back to the old automatic drawer
   when none does (so a new block still draws). Added rail arrows (`power:VCC` with the net as its value), a second
   ground symbol for the gauge's own ground (CELL_1N), dashed frames, bold titles, multi-line notes, text
   justification, a page size per sheet, and stable `#PWR` numbering (crc32, not `hash()`).

Per sheet:
- **3V3 Rail**: PACK_P arrow, input capacitor, buck, inductor, output capacitor, 3V3 arrow on one line; the six bulk capacitors as one bank; page shrunk to fit.
- **Cells and Gauge**: pack power path across the top (fuse, charge FET, discharge FET mirrored, igniter under the fuse);
  cell-tap ladder into the gauge; second-level protector; low-side current sense with its Kelvin filter; NTC wire pads.
- **MCU**: module with its decoupling rail, antenna pi match drawn as a pi, pull-ups on their pins, debug pads wired by the reset net.
- **USB Port (x2)**: connector, CC protection and PD controller on a VBUS rail; the four-switch bridge drawn as an H with both sense
  resistors and their filters; charger controller with its programming dividers and the value each one sets; 5 V buck; 9.6 V LDO with the diode-OR.

## What I would do next

- Derive the views from the `draw_as(...)` hints already in the block files (buck, bridge4), so a new buck or bridge
  draws itself without a hand-written view. The toolkit helpers are the building blocks for that.
- Measure text with KiCad's real font metrics. Text width is estimated (1.15 mm per character), which is why some pitches are set by hand.
- Let the toolkit choose the pitch of a bank and the size of a section frame from their contents; today both are numbers in the view.
- Draw small ground straps (ADCIN, WP, A0-A2, RT) downward. They are now sideways ground symbols at the pin: correct, but not the convention.
- Run ERC in `make.sh` as a second gate, and add the lint count to its last line.

## Limits and things to know

- Nothing blocked the work.
- Views are per-block layouts with fixed coordinates. They are generated from code and checked against the netlist,
  but a part added to a block needs a line in its view (the build fails and names the part if it is missing).
- Sheets use custom page sizes (3V3 236x152, MCU 297x168, Cells 424x219, USB 430x297 mm) so each page is filled without crowding.
  The USB sheet is slightly wider than A3.
- Net names are not compared by `tools/compare.py`, only connectivity. Three unnamed nets on the Cells sheet are shown with
  display names (OVP_OUT, FUSE_G, FUSE_HTR), and each port's `Px_LDO_3V3` is shown as LDO_3V3 inside its own sheet.
- C409, C449 and C407 are drawn on their rails (PPHV, PP5V), not beside the pin they decouple; the NOTES do not say which pin they serve.
- The wording of the NOTES blocks comes from the comments in the block files. Two statements are mine and worth a check by the
  owner: "REGN (5 V)" on the USB sheet, and "R304/R305 are the only pull-ups of the system I2C bus" on the MCU sheet.
- `tools_view.py` and `scratch/` are my review helpers (crop a rendered page); they are not part of the build.
