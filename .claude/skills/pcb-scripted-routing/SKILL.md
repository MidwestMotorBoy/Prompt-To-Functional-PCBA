---
name: pcb-scripted-routing
description: Route or re-route a KiCad board by program - a grid A* router that stays legal against real DRC, exact pad escapes, vias and pours handled correctly, a cleanup pass that redraws a net as one tree with few bends and one width, a tidiness measure that scores what a person sees, and the accept-or-revert loop around them. Use when writing, tuning or running an auto-router or a routing cleanup pass, when routed copper looks untidy (zigzags, width steps, needless vias), or when planning how to automate routing end to end.
---

# Scripted routing

What it took to route the 430-part, six-layer Monolith P0 board by program (2026-11-09 to 11), compare it with
the same board routed by hand, and then clean up what the owner's eye objected to. Layout reasoning (which layer,
return paths, hot loops) is in `pcb-layout`; the check loop that must follow every pass is in
`pcb-layout/references/solver-verified-layout.md`. This skill is about the router itself.

Tools: `hardware/Production/groundup/` (`router.py` the maze router, `handadd.py` spec-driven edits, `ml.py`
exact-clearance link search, `vsite.py` via site test, `tidynet.py` / `tidyall.py` cleanup pass, `runwidth.py`
one width per run, `dumpcu.py` / `dumpkeep.py` copper and keep-out dumps, `step.sh` / `finish.sh` edit + DRC) and
`compare/tidy.py` (tidiness measure). They were written for one board; section 8 says what is general.

## 1. The three verdicts a routed board has to pass

1. **Legal**: full-rule DRC with schematic parity, zero errors, zero unconnected. Necessary, cheap, and far
   from enough.
2. **Works**: the solver loop (path resistance on a fine grid, Kelvin taps, hot loops per capacitor, gate
   loops, field coupling, via currents). Four real faults on this board were legal. Three of them were made
   by *signal* tracks or vias damaging a power path they were not part of.
3. **Looks intended**: the owner opens it in KiCad and nothing makes them ask "why does this trace do that?".
   No rule and no solver scores this. On this board the first two verdicts were passed and the third failed
   within a minute: a gate net that zigzagged 37 mm between pads 16 mm apart, and tracks that "randomly switch
   size". Both were real faults of the method. **Measure it** (section 6) or it will not get fixed.

## 2. Architecture that worked

- **KiCad for truth, plain Python for search.** KiCad (pcbnew in Docker) loads the board, applies edits, refills
  zones, runs DRC and dumps copper to JSON: tracks, vias, zone fills as polygons, pads as polygons per layer,
  board outline, unplated holes, rule areas. The router and every analysis run on the JSON with numpy on the
  host. A search step that needs pcbnew is 100 times slower and cannot run in parallel.
- **Every change is a small spec file** (`delete this, add that, set this width`) applied by one script that
  also refills, runs DRC and dumps the copper again (`step.sh`). A pass can be replayed, and one bad step can
  be dropped without redoing the rest.
- **Accept or revert, per net.** A change is kept only when the real DRC shows nothing new and its score
  improved. Home-made clearance tests are for steering the search, never for the verdict.
- **Fixed copper is recorded by id** (hand-drawn power copper, Kelvin taps, gate drives), so later passes know
  what they may not touch.

## 3. Making a grid router legal

A 0.05 mm grid with 0.2 mm tracks and 0.15 mm clearance leaves no room for rounding. What went wrong, in the
order it was found:

| Symptom in real DRC | Cause | Fix |
|---|---|---|
| Clearance errors of a few microns against other tracks and vias | Obstacles rasterised and dilated: a disc comes out a cell small or large | Mark blocked cells by **exact distance** from the cell centre to each other-net segment and via (half width + clearance + own half width + 5 µm). Raster + dilation only for polygons (pads, pours), with a 30 µm margin |
| Tracks through an antenna keep-out, 0.1 mm from the board edge, beside unplated holes | The dump had no outline, holes or rule areas | Dump them (`dumpkeep.py`) and block them, with the project's own edge and hole rules |
| Clearance errors at a re-used via site | The router's vias have no pads on unused inner layers; a new via at the same site got pads on all | Give new vias the same setting (remove unused layers, keep start and end), and allow a layer change at an old site only to layers where a pad is legal |
| 0.1 mm stubs flagged | Under the board's minimum track width | Know the minimum (0.15 mm here) |
| A power pour in two pieces, an unconnected ground pad | A legal track cut the last bridge of a pour | Before accepting, estimate the fill after refill and refuse a route that raises the number of pieces of a power pour, or leaves a ground pad on a piece with no via. Section 5 |
| Pins at 0.4 to 0.5 mm pitch unreachable | The clearance halos of the neighbours cover every grid cell of the pin | Exact escapes: straight out along the pin, or keep the existing escape verbatim to the first grid node. The old router ends tracks **anywhere inside a pad**, not at its centre: start the walk from every track end inside the pad polygon |
| Vias re-netted after a width change | pcbnew propagates nets on load when a widened track overlaps a via of another net | Record nets before, restore after, let DRC see the short |
| Zone edge-clearance errors after a scripted refill | Refill artefact | Judge only the DRC of the saved file under the project's name |

Also: pad centres are rarely on the grid (join with a short stub inside the pad copper); two pads can share
one grid node as their first escape node (keep both escapes); old copper that runs straight from pad to pad
with no grid node on the way has to be kept as a link or the pad is unreachable.

## 4. Cost terms that carried weight

| Term | Value used | Effect |
|---|---|---|
| Bend | 0.1 mm per 45°, 0.4 mm per 90°, sharper forbidden | Without it a grid router staircases: 1120 segments under 0.2 mm on this board |
| Via | 2.5 mm (4 mm in the first router); 0.6× at an existing site | Fewer layer changes; re-use holes that are already drilled |
| Inner layer direction | off-direction steps cost more (relaxed Manhattan) | Kept crossings possible. Strict Manhattan could not finish this board |
| Outer layers | 1.6× to 1.8× | Outer layers stay for parts and escapes |
| Inside a power pour | 3×, and no new via in a pour on any layer | Signals cut planes only when nothing else is left |
| Near switching copper | 2.5× within 1 mm on the same layer, 2× within 0.6 mm on the layers next to it, no new via within 1 mm | Took signals over 10 mV per edge from 14 to 8 before any hand work. Every remaining hot spot was a via |
| Re-using the net's old copper | its length + 0.3 mm | Lets a re-route pass keep a good stretch without preferring it |

**Order beats cost.** Ground and layer-change vias before signals. Fan-out of dense ICs first. Short nets
before long ones (local links claim the space next to their pins; long nets can go round). Kelvin pairs and
gate drives by explicit construction before the general router runs.

**One net at a time is the ceiling.** With everything else fixed, a net can only take what is left. The
remaining detours on this board are nets that would be straight if two neighbours moved 0.2 mm. That needs
either rip-up of small groups routed together, or shove. Not built yet; see section 9.

## 5. Pours and planes

- A via cuts every layer. A track on a plane layer cuts that plane. Both are legal.
- Treat **power pours as costly, never as free** in every search, including the link search for hand repairs.
- After a candidate route, estimate the refilled pour: today's fill, plus the cuts of the net's old copper where
  nothing else blocks them (they heal), minus the new copper with clearance. For power pours and inner planes
  the number of pieces must not rise. For the stitched ground fill on outer layers a cut is normal; what must
  not happen is a piece that holds a ground pad and has no via of its own.
- The piece count is a screen, not a verdict. A neck that got 0.3 mm narrower passes it. Only the DC solver on
  a 0.05 mm grid and the hot-loop per-capacitor list see that.

## 6. Tidiness: measuring what a person sees

`compare/tidy.py` scores every net that is routed as tracks (nets with a real pour are left out; teardrops are
zones too, so "has a zone" is the wrong test, use fill area over 3 mm²):

| Number | Meaning | Hand-routed board | Script board before cleanup |
|---|---|---|---|
| Length ÷ shortest tree over the pads | 1.0 to 1.4 is a direct route with 45° corners | 1.20 | 1.54 |
| Nets over 1.5× / over 2× | The ones a person points at | 5 / 0 | 46 / 17 |
| Bends | Direction changes | 1044 | 2861 |
| Segments under 0.2 mm | Staircase steps | 243 | 1007 |
| Vias on signal nets | | 171 | 351 |
| Nets drawn in one width | | 128 | 72 |
| Places where two widths meet / of those, further than 1.6 mm from any pad of the net | A step at a pad is a pin-escape neck; one out in the run reads as random | 4 / 0 | 136 / 29 |
| Segments over 0.3 mm off the 45° grid | | 0 | 295 |

(The 144 nets that are routed as tracks on both boards.) Run it in every check loop and report it beside DRC.
The owner's rules read off his board: **one width per net** (0.2 mm for signals, gate drives included), narrower
only for the escape from a fine-pitch pin; every segment at a multiple of 45°; a track goes where it is going.

Two things the table shows that a per-net pass cannot repair:

- **The shortest trees themselves were longer.** Summed over the same 144 nets, the shortest tree across the pads
  is 1516 mm on the hand-placed board and 1937 mm on the script-placed one. 28 % of the extra track was decided
  at placement. Score a placement by this sum before routing it (`pcb-scripted-placement`).
- **Buses.** Drawn side by side (`sigpic.py`), the hand-routed board is a few bundles of parallel tracks in
  lanes, with open board between them. The script board is a web: every net found its own way. Signals that
  share a source and a destination (an I2C pair, a group of enables, the gauge's cell taps) should be routed
  as one bundle through one lane. Nothing here does that yet.

Where the untidiness came from:

- **Staircases and zigzags**: no bend cost, and nets routed late squeezed through what was left.
- **Wandering nets**: each connection of a multi-pad net was routed on its own, to the nearest copper of the
  net at that moment, by a router that rips and retries. The result is a chain of detours, not a tree.
- **Random width steps**: the widening pass raised every track of a class toward its class width and lowered
  *single segments* where DRC objected. Legal, and it reads as random. Width is a property of a run, not of a
  segment.
- **Off-angle segments**: escapes from pads that end anywhere inside the pad, joined to the grid by whatever
  angle resulted.

## 7. The cleanup pass

`tidynet.py` redraws one net; `tidyall.py` runs it over the board; `runwidth.py` fixes widths on what is left.

One net (`tidy()`):

1. Take the net's pads in shortest-tree order. Everything else on the board is fixed.
2. Grid aligned to the old router's nodes, so old via sites and old track nodes are grid points.
3. A* with direction state from each pad to the tree built so far (bend, via, pour and switching-copper costs
   of section 4). One width for the whole net: 0.2 mm, and if that fails, 0.15 mm for the whole net.
4. Pads the grid cannot reach leave along their old escape to the first grid node, kept as drawn.
5. Kept stretches are pulled tight inside copper already known to be legal (the union of the net's old and new
   copper), and collinear segments are merged.
6. Refuse the route if a pad cannot be joined or a pour would fall apart (section 5).

Board (`tidyall.py`): plain signal nets only (default class, no pour, not switching, not a sense pair, not RF
or USB data, not drawn wide on purpose, no track in a ground plane), short nets first, two sweeps. A new route
is kept only if it has no more vias, is at most 5 % longer, and scores at least 3 % better on
`length + 2.5 mm per via + 0.15 mm per segment + 1 mm per extra width`. Then one spec for all kept nets, the
real DRC, and the full solver loop, because a tidier signal can sit closer to a switch node than the untidy
one did.

**Protect what a solver put there.** The first whole-board run redrew a slow enable net whose route had been
moved by hand in an earlier pass for two reasons no rule knows: to keep it away from a buck's switch node and
to keep a plane gap open between that buck and its bulk capacitor. The tidier route was legal, shorter, and
took the net from 1.7 to 18 mV per switching edge and the capacitor's loop from 0.95 to 1.11 nH. The check loop
caught both and the net went back. Keep a list of protected nets with the reason for each, written when the
repair is made, and have every later pass read it. A cleanup pass optimises what it can measure; a repair
exists because of something it cannot.

Widths (`runwidth.py`): a run is a chain of segments on one layer between pads, vias and junctions. Signal,
gate and Kelvin runs take their narrowest width over the whole run, with a narrower escape allowed at a pad.
Power runs take the widest width that 60 % of their length already has, with one neck width for the rest. It
only narrows, so the result is legal if the input was.

With `--palette` every width of a mixed-width net is then rounded down to a short list (0.8, 0.5, 0.3, 0.2,
0.15 mm here), so a net shows a few widths that mean something and not seven. Ground and high-current stubs
are left as drawn.

Result on this board (54 nets redrawn, 225 segments re-widthed, same 144 nets as the table in section 6):
length over shortest tree 1.54 to 1.46, bends 2861 to 1837, segments under 0.2 mm 1007 to 456, signal vias 351
to 310, width changes away from a pad 29 to 0, nets over 2× 17 to 12. DRC stayed at 0 errors. Better on every
line and still well short of the hand-routed board (1.20, 1044, 243, 171): what is left is placement, bundles
and the nets this pass does not touch (section 9). The record is in
`hardware/Production/groundup/README.md`, cleanup pass section.

## 8. What is general and what is this board's

General: the dumps, the spec-and-step loop, the exact-distance marking, the escape handling, the pour check,
the tidiness measure, the cleanup pass, the width pass.

This board's, to be replaced by data from the schematic or the project: net-class names and widths
(`tidynet.ncls`, read from the `.kicad_pro`), the regular expressions that name plane nets, switching nets and
nets to leave alone, the layer list (F, In2, In3, B route; In1, In4 are ground planes), via size 0.45/0.3 mm,
clearances 0.15 mm (0.25 mm between high-current and signal), edge and hole margins, minimum track 0.15 mm.

## 9. What to build next (untested)

In the order that looks most valuable for an auto-router:

1. **Block first** (the owner's own method): finish each subsection (an IC with its decoupling, feedback,
   sense filter, gate drives, local returns) before any link between subsections; each finished block declares
   where its signals leave and on which layer. Routing between blocks then starts from declared exits, and
   placement reserves the lanes between them.
2. **Groups instead of single nets**: rip up a net together with the two or three neighbours that box it in,
   route them in several orders, keep the best total score. The stand-in for push-and-shove.
3. **Shove inside clearance**: slide a neighbour's segment or via sideways where its own clearances allow it.
4. **Bundles**: group nets that share both ends, plan one lane for the group at placement, route the group as
   parallel tracks at minimum pitch.
5. **Straight escapes by construction**: for every fine-pitch pin, generate the escape along the pin axis to the
   first free grid node and test it with the real DRC once, before any routing. Removes the off-angle
   segments and the "anywhere in the pad" ends.
6. **Many versions of one block, scored by the solvers** (`pcb-loop-and-coupling-solvers`): gate-drive pairs,
   hot-loop capacitor groups, feedback dividers.
7. **Constraints from the schematic**, not from regular expressions: which nets switch and how far, which pairs
   are Kelvin, which pads close which loop, which parts are fixed. See `pcb-proto-flow`.
8. **Speed**: the cleanup pass takes about 15 minutes for 94 nets in single-threaded Python. Nets whose search
   boxes do not overlap can run in parallel; the inner loop wants numba or a compiled core.

## 10. Working with the board's owner

The loop that produced every improvement above: the owner states a rule or points at a picture; it becomes a
cost, a check or an order change; it is tested on one net or one block; the before/after picture and the
numbers go back; what wins is written here. Send a picture and the tidiness table after every pass. Do not
propose that the owner routes part of the board by hand when the goal is an automatic flow.
