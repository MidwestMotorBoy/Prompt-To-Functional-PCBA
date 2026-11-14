# Notes (final round first, then earlier rounds)

## Final round
- Checker made stricter: 1.25 mm per character, 2 mm text height, smaller tolerance. It now reports the TH101/R113/PACK_P cluster,
  R105/D101_K, R115/GAUGE_FUSE, and USB label/value hits (6-7 per sheet). It still does not test wires or symbol bodies, so
  it under-reports (reviewer saw about 12 on U101 alone). Next step: register bodies and wires in the same list.
- Two adjacent inline parts are no longer allowed on one face: the second one is demoted to a lane. Widening the rule to 6 mm
  broke the netlist (lanes cross the ladder's wires on U101's left face), so it stays at 2.54 mm.
- Template notes: `note="..."` in the `pi`, `fetpair` and `kelvin` hints prints one line under the drawing.
- Sections are packed bottom-left in power-flow order (Cells now uses two columns).

## Still open, in order of value
1. Floating parts (USB D401, U402, C451/C452/C404/C408, R432, Q409, TP412; Cells D101, J1xx terminals, MCU TP301). Plan: record each
   label end point (net -> x, y, direction) while drawing and put single-pin parts of that net there; D101 as a series part in
   front of R105 on the BAT row.
2. Inline/lane crowding on U101's left face (TH101, TH104, R113, C105) and U403's right face (R444-R447, R412-R414): needs lanes
   that coexist with the ladder (route lanes below the ladder, or give the ladder its own side offset).
3. Straight protection path: rotate Q101/Q102 by 90 (Sheet.symbol takes angle, mirror; use rot()) so S and D lie on the path
   line. Not attempted.
4. Page balance of USB (still about a third empty) once the floating parts are gone.

# Notes (round 3 summary first; round 2 below)

## Round 3
- Overlap checker in `Sheet` (draw.py): bounding boxes of every label, text and ref/value field, collisions printed to stderr per
  sheet by make.sh ("overlap check ..."). Does not see wires or symbol bodies. Now 0 (3V3, MCU), 2-5 (Cells, USB) text collisions.
- `ladder` template (hint `draw_as("ladder", "LAD_x", target="U101", rows=[[R, C], ...])`): cell-tap filters of U101 and U102 drawn
  as rows fanned out left of the IC, capacitors standing between neighbouring rows, last one to the return rail; no VC/V labels.
  Ladder jogs start beyond the inline parts on the IC's left (offset = labl).
- Aliases always prefixed with the ref (`U101_VCC`, `U102_OUT`), unique per sheet.
- `inline()`: a part beside a pin that carries a label steps out past the label; when no free row exists the text stays on its
  body (above/below) instead of drifting to the far end.
- Packing is now bottom-left in section order (power flow order) at the best page width, instead of shelves.

## Still open (in priority order)
1. Floating support parts (USB: D401, U402, C451/C452/C404/C408, R432, Q409, TP412; Cells: D101, J117/J119 and the terminal
   section; MCU: TP301): attach_plan must accept top/bottom pins and attach single-pin parts to the net where it is first drawn.
   Their leftover rows are also what keeps the USB and Cells sections tall and the page half empty.
2. The `fetpair` is still a U shape (drains on an upper line, sources dropped to buses); the reviewer wants F102 - Q101 - Q102 on one
   line, which needs rotated FET symbols or a custom symbol with D and S on opposite sides.
3. U101 left face is still tight (R113/TH101/TH104 text, PACK_P label), and R115/R116 text touches the SCL/SDA labels; USB U403
   rows R444-R447 and R412-R414 are still crowded; C401/C402, C405, C439 shunts are still sideways.
4. Checker should also test wires and symbol bodies.

# Round 2

## Changed (draw.py unless noted)
- Aliases for auto-named nets (`Net-(U101-VC3)` -> `VC3`, `Net-(C110-Pad2)` -> `C110_2`): one `alias` map in `draw_block`,
  used by `short()`, so every label of a net matches. The gate ignores names, so no netlist change.
- Reference rails: `ref_rail(net)` in kernel.py (hint in cells_gauge.py for CELL_1N). `isg()` treats such a net like ground in
  ranking, lanes, hang, chains and banks; `gnd_at()` draws a ground symbol for GND or a short stub plus label for a rail.
  Parts now hang from their signal lane and end in a CELL_1N stub (TH101 on TS1, C104 on VC1 and so on).
- Templates with an `anchor` and `parts` list in the hint (consumed parts are skipped by the generic placer):
  - `pi` (antenna match): series, shunt, series, shunt, left to right.
  - `fetpair` (Cells protection path): CELL_P_RAW terminal -> F102 -> CELL_P bus -> Q101/Q102 back to back (drains meet, sources
    drop to buses that run outward) -> PACK_P; gate networks beside the gates, ESD pair under the FETs, mid-cap chain, wake
    pull-up with its test point, fuse-heater FET with its gate network under the fuse. All wired, no islands.
  - `kelvin` (RS101): path with the two filter resistors dropping to SRP/SRN and the cap across them.
- `inline()`: ref above and value below the body when the neighbouring rows are free (checked against what is drawn on adjacent
  pin rows); one-sided or after-the-part text otherwise. Shunts to GND end with a corner and a downward ground symbol.
- Packing: sections are shelf-packed at the page width that gives the most balanced (about 3:2, smallest area) sheet; paper
  fits the content (min height 130 mm); section titles count toward sheet width; terminals/test-point sections go last.

## Not done
- Cell-tap ladder drawn with the cap vertically between two lanes (item 4): the VC4 row is an inline part, not a lane, so it needs
  the lane code reworked.
- Floating support parts on the USB sheet (D401, C451/C452/C404/C408, R432, Q409, U402) and Cells (D101, J115-J120): need
  attach_plan to accept top/bottom pins and single-pin terminals attached to a net already drawn.
- Sideways shunts elsewhere (C401/C402, C405, C439, R412-R414) and U401/U405 bottom pin number pile-up.
- TH101/TH104 inline on U101 still collide with neighbouring pin labels; U101 pin-row labels vs inline parts need a spacing rule.
- Overlap checker (bounding boxes in Sheet) not written; I checked by zooming renders.
- Terminals strip on Cells ("Cell and load wires") should become one connector-style row; J120 label touches J116.
