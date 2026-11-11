---
name: pcb-layout-review
description: Review a placed or routed KiCad PCB (read-only) for current-path resistance, Kelvin sense taps, keep-outs, clearances vs copper weight, fab rules and enclosure fit, and hand the layout owner fixes with exact coordinates. Use when asked to review a board layout, a new board revision, or a "is this ready for fab" check.
---

# PCB layout review

A board review here is **read-only**: the agent measures and reports, and the layout owner moves the copper. Give every finding a net, a layer and KiCad board coordinates in mm, so the owner can find it in seconds. The method comes from the placement review and revs 1–13 of a routed 6-layer, 2 oz power board (`docs/reviews/2026-10-30-routed-board/`). For the layout rules themselves (stack-up, return paths, hot loops, routing discipline), and for its render and DRC-summary scripts, use the `pcb-layout` skill and its `references/review-checklist.md`. This skill is about running the review and measuring.

## Setup

1. **Snapshot what you review.** Copy the `.kicad_pcb`, `.kicad_pro` and `.kicad_dru` into a dated folder (`review/revN-drc/`). Every number in the report refers to that snapshot.
2. **Diff against the last reviewed snapshot,** not against some intermediate file. One rev was misreported as "only SCL changed" because it was diffed against the wrong copy. Diff footprints (ref, position, rotation, layer), tracks, vias and zone outlines by net.
3. **Refill zones on a copy before measuring copper.** Saved fills can be stale. Refill (KiCad MCP `refill_zones`, or the GUI) on the copy, never on the owner's open file.
4. **Run DRC and ERC** on the refilled copy (`kicad-cli pcb drc --format json --severity-all`; add `--schematic-parity` where your version has it). Read every error. Group warnings by type and count them, then say which are known and accepted.
5. **Netlist against board.** Every schematic pin should match a pad on the same net. List anything that's only in one of the two.

## Checks

### Placement (before routing)
- **Hot loop first.** Input caps right at the half-bridge FETs; nothing else in the switch-node path. A FET rotated 180° can cut its own input caps off one leg.
- Copied blocks: is port 2 a translated or a mirrored copy of port 1? A translated copy puts the connector on a different side relative to the stage, so check each one on its own.
- **Enclosure fit.** Check every part's height against the height zone it sits in, and every part near an edge against the enclosure's inside corner radius *with tolerance*. On this project an inductor hit the cup's corner fillet. The fix was a 2.0 mm tall part on the same land, not a move.
- Mounting pegs, sleeves and wire exits against nearby parts and courtyards.
- Parts parked off the board outline (an RF match network was left outside it).

### Current paths
- For each high-current path, estimate the resistance and the loss at the real current (see `pcb-copper-resistance`). Look for planes cut by traces on the same layer: one port's battery path read 35 mΩ because vertical inner-layer traces split its plane, and the current went round the far end of the board.
- **Current per via.** Find the hottest via. More than about 1.5–2 A in a 0.3 mm via in a power path is worth a fix; add vias around it.
- **Necks.** Find the narrowest copper width on each power net (KiCad's `connection_width`, or a neck search on the rasterised copper). Anything under the fab minimum is an error. Narrow pinch points also carry hot spots.
- **Fuse-adjacent and heater paths.** A 0.2 mm, 0.5 oz inner trace at 1 A heats up; check that it can carry the current for as long as the event lasts (a fuse heater can take up to a minute to blow).

### Sense and signal integrity
- **Kelvin taps.** Each sense line (charger SRP/SRN and ACP/ACN, gauge SRP/SRN, voltage feedback) must start at the sense resistor's own pad. It must not touch a plane, a pour or a via that carries load current. Compute the reading error: the voltage between the tap points divided by the voltage across the resistor's pads. Errors seen on this board: 1.8× (an SRN tap on the plane via), 23 % (ACN vias inside a pour on another layer), 7 % (SRP taken at a capacitor instead of the resistor). All of them were fixed to within 1 %.
- **A Kelvin trace that also carries current isn't Kelvin.** Here the ACP trace also fed a VAC/REGN filter, so its current dropped voltage along the sense path.
- **Keep-outs around tap vias must clear thick copper.** On 2 oz outer layers the fab's real spacing is about 0.2 mm, so a pour stopping 0.08–0.12 mm from a via pad can bridge. Make the keep-out about 1 mm or more.
- Gate-drive traces short and wide enough (0.2 mm is thin for a gate loop), with their return next to them.
- I2C and other slow digital lines kept away from switch nodes, and not routed under the inductor.
- Feedback (VOS, FB) lines not next to SW copper.

### RF and keep-outs
- An antenna keep-out must cover **every layer** the module maker requires. A footprint's keep-out zone can end up on one layer after a library edit. Compare the board's zone with the library footprint (KiCad's footprint-mismatch DRC warning is the hint), and check the fill of every pour on every layer under the antenna strip.
- NTC and other thermal sensors: keep the inner planes under them (an isolated island removes only about a third of the board error) and route their low side as its own trace.

### Fab rules
- Load the fab's capabilities into `.kicad_pro` and `.kicad_dru` and recheck (see `jlc-fab-files`). Via-to-via hole spacing and pad-hole spacing are separate limits.
- Plated wire holes, NPTH pegs and connector shell slots close to vias.
- Clearance of new copper to other nets ≥ the fab minimum *for that copper weight*.

### Clean-up
- Dangling vias and track ends, zero-length segments, silk over pads and the board edge, overlapping same-net zones with the same priority.

### A board routed by script

A script-routed board arrives legal. Review it for what legality does not cover (found on the ground-up
Monolith board, 2026-11):

- Run the whole solver loop and compare with the last reviewed board of the same circuit, number by number
  (`pcb-layout/references/solver-verified-layout.md`). Signal tracks and vias of other nets are what damaged power
  paths there: a via in a pour neck, a short hop on a plane layer that closed the last gap to a bulk capacitor.
- Tidiness table (`hardware/Production/groundup/compare/tidy.py`): length over shortest tree, bends, staircase
  segments, vias, widths per net, width steps away from pads, off-angle segments. Then look at the worst ten
  nets in a picture. The owner will.
- Signal track on the ground-plane layers, in millimetres, and how many nets cross each slot.
- Nets that an earlier repair moved for a solver reason: are they still where the repair put them?
- "No part moved" and "power copper untouched" are checked with a diff of pad positions and of path
  resistances, not taken from the change description.

## Report format

- **Must fix / should fix / clean-up**, each with net, layer, coordinates, the measured value and a concrete fix. Example: "add B.Cu keep-out x 97.59–98.50, y 99.73–100.63".
- A "fixed since last rev" list that ticks off the previous report.
- Figures: a heat map of current density for each high-current path, before and after the proposed fix (see `pcb-copper-resistance`).
- Board figures go in the repo as markdown + PNG (`docs/reviews/<date>-<topic>/`). Outside reviewers can't open private chat-app links.
- Say what you couldn't run (DRC with the KiCad server down, for example).

## Pitfalls seen
- A box clipped too tight around a path in the solver gave 2.84 mΩ instead of the real 1.87 mΩ. Use the full net.
- At a 0.1 mm grid the solver bridged a 0.08 mm gap that doesn't conduct on the real board. Re-run gaps like that at 0.03 mm.
- The KiCad MCP's `open_board` / `refill_zones` rewrite the file. Use a copy, or the owner's KiCad shows "file changed on disk".
- The owner may object to loose wording ("via" vs "pad corner"). Be exact about which copper feature the error comes from.
