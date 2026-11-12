# Stage 6: floorplan (work in progress)

`floorplan.py` holds the intent file (board box, fixed parts, one region per block or block section and side,
lanes) and its demand score. `place_sa.py` is a first generic placer driven by the intent file.

## What the first measurements say (2026-11-11, Monolith hand board against the scripted board)

Signal demand is the half-perimeter of every net with fewer than 12 pads, at pad level.

| | Hand board | Scripted board |
|---|---|---|
| Detailed placement, half-perimeter | 2064 mm | 2508 mm (+21 %) |
| Floorplan only, 5 sheet regions (every part at its region centre) | 1007 mm | 1027 mm (+2 %) |
| Floorplan only, 29 section regions | 1719 mm | 1786 mm (+4 %) |
| Nets inside one section | 69 nets, 282 mm | 69 nets, 475 mm (+68 %) |
| Nets between sections | 92 nets, 1782 mm | 92 nets, 2033 mm (+14 %) |
| Section region area, summed | 8025 mm2 | 9009 mm2 (+12 %) |

1. The two boards have almost the same floorplan. Only 9 parts of the scripted board sit outside the hand
   board's sheet regions. Where the blocks go does not explain the scripted board's extra wiring.
2. The difference is inside the blocks: how tightly each section is packed, and which way its pins face. Nets
   that stay inside one section are 68 % longer on the scripted board.
3. So a block-level floorplan cannot be accepted on its own score. The score has to be taken on the placed
   parts, and the intent has to reach down to sections and to pins ("this capacitor at that pin").

## First generic placer: flat annealing is not enough

`place_sa.py` anneals every part inside the hand board's own section regions, from a random start, with a
spring from each decoupling capacitor to the pin it serves. Two runs of 2 million moves (about 9 minutes each):
2677 and 3104 mm, with 1 to 7 mm2 of overlap left and capacitors on average 10 mm from the pin they serve.
That is worse than the scripted board (2508 mm) and far from the hand board (2064 mm), and the two runs differ
by 16 %. Moving one part at a time cannot build a tight section.

This agrees with the floorplanning research (`/mnt/project-files/floorplan-research/`): pack blocks with a
solver, place each power stage from a template scored by the loop solver, place support parts greedily at
pin targets, and accept on a trial route. Next step: place section by section (the part with most pins first,
then its served parts at their pins), then pack the sections, and measure against the same two boards.

## Section placer: clusters at pin targets, then packing (same day)

`place_sections.py` builds each of the 29 sections as a tight cluster on its own: main part first, then always
the part most connected to what is placed, at the spot and rotation with the least wiring to placed pads, with
a strong pull from a decoupling capacitor to the pin it serves. 7 seconds for the board. `place_pack.py` then
moves the clusters as rigid pieces (annealing over about 30 pieces) and finishes with small single-part moves.
Connectors, holes and test points stay where the hand board has them. Nothing else is taken from the hand board.

| | Signal half-perimeter | Overlap |
|---|---|---|
| Hand board | 2064 mm | |
| Scripted board (the Battery-Bank flow) | 2508 mm | |
| Flat annealing, two runs | 2677, 3104 mm | 1 to 7 mm2 |
| Section placer, clusters packed, three runs | 1949 to 2185 mm | under 1 mm2 |
| Section placer after refinement, three runs | 1714, 1817, 1907 mm | 0 |

Inside sections: 170 mm of wiring against 242 mm on the hand board; served capacitors 228 mm from their pins in
total against 440 mm. About 15 minutes per run on one core.

Read this with care:

- It is wirelength only. The placer does not know hot loops, gate loops, Kelvin pairs, heat, which nets are
  noisy, or the enclosure keep-outs (pegs, lips), and bodies are pad boxes plus 0.1 mm, not courtyards. A real
  board needs more room than this, so the true gap to the hand board is smaller than the table shows.
- What it does show: placing section by section at pin targets and then packing gets a generic placer, with no
  board-specific coordinates, to the hand board's wiring demand. The flat approach could not.
- Next: the intent statements from the floorplanning research (near, order, keep-apart, lanes) with a compiler
  that checks them against the netlist; courtyards and keep-outs; crossing and hot-loop terms in the score;
  power-stage templates scored by the loop solver; then the trial route as the acceptance gate.

## Intent statements, and a placer that obeys them (same day)

`intent.py` holds the statements from the floorplanning research: `near`, `keepapart`, `order`, `kelvin`, `fixed`,
`lanes`. `derive` writes the ones that follow by rule from the circuit code (for Monolith: 106 near from the
served pins and hot loops, 6 keep-apart from switching and sensitive nets, 4 Kelvin pairs). `validate` rejects any
statement that names a part, pad or net the netlist does not have. `check` measures them on a placed board.
`place_sections.py` and `place_pack.py` take the file and use the statements as pulls and cost terms.

| Placement | Statements that hold (of 112) | Signal half-perimeter | Overlap left |
|---|---|---|---|
| Hand board | 72 | 2064 mm | 0 |
| Scripted board | 74 | 2508 mm | 0 |
| Section placer, wirelength only (run 2) | 48 | 1714 mm | 0 |
| Section placer with the statements, three runs | 103, 103, 101 | 1983, 2292, 1863 mm | 1 to 2 mm2 |

- Wirelength alone made a placement that looked best and broke more than half the statements. With the
  statements in the cost it keeps about 92 % of them at roughly the hand board's wiring demand.
- The limits are first guesses (2 mm for the first hot-loop capacitor, 2.5 mm for a served pin, 5 mm for bulk,
  centre to centre). The hand board fails 40 of them, mostly large capacitors that cannot physically sit 2.5 mm
  from a pin, so the limits need to scale with part size before the count means much as a pass mark.
- 1 to 2 mm2 of overlap remains after 300 000 refinement moves; a legalising pass is still needed.
- Still wirelength plus statements only: pad boxes for bodies, no enclosure keep-outs, no crossing count, no loop
  solver in the loop.

Update: `near` is now measured from the target pad's centre to the nearest pad edge of the part, so a large
capacitor is not penalised for its own size, with limits 1.5 mm (first hot-loop capacitor), 2 mm (served pin) and
4 mm (bulk). On that measure: hand board 69 of 112, scripted 69, placer with statements 92 to 93, wirelength-only
placer 48. The hand board's misses are of two kinds: near misses of a few tenths of a millimetre, and bulk
capacitors that the circuit code declares as serving a FET pin but that sit 6 to 8 mm away by design. The code's
`serves` does not yet say "bulk" or "at the pin", so the limit classes need the owner's judgement or a rule from
capacitor value before the count can be a pass mark.

Update 2: limits by capacitor value (up to 1 uF 2 mm, up to 10 uF 4 mm, larger 10 mm; first hot-loop capacitor
1.5 mm), offered to the owner as the default with an override in the circuit code. On that rule: hand board 92
of 112, scripted board 84, placer with statements 97 to 99 (it was run against the earlier limits). This is the
first version of the check that ranks the hand board above the scripted one.

## With real courtyards and enclosure keep-outs (same day)

`dump_board.py` now writes each footprint's courtyard and the board's keep-out areas; the placers use courtyards
as bodies and count a no-footprint keep-out on a part's side as overlap. The last quarter of refinement weighs
overlap far above wiring.

| Placement | Statements that hold (of 112) | Signal half-perimeter | Overlap left | Off board |
|---|---|---|---|---|
| Hand board | 92 | 2064 mm | 0 | 0 |
| Scripted board | 84 | 2508 mm | 0 | 0 |
| Section placer, three runs | 104, 102, 99 | 2629, 2602, 2485 mm | 14.6, 0.8, 1.0 mm2 | 1.6, 0.5, 0 mm |

The earlier lead over the hand board was the pad-box bodies, as warned. With real courtyards the board is
nearly full (cluster boxes add up to 3313 mm2 on a 3212 mm2 board face), the placer lands at the scripted
board's wiring demand, 20 % above the hand board, and it is not yet legal: a little overlap is left in every run.
It does hold more of the intent statements than either board.

What this says about the next step: on a board this dense the packing is the hard part, not the sections.
Rigid rectangular clusters waste the room a person saves by interleaving sections and using the back side.
Options, cheapest first: let clusters deform during packing (parts keep their pulls but are free), a proper
legaliser (shift along the least-crowded direction), and many more runs with selection, since runs are cheap.

## Faster refinement and a repair step: first legal placements (same day)

Refinement now recomputes only what the moved part touches (about 0.2 ms a move, 12 times faster), so a run
does 2.5 million single-part moves. A repair step then moves any part that still overlaps to the best free spot
within 8 mm. `overlaps.py` lists courtyard overlaps, keep-out hits and parts off the board for any placement.
About 15 minutes a run on one core.

| Placement | Legal | Statements that hold (of 112) | Signal half-perimeter |
|---|---|---|---|
| Hand board | yes | 92 | 2064 mm |
| Scripted board | yes | 84 | 2508 mm |
| Run 1 | no: inductor L401 on a mounting hole | 107 | 2522 mm |
| Run 2 | no: radio module U301 on a test point | 106 | 2461 mm |
| Run 3 | yes | 105 | 2292 mm |
| Run 4 | yes | 102 | 2522 mm |

"Legal" means no courtyard overlap between a movable part and anything else, nothing in a no-footprint keep-out,
nothing off the board. (The hand board's own fixed connectors touch by a few hundredths of a millimetre in this
box measure; those are ignored for every row.)

- Two of four runs are legal. The two failures are each one large part boxed in against a fixed part, with no
  free spot of its size within reach. Large parts should be placed first and treated as anchors, which is also
  what the layout guides say for the power path.
- The best legal run sits between the scripted board and the hand board on wiring demand (11 % above the hand
  board) and holds more intent statements than either.
- Selection between runs is by legality first, then statements, then wiring: a small tournament already.
- Not yet in the score: crossings, hot-loop inductance, lanes. Not yet done: applying a placement to a board file
  and the trial route, which is the real acceptance gate.

## First trial routes: what the scores missed (2026-11-11 and 12)

`apply_placement.py` writes a placement into a KiCad board and strips all copper; `open_connections.py` writes the
router's work list; the Battery-Bank A* router then routes every signal net on the bare board (seven power nets
skipped, 380 connections). Same router and rules for every placement.

| Placement | Statements (of 112) | Half-perimeter | Crossings | Routed (of 380) | Failed with no path even on an empty board |
|---|---|---|---|---|---|
| Scripted board | 84 | 2508 mm | 612 | 373 | 7 of 7 |
| Hand board | 92 | 2064 mm | 391 | 361 | 19 of 19 |
| Placer, courtyards only (run 6/4) | 104 | 2498 mm | 795 | 335 | 40 of 45 |
| Placer + crossing cost (run 7/4, one capacitor off the board) | 103 | 2340 mm | 402 | 327 | 51 of 53 |
| Placer + crossing cost + escape room (run 9/1) | 89 | 2841 mm | 653 | 360 | 18 of 20 |
| Compiled placer, seed 7 | 93 | 2351 mm | 482 | 365 | 13 of 15 |
| Compiled placer, seed 12 | 89 | 2503 mm | 456 | 357 | 20 of 23 |
| Compiled placer, seed 9 | 95 | 2440 mm | 415 | 357 | 21 of 23 |

What this says:

- **Neither wire length, nor intent statements, nor crossings predicted the route.** The first placer run beat both
  boards on statements and matched the scripted board on length, and routed far worse. Halving its crossings
  (`crossings.py`: spanning tree per net, count edge pairs of different nets that cross) changed nothing.
- **The cause was escape room.** Nearly every failure was a connection with no path even with every other route
  removed, at the fine-pitch ICs: the placer had 9 to 18 parts within 0.3 mm of each, the scripted board 2 to 5.
  `place_pack.py` now gives every part with 12 or more pads 0.5 mm of extra body. That took the placer from 327-335
  to 357-365 over four buildable placements, level with the hand board.
- **The scripted board has a home advantage**: it was tuned against this router. And a bare board has no power copper,
  so this measures signal routability only.
- The trial route is therefore the gate, as the research report said; the cheap scores are for steering the anneal.

Faults the real KiCad checks found in these tools, all fixed:

- Thermal pads on the back of an IC, and through-hole pads, sat under parts on the other side (shorts in DRC, while
  the courtyard check said legal). Pads that reach the far side now block parts there, in the placer and `overlaps.py`.
- `kicad-cli pcb drc` lists at most 499 unconnected items. A bare Monolith has 710, so the first routes covered 182 of
  380 signal connections without saying so. `open_connections.py` writes the full list.
- `pcbnew`'s `Save` rewrites the project file with default rules; removing tracks through `pcbnew` crashes. The tool
  now strips by text and puts the project file back.
- A loose `grep` filter over `overlaps.py` output hid a radio module sitting on two connectors. `run_seeds.py` now
  compares against the reference placement's own lines exactly.

Still open: the placer uses the board's bounding box, so 3 to 8 pads end up inside the edge clearance of the real
outline; about a third of seeds are buildable (15 seeds: 5; the rest are mostly slivers or one large part boxed in);
the placer's wiring is 15 to 40 % longer than the hand board's.

Speed: `fastcore.py` compiles the cluster and refine stages with numba. One full Monolith run (2 million cluster
moves, 2.5 million part moves, repair) takes 3 min 20 s on one core; the numpy path took 20 to 40 min for a
twentieth of the cluster moves. Without numba the numpy path is used.

## Power first: stages, a loop score and a hard-limit gate (2026-11-12)

Logan's point: the placer above optimises signal wiring, and what matters most on this board is loop area and
power paths. His order of priorities: first the hard thresholds (violate one and the part does not work), then
ringing, then losses and heat together; routability is what is left. Until now nothing in this stage measured a
hot loop, and the trial route skips the power nets.

**What was measured first.** `stage_copper.py` lays down power copper for each hot loop of a placement by fixed
rules (below), `hot_score.py` runs the PEEC loop solver on it, `power_gate.py` turns the result into pass or
fail. On the hand placement with rule copper all seven loops close, first capacitor 0.41 to 0.64 nH (the real
hand copper reads 0.38 to 0.90). On three buildable results of the placer above, two or three of the seven loops were open (a
capacitor turned the wrong way round, or left behind) and the rest read up to three times the hand board. The signal-only placer was failing
the thing that matters.

**Copper rules (`stage_copper.py`).** Ground planes on In1 and In4. Per hot loop: a supply pour and a return
pour on the switch part's layer over the hull of the loop's pads (supply wins where they overlap), return vias at
every capacitor and at the switch's return pads, a strip of return copper where a fine-pitch return pin has no
room for a via, and for the bulk capacitors supply vias to a supply pour on In2. No routing, no judgement: the
same rules on every placement, so two placements can be compared.

**Hard limit (tier 1, `power_gate.py`).** The first capacitor of each loop must close its loop on the rule copper
(a bulk capacitor the rule copper does not reach is a note: routing will connect it), and
supply voltage plus turn-off spike must stay under the switch's absolute maximum. The layout guides give no
numbers (BQ25756 table 9-1: "Minimize loop area", "close to the switching FETs"), so the limit is derived:

| Loop | Switch | Estimate | Inputs (source) | Limit on total loop inductance |
|---|---|---|---|---|
| Port input leg | SiZ240DT | ring: I sqrt(L / Coss), no damping | 22 V (circuit code), 40 V VDS and Coss 170 pF (datasheet p.1, p.2), 6.5 A = 1.3 x 5 A | 1.30 nH |
| Port battery leg | SiZ240DT | ring | 16.8 V, 40 V, 170 pF, 6.5 A | 2.17 nH |
| 5 V buck | TPS62933 | edge: L I / t | 16.8 V, 33 V SW transient (p.5), 5.8 A current limit (p.6), half of the 5 ns edge the circuit code declares | 7.0 nH |
| 3.3 V buck | TPS62177 | edge | 16.8 V, 30 V VIN (p.4), 1.2 A current limit (p.5), half of 5 ns | 27.5 nH |

Total = board loop with all capacitors and their package inductance in parallel, plus 0.2 nH assumed for the
switch package. The ring estimate is an upper bound (the FET is also avalanche rated, which is not relied on);
the edge estimate is used where a datasheet has no Coss. Assumptions that are not from a datasheet: the 0.2 nH,
the factor 1.3 on current, half the declared edge time. These are best calls, open to Logan's correction; each
is one constant at the top of `power_gate.py`. The facts are in the limits files with page and quote and pass
`intent_check.py verify`.

Gate drive, derived from the datasheets and to be checked once the gate tracks exist (the gate-loop solver needs
routed copper, so nothing here is computed yet):

| Question | Result | From |
|---|---|---|
| False turn-on through the Miller capacitance | no layout limit: a 22 V edge puts at most 0.84 V on a floating gate, under the 1.1 V minimum threshold | Crss/Ciss 0.038 max, VGS(th) 1.1 V min (SiZ240DT p.2) |
| Gate overshoot past the +20 V rating | no layout limit: an undamped step from the 9.6 V drive supply peaks at 19.2 V at most | VGS +20 V (p.1), drive supply from the circuit code |
| Gate ringing (tier 2 target) | each gate loop 17.6 nH or less keeps damping at 0.5 or better (overshoot about 16 %) | driver turn-on 3.4 ohm typical (BQ25756 p.12), gate resistance 0.46 ohm min and Ciss 1180 pF (SiZ240DT p.2), 0 ohm gate resistors |
| Bootstrap capacitor (tier 1) | its loop to the BTST and SW pins at most 1.46 times the gate loop, so the pin voltage stays above the 3.9 V refresh threshold at the turn-on step | VBTST_REFRESH 3.9 V max (BQ25756 p.12), 9.6 V drive; inductive divider at the step |

Decoupling distance stays a weighted statement, not a gate: the circuit code declares no distance, the
datasheets say "as close as possible", and the hand board itself misses 15 decoupling distance statements and
works. Still to be written as a gate: junction temperature at worst-case loss (needs the power copper stage).

**Tier 2.** Loop inductance itself, lower is better: total and first capacitor per loop, against a reference.

**Placer changes.**
- The circuit build now writes `pin_pads` (pin name to pad numbers) and checks each hot loop (switch pins on
  the supply and return nets, capacitors across them). Before, a `serves="U204.VIN"` pull went to the part
  centre, because the placer compared a pin name with pad numbers.
- `place_sections.py` builds each stage first: a switch part, then straight away its own hot-loop capacitors,
  each capacitor pad pulled to the nearest point of the switch pads on its net, with a penalty when another
  net's pad lies in between; a switch part keeps 1.6 mm of room for its capacitors. Capacitors declared in
  another section of the circuit join their switch part's group.
- `intent.py`: hot-loop statements are pad to pad and weighted; the inductor at a switch node belongs to its
  stage.
- `place_pack.py`: a stage (parts joined by weighted pad statements inside one cluster: switch parts,
  capacitors, inductor) keeps its shape. In refinement each weighted statement is tightened to the distance the
  cluster was built with plus 0.3 mm; before repair the stage is put back into exactly that shape; repair moves
  neighbours off a stage or moves the stage as one piece, and works stages first, then large parts, then small
  parts. Parts on a keep-out are now repaired too.
- `stage_bench.py`: a placement holding only the stages, so the stage shapes are scored in about three minutes.
- `hot_score.py`: small loops on a 0.2 mm cell (0.3 mm read 20 % low on a fine-pitch part); a loop that reads
  open on 0.3 mm is solved again on 0.2 mm (one "open" was a neck of copper thinner than the cell); a capacitor
  over 15 mm from its switch counts as open and stays out of the solve (memory).

**What did not work.** Locking stage parts in place without moving them as a piece (0 and 1 of 8 seeds
buildable). A heavier weight on centre-to-pad distance statements (the capacitor sat near its pins but turned so
that the other net's pin was in the way). Repairing a switch part and letting its capacitors follow without
checking where they land.

**Results on Monolith (8 seeds, 4 cores, about 5 minutes a seed; loop score about 10 minutes a board).**

| | Buildable | Hot loops passing tier 1 | Loop total, nH: 3.3 V buck / 5 V bucks / port input legs / battery legs | Trial route, of 380 |
|---|---|---|---|---|
| Hand placement, rule copper | yes | 7 of 7 | 1.27 / 0.82, 0.94 / 0.77, 0.78 / 0.75, 0.74 | 361 |
| Placer before this work (3 buildable seeds scored) | 18 of 24 | 4 or 5 of 7 (2 or 3 loops open) | closed loops up to 3 times the hand board | 357 to 365 |
| Placer with stages | 6 of 8 | 7 of 7 on five seeds, 6 of 7 on one | 1.07 to 1.11 / 0.69 to 0.85 / 0.66 to 0.70 / 0.62 to 0.66 | 365 (seed 3) |

Loop totals include 0.2 nH for the switch package and the capacitors' own inductance. The stage shapes are the
same in every seed (that is the point of keeping them whole), so the loops barely move from seed to seed; the one
failure (seed 5, the 3.3 V buck's capacitor with no path) was not the placement: see the tournament below. Signal wiring got longer (half-perimeter 2900 to 3840 mm against 2520 to 3150
before) and the trial route did not get worse.

Limits of this result: the rule copper is not the final copper (on the hand placement the first capacitor of the
four FET legs reads 13 to 19 % under the real hand copper; the converter ICs differ more, the 3.3 V buck 37 %
under and one 5 V buck 70 % over); nothing is checked against a measurement; the
bulk capacitor of one 5 V buck is reached only through vias (1.7 nH on its own); two seeds in eight are still
not buildable; gate drive, coupling, losses and heat are not scored yet.

**Tournament in one command, and a keep-out that stayed behind.** `tournament.py` runs the seeds, the rule
copper, the loop solve, the gate and the ranking. Its first run (seeds 9 to 12, all four buildable) failed the
3.3 V buck on two seeds whose stage had the same shape as on the passing seeds. Cause: the hand board has a
no-pour area on all layers under the Bluetooth module's antenna, and it stayed at its old coordinates while the
module moved; a stage placed there got no copper. `apply_placement.py` now moves a keep-out that forbids pours on
every copper layer with the part whose body contains it, and `--strip` removes pour voids drawn on single layers
(they belong to the copper that is stripped). Rerun:

| Rank | Seed | Hot loops passing tier 1 | Tier-2 sum, nH | Crossings | Signal half-perimeter, mm |
|---|---|---|---|---|---|
| 1 | 9 | 7 of 7 | 5.26 | 537 | 2688 |
| 2 | 11 | 7 of 7 | 5.14 | 774 | 2934 |
| 3 | 12 | 7 of 7 | 5.15 | 929 | 3390 |
| 4 | 10 | 7 of 7 | 5.17 | 996 | 3459 |

Over seeds 1 to 12: 10 of 12 buildable, and every buildable seed passes 7 of 7 once the keep-out moves (seed 5
was the same fault). Tier-2 sums are 5.14 to 5.26 nH, a spread the solver does not resolve, so the ranking treats
sums within 5 % of the best as equal and lets crossings decide (my call). With stages kept whole the loop score
no longer separates seeds; it guards against a broken stage. Open: the antenna clearance should be declared in
the circuit code with its datasheet source, not inherited from a board, and the placer does not yet keep other
parts off it.

Kept in `example/monolith`: `seeds9-12_tournament.json`, the build's `constraints.json` and `netlist.json`, the new `clusters.json` and
`intent.json`, `placements/seed3_stages_routed365.json` with its loop result, the hand placement's loop result,
and the seed summary.

## Run it

```
python3 floorplan.py extract <board dump.json> intent.json [<netlist.json>]
python3 floorplan.py score intent.json <board dump.json> [<netlist.json>]
python3 place_sa.py intent.json <board dump.json> <netlist.json> <constraints.json> out.json [moves] [seed]
python3 intent.py derive <build dir> <design dir> intent.json ; python3 intent.py validate intent.json <build dir>
python3 intent.py check intent.json <board dump.json> [placement.json]
python3 place_sections.py <board dump.json> <netlist.json> <constraints.json> clusters.json [J,H,TP,SW] [intent.json]
python3 overlaps.py <board dump.json> [placement.json]
python3 place_pack.py clusters.json <board dump.json> placement.json [cluster moves] [seed] [refine moves] [intent.json] [crossing weight] [escape room mm]
python3 crossings.py <board dump.json> [placement.json]
python3 run_seeds.py example/monolith/clusters.json example/monolith/board_dump.json example/monolith/intent.json <out dir> <first seed> <count>
python3 apply_placement.py <in.kicad_pcb> <out.kicad_pcb> [placement.json] [--strip]      (KiCad's python)
python3 open_connections.py <board.kicad_pcb> <drc.json>                                  (KiCad's python)
python3 stage_copper.py <placed bare board.kicad_pcb> <constraints.json> <out.kicad_pcb>   (KiCad's python)
PCB=<board with copper> python3 hot_score.py <constraints.json> [out.json] [loop name ...]
python3 power_gate.py <constraints.json> <netlist.json> <limits dir> <limitsmap.json> <hot_score out.json> [reference.json]
python3 stage_bench.py clusters.json <board dump.json> <constraints.json> placement.json
KICAD_PYTHON="<command that runs KiCad's python in the work dir>" python3 tournament.py <build dir> <limits dir> <limitsmap.json> clusters.json <board dump.json> intent.json <board.kicad_pcb> <work dir> <first seed> <count>
```
