# Notes: readable generated Monolith sheets

State: `./make.sh` ends with "NETLIST OK" (285 parts, 168 nets, 0 differences). Renders are in `out/render/`.

## What changed

`design/draw.py` was largely rewritten (Sheet writer kept, layout engine new). All of it is general; per-block
hints are listed at the end.

1. **Parts are wired to the pin they serve instead of labelled.** Every small part is assigned to one IC pin by
   growing a tree out of each pin: `serves=` hints first, then parts of the IC's own section, then anything left.
   Each pin with parts gets a horizontal "lane":
   - parts to ground hang from the lane, pull-ups stand on it, series parts sit in line and the drawing follows
     them to the next net (so R - D - label, or R - node with shunts - transistor, is one wired chain);
   - a part between two neighbouring pins stands between their lanes: cell-filter ladders, divider columns
     (PPHV/R409/ACUV/R410/ACOV/R411/GND is one vertical column), differential filter caps, bootstrap caps,
     the reset pull-up between VDDS and RSTN, the REGN/DRV_SUP diode;
   - neighbouring lanes that each only have a pull-up to the same rail share one rail wire (I2C pull-ups);
   - a chain that returns to the neighbouring pin is closed as a loop (antenna pi network);
   - a small transistor, wire pad or test point on the last net is drawn at the end of the lane;
   - lanes sit as close to their pins as their contents allow (variable pitch), so fan-out wires are short.
2. **Labels only where a net leaves the group.** A label is drawn only if the net has pins not wired in that
   tree. Unconnected-looking "Net-(...)" labels are mostly gone.
3. **Pins without parts**: neighbouring pins on one net are joined by a wire with one label or one ground symbol
   (D+/D-, grounded GPIOs, EN tied to VIN); bottom ground pins share one ground symbol; top supply pins get
   their decoupling on a short rail above the part.
4. **Templates**: `buck` and `bridge4` kept. `bridge4` now draws each shunt's Kelvin RC filter at the shunt
   (found from the existing `kelvin()` declarations). New `fetpair` template: two back-to-back FETs as a power
   path with gate-source parts between gate and source rail and series parts across the pair.
5. **Junctions are computed, not hand-placed**: wires are split wherever a pin or wire end lands on them and a
   dot is added where three or more meet.
6. **Page**: each IC group is drawn on its own canvas and measured; sections are packed into rows and columns
   and the page size is chosen to fit (no more A2-and-taller pages with a corner filled).
7. **Annotation**: section titles in bold; under each title short notes written in the block (`note()` in
   kernel.py), the design targets from `expect()` ("battery regulation: 16.8 V +/-1% at U403.FB (set by R419,
   R418)"), and "Also drawn here: ..." when a section's parts were drawn at another section's IC. Reference and
   value of in-line parts are on one line above the part.

Per-block hints added (drawing only): `note(...)` lines in all four block files; `draw_as("fetpair", "Q101",
q_out="Q102", bypass=["C110", "C111"])` in cells_gauge.py; C457/C557 removed from the 5 V buck's `cin` list in
usb_port.py so it is drawn at the LDO input it serves.

## What I would do next

- The BQ40Z50 and BQ25756 have 12 to 16 lanes on one side; the fan-out staircase between pins and lanes is
  correct but is still the busiest part of those sheets. Splitting such an IC into two symbol units, or letting
  a block move a group (thermistors, current sense) to a labelled sub-drawing, would shorten it.
- Power-port symbols (arrow up) for the global rails 3V3 and PACK_P instead of global labels on pull-up tops.
- Draw F102 in line with the protection FET pair (PACK+ wire, fuse, FETs as one path) and wire the fuse heater
  to Q104 instead of two "Net-(F102-HTR)" labels.
- Attach leftover single pads (TP301, TP412, load wires) to the rail they probe.
- The page packer is greedy; the Cells sheet still has an empty band left of the title block.
- Reference/value text of a few parts with top pins (J301, U405, U402) sits close to pin stubs.

## Blocked / caveats

- Nothing blocked. `scratch/dbg.sh` is a copy of make.sh that still renders when the netlist differs (debug only);
  `scratch/design_orig/` is the design folder as received.
- Text width is estimated (1.2 mm per character), not measured, so very long values could touch a neighbour.
- I checked every page at 100 dpi and several crops at higher zoom, but not every label on the two port sheets
  individually; port 2 is the same drawing as port 1 with 5xx references.
