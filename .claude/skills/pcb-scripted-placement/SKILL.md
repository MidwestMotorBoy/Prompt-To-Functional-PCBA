---
name: pcb-scripted-placement
description: Place the parts of a KiCad board by script - a footprint database built from the board, fixed parts from the enclosure, power stages from explicit coordinates, support parts by a greedy placer with per-pad targets, repeated blocks by translation, courtyard and enclosure checks after every change. Use when writing or running an auto-placer, re-placing a board from scratch, moving a block, or when a routing failure traces back to where a part sits.
---

# Scripted part placement

Placement decides the hot loops, the Kelvin taps, the escapes and the signal corridors. A router can only spoil
them. This skill is the method that placed the 430-part Monolith P0 board a second time by script (2026-11-09,
tools in `hardware/Production/groundup/`: `placelib.py`, `fpdb.py`, `place*.py`, `run.py`, `apply_place.py`,
`mechcheck.py`, `placescan.py`). The layout reasoning itself (what goes next to what) is in the `pcb-layout`
skill, `references/placement.md`; read that first. Everything below is about doing it by program.

One board, modelled and not built. Treat the numbers as examples.

## 1. What worked

**Placement is data, the board file is output.** Keep `placement.json` (`{ref: [x, y, rotation]}`) as the thing
you edit, and write it into the board with one script (`apply_place.py`). The placement can then be diffed,
replayed, checked without KiCad, and a block can be moved by changing one number.

**A footprint database built from the board, not from the libraries.** `dump.py` writes every footprint's pads
(position, size, net, pin function), courtyard box, side, lock state and sheet to JSON. `fpdb.py` turns that
into local pad coordinates per reference, so any candidate position gives pad positions in world coordinates
with plain numpy and no KiCad in the loop. KiCad's rotation is clockwise-positive with y down:
`dx = lx·cos + ly·sin`, `dy = −lx·sin + ly·cos`. Get this wrong and every rotated part is mirrored.

**Three kinds of parts, three methods.**

| Kind | Method | Why |
|---|---|---|
| Fixed by the enclosure or by choice (connectors, holes, wire pads, antenna module, sensors, tall parts, the back side) | Read from the existing board, locked, never moved | They define compatibility. Decide this list first and write it down |
| Power stage: FETs, inductor, input and output capacitors, sense resistors, controller | Explicit coordinates in a short script, worked out by a person or an agent looking at a rendered picture | The geometry is the design. A cost function does not find "100 nF across the FET pads with ground vias beside it" |
| Everything else: decoupling, dividers, filters, pull-ups, test points | Greedy placer, one part at a time, with **per-pad targets** | Hundreds of parts whose right place is "at the pin it serves" |

**The greedy placer** (`auto()` in `placelib.py`): for one part, scan a 0.05 mm grid of positions within a radius
(4, then 8, then 14 mm) and the four rotations; drop every position whose courtyard overlaps another courtyard, a
keep-out, an enclosure limit or a reserved via site; score the rest by the summed Manhattan distance from each of
its pads to the nearest pad of the same net on parts already placed; take the minimum. The things that made it
useful:

- **Explicit pin targets** (`pins={'1': 'U403.14', '2': 'U403.13'}`) for every part whose job is at one pin. The
  automatic target (nearest same-net pad) is right for a pull-up and wrong for a filter capacitor on a net with
  six pads.
- **Plane nets are ignored** as targets (GND, the supply planes) unless named. Otherwise every decoupling
  capacitor is "0 mm from ground" everywhere and the score is flat.
- **Order is the algorithm.** Place in the order of importance at each IC: the capacitor of the noisiest pin
  first, then feedback and sense parts, then the rest. The first part gets the best spot.
- **Clear bands round dense ICs** (`RINGS`): 0.5 to 1.2 mm round every IC with fine pitch stays free of parts so
  the pins can escape. Without it the placer fills the fan-out ring with 0402s, and the router then fails at
  exactly those pins.
- **Reserved via sites** (`keep_vias.json`): spots where a layer-change or ground via must go are blocked for
  parts before placement starts.
- **Two passes.** Hand-placed parts are recorded on the first run and reserved on the second, so automatic parts
  never take a spot a later explicit `put()` needs.

**Repeated blocks are placed once and translated.** Port 2 is port 1 shifted in x. While port 1 is being placed,
the already-placed parts are mirrored back as "ghost" boxes, so no port 1 spot is chosen whose port 2 copy would
land on something.

**Check after every change, without KiCad.** `check()`: courtyard overlaps per side, enclosure limits (edge
lips, pegs, notches as plain boxes and circles), parts not placed yet. `show()`: a picture with pad numbers and
net names. Then DRC with schematic parity once the placement is in the board.

**Mechanical fit without a STEP export** (`mechcheck.py`): the mechanical model holds one mesh per footprint
from an earlier STEP export. Each mesh is moved rigidly from its old position to the new one and the enclosure's
own check function runs on the result. Seconds, and it runs after every placement change.

## 2. What went wrong, and the rule that follows

| What happened | Rule |
|---|---|
| No lane was kept for slow signals that had to pass between the two power stages. Two fix passes later 258 mm of signal track was still cut into a ground plane, because the stages had closed every other route | **Reserve signal corridors and their via sites at placement**, as blocked boxes, before the support parts go in. List every net that crosses from one block to another and give each a lane on a signal layer |
| The 100 nF capacitors sat 1.3 to 2.3 mm from the FET pads: 0.78 to 0.93 nH of board loop. At the pads with ground vias beside them: 0.37 to 0.39 nH | Hot-loop capacitors belong to the power stage's explicit coordinates, and their ground vias are placed with them |
| Ground vias were added after signal routing and displaced routes | Ground and layer-change vias exist before the first signal is routed (reserve the sites at placement) |
| A feedback divider resistor 5 mm from its pin gave a net that picked up 204 mV per switching edge. Moving the resistor fixed it; no re-route did | When a signal fails a coupling or length check twice, move the part. Then diff pad positions before writing "no part moved" |
| The bulk capacitors of a PD controller ended up 4 mm from its pins | Give big parts explicit targets too; the greedy score lets a large courtyard lose to three 0402s |
| A router failure at one IC, repeated however the router was tuned | A connection that fails with nothing else routed is a placement fault. Map failures to parts; re-orient the part so each side faces where its nets go |
| Summed over the 144 signal nets, the shortest tree across each net's pads came to 1937 mm. On the hand-placed board the same nets need 1516 mm. That 28 % was paid again in track length, vias and crossings | Compute the sum of shortest trees for every candidate placement and compare. It takes a second and needs no routing |
| On the hand-routed board, groups of signals run as parallel bundles in a few lanes. The script placement left no lanes, so every net found its own way and the lower half of the board became a web | Plan lanes for bundles (bus pairs, enables, cell taps) at placement, with their via fields at both ends |
| 14 reference designators could not be shown | Silkscreen room is a placement cost. Count it, or decide early that passives are unlabelled |

## 3. Method for a new board

1. Dump the board (or a board freshly updated from the schematic) to JSON. Build the footprint database.
2. Write the fixed list. Lock those parts.
3. Describe the enclosure limits as boxes, circles and height zones in one place.
4. Floorplan by zones in power-flow order (see `placement.md`). Draw the zones on a picture and get the owner's
   yes before placing anything.
5. Reserve: fan-out bands round dense ICs, via sites for power layer changes and ground returns, signal
   corridors between blocks.
6. Power stages from explicit coordinates. Render, look, adjust. Run the hot-loop solver on the pours as soon as
   they exist (`pcb-loop-and-coupling-solvers`), before any signal is routed.
7. Support parts with the greedy placer, IC by IC, pin targets given, in order of importance.
8. Translate repeated blocks.
9. Check: overlaps, enclosure, mechanical fit, parity. Render both sides.
10. Rough routability: sum of shortest-tree lengths per net and a count of nets that cross each block boundary.
    Compare two candidate placements by these before routing either.

## 4. Where an automatic placer could go next (untested)

These are the open ideas from this work. Nothing here has been tried.

- **Score a placement by the solvers, not by wire length.** Loop inductance of each hot loop on a quick pour,
  and the tidiness numbers of a fast trial route (`pcb-scripted-routing`), are the scores that matched what the
  board's owner cared about.
- **Block templates.** A buck stage, a charger stage, a QFN with its decoupling: place once, score, store as a
  block with declared signal exits (side and layer). Placement then becomes arranging blocks and aligning exits.
- **Derive the pin targets from the schematic.** Pin function and net topology say which capacitor serves which
  pin (the one whose other pin is ground and whose net has two or three pads). Today the targets are typed.
- **Swap and nudge after routing.** Use the router's failures and worst detours as the signal for moving a part
  0.5 mm or rotating it 180 degrees, then re-route only the nets of that part.
