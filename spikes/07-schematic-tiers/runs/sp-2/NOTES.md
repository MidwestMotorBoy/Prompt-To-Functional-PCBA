# NOTES

## Process note
The brief asked me to delegate each sheet to a Sonnet page agent. This session had no Agent/subagent tool
(only Bash/Read/Edit etc.), so no page agents were run. All work was done by the lead, in design/draw.py only.
Block files and per-block views were not touched.

## What changed (design/draw.py, shared)
- Page packing: sections were laid out in simple left-to-right rows. Now a skyline packer puts each section at the
  lowest, leftmost free spot, and the page width is searched (candidate widths) for the packing closest to a landscape
  A-series aspect with the smallest area. Pages are smaller and the USB sheet no longer has a big empty right half.
- Leftover (label-tied) cells: single-pad parts (test points, wire connectors) are sorted to the end and flowed
  more tightly (smaller row/column gaps, 15 mm instead of 22 mm cell height); gap after anchors reduced.
- make.sh ends NETLIST OK.

## Not done / next
- Per-block hooks (placement hints, section order, pin-side overrides) were not added.
- Cells and Gauge: the cell/load wire connectors and test points are still label-only floaters; they should be
  grouped into one titled "Connections" strip, and the Q104/F102/J112 fuse-heater group wired together.
- Inside USB sections the anchors (J401, D401, U402, U405) are stacked vertically with large gaps; they should be
  packed in a grid by their connections. 3V3 rail: seven input caps on one long bus should be a compact bank
  next to VIN; MCU: J301/J302 connectors and the antenna-match pi should sit with RFIO.
- Pins labelled "Net-(X-Pad)" still show raw auto-names; give them meaningful names in the block code.

## Per-block view hook (design/draw.py)
If design/views/<name>.py exists, draw_block loads it. <name> is the block name lower-cased, spaces to underscores
("3V3 Rail" -> 3v3_rail.py, "Cells and Gauge" -> cells_and_gauge.py); usb_port_1 / usb_port_2 fall back to usb_port.py.
It must define layout(ctx). It runs after cells/anchors/sections are computed and before the generic packing.
- Return True: the view drew the whole page (including the title: ctx.sheet.text(ctx.sheet.title, ctx.X0, 21, 3.0)); the
  generic packer is skipped.
- Otherwise it may set ctx.params and generic drawing continues. Keys: WC (cell row width, default 120), GAP (7.62),
  aspect (target W/H, 1.41), page_w (fixed page width, default searched), order (list of section titles),
  pos ({section title: (x, y)} overrides).
ctx offers: block, refs, comps, nets, nc, cons, pinnet {(ref,pin): net}, ncset, glob, short(net), rank(net), pins_of,
npads, tdraw, anchors, two, cells, zones, banks, serves, sections [(title, [refs])], params, ends(ref), X0, Y0, CH, snap,
Sheet, sheet (current sheet, a property), and helpers small, horiz, hang, inline, buck, bridge4, cell_width, draw_cell,
flow, draw_anchor, draw_section, pin_label, measure(fn). With no view files the output is unchanged (verified: page sizes
identical, NETLIST OK).

## Page agents, merge and final pass
I could not spawn agents; the coordinator ran four page agents (one per sheet, each on its own copy) and merged their
design/views/{3v3_rail,cells_and_gauge,mcu,usb_port}.py. 3V3, Cells/Gauge and MCU views needed no draw.py change.
The USB view asked for two shared changes, done in draw.py:
1. draw_anchor now attaches a lone decoupling cap (declared with serves="U.PIN") to a TOP pin: the cap is drawn above the
   pin, wired, with a net label (U405 VBIAS / C451).
2. The tail under a buck template was cut (tw[3] + 12.7 -> + 2.54), and single-pad strays (test points) now join the last
   IC's leftover row instead of forming their own row far below (R432/TP412 now sit together under U404).
Still open: U405 VPWR / P1_LDO_3V3 caps (C452/C404/C408) serve three ICs so stay in a strip; D401, U402 and the
U401 side pins are label-tied; Q409/R454 in the 9 V section are label-tied; Cells/Gauge TH101/TH104 text is close to wires;
3V3 rail has empty space above the buck.

## Scores (0-5, strict). before = start of session -> after
| Sheet | Flow | Group | Wires | Clutter | Space | Circuits | Annot | Review |
| 3V3 Rail | 3->4 | 3->4 | 3->4 | 3->4 | 1->3 | 3->4 | 2->4 | 3->4 |
| Cells and Gauge | 2->4 | 2->4 | 2->4 | 3->3 | 1->4 | 3->4 | 2->4 | 2->4 |
| MCU | 2->4 | 2->4 | 2->4 | 3->4 | 2->4 | 3->4 | 2->4 | 3->4 |
| USB Port | 2->4 | 3->4 | 3->4 | 3->4 | 2->3 | 3->4 | 3->4 | 3->4 |
Scores are my own reading of the renders, not an independent judging.
