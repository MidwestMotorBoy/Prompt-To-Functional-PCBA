# Solver-verified layout

A rule check proves that copper is legal. It does not prove that the board works. This file is the check loop and
the order of work that came out of laying out the Monolith P0 board a second time by script (2026-11-09/10, about
18 hours, three versions, each compared with the hand-routed board by the same solvers). Read it before any
scripted routing pass, before any hand edit near power copper, and when reviewing a board somebody else routed.

Everything here is modelled, not measured, and it comes from one board. Treat the numbers as examples and the
method as the reusable part.

## 1. What the rule check missed

Four real faults passed DRC, schematic parity, the open-connection count and the plane-island check. Each was
found by a solver, never by a rule.

| Fault | What made it | What the rules saw | What showed it |
|---|---|---|---|
| Battery bus cut: 2.6 to 27.8 mΩ | Three hand-drawn gate and switch-node tracks across a B.Cu power pour | Legal. The net stayed in one piece through other layers | Copper path solver |
| Battery sense taps +2.2 and +2.7 % | Four power vias added beside the Kelvin taps | Legal | Kelvin solver, 0.05 mm grid |
| Battery bus pinched: 2.6 to 4.5 mΩ | One signal via in a 0.85 mm neck of a power pour | Legal | Copper path solver on the 0.05 mm grid only. The 0.1 mm grid bridged the cut-out |
| Bulk capacitor cut off from its buck | A 4 mm signal hop on the power-plane layer closed the last gap between two via cut-outs | Legal. The net stayed in one piece through other layers | Hot-loop solver: that capacitor's loop went from 1.45 nH to thousands of nH |

The pattern: **a signal track or via, legal in itself, damages a power path it is not part of.** The check you run
on the signal you just routed (clearance, coupling) cannot see it. Only a check of the power path can.

## 2. The check loop

Run this after every routing pass, and after every hand edit within a few millimetres of power copper. One
changed via is enough to need it.

| Step | Check | Catches | Time here |
|---|---|---|---|
| 1 | Full-rule DRC with parity, on a copy named like the project (`kicad-practice.md` §7) | Shorts, clearances, opens | 10 s |
| 2 | Plane islands: every plane net is one group over all layers | A pour cut into pieces that no pad happens to sit on | 10 s |
| 3 | Plane pieces per layer, drawn in different colours | A plane that is one net but two pieces on its own layer (fault 4). Step 2 does not see this | 5 s |
| 4 | Copper path resistance of every power path on the **fine** grid | Cut or pinched pours and necks (faults 1 and 3) | 90 s |
| 5 | Kelvin tap error of every sense resistor, fine grid | Taps that read plane drop (fault 2) | 2 min |
| 6 | Hot-loop inductance, and the **per-capacitor list** compared with the run before | A capacitor that dropped out of its loop; a loop that grew | 5 to 8 min |
| 7 | Gate-loop inductance | A drive routed away from its return | 8 min |
| 8 | Coupling from switching copper into every signal, then again with a location printout for each flagged net | Signals beside switch nodes; shows the via or stretch that picks it up | 4 min |
| 9 | Per-via current on every power path | A layer change carried by too few vias | 1 min |
| 10 | Mechanical fit, if any part moved | Parts in keep-outs | 1 min |
| 11 | Tidiness table: length over shortest tree, bends, short segments, vias, widths per net, width changes in mid-run, off-angle segments (`routing-discipline.md` §7) | Routes that are legal and work but wander, staircase or change width; the first thing the owner sees | 5 s |

Steps 1 to 5 and 11 are cheap enough to run after every single edit. Steps 6 to 9 run after each pass and once more on
the final file. **Any repair is an edit: run the loop again after it.** Both faults of the second fix pass were
introduced by signal re-routes and one of them was found only because the full set ran one more time.

How to read the results:

- Compare with the previous run, not with a limit. A number that moved and should not have is the finding.
  "Power copper was not touched" is a claim to prove: path resistances and loop inductances must match the run
  before to the last digit that matters.
- A loop of thousands of nH is not a bad loop. It means the solver box does not contain a closed path: either
  the box setting cut the return (a solver artifact) or the copper really is cut. Find out which before moving on.
- When a solver result is going to be reported as "unchanged", check that it was computed on the current file.
  A solver that resumes from an earlier result file will hand back numbers of the board before the edit.
- Before writing "no part moved", diff the pad positions of the two board files.

## 3. Grid size matters

The copper solver rasterises one net. At 0.1 mm a via cut-out in a narrow neck, or a 0.08 mm gap, still conducts
in the model. Use 0.1 mm for the loss budget and **0.05 mm (0.03 mm for gaps under 0.15 mm) whenever a via or track
was added near a pour neck, and always for Kelvin taps.** The coarse grid reports tens of percent of false tap
error and hides real pinches.

## 4. Rules the router and its helpers must know

- **Pours are not free space.** A link search that treats plane and pour copper as passable (so that it can
  route signals through a plane layer) will also put a via into the only neck of a power pour. Test every new
  via and every new track on a power layer against the pour it lands in, not only against other tracks.
- **A via cuts every layer.** A signal via between two existing cut-outs can close the gap between them on a
  plane layer the signal never uses.
- **Ground vias before signals.** Place the return vias of the power stages and the layer-change vias of the
  power paths first. Signals routed first take the sites.
- **Give the router a cost for running near switching copper**, on the same layer and on the layers above and
  below. Without it the shortest path for a slow signal is across a power stage.
- **Coupling hot spots are almost always vias.** In this layout every signal that took more than 10 mV from a
  switch-node edge did so at a via barrel within about 1 mm of switching copper, or on a short stretch on the
  layer next to it. Moving that via 0.3 to 1 mm fixed each one. Find it with the location printout, do not
  re-route the net.
- **A stacked sense pair** (plus on one inner layer directly over minus on the next) encloses almost no plan
  area. It took one input pair from 40 to 7 mm² and another from 13 to 0.6 mm². Check afterwards that neither
  line lies over a track that was cut into the plane beneath it.
- **The 100 nF capacitor at the FET decides the hot loop.** Pads at the FET pads with ground vias beside them
  gave 0.37 to 0.39 nH of board loop; 1.3 to 2.3 mm further away gave 0.78 to 0.93 nH.
- **A high-side gate drive follows its switch-node return**, beside it on the same layer or directly over it on
  the next. A drive that took the free way round its controller was 14 nH; beside the return it was 6 nH.

## 5. Order of work for a scripted layout

1. Fixed parts from the mechanical model, locked: outline, holes, connectors, pads for wires, tall parts.
2. Placement, checked against the enclosure after every change. **Reserve the signal corridors now**: every
   slow signal that has to pass between two power stages needs a lane and a via site on a signal layer. This
   layout did not reserve them, and 258 mm of signal track ended up cut into a ground plane, crossed by 28 other
   nets. Two passes later that was still the one thing it could not buy back, because the stages had closed
   every other route.
3. Power copper and Kelvin taps, drawn from explicit coordinates net by net. Run steps 1 to 5 of the loop.
4. Ground and layer-change vias.
5. Hot-loop capacitors and gate drives by hand. Run steps 6 and 7.
6. The router for everything else, with the switching-copper cost. Pass after pass, each with a picture and the
   count of open connections.
7. What the router cannot close: one link at a time with an exact-clearance search, each followed by steps 1 to 4.
8. The whole loop on the finished file. Fix, and run it again.

Keep every hand change as a small spec file (delete this, add that) applied by one script that also runs steps 1
to 3. A pass can then be replayed, and a bad step can be dropped without redoing the ones after it.

Look at the board after every pass. A scripted layout is only seen through pictures the script makes, so make
them: whole board per layer, and a crop of each spot that was edited. Where a KiCad window or a KiCad MCP is
available, use it as a second, independent view.

## 6. The tools in this repository

They live in `hardware/Production/groundup/` (layout and checks) and `hardware/Production/groundup/compare/`
(solvers). Every solver reads the board from the `PCB` environment variable and tags its output with `TAG`, so
several board files go through the same code and can be compared.

| Check | Tool |
|---|---|
| Edit + DRC + plane islands + copper dump in one step | `step.sh <in> <out> <spec.json>` with `handadd.py`, `isl.py`, `dumpcu.py` |
| Plane pieces per layer | `piecepic.py` |
| Exact-clearance link search, via site test | `ml.py`, `vsite.py` |
| Where a track could change layer unchanged, and what blocks it | `lfree.py` |
| Power path quick check on the fine grid | `RES=0.05 python compare/k/pk.py` |
| Path resistance, loss tiles, via currents, Kelvin taps | `compare/k/lossmap.py`, `viacur.py`, `kelvin.py` (method: the `pcb-copper-resistance` skill) |
| Hot loops and gate loops (3-D partial inductance) | `compare/run_hot2.py`, `run_gate3.py` |
| Coupling from switching copper (3-D electrostatic) | `compare/coup.py`, `coup_post.py`; `WHERE='<net suffix>'` prints where on the victim the charge lands |
| Sense-pair routing and enclosed area | `compare/senspair.py` |
| Tracks cut into a ground plane and what crosses them | `in4fig.py`, `in4cross.py` |
| Tidiness of every track-routed net, and a table over several boards | `compare/tidy.py`, `compare/tidycmp.py` |
| Redraw a net as one tree, few bends, one width; the same over the board with accept-or-revert | `tidynet.py`, `tidyall.py` (need `dumpkeep.py` for outline, holes and rule areas) |
| One width per run | `runwidth.py` |
| Before / after pictures of one net, or of all signal tracks of several boards | `netpic.py`, `sigpic.py` |
| Everything on one more board file | `compare/runfix.sh <board> <tag>` |

**They are not turnkey for another board.** The physics is general, the tables are Monolith's. Before using them
elsewhere, fill in:

- the stack-up heights and copper thicknesses (`compare/peec.py`, `compare/coup.py`, `compare/k/solve.py`);
- the hot loops: supply net, FET or IC pads, capacitors in reach (`compare/run_all_defs.py`, `run_hot2.py`);
- the gate loops: driver pin, gate resistor, FET, drive and return nets (`compare/run_all_defs.py`);
- the power paths and their source and sink pads, and the sense resistors with their tap nets
  (`compare/k/lossmap.py`, `viacur.py`, `kelvin.py`, `compare/senspair.py`);
- the switching nets with their voltage swing, and the rules that sort victim nets into classes
  (`compare/coup.py`, `compare/victims.py`);
- board extents and any zones that are counted (`compare/custats.py`, `in4cross.py`).

Check each tool against a known answer before trusting it on a new board (an earlier study, a vendor EVM, a
hand calculation of one simple path).

The placement scripts, the hand-drawn power copper and the hand specs in `hand*/` are coordinates for this one
board and are a record, not a library. The maze router is general in principle, but used without the solver
loop it produced a board that was legal and clearly worse than the hand-routed one on every fast-edge measure.

Limits met in a 4-core, 14 GB cloud container: the dense inductance matrix needs about 8 bytes × branches², a
run above roughly 27 000 branches is killed without a message, and two large loops cannot run side by side.

## 7. A third verdict: does it look intended

Added 2026-11-11. The board that came out of sections 1 to 6 passed DRC and every solver. Its owner opened it in
KiCad and within a minute pointed at a gate net that zigzagged ("this trace area makes no sense") and at tracks
that "randomly switch size". Measured against his hand-routed board on the 144 signal nets both have: length
over shortest tree 1.54 against 1.20, 2861 bends against 1044, 136 places where a track changes width
against 4, 295 segments off the 45° grid against none.

No rule and no solver sees this, so it is a check of its own (step 11) with its own repair pass. The causes, the
measure and the cleanup pass are in the `pcb-scripted-routing` skill, sections 6 and 7. The cleanup pass moves
signal copper, so the whole loop runs again after it. It did find something: one redrawn enable net, whose old
route was a hand repair from the pass before, went from 1.7 to 18 mV per switching edge and took a bulk
capacitor's loop from 0.95 to 1.11 nH. That net was put back. **Nets that were repaired for a solver reason
need a protected list that later passes read.**

## 8. Methods to test next

Nothing in this section has been tried. Each entry is a method the board's owner or a review proposed. When a
run tests one, move it into the sections above with its picture and its numbers before and after, or delete it
with the reason. Test on one block first (one charger stage, one buck), not on the whole board.

- **Block first, then the links between blocks** (Logan, 2026-11-10; his hand method, done with KiCad's
  push-and-shove router and a few tear-ups afterwards). Finish each subsection as far as it goes: the IC with its
  decoupling, feedback divider, sense filter, gate drives and local returns. Only then route the connections
  between subsections. This matches §5 steps 5 and 6 in spirit, but §5 hand-finished only the hot-loop
  capacitors and gate drives and gave every other link to the board-wide router, which is where slow signals
  ended up crossing power stages. Three additions for a scripted version:
  - a block mode in the router that routes one subsection alone and runs steps 4 to 8 of the loop on that block;
  - each finished block lists where its outgoing signals leave and on which layer, which is the corridor
    reservation of §5 step 2 made concrete;
  - an automatic tear-up in place of push-and-shove: slide a track or via sideways inside its clearance where
    that frees the lane, rip up and re-route where it does not, and run steps 1 to 5 after each one.
- **Many versions of one block, scored by the solvers.** A script can route a feedback divider, a gate drive or
  a hot-loop capacitor group many ways and keep the version with the best loop inductance, coupling and tap
  error. Identical circuits (the two charger stages) can share the winning block.
