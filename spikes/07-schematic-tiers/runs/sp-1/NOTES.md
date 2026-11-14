# Notes

## What I changed (design/draw.py only)
- Per-block layout hook: if design/views/<sheet>.py exists (sheet name lower-cased, spaces to underscores; usb_port_2 falls
  back to usb_port.py), draw_block loads it and calls layout(ctx). ctx exposes the drawing helpers (small, horiz, hang,
  inline, buck, bridge4, draw_anchor, draw_cell, draw_section, flow, measure, ...). Return True to take over the page.
  The view may also set PAGE_W and WC for the default packer. No view files exist yet.
- Page packing: when a view does not set PAGE_W, the packer tries widths 160-700 mm and picks the one closest to a 1.5:1 sheet.
  The MCU page went from 1812x827 px (very wide, mostly empty) to 1418x1221 px.
- make.sh passes (NETLIST OK).

## What did not happen
- I had no Agent tool myself. The coordinator ran the four page agents (one per sheet, own copies) and merged their view files.

## Next
- 3V3 rail: seven input caps in a long row; put them in a bank at U204 VIN and add feedback/output order.
- Cells and gauge, MCU: MCU has the antenna match, debug connectors and TP301 spread far apart; put C313/C314/C315/R321 into
  one pi-filter view between RFIO and ANT_IN, move J301/J302 beside the module.
- USB port: sections pack one per row, so the page is tall and 2/3 empty. Several parts (Q409, R432, TP412, U402, DA401) float alone.
  Add views/usb_port.py that places the sections in two columns.

## Page agents and lead pass
- 3V3 rail, cells and gauge, MCU: each agent wrote a view file; no draw.py change was needed. USB agent asked for placing
  leftover cells beside an IC: added view attribute BESIDE (set of anchor refs) read by draw_section; usb_port.py uses it,
  so the decoupling strips and I2C parts now sit right of their ICs. Pages were opened after the merge; no overlaps found.
- Still floating on USB sheets: D401, U402, Q409, R432, TP412 (need explicit per-part placement beside their pins).
- Cells and gauge: ~15 long parallel lane wires left of the gauge; MCU page has empty right/bottom.

## Scores (0-5 mean over the eight criteria, my rough judgement)
| sheet | before | after |
|---|---|---|
| 3V3 Rail | 2.5 | 3.5 |
| Cells and Gauge | 2 | 3.3 |
| MCU | 2 | 3.2 |
| USB Port | 2 | 2.8 |
