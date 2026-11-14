# Team B log

Newest entry last. One entry per work session: what was done, the numbers (scorecard only), the files.

## 2026-11-14, lead: baseline and plan

**Baseline screen of the hand placement** (`tools/score/score_board.sh runs/hand_screen --route=0 --no-hot`, about 7 min, finished):

| Measure | Hand placement, generated copper |
|---|---|
| Blocked edges | 56 of 452 |
| DRC errors | 0 |
| Copper loss | 1.36 W |
| Power open | Port 1 PP5V at U401 (a hard-limit miss on the hand board itself); 3V3 at L201 and GND at J301, J302 (allowed) |
| Full route, hot loops | not run in this screen (charter reference: 391 of 448 in 18 min) |

Blocked edges by sheet (from `runs/hand_screen/ghost.log`): Port 2 25, Port 1 19, between the ports 3 (SDA and SCL from U401 to U501),
MCU 4, cells and gauge 2, other cross-sheet 3. By chip: U503 and U401 9 each, U501 8, U403 and U505 4 each, U405 3.
Per-net loss on the hand placement: GND 0.335 W, PACK_P 0.309 W, Port 1 AC_SNS_N 0.229 W, CELL_P 0.141 W.

**All parts at box centres.** Not run through the scorecard: with every part of a section on one point the board is
not a placement (all courtyards overlap), so copper, DRC and blocked edges would mean nothing. The cheap reference is the
wiring estimate, `tools/hpwl.py` (new):

| Placement | Signal half-perimeter |
|---|---|
| Hand placement | 2064 mm |
| r2d boxes, every part at its box centre (the brief's number, reproduced) | 2238 mm |
| r2d boxes, cup-fixed parts held where the template has them | 2316 mm |
| B1 boxes (r2d amended for the cup-fixed parts), cup-fixed parts held | 1847 mm (charger programming and the MCU parts share their chip's box, so part of the drop is the merge) |

**Finding: the r2d boxes do not fit the cup-fixed parts.** r2d was made with only J, H, TP, SW fixed. With U301, L401, L501,
the four NTCs and the ten back-side capacitors also fixed (groundup README), five r2d boxes hold a fixed part of another
section or miss their own anchor: Port 2 stage (L501 is 3 mm above its box), Port 2 charger and Port 1 9 V supply (L501
inside), protection FETs and second-level protector (U301 inside), MCU module, pull-ups and antenna match (U301 is 20 mm
away), and the three bottom boxes. Picture: `plan/r2d_vs_fixed.png`. The amended boxes are `plan/boxes_B1.json`
(`plan/boxes_B1.png`), each change with its reason in the file's `why`. Port 1's r2d boxes are kept except the 9 V supply.

**Finding: two boxes are over-full on the top side** (courtyard area over free box area): Port 1 9 V supply 1.37 and
Port 2 5 V buck 1.14; second-level protector 1.31. Whole top side: 1441 mm2 of movable courtyards on 2538 mm2 free (57 %).
So the plan puts both 9 V gate-drive supplies and the second-level protector's filter parts on the bottom side.

**Finding: the shared `apply_placement.py` cannot change a part's side.** Bottom-side moves need a team copy that flips, and
the scorecard is then fed the placed board file instead of a placement json.

Files: `PLAN.md`, `plan/boxes_B1.json`, `plan/boxes_B1.png`, `plan/r2d_vs_fixed.png`, `plan/clusters_movable.json`
(245 movable parts by section), `tools/hpwl.py`, `tools/draw_boxes.py`, `runs/hand_screen/` (score.json, F.png, B.png, ghost.log).

## 2026-11-14 14:35 UTC, orchestrator note (applies to every team B agent; overrides "do not push" for this one case)
Full trial routes can now run on Logan's 16-core PC, up to 12 at once (approved by Logan). Prefer this to a local 45-min route.
To queue a board: copy the scorecard's cu.kicad_pcb, cu.kicad_pro, cu.kicad_dru to docs/layout-teams/B/route_queue/<new-unique-name>.kicad_pcb/.kicad_pro/.kicad_dru, commit ONLY those files on layout-team-B, then `git pull --rebase origin layout-team-B; git push -u origin layout-team-B` (retry up to 4 times on network errors). Pushing to layout-team-B is allowed for this; never push any other branch.
Results (server polls every 2 min; a route takes up to ~45 min): `git fetch origin route-results && git show origin/route-results:B/<name>-<first 8 of the .kicad_pcb file's git blob sha>.json` (blob sha: `git hash-object <file>`). It holds routed, failed, total edges, minutes, status; a .log sits beside it. Use a new name for each changed board. Keep blocked-edge screens local.

## 2026-11-14 16:10 UTC, framework worker: placement framework and its tests

**Built** (all in `tools/`, usage in `tools/README.md`): `blib.py` (board as data, transform with flip, legality,
cost terms), `secplace.py` (recipes to fragments), `check.py` (legality, rings, escape, pin distances, box/region,
bottom count, hpwl, picture), `stitch.py`, `apply_b.py` (KiCad: flips, `--partial`, pad check against blib),
`screen.sh` (+ `score_part.sh`, a copy of the scorecard steps for partial boards, and `partcons.py`, the filtered
constraints), `blame.py`, `hand_fragments.py`; `tools/data/board_extra.json` (real outline and pin names from the bare
template). Fragments: `fragments/hand/` (the hand placement as port1/port2/pack, the usual `--base`) and
`fragments/example_buck5v/`. Recipes: `recipes/common/border.json` (PLAN 5 via fields and centre area) and the worked
example `recipes/port1/05-buck5v.json`. KiCad 10 flip, found by test: `Flip(pos, FLIP_DIRECTION_LEFT_RIGHT)`, then try the
orientations; every pad matched blib's lx -> -lx, then turn.

**a. Round trip** (hand fragments, turn 0, template side; `stitch.py` then `screen.sh --route=0`, `runs/fw_roundtrip2`):
56 of 452 blocked, 0 DRC errors, 1.36 W, power_open as `runs/hand_screen` (Port 1 PP5V at U401, 3V3 at L201, GND at
J301, J302). Same blocked-edge list and same copper plan as `runs/hand_screen`. The shared scorecard on the same
placement as a 3-element json (`runs/fw_shared_hand3`): same bare board, copper plan and blocked edges, 1.359 W.
Loss differs between runs in the 4th decimal (GND 0.3352 vs 0.3350 W) even on identical bare boards and copper plans:
the copper file is written in a different order and the zone fill differs, so compare losses at 0.01 W.
Not met: "check.py reports no overlap among movable parts". The hand placement itself has 34 courtyard overlaps over
0.05 mm (worst C108/Q103 0.97 x 0.85 mm) and 121 touching pairs; `stitch.py` refuses it without `--allow-overlaps`.

**b. Flip test** (R455 to the bottom at 117.0, 76.0, `runs/fw_flip`): apply_b pad check passed (965 pads against
blib), R455 on B.Cu in cu.json, 0 DRC errors, 56 of 452 blocked, 1.359 W, same power_open.

**c. Partial reference screens of the hand placement** (`screen.sh <fragment> --partial --hot=<group's loops> --route=0`).
These are the pass marks; a group's partial screen is compared with these only (with the other groups absent the
planner draws different pours, so the counts are not the group's share of the whole-board 56):

| Group | Run | Blocked edges | Loss | Open power pins (besides GND at J301, J302) | Hot loops, loop total with package (tier 1) | DRC errors |
|---|---|---|---|---|---|---|
| Port 1 | `runs/hand_port1` | 27 of 180 | 0.482 W | none (PP5V at U401 joins here) | HL_5V 0.92, HL_IN 0.87, HL_OUT 0.77 nH (3 of 3 pass) | 0 |
| Port 2 | `runs/hand_port2` | 42 of 173 | 0.407 W | none | HL_5V 1.17, HL_IN 0.84, HL_OUT 0.85 nH (3 of 3 pass) | 0 |
| Pack side | `runs/hand_pack` | 7 of 156 | 0.613 W | 3V3 at L201 | HL_3V3 1.33 nH (1 of 1 pass) | 0 |

**d. Worked example** (Port 1 5 V buck on the hand base, `recipes/port1/05-buck5v.json`): runs clean, 12 parts placed,
0 failed steps. It puts the chip back at its hand spot: with every other hand part in place, the B1 5 V box holds
the chip, inductor and input capacitors but not the three 22 uF output capacitors (tried first). The hand spots of
C441..C443, R433, R434, C444, C446 and L402 cross region lines, hence the claims.
- Partial Port 1 (`runs/fw_buck_port1`): 25 of 179 blocked (hand 27 of 180), 0 DRC, 0.478 W, HL_5V passes 1.18 nH (hand
  partial 0.92), **GND open at U404** (hand partial: joined).
- Whole board stitched with the hand's other parts (`runs/fw_buck_whole`, `--route=0 --no-hot`): 54 of 454 blocked,
  0 DRC errors, 1.355 W, power_open adds **GND at U404**: a hard-limit miss, so this is a framework test, not a candidate.
- Finding: the copper planner is very sensitive at U404. C446 at its cheapest spot (0.27 mm above the hand's) opened
  both HL_5V and GND at U404; held at the hand height (0.02 mm off the hand spot) HL_5V closes but GND stays open;
  exactly at the hand spot both join (partial screen). The hot cost in secplace (edge gaps, a clear L-shaped way per
  link, no crossing, a return-via spot) does not model the planner's loop pours. Screen every hot step.
- Output capacitors C442, C443 land 2.0 and 6.8 mm from L402 pad 2: greedy, on a full hand base.

**What does not work or is limited:** `secplace.py` is greedy (one part at a time, best spot), so a part placed early
can strand its neighbour; the fixes are recipe order, `reserve` with `except`, `within` and `step`. The whole-board
`screen.sh` runs hot loops only with `--hot=all`. `check.py` pin limits cover the first hot-loop capacitor and the
`serves` capacitors only. `check.py` on the hand board, for reference: 77 escape faults (U403 15, U401 13, U501 13, U503 13, U101 10, U301 8, U405 3, U505 2), 34 overlaps, 5 edge, 56 parts outside their group's region, 13 pin-distance faults.

Files: `tools/*`, `recipes/common/border.json`, `recipes/port1/05-buck5v.json`, `fragments/hand/`,
`fragments/example_buck5v/`, `runs/fw_roundtrip2`, `runs/fw_shared_hand3`, `runs/fw_flip`, `runs/hand_port1`,
`runs/hand_port2`, `runs/hand_pack`, `runs/fw_buck_port1`, `runs/fw_buck_whole`.

## 2026-11-14, Port 1 worker: stage and charger passed, fragments/port1.json written (Port 2 can start)
Stage (`recipes/port1/01-stage.json`) and charger (`recipes/port1/02-charger.json`) passed their partial screen
(`runs/port1-chg-9`, `screen.sh --partial --hot="USB Port 1/HL_IN,USB Port 1/HL_OUT"`, 48 parts): HL_IN 0.80 nH, HL_OUT 0.74 nH,
both tier 1 (hand partial 0.87 / 0.77; hand all-parallel reference 0.82 / 0.83), 0 DRC errors, no open power pin besides GND at J301/J302,
9 of 96 blocked (partial, stage and charger parts only). Every stage and charger part was placed with `twin_check` on
(dx -23.02577, dy +0.006368) except R424, R427 (per port) and D410, D411 (9 V section). `fragments/port1.json` now holds all 88 Port 1
parts (front end and 9 V too; full-group numbers follow in the next entry). Port 2: copy the stage and charger refs from it with a
`translate` step.
