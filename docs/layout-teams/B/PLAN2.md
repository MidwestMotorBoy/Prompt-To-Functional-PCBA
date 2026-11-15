# Team B plan, phase 2: from placement r4 to a fully routed board

Lead's plan of 2026-11-15. Read `../CHARTER.md`, the last four entries of `LOG.md` and `tools/README.md` (last section)
first. Phase 1 ended with placement r4 (`best_placement.json`, `score.json`, `F.png`, `B.png`). Logan asked to go on to
a fully routed board. His order of priority is unchanged: hard limits first, then ringing, then loss; loop area and
power paths matter more than wire length; look at the renders.

## 1. Where we start (all numbers from existing runs of r4)

| What | Number | Run |
|---|---|---|
| Blocked edges, shared scorecard | 19 of 437 | `runs/r4chg-hot` |
| Full route, shared scorecard | 411 of 437, 26 failed, about 17 min, not timed out | `runs/r4-route` |
| Hot loops before routing | 7 of 7 tier 1, sum 5.54 nH | `runs/r4chg-hot` |
| Loss before routing | 1.125 W | `runs/r4chg-hot` |
| Blocked edges, one zone per outline, PACK_P and 3V3 straps (the phase 2 baseline) | 15 of 420, DRC 0, loss 1.124 W | `runs/p2-base-screen` (2026-11-15, screen only) |
| Routed board, PACK_P straps only: route | 391 of 416, 25 failed, about 31 min, not timed out | `runs/r4-final` |
| Routed board: KiCad unconnected items | 37 (GND 8, 3V3 7, the rest signal and a few power-net pads) | `runs/r4-final/routed/drc.json` |
| Routed board: DRC errors | 3 clearance errors, all CELL_1N on F.Cu against a signal track | same |
| Routed board: power open (dc_score) | 3V3 at L201 | `runs/r4-final/final.json` |
| Routed board: loss | 2.854 W; PACK_P to J113 15.6 mohm (2.24 before routing), to R427 15.4 mohm (2.17) | `runs/r4-final/routed/dc.json` |
| Routed board: hot loops | 7 of 7 tier 1, sum 5.56 nH | `runs/r4-final/final.json` |

The 15 blocked edges of the baseline (`runs/p2-base-screen/ghost.log`), all at pins:
- C_CC1 U405 pad 4 to pad 7, J401.A5 to U405.4; C_CC1 U505 pad 7 to pad 4, U505.4 to J501.A5; C_CC2 U505.5 to J501.B5;
- DRV9_OFF Q509.1 (bottom) to U501.37; 3V3 at U501 pad 38;
- GND at U401 pads 26, 31, 36 and U501 pads 31, 36; GND at C304.2;
- HG2 R446.2 to Q402.1 and R546.2 to Q502.1 (the BAT_SNS_P copper wraps the gate pad).

Failed in the full routes beyond those (congestion, they change from route to route): EN_5V1 (two edges, one of them
U301.12 to U404.2, 54 mm), Port 1 CC2 (C402.1 to U405.11), Net-(U102-V4), TS1 (TH101 to U101.10), Port 1 I2CC_SDA and
I2CC_SCL, Port 2 I2CC_SDA, SS_5V, Net-(U504-FB) x2, GND U401.27.

## 2. Definition of done (all measured on the ROUTED board, `final.json` of `tools/final_route.sh`)

| Gate | Limit | Where it is read |
|---|---|---|
| Unrouted connections | 0: KiCad's unconnected list of the routed board is empty, signal and power | `routed.unconnected_items` |
| Power paths | `routed.power_open` empty. 3V3 must reach L201 and GND must reach J301/J302 on the routed board; no pad listed by `tools/loose.py`; the PACK_P In2 sheet and the 3V3 In3 bus each one piece | `routed.power_open`, `routed.loose`, `routed.unconnected_power` |
| DRC | 0 errors on the routed board (and 0 on the copper board before routing) | `routed.drc_errors`, `drc_errors` |
| Hot loops | 7 of 7 tier 1 on the routed board | `hot_routed.pass_count` |
| Ringing | routed sum no more than 0.05 nH above the 5.54 nH before routing, no loop more than 0.02 nH up | `hot_routed`, `hot_pre_source` |
| Loss | routed board 1.25 W or less (1.12 W before routing); PACK_P to J113 and to R427 3.0 mohm or less each | `routed.loss_W`, `routed/dc.json` |
| Renders | F, B, In2 and In3 of the routed board looked at by the lead: no power part or power strip sprawling, no signal track through a hot-loop pour, no track that wanders | pictures committed with the board |
| Honest numbers | every route says whether it timed out; a number comes from a named run | `LOG.md` |

Dangling track ends and KiCad warnings are reported, not gated. The deliverables at the end: the routed board file,
its `final.json`, the four renders, the one command that rebuilds it from `best_placement.json`, and the charter's
`REPORT.md` and `SKILL-NOTES.md` (both still owed from phase 1; the lead writes them in the last round).

## 3. What the existing runs show, and what follows from it

1. **Why PACK_P goes to 15.6 mohm.** In2 is the router's north-south signal layer and is half-ounce copper (about
   1 mohm per square). The 10 A path from Q102 (97.5, 118.7) to J113 (119.43, 108.97) and the 5 A path to R427
   (119.9, 104.9) run east-west on In2, across the signal lanes. On `runs/r4-final/routed.kicad_pcb` three signal
   nets run north-south on In2 just west of J113 and cut the sheet there: EN_5V2 (x 113.1 to 116.3, y 104.8 to 114.1),
   Port 1 TS (x 114.2 to 118.0, y 96.9 to 113.2) and SCL (x 117.3 to 119.2, y 93.0 to 107.4). J113 and R427 are then
   fed by the strap that comes down from the north at x 120.2 (1 mm wide from y 88.4 to 102.2, 0.5 mm in places below
   that). Straps keep the path joined, they cannot keep it wide.
2. **The outer layers are 2 oz (0.07 mm), four times In2.** On the bottom the way from Q102's PACK_P vias (B.Cu pour at
   x 92.7 to 95.6, y 115.7 to 119.7) to J113 is nearly empty before routing: between the south row of the fixed bottom
   capacitors (C208, C210, C209; their PACK_P bottom pours end at y 111.9) and the FET_MID bottom pour (north edge
   y 114.7), a gap of 2.8 mm, then east past the fixed TH104 (115.5, 112) to J113, which is a through-hole pad, then
   3 mm north to R427's five vias (119.9, 106.4). About 28 mm at 2.4 mm and more is 2 to 3 mohm on 2 oz (0.25 mohm per
   square), in parallel with what is left of In2. This is the first thing to try.
3. **The router obeys KiCad rule areas** (`router.py` `mark_ko`: an area with "no tracks" is closed to tracks and vias
   on its layer, "no vias" only to vias). So a no-signal corridor on In2, or a no-via area over a hot-loop return pour,
   needs no router change: only a writer that puts rule areas into the board.
4. **The router has a continuation mode** (`--cont --keep=<board before routing>`): nets with open connections or DRC
   errors are lifted and routed afresh, every other net may be pulled. This is the base for a finishing pass. It also
   has `--avoid=<net regex>:<mm>:<cost>`, `--rips`, `--maxrip`, `--riptime`, `--phases`, `--only`, `--skip`.
5. **The 3 DRC errors are one rule.** `HighCurrent copper to small signals`, 0.25 mm; the router keeps 0.15 mm between
   a CELL_1N track and a signal track (actual 0.224 mm). A router copy must take the rule's clearance for that pair.
6. **Logan's PC returns counts only.** `route_server.py` runs the stock `tools/score/router.py` with the stock options
   and pushes the routed and failed counts and the log (with the FAILED lines), not the routed board. So the PC is for
   comparing copper-plan variants by route count; routed-board loss, DRC and a team copy of the router need a local route
   (one at a time per agent, 20 to 30 min).
7. **Signal vias in a hot-loop return pour cost 0.01 nH each loop** (Port 1 and Port 2 HL_IN, LOG 03:40). Small, but
   it is ringing, and a no-via area is cheap (finding 3).

## 4. The flow we build (one command at the end)

```
best_placement.json
  -> shared scorecard screen (runs/r4chg-hot: bare board, spec.json, cu.json)          [exists]
  -> copper-plan filters on spec.json, in this order:
       straps.py PACK_P (In2) and 3V3 (In3)                                              [exists]
       power filters: outer-copper PACK_P trunk, corridors, no-via areas                 [worker A]
       pin filters: pre-routed pin escapes for the edges no router can make              [worker B]
  -> write_copper_split.py (one zone per outline), DRC, DC loss, blocked edges           [exists]
  -> full trial route                                                                    [exists]
  -> finishing pass on the routed board (continuation route, scripted last tracks, DRC)  [worker B]
  -> routed-board check: DRC, unconnected, power paths, loss, loose pads, 7 hot loops    [exists]
```
`tools/final_route.sh` carries the two new steps as hooks since 2026-11-15 (tested with a no-op filter on
`runs/p2-base-screen`): `--filters="<script> <options>;..."` runs each filter as
`python3 tools/<script> <spec in> <source cu.json> <spec out> <options>` after the straps (the call form of `straps.py`),
and `--post="<script> <options>"` runs `tools/<script> <out dir> <options>` after the route; when it writes
`<out dir>/finished.kicad_pcb`, that board is scored. The baseline command of phase 2:
```
ST="--net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V;--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
bash tools/final_route.sh runs/r4chg-hot runs/<new> --straps="$ST" [--filters="..."] [--post="..."] [--route=0] [--no-hot]
```

## 5. Work packages

**A. Power copper that survives routing (round 1, worker A).** PACK_P to J113 and R427 at the resistance it has before
routing, on the routed board; 3V3 joined at L201; no power pour in pieces. In this order: the bottom 2 oz trunk
(finding 2), an In2 no-signal corridor where the trunk cannot go (finding 3), both; then no-via areas over the
hot-loop return pours. Each as a filter on spec.json. Judged by a local full route and the routed-board numbers.

**B. The failed connections (round 1, worker B).** (1) The 15 edges blocked at pins get their copper before routing,
by rule where there is one (a GND pin of a QFN next to its own exposed pad, a gate pad wrapped by its own stage's
pour) and by a short table of explicit escapes where there is none (CC pads under the protection chips); blocked edges
go to 0. (2) A finishing pass for what a full route leaves: continuation route with a team copy of the router (the
0.25 mm rule, more pulls), then the last connections by explicit track and via coordinates with a clearance check and
KiCad DRC after each, then dangling ends removed.

**C. Merge (round 2, lead).** One command with both sets of filters and the finishing pass; one local full route with
the hot loops; the same copper board queued on Logan's PC next to variants (filter options) for the spread of the
route count. What is still open after that decides round 2's worker tasks:
- a pin that is still boxed in: a part nudge of at most 0.5 mm in the fragment recipe (charger worker's method,
  `tools/part_peek.py`, partial screen), never a power-stage or hot-loop part;
- congestion that returns in every route (EN_5V1 from the MCU to U404 across the board, the I2C pairs to the ports):
  a planned lane or a pre-routed trunk for those nets;
- router quality: tracks that wander or change width (the cleanup pass of the pcb-scripted-routing skill, sections 6
  and 7), only after the gates are met.

**D. Final board (last round, lead).** The one command on a clean checkout; renders of F, B, In2, In3 looked at;
`final.json`; the routed board committed; `REPORT.md` and `SKILL-NOTES.md` with the phase 2 method added; `score.json`
kept as the shared-scorecard result of the placement.

## 6. Rules for every agent in phase 2

- Branch `layout-team-B` only. Shared tools (`tools/` at the repo root) are called or copied into `B/tools/`, never
  edited.
- Files: worker A owns `tools/straps.py`, `tools/write_copper_split.py` and its own new files; worker B owns only its
  own new files; the lead owns `tools/final_route.sh`, `tools/final_json.py`, `best_placement.json`, `candidates/`,
  `fragments/`, `PLAN2.md`. Each worker adds one section at the end of `tools/README.md` and one entry at the end of
  `LOG.md`; nothing else in those files is touched. A placement change is proposed as `candidates/<name>.json`, not
  written into the fragments, in round 1.
- Run dirs `runs/p2a-<name>` (worker A), `runs/p2b-<name>` (worker B), `runs/p2-<name>` (lead). Queue names on
  Logan's PC the same way. One router or hot-loop job at a time per agent on the local box.
- A copper-plan change is a filter on spec.json with the call form above, checked exactly (shapely, as `straps.py`
  does), and the copper board after it has 0 DRC errors.
- Real numbers only, each with its run dir; say when a route timed out. No model names in files or commits.
- Never order PCBs, never call a JLCPCB endpoint. Logan is reviewer only.
