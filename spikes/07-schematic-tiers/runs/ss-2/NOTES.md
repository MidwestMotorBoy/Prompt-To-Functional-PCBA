# Notes (ss-2)

## Changed (all in design/, make.sh ends NETLIST OK)
- draw.py: sections are packed with a bottom-left skyline packer in reading order; the sheet width is searched
  (aspect target about 1.45, small area) instead of a fixed 594 mm. Sheets shrank (USB 2678x2245 -> ~2000 wide, landscape)
  and the gaps beside short sections fill with later sections.
- draw.py: a small IC's leftover cells (those not wired to its pins) are placed beside it, not below it.
- draw.py: private nets drawn as "U101.VC3" / "C110.2" instead of "Net-(U101-VC3)" (net names are not compared by the gate).
- draw.py: page extent now counts text width (the MCU antenna title used to run off the page).
- kernel.py: section(title, note="") adds a one-line note under the section title; notes added in rail_3v3, cells_gauge, usb_port.

## Next
- Antenna pi network (C313/R321/C315/C314) should be a "pi filter" template in one row; today three parts sit with U301 and one is alone.
- Cells sheet: single-pin wire/test-point terminals (J1xx) should be a compact table next to the net they land on;
  Q104/F102/R125 fuse-ignition circuit should be a template (FET, gate divider, fuse in series).
- Overlaps remain: J113 PACK_P label on TP106, some pin labels at U101 right side, CELL_1N stubs.
- Lane wiring for the gauge cell inputs still has crossing wires; needs a router rather than fixed lanes.
- 3V3 sheet is still half empty; use A4 sizing there / row-wrap the bulk caps under the buck.

## Round 2
- Added `pi_filter(series, shunt)` hint (kernel.py) and `draw_pi` (draw.py): the MCU antenna match now draws as a textbook pi
  (RFIO - C313 - node/C314 - R321 - node/C315 - ANT_IN).
- Small ICs without leftover cells in one section share a row; page minimum size reduced (A5-ish) so small sheets are not mostly empty paper.
- Not fixed: Q104/F102 fuse circuit still stacked vertically (Q104 has leftover cells so it misses the row rule); PACK_P label overlap on J113/TP106;
  gauge lanes crossing; 3V3 and MCU sheets still sparse. See review-r2.md for scores and the list.

## Round 3
- Single-pin parts (J wire stubs, test points) are no longer pulled into IC zones; they form one tidy row in their own section,
  and their cell width counts value text plus label so nothing overlaps (J113/TP106, J120/J116 fixed).
- Fuse circuit (F102, Q104) now sits side by side instead of far apart (row rule from round 2 now takes effect).
- Still open: U101 pin-label collisions on the left (VCC/PBI vs R105), crossing gauge lanes, R432 (EN_5V1 pull-down) and TP412 alone at the
  bottom of USB sheets, D101 floating below the gauge, fuse circuit not a series template. See review-r3.md.

## Round 4
Review only plus a packing-weight tweak (no visible effect). Remaining work is the five items in review-r4.md.
