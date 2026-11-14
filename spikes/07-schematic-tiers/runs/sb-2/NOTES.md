# NOTES (sb-2)

## What changed (design/ only; make.sh ends NETLIST OK)
- design/page.py (new): Page helper (explicit coordinates, pin-to-pin wiring, auto-tag of unused pins) and Offset proxy.
- design/scenes.py (new): hand-laid whole-sheet scenes for 3V3 Rail, MCU, Cells and Gauge; section scenes for USB ports (connector/protection, PD controller, charger, 9 V supply, 5 V buck). Four-switch stage still uses the generic bridge4 template.
- design/draw.py: hooks for scenes/sections, per-sheet paper size, per-block page width, justify override.
- design/symlib.py: AGM404AP1 MOSFET redrawn horizontally (same pins).
- design/kernel.py + blocks/*: shorter section titles, section notes; nets renamed in cells_gauge.py (names only).
- q.sh: quick draw+render without netlist proof.

## Next
- Four-switch stage and its R424/R427 on USB sheets still generic and sparse; give it a scene.
- Remaining small text collisions (charger R409/R435 values, 5 V buck EN label, MCU R305/R314, protector section near title block).
- Unused-pin auto-tags (U406/U506 pins 6,7, U101 NC) could be given explicit no-connects.
- "NOT PLACED C409/C449" message is expected (drawn by the charger scene).

## Blocked / caveats
- Adjacent 2.54 mm pin rows make shunt parts collide; solved with staircases, staggering, labels.
- Pins/power symbols on mid-wire need explicit junctions; labels must lie on wires (cost several netlist iterations).

## Round 2
- Fixed rotated-part text justification (page.py), charger/PD/9V/5V text collisions, section gap 12.7, explicit NC tags (tag_all), SMBus resistor positions on Cells.
- Still open: four-switch stage scene, Cells whitespace (NTC pads), R123/C116 text, root sheet content. See review-r2.md.

## Round 3
- Tightened USB section origins, four-switch height, NTC pad pitch, R123 text. NETLIST OK.
- Still open: four-switch scene, remaining whitespace on Cells and USB sheets, root sheet pins. See review-r3.md.

## Round 4 (final)
- Root sheet now carries a title, a power-flow note and a one-line description under each sheet box (ROOT_HEAD/ROOT_NOTES in scenes.py, emitted by draw.py).
- Row gap on packed sheets reduced. All six pages re-viewed; NETLIST OK.
- Not done: four-switch stage scene, Cells whitespace, remaining ~10 mm slack per section on USB sheets.
