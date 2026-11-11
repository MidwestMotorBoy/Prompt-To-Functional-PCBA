---
name: jlc-fab-files
description: Prepare a KiCad board for JLCPCB fabrication and assembly - fab-rule DRC setup, gerbers and drill, BOM and CPL built from the board, top-only assembly with a hand-solder list, consigned parts, and rotation fixes from JLC's placement preview. Use when making an order package, setting DRC rules for a fab, or fixing CPL rotations.
---

# JLC order files

From the P0 order package in `hardware/Production/jlc/` (see its `ORDER-NOTES.md`): a 6-layer, 2 oz outer / 0.5 oz inner, ENIG board, 261 placed parts, top side assembled by JLC and 12 bottom parts soldered by hand.

## 1. Put the fab's limits into the design rules first

Copy the fab's current capabilities page for your exact stack-up (layer count *and* copper weight) into `.kicad_pro` (board setup minimums) and `.kicad_dru` (custom rules), then rerun DRC. The values used here (JLC 6-layer, 2 oz outer, 2026; recheck before reuse):

| Rule | Value |
|---|---|
| Track / clearance on 2 oz | 0.15 / 0.15 mm |
| Via | 0.3 mm drill / 0.45 mm pad |
| PTH annular ring on 2 oz | ≥ 0.25 mm (holes ≥ 0.5 mm) |
| Hole to hole, via to via | 0.2 mm |
| Hole to hole, either one a pad hole ≥ 0.5 mm | 0.45 mm |
| NPTH | ≥ 0.5 mm |
| Copper to edge | 0.25 mm (0.2 mm minimum where a connector needs it) |

KiCad 10 `.kicad_dru` syntax gotchas (see `hardware/Production/Monolith.kicad_dru`):
- Every constraint value needs units: `(min 0.25mm)`.
- Use `A.memberOfFootprint('J401')`, not `A.Parent.Reference`.
- A rule that names the `Default` netclass is flagged as undefined. Write it as the complement: `!B.hasNetclass('Power') && !B.hasNetclass('GND') ...`.
- Comment every rule with why it exists and which fab limit it encodes.

Via arrays at a tight pitch produce hundreds of hole-to-hole warnings. Check them against the real fab limit and set the rule to that limit instead of ignoring the warnings. (`pcb-layout/references/dfm-jlcpcb.md` keeps `min_hole_to_hole` at 0.25 mm as a margin; this board was relaxed to JLC's 0.2 mm on 2026-10-30, after the fab limit was checked. Choose one on purpose.) More DFM detail is in that file.

## 2. Pre-fab gate (all on the final saved file)

- DRC on a refilled copy: 0 errors, 0 unconnected. List the remaining warnings and say why each is accepted.
- ERC: 0 errors; known warnings listed.
- Schematic netlist against board pads: an exact match, apart from intended exceptions.
- Kelvin taps and other critical copper unchanged since the last review (rerun the checks from `pcb-layout-review` if anything nearby moved).
- Enclosure fit and height zones still met by any part that was swapped late.

## 3. Generate

With `kicad-cli` (or the KiCad MCP's `export_gerbers` / `export_drill` / `export_pos`); check `--help` for your version's flags:
```
kicad-cli pcb export gerbers -o gerbers/ --layers F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.SilkS,B.SilkS,Edge.Cuts board.kicad_pcb
kicad-cli pcb export drill -o gerbers/ --format excellon --excellon-units mm --excellon-separate-th board.kicad_pcb
kicad-cli pcb export pos -o kicad-pos.csv --format csv --units mm --side both board.kicad_pcb
```
- Zip the gerbers, drill files and job file. Rename inner-layer files so there are no spaces in the names.
- **Build the BOM and CPL by script from the board's footprints**, not by hand. That way they match the copper exactly.
  - Skip footprints marked exclude-from-BOM, DNP or exclude-from-position-files, and test-point or wire pads.
  - BOM columns: Comment, Designator, Footprint, LCSC Part #, MPN, Qty, with one line per unique part.
  - CPL columns: Designator, Mid X, Mid Y, Layer, Rotation.
- **Top-only assembly** (to save cost, or when bottom parts are few): write `*_top.csv` BOM/CPL files plus a `bottom_hand_solder.csv` with the parts to buy and fit by hand.
- **Parts JLC doesn't stock:** consign them, or use JLC's global sourcing. List them in the order notes. If a part's LCSC number exists only in the JLC BOM and not in the schematic, say so and fix the schematic later.

## 4. Rotations: check every part in JLC's preview

JLC's library footprints don't always share KiCad's zero orientation. Go through the placement preview part by part, especially QFNs, diodes and TVSs (pin 1), USB-C, FETs and anything on the bottom side. Then correct the CPL:
- The CPL rotation is counter-clockwise positive, so "turn 90° clockwise" means −90.
- If JLC's body outline sits off its pads, correct Mid X / Mid Y (one fuse needed +0.65 mm).
- Write every correction into the order notes (part, change, time) and apply it to every CPL variant (full and top-only).
- A diode or TVS at the wrong rotation can short a rail (VBUS to GND). Flag those for a second look.

## 5. Order notes

`ORDER-NOTES.md` next to the files: the file list; the PCB options (layers, size, thickness, finish, copper weights, via covering such as epoxy filled and capped for via-in-pad, stack-up and impedance needs); the assembly scope, paste and consigned parts; the checks run on this save; and the rotation fixes. Copy the package to wherever the person orders from, and to the repo.

## 6. After a late part swap
- Update the schematic fields, then the JLC BOM (full and top-only), the hand-solder list if it applies, and the tracker.
- If the land pattern stayed the same, keep the footprint and say so. If not, the layout owner updates the PCB first and the files are regenerated.

## 7. Order files belong to one board file

Gerbers, drill, BOM and placement file are one set, made from one saved board. On this project a second,
script-built layout replaced the board file on the main branch while the order folder still held the package of
the reviewed, hand-routed board. Nothing looked wrong: the folder was complete and the board passed DRC.

- Write the board's commit (or a hash of the board file) into the order notes and at the top of the BOM and
  placement files.
- When the board file changes, either regenerate the whole set or put a warning at the top of the order notes
  the same day: which board the files are for, and that gerbers from the newer board must not be mixed in.
- A regenerated gerber zip is checked in a viewer before it replaces the old one (an early zip here printed pads
  as silkscreen).
- Renders, layer plots and reviews go stale the same way. Say which board each one shows.

