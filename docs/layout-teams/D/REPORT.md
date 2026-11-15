# Team D report: lead-planned hand placement and tiered hand routing

Method set by Logan: a lead designs the floorplan and the interconnect plan; cheaper workers (Opus) hand-place and
hand-route the detail in feedback rounds; the lead may tear up its own plan. All numbers below are from
`tools/score/score_board.sh` (or its parts) on the cloud container, except where "PC" says Logan's route server.

## Result

| | Hand board (reference) | Team D, round 2 placement |
|---|---|---|
| Open power paths | Port 1 PP5V open at U401 | none (only the allowed 3V3 at L201, GND at J301/J302) |
| DRC errors | 0 | 0 |
| Hot loops, tier 1 | 7 of 7 | 7 of 7 |
| Hot loops, sum | 6.75 nH | 6.16 nH |
| Loss (generated copper) | 1.359 W | 1.013 W |
| Blocked connections (quick screen) | 56 of 452 | 28 of 427 |
| Full route, plain router | 394 of 452 (87 %) | 397 of 427 (93 %), PC, 71 min, finished |

`best_placement.json`, `score.json`, `F.png`, `B.png` are this round 2 board (run `r2_all`).
Of the 28 blocked, 12 are Kelvin taps and thermistor lines the router never attempts on any board.

Round by round (placement):

| Run | Blocked | Hot loops | Loss | Power opens | Full route |
|---|---|---|---|---|---|
| hand | 56 of 452 | 7 of 7, 6.75 nH | 1.359 W | PP5V at U401 | 394 of 452 |
| round 1 (8 rooms, 8 workers) | 37 of 428 | 7 of 7, 6.52 nH | 1.014 W | GND at U404 | 387 of 428 (PC, 74 min) |
| round 2 (2 fixers) | 28 of 427 | 7 of 7, 6.16 nH | 1.013 W | none | 397 of 427 (PC, 71 min) |

Where the loss went (W): PACK_P 0.26 (hand 0.21 to J113 alone plus other branches), GND 0.33, CELL_P 0.11
(hand 0.14), Port 1 input sense path 0.04 (hand 0.23), Port 2 0.03.

## What was tried

### Placement
- **Floorplan as data** (`tools/make_rooms.py`): 8 rooms with part lists, reserved lanes and hand-off points, a
  brief per room, one Opus worker per room using `tools/room.py` (`put`, `beside`, `row`, `done`) and looking at the
  picture after every run. Worked: all eight rooms came back legal on the first assembly, and the board beat the
  hand board on blocked connections, loops and loss in round 1.
- **Lead decisions that paid**: Port 2 5 V buck moved from bottom-left to beside its PD chip (the hand PP5V ran
  46 mm); shunts R424/R524 feed the input capacitor column from above (Port 1 input path 0.23 W to 0.04 W); a
  worker turned pack FET Q102 so its PACK_P pads face north.
- **Round 2 as surgical fixes** (two fixers, exact list of blocked connections with causes, power parts frozen):
  37 to 28 blocked, ground open at U404 removed, loops 6.52 to 6.16 nH. One fixer needed 1 scoring run, the other 1.
- **Did not work / left**: C544 cannot sit near U504 (bulk not reached, loop still passes); C511 (0805) does not fit
  at U503 pin 23; gate pads of Q401/Q501 sit inside the input pour after the 180 degree turn (solved by a via in the
  pad in routing); pins under the USB connectors' VBUS copper (C_CC lines) stay blocked for the router.
- **Tear-up considered, not done**: a vertical pack FET stack with PACK_P at the top, nearer J113. PACK_P is now the
  largest single loss (0.26 W), so this is the next placement experiment.

### Routing (same tiers: lead plans, workers do the detail)
Tools built: `tools/obst.py` (every obstacle of a board; `free_vias`, single-layer path `auto`, `link`, clearance
check), `tools/hr.py` (hand routes and pour cuts on the copper plan), `tools/hr2.py` (hand routes on a routed
board, real DRC), `tools/stage_route.sh` (router tiers with `--only`), `ROUTING-GUIDE.md` for workers.

1. **Lead key routes**: 8 Kelvin sense taps as In3 pairs from the inner edge of each shunt pad, vias in the two
   high-side gate pads. 0 DRC errors. A via in the thermistor pad fails DRC (SW pour on B), dropped.
2. **Router tiers**: gate, bootstrap, sense and driver nets first (81 to 83 of 83 routed), then the rest.
3. **Workers by region** on what was left, with the checker and real DRC.

| Pass | What | Open after | DRC | Scored with own copper |
|---|---|---|---|---|
| 1 | Kelvin + router tiers + 2 workers | 12 connections | 0 | 1.29 W, 7 of 7 at 7.27 nH, **PACK_P open at J113 and R427** |
| 2 | pours kept, PACK_P strap, Kelvin, router tiers, 3 workers | 25 connections | 0 | 1.114 W, 7 of 7 at 6.20 nH, **PACK_P open at U504** |
| 3 | second PACK_P strap, Kelvin, router tiers only (no worker tier yet) | 49 connections | 4 (router tracks beside CELL_1N) | 1.157 W, 7 of 7 at 6.31 nH, **no open power path** |

**Findings from scoring routed boards with their own copper (nobody had done this):**
- `write_copper.py` writes zones with several outlines; KiCad keeps only the first outline when the board is saved
  again, so the router's final refill drops most F/B power pours (VBUS F 51 to 2.4 mm2, PACK_P F 104 to 1.2 mm2).
  The scorecard scores power before the route, so it never shows. Plain-router route counts on such boards are
  flattered because the router runs through where the pours were. Fixed for team D in `hr.py` (one zone per outline).
  With pours kept, pass 2's router left 52 open items where pass 1 left 37.
- The In2 PACK_P pour is soft for the router; signal tracks cut it into islands. Pass 1 lost the pack connector,
  pass 2 (with one strap) lost the Port 2 5 V buck. Once routed, no legal bridge was left (23 legal via spots in
  18 x 18 mm). Power straps have to be hard tracks laid by the lead before any signal.
- Routing costs loss even when nothing opens: 1.013 W before, 1.11 to 1.13 W after (PACK_P 0.26 to 0.33 to 0.35 W).

### What the worker tier could not close (pass 2, 25 connections)
3V3 pour scraps on In3 with no legal via (C207, R314, C403 groups), SCL at the Tag-Connect pad J302.6, CHG_INT and
I2CC_SDA at U403 south pins (under the PACK_P strap), FB at U403.12 (walled by a Kelvin track), CELL_P taps at
R110/R118, CELL3 at J111, IRQ_N and EN_5V2 long runs, both thermistor lines, Net-(C313-Pad2).
Most of these are consequences of earlier copper (straps, Kelvin tracks, router vias), not of placement.

Pass 3 is the routed board to continue from (`routed/pass3.kicad_pcb`): every power path is joined after routing,
378 of 427 connections are closed, and it still needs one worker tier for the 49 open connections and 4 DRC errors.
Pass 2 (`routed/pass2.kicad_pcb`) has more connections closed (402 of 427, 0 DRC) but the Port 2 5 V buck input open.
Neither routed board is finished; the placement in `best_placement.json` is the deliverable that meets every hard limit.

## Cost
Placement: 8 room workers + 2 fixers. Routing: 2 + 3 region workers (170 to 290 k tokens each). A quick score takes
6 to 20 min in the container, a router tier pass 20 to 45 min, a full plain route 71 to 74 min on the PC.

## What I would do next
1. Third tear-up of the routing plan, not the placement: reserve via fields and 3V3 In3 necks the same way as the
   PACK_P straps (hard copper first), then router tiers, then workers once.
2. Give the checker the real rule set (0.15 / 0.25 HighCurrent) and a two-layer path search; both were the workers'
   main complaints.
3. Vertical pack FET stack to shorten PACK_P to J113.
4. Fix `write_copper.py` and score every routed board with `--keep-copper` in the shared scorecard.
