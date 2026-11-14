# Stage 7: power copper (spec section 9, step 3)

Power pours, vias and short tracks generated from the circuit code on a placed board, then scored on the real
copper: loop inductance (tier 1 and 2), DC drop and loss, and board heat (tier 3). Nothing is typed by hand per
board: the same rules run on every placement, so placements can be compared on their copper.

## How to run

```
tools/copper/run.sh <work dir> <stem> <constraints.json> [plan_copper.py options]
```

`<work dir>/<stem>_bare.kicad_pcb` is the placed board without copper (for example from
`tools/floorplan/apply_placement.py ... --strip`), with its `.kicad_pro` and `.kicad_dru` beside it. The script runs:
`cu_dump.py` (board to JSON, KiCad python), `plan_copper.py` (the plan), `write_copper.py` (zones, vias and tracks
into the board, filled; KiCad python), KiCad DRC, `dc_score.py` (DC solve with a loss map), `thermal.py` (heat).
It needs Docker with `kicad/kicad:10.0` (on a PC with KiCad, run the two KiCad-python scripts with KiCad's python).
About 75 s for the plan and 3 min in all on Monolith. The loop solve is separate and slower (5 to 15 min):

```
PCB=<stem>_cu.kicad_pcb python3 tools/floorplan/hot_score.py <constraints.json> <stem>_hot.json
python3 tools/floorplan/power_gate.py <constraints.json> <netlist.json> spikes/02-seeded-faults/limits \
    spikes/02-seeded-faults/limitsmap.json <stem>_hot.json [reference_hot.json]
```

`render.py` draws one layer coloured by net, for a person checking the copper by eye.

## What the circuit code must declare

- `declare(net, kind="power" | "switching", current_a=...)`: which nets get power copper and how wide.
- `hot_loop(...)`: supply, return, switch pins and capacitors (high-frequency capacitor first).
- `kelvin(...)`: sense resistors (their pads are current terminals; the taps are left to the router).
- `heat(ref, watts, why)` (new in `kernel.py`): part losses for the thermal model. Monolith's come from
  Battery-Bank `heat_sources.py` at 100 W out from a 12 V pack (14.85 W in all).

The Monolith cell path (CELL_P_RAW, CELL_P, FET_MID, CELL_N) is now declared at 10 A in `cells_gauge.py`.
`tools/floorplan/example/monolith/constraints.json` was patched to match (the build needs KiCad's symbol
libraries, which the cloud container does not have): rebuild it on a PC with KiCad.

## What the generator does

`roles.py` decides, from constraints.json, which pads of a power net carry its current (series terminals: switch
pins, connectors, inductors, fuses, FETs, shunts, an IC's large power pads; shunt terminals: capacitors) and how
much each carries. `plan_copper.py` then draws, each step seeing the copper of the steps before:

1. Return planes on In1 and In4.
2. Hot loops first: a supply pour and a return pour over each loop's pads. Four shapes are tried (hull of each
   net's pads, or pair hulls from each capacitor to the switch pad, grown 0.3 mm or not at all, supply or return
   cut first); the one that closes the most capacitors on the layer, high-frequency capacitor first, wins. Return
   vias at every capacitor and at the switch's return pins.
3. Switch nodes, then the other power nets by current: a copper tree on the outer layer that carries most of the
   current, terminal by terminal along a shortest path as wide as the current needs; via arrays (1 A per via) to
   the other side; a detour on the other outer layer when there is no room; an inner-layer pour for a rail with
   many terminals spread wide (PACK_P on In2, 3V3 on In3).
4. Every return pad gets a via, or a short path on its layer to a piece of return copper that has one.
5. `--mirror=3` (default): nets of 3 A or more (not switch nodes) get a copy on the other outer layer where it is
   free, stitched by vias at each terminal.
6. `--grow=1.5` (default): all power copper grows into the room that is left, in 0.5 mm rounds.

Signal pads keep 0.4 mm of escape room beyond the clearance, and lanes from the intent file stay free.

## Results on Monolith (2026-11-12)

Same circuit code and rules for all; "hand" is the real hand-drawn copper of Battery-Bank commit 8dd9eb6.

| | Hand copper, hand placement | Generated, hand placement | Generated, seed 9 | Seeds 10, 11, 12 |
|---|---|---|---|---|
| DRC errors | | 0 | 0 | 0 |
| Hot loops passing tier 1 | 7 of 7 | 7 of 7 | 7 of 7 | |
| Tier 2, sum of loop inductances | 8.15 nH | 6.64 nH | 5.49 nH | |
| Copper loss, all power nets | 1.10 W | 1.29 W | 1.80 W | 3.19, 2.92, 3.96 W |
| Heat, highest / mean rise (comparative only) | 296 / 261 K | 293 / 262 K | 306 / 269 K | 329 to 332 K |
| Current terminals left to the router | | 3V3 L201 (0.5 A), J301 and J302 ground | U501 on VBUS, PPHV (5 A) and PP5V | 5 to 6 each |

Read this with care:

- The heat figures assume a bare board in still air (h = 10 W/m2 K both faces) with no enclosure, so the absolute
  rises mean nothing; only the differences between boards do. Copper loss is under 2 W of the 15 to 17 W, so heat
  follows the part losses and how far apart the hot parts sit.
- Generated copper beats the hand copper on loops on the same placement (the loop pours are wider and closer), is
  about 17 % worse on losses, and is worse on Port 1 SW1 (30 mV against 2 mV: the loop pours now go first and
  leave the switch node a narrow way out).
- The loop-only tournament ranking does not hold on copper. Seed 11, its winner, loses 2.9 W against seed 9's
  1.8 W and leaves 5 A paths open. Seed 9 has the best loops and the best losses of the four, but U501 (Port 2's
  PD controller) has no room for its 5 A paths. The tournament should score generated copper (loss and opens),
  not loops alone.

Per net, worst drop in mV / loss in W:

| Net | Hand copper | Generated, hand placement | Generated, seed 9 |
|---|---|---|---|
| CELL_P | 12.9 / 0.129 | 11.5 / 0.115 | 15.2 / 0.152 |
| CELL_P_RAW | 4.9 / 0.049 | 2.1 / 0.021 | 24.4 / 0.244 |
| PACK_P | 19.5 / 0.284 | 20.1 / 0.298 | 20.3 / 0.295 |
| GND | 13.5 / 0.398 | 11.8 / 0.334 | 13.6 / 0.336 |
| Port 1 AC_SNS_N | 14.4 / 0.072 | 7.0 / 0.035 | 24.4 / 0.122 |
| Port 2 AC_SNS_N | 13.2 / 0.066 | 15.0 / 0.075 | 23.3 / 0.117 |
| Port 1 SW1 | 2.1 / 0.011 | 30.4 / 0.152 | 7.6 / 0.038 |
| Port 2 VBUS | 5.6 / 0.028 | 8.0 / 0.040 | open at U501 |

## Lessons

- Hot loops must get their copper before the switch nodes. With switch nodes first, seed 9's six USB loops read
  open in the loop solver: the switch-node pours cut the FETs' return pins off.
- Judge connectivity as KiCad fills (a neck under the 0.15 mm minimum width vanishes): the plan opens every
  polygon by 0.1 mm before it decides that a pad is joined.
- A 0.5 mm-pitch switch (the 5 V bucks U404, U504) needs loop pours as wide as the pads, not 0.3 mm wider, or the
  supply pour swallows the return pin next to it.
- Tracks are not on the planning raster, so vias are checked against them exactly.
- The DC solver and the loop solver both report a pin whose copper is an island; read their opens, not only DRC.

## Logan's review and the anchored workflow (2026-11-12, later)

Logan rejected the seed 9 copper on sight. The power paths sprawled: the Port 2 PD switch U501 sat 69 mm from its
USB-C connector, switch nodes ran 20 mm strips on the bottom, and 5 A paths were thin tracks. The scores above
missed all of it. So:

- The copper now refuses to snake. A path longer than 1.5 x straight + 3 mm is not drawn and is reported as a
  placement failure. Bottom-layer detours are capped at 10 mm (switch nodes may detour, as the hand board does
  from the half-bridge's enclosed SW pad). Nets under 1 A get no outer tree, only a router track.
  `report.outer_layer_use` gives the share of each outer layer the power copper takes.
- `tools/floorplan/power_chains.py` adds placer statements that keep each power path's current-carrying parts
  together (18 on Monolith; the hand board meets 14, seeds 9 and 11 failed 9 to 12).
- Logan's workflow: he places the parts that set the power flow, and the placer and generator do the rest.
  `tools/floorplan/anchors.py --power` lists them: the cell path, PD switches, power FETs, inductors, shunts and
  bucks (21 on Monolith), plus each hot loop's first capacitor. That last one matters: with only the FET anchored,
  the placer drifted C430 9 to 12 mm from Q401 and 3 of 6 loops read open. `anchors.py <dump>` reads which parts
  a person placed inside the outline; pass them to `place_sections.py` as fixed refs.
- Trial on the hand board, with its 28 parts anchored and the placer filling in the rest: all paths of 5 A or more
  joined; 6 of 6 solved loops pass tier 1, at 6.4 nH (one loop ran out of memory in the solver); 1.39 W loss.
  Left to the router: U501's 1.5 A PP5V pin, 3V3 (0.5 A), J302 ground. The placer pushed U301 off the board in
  that seed.
- Tried and parked: no-footprint corridors between anchored parts. Signal wiring got 18 to 55 % longer and the
  copper got no better.

## Not done yet

- Trial route with the power copper in place (Battery-Bank router, `--softnets=GND,PACK_P,3V3`), to check that
  the lanes and escape room still leave the signals routable.
- Growing copper where the DC solver shows crowding (`--grow` is blind to current flow).
- Copper in the tournament's score.
