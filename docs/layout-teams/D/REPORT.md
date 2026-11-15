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

### Fully routed board (2026-11-15, lead closing pass)

`routed/final.kicad_pcb` is now the fully routed board: **KiCad DRC reports 0 errors and 0 unconnected items**, every
power path is joined with the board's own copper, 7 of 7 hot loops pass at 6.30 nH, and the loss with its own copper is
**1.845 W** (`routed/final.score.json`, pictures `routed/final_F.png`, `routed/final_B.png`).

| | Worker-tier board (pass 3, q2) | Fully routed board |
|---|---|---|
| Unconnected items in DRC | 26 | 0 |
| DRC errors | 0 | 0 |
| Open power paths | 3V3 at L201 (allowed) | none |
| Hot loops | 7 of 7, 6.30 nH | 7 of 7, 6.30 nH |
| Loss, own copper | 1.187 W | 1.845 W |

The loss is higher than the pass 3 board because the bottom-side pack strap is gone: the I2C, interrupt and
thermistor lines cross the pack path on the bottom layer where that strap ran, so the pack path to J113 is the 3 mm
In2 strap alone (5.7 mohm instead of 2.3). Pack net 0.98 W of the total (0.40 W before). Routing count was put
ahead of loss, as Logan ranked them.

Things a reviewer should know about this board:
- Two ground vias sit in the ground pad of C543 (79.45, 78.7 and 79.3). The Port 2 5 V capacitors' ground pour had no
  via to the planes on any earlier board, and the In2 pack track plus the bottom 5 V pour leave no other legal site.
- The In2 pack strap is 2 mm wide (not 3) for 5 mm under the Port 1 charger's south pins, so pins 3 and 7 get vias.
- The Port 2 pack feed (R527) crosses from In2 to the bottom pour through three vias at (100.05, 112.67),
  (99.5, 112.95), (99.9, 113.65); 8.3 mohm to R527.

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
| 3 | second PACK_P strap, Kelvin, router tiers | 49 connections | 4 (router tracks beside CELL_1N) | 1.157 W, 7 of 7 at 6.31 nH, no open power path |
| 3 + workers | three Opus workers by region on pass 3 | **18 connections** | **0** | **1.187 W, 7 of 7 at 6.30 nH, no open power path** |

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

The pass 3 board with the worker tier (kept as `routed/pass3_workers.kicad_pcb`): 409 of 427 connections closed by real copper (96 %), 0 DRC
errors, every power path joined after routing (only the allowed 3V3 at L201), 7 of 7 hot loops at 6.30 nH, 1.187 W.
It is the first Monolith board scored after routing with its pours intact; the hand board's 1.36 W and the plain
router counts are pre-route / pour-less numbers and are not like for like.

The 18 that were still open on that board (all closed later by the lead, see below): the north 3V3 In3 island (U401.38, C403) and the R314 3V3 group, SDA / IRQ_N / CHG_INT long runs
from the Port 1 side to the MCU (blocked by the In2 PACK_P strap and the busy In3 south of it), I2CC_SDA at U401.16
and U503.2, CHG_INT at U501.18, CELL_P taps at R110.2 / R118.1, SCL at the Tag-Connect pad J302.6, FB at U403.12
(walled by the SRN_F Kelvin track), CE_N, Net-(C313-Pad2), both thermistor lines. Several are caused by the lead's
own straps and Kelvin tracks: the next plan should leave a crossing lane through the strap for the I2C bus and
keep Kelvin tracks off chip pins.

### Closing pass by the lead (26 unconnected items to 0)

Whole-net rip-up, region rip-up with 8 orders, and a recursive rip-up all closed nothing more after 12 were left.
What closed the rest was slower and local (scripts `routes/hand_c.py` to `hand_q.py`, each applied with `tools/hr2.py`
and checked by real DRC):

1. Look first. `tools/crop.py` draws the four signal layers of a window with net names; `routes/lane_map.py` prints a
   text map of free lanes. Every remaining open was read off a picture before any copper moved.
2. Fine-pitch pins: a hand stub straight out of the pin to a via site tried one by one (`escape_try`), neighbours
   pulled only inside a 1 mm circle and re-laid (`cross2`). Closed FB, both I2CC_SDA pins, Port 2 CHG_INT and TS.
3. The pack strap under the Port 1 charger: narrowed from 3 mm to 2 mm for 5 mm and moved 0.4 mm north. That gave
   pins 3 and 7 (CHG_INT, CE_N) via sites; both then closed with local re-lays.
4. SDA, the last and longest (PD chips to MCU, 45 mm): laid as forced pieces. Hand-placed seeds (a bottom-layer hop
   past the Port 2 pack-feed vias, an In2 run beside the thermistor and charge lines moved 0.15 mm by hand, a via at
   (101.6, 119.3), an In3 lane north of the 3V3_SLEEP line with 0.03 mm to spare) and the path search joining seed to
   seed inside a 2 to 4 mm margin. Left free, the search always took the cheapest path, which walled the pack pour.
5. Score after every pass with the board's own copper. A 0.4 mm ground track that an earlier automatic pass had laid
   on In2 cut the pack pour off from the Port 2 feed: nothing was reported open, loss went to 4.05 W (R527 at
   98 mohm). Removing that one track brought it back to 1.72 W. The first SDA route did the same and split the pack
   net in two; DRC caught that one.
6. 3V3 pour pieces cut by a refill were rejoined with a track between a via and a pad, not pour to pour, because the
   next refill cut the pour-to-pour link again.
7. The last DRC item named a zone corner at the top-left of the board. The real island was 15 mm away: the ground
   pour under the Port 2 5 V capacitors, with five ground pads and no via.

## Cost
Placement: 8 room workers + 2 fixers. Routing: 2 + 3 region workers (170 to 290 k tokens each). A quick score takes
6 to 20 min in the container, a router tier pass 20 to 45 min, a full plain route 71 to 74 min on the PC.

## What I would do next
1. Plan the bottom layer as well as In2 for the pack path before any signal: this board paid about 0.5 W for the
   bottom strap the signals took over. A 4 mm slot for the I2C bus through both straps at the plan stage would keep both.
2. Put "score with own copper" and "list pour islands without a via" into the shared scorecard; both found real
   faults that DRC and the open-power check missed.
3. Give the workers the closing tools (`crop.py`, `lane_map.py`, `hand_lib.py`) and the forced-pieces method; the
   lead spent most of the closing pass on reading geometry a cheaper worker could read.
4. Vertical pack FET stack to shorten PACK_P to J113.
