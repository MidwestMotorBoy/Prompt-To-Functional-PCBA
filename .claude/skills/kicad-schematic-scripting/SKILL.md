---
name: kicad-schematic-scripting
description: Edit KiCad 9/10 schematics (.kicad_sch, .kicad_sym) safely by script or text, with a netlist diff to prove only the intended nets changed. Use when changing part fields, swapping parts, adding or rewiring symbols, or generating a custom symbol, especially when KiCad itself isn't available.
---

# Editing KiCad schematics by script

KiCad files are S-expressions. An agent can edit them as text, which works in a cloud container with no KiCad installed. The risk is a silent wiring change. So every edit ends with a netlist diff. The helpers this project used are `hardware/Production/tools/schlib.py` (blocks, pin positions, wires) and `hardware/DevBoard/tools/sch_edit.py` (find a symbol by reference, set a property, move a label).

## Ground rules

1. **Schematic, not board.** Change the schematic, then the person who owns the layout runs *Update PCB from Schematic* and fixes the copper. Don't edit `.kicad_pcb` unless that person explicitly asks for a specific board edit. (Owner's rule on this project: "Don't make any changes to the PCB. Just make schematic changes.") Reading the board for review or analysis is fine.
2. **Back up first.** Copy each file you'll touch to a `review-backups/<what>/` folder, or make sure it's committed.
3. **Don't write under an open editor.** If KiCad has the file open (a `.lck` file sits next to it), ask the person to save. Write with a modification-time guard, then have them do *File > Revert*. Otherwise their next save overwrites your edit, or a revert loses their unsaved work.
4. **Keep the file's line endings.** Files saved on Windows are often CRLF. Open with `newline=''` in Python and write back the same way.
5. **Datasheet first.** Any pin number you write comes from the datasheet's pin table and package drawing, quoted in the script's docstring (see `hardware/Production/tools/tpd6s300.py`).

## Text-level mechanics

- **Find a block by balanced parentheses, skipping strings.** A regex can't match an S-expression. Scan characters, track depth, and jump over `"..."` with backslash escapes (`block_end()` in both helper files).
- **Find a placed symbol** by `(property "Reference" "U401"`, then step back to the enclosing top-level `\n\t(symbol\n` block.
- **Set a field** inside that block only: `(property "LCSC" "C123")`. Assert exactly one match, so a missing field fails loudly instead of being skipped.
- **Embedded library copies.** Each schematic carries a `(lib_symbols ...)` copy of every symbol it uses. If you change a library symbol (`.kicad_sym`), update the embedded copy too, or the schematic keeps the old pins until someone runs *Update symbols from library*.
- **Pin positions in sheet coordinates.** Library Y points up and sheet Y points down. For a symbol at (X, Y) with rotation r and optional mirror: take the pin at (px, −py), mirror it (x mirror: negate y; y mirror: negate x), rotate by r, then add (X, Y). `schlib.symbols()` does this. Wires connect only when an end lands exactly on a pin point, so round to 0.01 mm and stay on the 1.27 mm grid.
- **Junctions.** Where a wire ends in the middle of another wire, add a `(junction ...)`. KiCad adds one when you draw by hand; a script has to add it itself.
- **New blocks need new UUIDs.** When you copy a symbol, wire or label, regenerate every `(uuid ...)` in it (`schlib.new_uuids()`).
- **Hierarchical sheets used more than once.** When one `.kicad_sch` is instantiated twice (port 1 and port 2), the real reference designators live in each symbol's `(instances (project ... (path "/<sheet-uuid>" (reference "U501") ...)))`. A field change in that file applies to **both** instances. Say so in your report: swapping L502 on this project also swapped L402, because both ports share one sheet.
- **BOM and placement flags.** Wire pads, test points and DNP parts need `(in_bom no)` / `(exclude_from_bom)`, `(dnp yes)` or `(on_board ...)` set deliberately. A forgotten flag shows up later as a BOM line the assembler can't place.

## Adding or replacing a part

1. Generate or copy the library symbol. If you generate it, build it from a table `(pin type, x, y, angle, name, number)` written straight from the datasheet. Then **re-read the package drawing and check every number**: a swapped pin pair in a generated symbol put CC1 on GND on this project.
2. Keep the footprint if the land pattern really is identical. Compare pad size, pitch and exposed pad from both datasheets. Otherwise point the Footprint field at a new footprint and tell the layout owner it changed.
3. Fill every field: Value, Footprint, Datasheet (URL or repo path), Description, MPN, LCSC (or "consign"), plus a Notes field explaining the choice and the date.
4. Wire pins by placing labels or power symbols right on the pin points. That way you don't have to route wires.
5. Mark unused pins with no-connect flags, but only where the datasheet allows them to float.

## Schematic style (if the drawing will be read by people)

- Use the GND power symbol, never a "GND" label, and power symbols for rails.
- Signal flows left to right: inputs on the left, outputs on the right, supply up, ground down.
- Name nets after their function (`CHG_INH`, `BAT_SNS_P`), not their pin.
- Put a short note block on each sheet giving the reason for anything unusual (0 Ω charge-limit resistor, DNP fuse-blow resistors), with the date.

## Proving the edit

1. **Netlist diff.** Export the netlist before and after (`kicad-cli sch export netlist --format kicadxml`), parse both into `{(ref, pin): net}` and diff them. Expect exactly the changes you intended: pins removed with a removed part, merges where a 0 Ω link became a wire, the new part's pins on the old part's nets. `hardware/Production/tools/check_netlist.py` does this for a whole derived schematic.
   - No kicad-cli available? Rebuild connectivity yourself from pin points, wires, labels and power symbols with `schlib.py`, and check the touched nets.
2. **ERC.** Run `kicad-cli sch erc` (or ask the person to). Compare the count with the previous run; new items must be explained.
3. **Netlist against board** (after the layout owner updates the PCB). Every schematic pin should match a board pad on the same net. Only intentional board-less items (test points that were removed on purpose) may differ.
4. **Report** which sheet(s) changed, which instances it affects, where the backup is, and what the layout owner still has to do (Update PCB, reroute pins X/Y, ERC/DRC).

## Fields that let placement and routing be automatic

A scripted placer and router need to know things that only the schematic's author knows: which nets switch,
which two pads are a Kelvin tap, which capacitor serves which pin, which pads close a hot loop, which parts are
fixed, which sheets are copies of each other. On this project those were typed into the layout tools as lists
and regular expressions, which is why the tools do not move to another board unchanged. When a schematic is
written for an automated flow, put them in symbol fields and net classes from the start. The list of
declarations and what each one feeds is in the `pcb-proto-flow` skill, section 3.

