# hi-1: notes

## What changed
All changes are under `design/`; `make.sh` ends with `NETLIST OK` (285 parts, 168 nets, 0 differences).

- **`design/lay.py` (new): a small drawing engine.** A sheet is drawn by a layout function from explicit placements
  (`ic`, `two`, `one`, `w`, `label`, `netlabel`, `gnd`, `gndx`, `rail`, `nc`, `fan`, `chain`, `text`, `heading`).
  The engine never decides connectivity. It does the housekeeping a person does: junctions where three things meet,
  the smallest standard paper for the drawing, the drawing centred on it, header above the content.
  It also runs a **lint** on every sheet and prints it during `make.sh`: wires through symbol bodies or text, overlapping
  text and bodies, unconnected pins, shorted nets (geometric union-find), duplicate wires. All five sheets are at 0 warnings
  except MCU (1, a false positive on a rail-symbol label). `Shift` lets a section be written in its own coordinates and
  placed anywhere (used for the second column on Cells and Gauge).
- **`design/layouts.py`, `design/layout_usb.py` (new): the per-block drawings.** Written as functions with named groups and
  a heading and one-line note on each group. Recognisable circuits: buck stage with inline inductor and output cap; RC cell
  input ladder with series R and shunt caps; Kelvin current sense (sense R in the rail, 10 R each side, differential and
  common-mode caps); pull-up ladders; pi network; back-to-back FET path with ESD pair; second-level protector with fuse FET;
  four-switch buck-boost as two half-bridges with the inductor between, bootstrap circuit under each half; TPS62933 buck with
  textbook BST/SW/FB placement; LDO with FB divider.
- **`design/draw.py`**: hook only. Blocks listed in `layouts.LAYOUTS` use the new engine; any other block falls back to the
  old generic drawing (still there, unchanged).
- Wires are used for local nets, labels for nets that leave a group (HIDRV1, SW1, REGN, ACP_F ...) and global labels / rail symbols
  for cross-sheet nets. Per-port nets (VBUS, PPHV, PP5V) are local labels, never power symbols (they would merge across ports).
- Page results: 3V3 Rail A4, MCU A4, Cells and Gauge A3 (two columns, was tall and narrow), USB ports A2.

## Round 3 (see review-r3.md)
- Cells and Gauge: the nested SRP..TS4 staircase on the gauge's left pins is gone. Those seven pins leave on label stubs and
  their circuits are two wired groups under the gauge: "Pack current sense" (J108, RS101 in the rail, R107/R108 down into a
  filter with C106 between, SRP/SRN labels, J114 and TP109 hanging on the ground side) and "Pack sense and thermistors"
  (R113 from PACK_P, TH101, TH104, wire pads J117-J120 at 28 mm pitch). `Net-(U101-PACK)` is renamed PACK_S.
- Checked and left alone: USB on A3 (needs 380 x 241 mm, is 419 x 284: three stacked rows plus a 400 mm bottom row, would need
  the power stage split), the charger's FSW/ICHG/ILIM/TS ladder, the EEPROM on labels (SDA/SCL pin order would force a crossing).
- Remaining ideas: split the USB power stage into two columns to reach A3; a label-bus version of the charger config pins;
  text-width lint.

## Round 4 (see review-r4.md)
- 3V3 Rail: notes moved beside the buck, bulk-cap group moved up (drawing 182 x 92 mm, was 172 x 106), heading clear of the PACK_P rail.
- USB: "Output feedback divider" note under R418/R419 so the divider reads as part of the charger.
- Evaluated and rejected: USB on A3 (area needed about 100,000 mm2 vs 86,000 mm2 usable at fixed symbol size), wiring the MCU
  pi network into RFIO/ANT_IN (needs the reset network moved 60 mm left), label-bus for the cell-input fan.
- Final state: all pages checked, make.sh ends NETLIST OK, lint 0 on every sheet but MCU (1 false positive).

## What I would do next
1. A general placer: the layouts are hand-placed. The next step is to turn recurring patterns (`kelvin`, `boot`, pull-up ladder,
   divider, hang-from-rail caps, `fan`) into library functions that a netlist-driven placer picks by net topology, with the
   layouts as per-block hints.
2. USB Port sheet is A2 (419 x 281 mm) and a bit sparse at the sides. Getting it on A3 needs the 5 V buck and the 9 V supply to
   move beside the stage, or the PD controller's right-hand ladder to be folded.
3. Cells and Gauge: the left fan still has long staircase wires from the gauge's 2.54 mm pins (VC and TS rows). A label-bus
   (stub label on every pin, mini-circuits drawn beside) as on the BQ25756 would remove them, at the cost of more labels.
4. Lint should also check wire crossings between different nets and label text against wires on the next row.
5. Symbol text: the SiZ240DT and BSC/AGM flat symbols print their pin names inside the body and mirrored versions read oddly.

## Round 2 (self-review, see review-r2.md)
- Scored every page before changes (3V3 3.9, Cells 3.0, MCU 3.8, USB 3.5) and fixed the five worst items:
  1. Cells: removed all text collisions (pads drawn hanging with text beside, "U" text on the protector resistor ladder,
     Q102 text placed left of the body, J113/TP106 spaced, ground labels clear of values, J118/J120 beside their pads).
  2. Cells: TP109/J114 now hang on the RS101 ground wire; the TS tower is tighter; charge/discharge path and second-level
     protector are placed with the new `Shift` helper (a section drawn in its own coordinates and moved as a block).
  3. USB: EEPROM has its own titled group with a note; D401 moved to the end of the VBUS rail; PP5V/PPHV tails shortened.
  4. USB: Kelvin-block nodes moved 10.16 below the rail, FSW row moved, group notes under each heading.
  5. 3V3: notes next to the circuit, bulk caps at 13.97 pitch; MCU: C314 at the C313/R321 node, connector texts clear.
- Engine additions in design/lay.py: `Shift`, `chain` "pad" terminals with orientation, `two()` text mode "W", `ic(hide=...)`.
- State now: all sheets lint-clean (MCU has one false positive: 'rail 3V3' text over gnd), make.sh ends NETLIST OK.
- Remaining ideas: label-bus on the gauge's left pins to kill the staircases; USB to A3; real FET symbols for Q101/Q102;
  lint for text-vs-text width overlap (the current estimate is approximate).

## Blockers and caveats
- The SiZ240DT / AGM404AP1 / BSC007 symbols are flat boxes with pins 2.54 mm apart on one side; the four-switch stage and the
  protection FETs are drawn with them rotated or mirrored (`mirror y` after rotation) so the pins land on rows.
- The ICs have 2.54 mm pin pitch, so every passive that needs room goes through `fan()` (staircase jogs); the number of
  columns grows with pin count.
- Docker was shared with other runs and was briefly unreachable once; waiting was enough.
- `exp/bk-hi1` (a stray empty-ish backup folder outside my working folder, created early on) could not be removed (blocked by a
  safety check), please delete it by hand.
