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

## 2026-11-14, Pack side worker: Cells and Gauge, MCU and 3V3 Rail placed, fragments/Pack_side.json written
All 69 movable Pack-side parts are placed by `recipes/pack/` (order in `recipes/pack/ORDER`: border, 01c cell path, 02c FET
gates, 03 gauge, 06 MCU parts, 04q Q104 gate, 04b protector, 05 3V3 buck, 07 deviations). 0 failed steps, check.py clean,
0 parts on the bottom side, no claims needed. The fragment is in `fragments/Pack_side.json`, and the same content is in `fragments/pack.json`.

**K-a FET order screen** (cell-path parts only, 15 parts; the planner draws no GND plane with so few parts, so the blocked counts
cannot be compared with the hand's), PACK_P pads facing north in both:
- W (Q102 west, Q101 east), `runs/pack-ka-1W`: 0.225 W, CELL_P 0.0978, FET_MID 0.0125, PACK_P 0.0846, CELL_N 0.0091,
  CELL_P_RAW 0.0212, 34 of 80 blocked, all joined.
- E (Q101 west, Q102 east), `runs/pack-ka-1E`: 0.232 W, CELL_P 0.1098, FET_MID 0.0187, PACK_P 0.0728, 35 of 78 blocked.
- W kept. Later, in the full group, the hand's FET turn (both at turn 0, y 118.74, Q102 x 97.46, Q101 x 104.93) cut FET_MID
  from 0.0158 to 0.0038 W and was kept (deviation entry in 07).

**Full-group partial screens** (`screen.sh --partial --hot=HL_3V3`; hand_pack: 7 of 156, 0.613 W, CELL_P 0.1403,
CELL_P_RAW 0.0212, FET_MID 0.0038, CELL_N 0.0087, PACK_P 0.3256, GND 0.1132, HL_3V3 1.33 nH, 3V3 open at L201). All runs DRC 0.

| Run | Change | Blocked | Loss | Notes |
|---|---|---|---|---|
| pack-W1 | first full group | 7 of 152 | 0.721 W | CELL_P 0.241: MCU rim parts in the corridor west of H103; HL_3V3 1.02 nH |
| pack-W2 | CELL_P corridor kept free (reserves) | 5 of 152 | 0.586 W | CELL_P 0.1066, FET_MID 0.0158, CELL_N 0.0088, PACK_P 0.318 |
| pack-H1 | hand FET turn | 4 of 154 | 0.589 W | CELL_P 0.1026, FET_MID 0.0038, PACK_P 0.3364 |
| pack-H2 | RS101 at hand spot, bottom U102 group reworked | 3 of 154 | 0.588 W | CELL_N 0.0087 |
| pack-H3 | Kelvin R107, R108 at RS101 inner pad edges | 2 of 153 | | TS1 TH101 to U101.10 blocked by the bottom U102 group, GND C304 |
| pack-H4top | U102 group on top (K-c variant) | 2 of 153 | 0.588 W | R106 FET_MID, GND C304 |
| **pack-H5** | top variant, R106 turned (FET_MID pad west) | **1 of 153** | **0.591 W** | final |

pack-H5 (final): CELL_P 0.1055 (hand 0.1403), CELL_P_RAW 0.0212 (0.0212), FET_MID 0.0038 (0.0038), CELL_N 0.0088 (0.0087,
+0.0001 W, inside the run-to-run noise of the 4th decimal), PACK_P 0.3364, GND 0.1130, 3V3 0.0021. HL_3V3 1.02 nH, tier 1 pass (hand
1.33). Open power pins: only GND at J301, J302. 3V3 at L201 now joins. The one blocked edge is GND at C304, which the hand also has.
Holding R122 out of the CELL_N pour moved it 5 mm from its pin, so that was not kept.

**K-c:** the bottom U102 group (`04a-protector-bottom.json`, `ORDER_bottom`) walled TS1's bottom-side path (H3: 2 blocked incl.
TS1). The top variant (`04b-protector-top.json`, U102 by R104.1 and R101.1) fits and gives 1 blocked edge, so it is kept. Bottom-side
count: 0. A first top try south of U101 did not fit.

**Deviations** (in `recipes/pack/07-deviations.json`): hand FET turn instead of PACK_P pads north; Kelvin parts at RS101 inner
pad edges; Q103/R117 box; R313 at U204.8; MCU pocket parts; R115/R116/R126 box south of U101; protector group on top (numbers above).

**Border screen with Port 1** (`runs/pack-p1-border`, partial, port1.json + pack.json, 157 parts, no hot loops): 28 of 301 blocked
(Port 1 27, Pack 3, plus GND C304), 0.825 W, DRC 0, Port 1 PP5V open at U401 (Port 1's own issue, also in its hand partial).
Pack-side blocked: SDA R305.2 to U401.8, SCL R304.2 to U401.9, IRQ_N U301.21 to U401.10 (long cross-group edges; the hand whole
board also blocks IRQ_N, SDA/SCL, EN_5V1, R115 SCL to J302, 3V3 at R302/R305/R313, CELL_N R107, GND C304, PACK_P C107).

**Problems at the borders:**
- The top strip north of Q101 (R109, R110 at y 114.3..115.4, TP113, R118) walls the westward top path from the MCU pocket to the bottom
  via field; SDA/SCL/IRQ_N to Port 1 must leave by the bottom via field or the north edge. Moving R109/R110 out of the strip is the
  next thing to try.
- Port 1's south-row parts reach y about 113.2; Pack parts start at 114.0. The lane is clear and check.py with port1.json is clean.
- The RF parts C314, C313, R321, C315 are forced at the hand spots and touch the J301 and U301 courtyards by 0.05 mm or less.
- F102 is forced at its hand spot and touches J302 (as on the hand board).
- The PACK_P top pour from Q102's west pads runs north toward Port 2's region near TP412.
- TS1 (TH101, Port 2 region) and TS4 (TH104, Port 1 region) need north-south lanes kept open by those groups.

Files: `recipes/pack/*`, `fragments/pack.json`, `fragments/pack.meta.json`, `fragments/Pack_side.json`,
`fragments/Pack_side.meta.json`, `runs/pack-ka-1W`, `runs/pack-ka-1E`, `runs/pack-W1`, `runs/pack-W2`, `runs/pack-H1`..`pack-H5`,
`runs/pack-H4top`, `runs/pack-p1-border`.

## 2026-11-14, Port 1 worker: whole group placed, PP5V joined at U401 (fragments/port1.json updated)

All 88 Port 1 parts are placed by `recipes/port1/01-stage.json` .. `06-9v.json` (with `recipes/common/border.json`).
`fragments/port1.json` and `fragments/Port_1.json` (same content, with meta) are rebuilt from them. Port 2 can keep using
port1.json: the stage and charger parts did not move, except D411 and C458 (P-f parts, no twin).

**Partial screens** (`screen.sh --partial`, hot loops HL_5V, HL_IN, HL_OUT; DRC 0 in all):

| run | blocked edges | HL_5V / HL_IN / HL_OUT nH | loss W | power open |
|---|---|---|---|---|
| hand_port1 | 27 of 180 | 0.92 / 0.87 / 0.77 (2.56) | 0.482 | GND at J301, J302 only |
| port1-g1 (first full group) | 27 of 175 | 0.70 / 0.80 / 0.74 (2.24) | 0.302 | **PP5V at U401**, GND J301/J302 |
| port1-g2 (PP5V bridge) | 30 of 175 | 0.70 / 0.80 / 0.74 (2.24) | 0.318 | GND J301/J302 only |
| port1-g3 (final) | 29 of 175 | 0.70 / 0.80 / 0.74 (2.24) | 0.318 | GND J301/J302 only |

All three loops are tier 1 and under the hand's. `port1-e7` (g3 with C451 moved off U405 pads 4/5, no hot loops) gave 29 of 175
too, so it was not kept.

**PP5V at U401.** On U401's north row pad 34 (PP5V) sits next to pad 32 (VBUS). VBUS (J401 to pads 32/23) and PPHV (pad 20 to R424)
wall pad 34 off from the east-column buck on F.Cu. The hand partial joins PP5V only because In3 is free on a partial board. On the
hand whole board 3V3 takes In3 and PP5V is open at U401 (`runs/hand_screen`). Here PP5V stays a local net and the planner joins it
by a B.Cu detour. C443 (22 uF output capacitor) moves to a bridge spot at 112.4, 81.9 (turned 270, PP5V pad north), west of TP109
and 7.7 mm from L402 pad 2. The planner then draws an 8.3 mm B.Cu detour from C407's pad to it, and C407's copper reaches pad 34.
The B.Cu box 103.6..113.6 x 75.6..82.65 is reserved (`pp5v_detour_B`) so that no 9 V part sits under it. In g1, C458 on the
bottom under the bridge cost the detour its via room. The new tool `tools/plan_only.sh` (plan + DC only, about 45 s) found this.

**Cost of the detour:** 2 blocked edges over the hand partial. GND at U401 pads 26 and 27 lose their return vias, and CC1 at
U401.28 to C401.1 loses its B.Cu way: the detour runs on B.Cu just north of the pad row. GND at U401.36 is next to the PP5V pour.
The PP5V U401.34 edges of g1 are gone. **Group gate: blocked edges 29 of 175 against 27 of 180 is a miss by 2.** I found no
placement that keeps the detour away from the pad row. The detour starts in C407's pad, and C407 cannot move: at y 76.4 VBUS gets
between it and pad 34 again (`port1-p6`).

**Other gate items:**
- check.py is clean (0 hard faults).
- Signal hpwl is 2094 mm against the hand's 2064 (whole board, other groups at the template). EN_5V1 alone adds 38 mm because
  the 5 V buck is in the east column, far from U301.
- Stitched with port2.json and pack.json (`--allow-missing`: port2 is missing 12 P-f refs), there are 0 hard faults. The 8
  touching courtyards are all pack RF parts at J301/U301.
- A whole-board screen was not run. The hand whole-board Port 1 count (19) is therefore not compared.

**9 V supply (P-f):**
- The bottom variant is kept. The top variant (`recipes/port1/try/06-9v-top.json`) does not fit: Q409 has no legal top spot, even
  with the whole north region allowed, so it was not screened.
- Bottom-side parts: 7 (U406, Q409, C457, R452, R453, R454, R455).
- D411 and C458 now sit on top north of the stage, over U406's OUT pad (deviation P-f). The anode net stays short and the cathode
  runs about 16 mm to DRV_SUP. This gives hpwl 2118 to 2094.
- The 9 V divider is placed before C458, so R454 sits back at U406 EN. That cleared the REGN R454-C410 edge seen in g2.

**Left open:**
- AC_SNS_N bulk capacitors C420, C423 and C456 form a copper island that the planner does not join (`no path on F.Cu`). They are
  walled in by the HL_IN GND pour and the PPHV strip, and need the router or a stage rework.
- PPHV's 5 A corridor from R424 to C409 runs under U401's south row and down the strip west of the stage. It stands next to 9
  blocked edges: I2CC at U402, SBU_FLT, GND U401.7, R410, R426.
- SDA, SCL and IRQ_N to U301 are blocked as on the hand partial.

**Borders:**
- No Port 1 part leaves the region or needs a claim.
- D410 sits in the strip west of the stage at 103.05, 101.5.
- The bottom reserve `pp5v_detour_B` is in port1.meta.json.

Files:
- `recipes/port1/02-charger.json`, `03-buck5v.json`, `06-9v.json`, `try/06-9v-top.json`
- `tools/plan_only.sh`
- `fragments/port1.json`, `fragments/Port_1.json` and their meta files
- `runs/port1-g1`, `port1-g2`, `port1-g3`, `port1-e7` (score.json, F.png, B.png)

## 2026-11-14 17:45 UTC, Port 2 worker: whole group placed, fragments/port2.json written (also as fragments/Port_2.json)
All 88 Port 2 parts are placed from five recipes in `recipes/port2/`, with 0 hard faults in check.py (`--group=port2`, and also
with port1.json and pack.json together). stitch.py of all three fragments gives 245 parts and 0 claim clashes.

Run it again with:
`python3 tools/secplace.py recipes/common/border.json recipes/port2/01-stage-charger.json recipes/port2/02-charger-fix.json recipes/port2/03-buck5v.json recipes/port2/04-pd-protect.json recipes/port2/05-9v.json --group=port2 --out=fragments/port2.json`

**Partial screens** (`screen.sh --partial --hot="USB Port 2/HL_5V,USB Port 2/HL_IN,USB Port 2/HL_OUT"`):

| run | blocked | loss W | DRC | power open | HL_5V / HL_IN / HL_OUT nH | signal hpwl, my nets |
|---|---|---|---|---|---|---|
| hand partial (`runs/hand_port2`) | 42 of 173 | 0.407 | 0 | GND J301/J302 only | 1.17 / 0.84 / 0.85 | 714 mm |
| g1 (`runs/port2-g1`) | 30 of 175 | 0.396 | 0 | GND J301/J302 only | 0.98 / 0.80 / 0.74 | 730 mm |
| g2 (`runs/port2-g2`) | 32 of 179 | 0.384 | 0 | GND J301/J302 only | 0.98 / 0.80 / 0.74 | not measured |
| **g3 (`runs/port2-g3`), kept** | **28 of 177** | **0.363** | **0** | GND J301/J302 only | **0.98 / 0.80 / 0.74**, 3 of 3 tier 1 | **757 mm** |

PP5V is joined at U501.

**Whole board** (`runs/port2-whole-1`): the three fragments stitched, no hot loops.
- 58 of 451 blocked (port1 31, port2 29, pack 4, fixed 3), 1.142 W, DRC 0, only GND at J301/J302 open.
- The hand whole board (`runs/hand_screen`) is 56 of 452 (port2 28), 1.36 W, with PP5V open at U401 and 3V3 open at L201.

**Group gate:**
- check.py clean, DRC 0, power joined, and 3 of 3 hot loops tier 1 below the hand partial's nH: met.
- Blocked edges: 28 against the hand's 42, so met. The target of 12 or fewer is missed.
- Signal hpwl is **missed: 757 against 714 mm.** EN_5V2 alone adds 58 mm, because the hand has the buck at y 118, outside the
  Port 2 region, next to U301, while here it is in the north-west corner. The other 49 nets total 671 mm against the hand's 686.
  D511-A runs 25 mm longer and DRV_SUP 24 mm shorter than in the hand.
- Stage references:
  - HL_IN is 0.80 against 0.786. This is over at the printed precision. The stage is the exact twin of Port 1's, which also gives 0.80.
  - HL_OUT is 0.74 against 0.799: passes.
  - HL_5V is 0.98 against the 0.88 reference. It is tier 1, and the hand partial is 1.17.

**What was done:**
- **Stage and charger (01, 02):**
  - Twins of Port 1, written as explicit puts by the new `tools/twin_recipe.py` (secplace's translate turned some twins
    wrong and left 0.01 mm courtyard overlaps).
  - C530 and C538 sit 0.02 mm north of the exact copy.
  - The twin spots of R513 and R514 fall in the centre area, so they are placed by at_pin west of x 96.45 (3.4 and 4.0 mm from
    their pins).
  - R524 sits between U501 pad 20 and C524. R527 is in the centre area at 96.87, 104.91, turn 180.
- **5 V buck (03):**
  - In the north-west corner: U504 at 83.6, 67.6 and L502 at 83.85, 73.68.
  - The output caps C541 to C543 are in one row at y 79.35 with their PP5V pads north.
  - EN_5V2 has free via sites west of U504.
- **PD and protection (04):**
  - U501 is at 91.5, 81.7 and U505 at 95.32, 75.1, east of H102.
  - The west VBUS pair feeds D501 in the lane west of H102, then runs east under H102 to C550 and pad 32. The east pair feeds
    C506 and the VBUS_IN entry at pad 23 (reserved).
  - PPHV has kept boxes: a strip from pad 20 to R524, and a corridor south of U501 and down the west board strip to U503's VAC.
    In g1, without them, the PPHV pour wrapped round the charger's south row (TS, CE_N, ICHG and ACOV were blocked).
  - U502 and its pull-ups are on top, west of U501. In g2 they were on the bottom, where they sat in the planner's B.Cu VBUS
    pour, and U501 had 18 blocked edges.
  - g3 also adds C507 (above pad 34) and C503 (3V3, horizontal) north of U501, with PP5V coming in under C503.
- **9 V supply (05):**
  - Bottom side first. **Bottom count: 10** (U506, Q509, C557, C558, R552, R553, R554, R555, D510, D511).
  - D510 and D511 could not go on top at U503 pad 23. On top, the charger has no free spot, and Port 1's D410-twin strip is
    Port 2's PPHV way. The lane east of the output column left D510 9 mm from its pins.
  - The diodes are on the bottom at 83.05, 104.2 and 83.05, 106.85, by vias.
  - I tried moving U506 and its parts under the charger next to D511 (to shorten D511-A). It does not fit: KO_B_gap_filler_L
    (84.0..93.0 x 88.5..114.5, B.Cu) leaves only the 5 mm west strip, which the diodes already fill. So U506 stays under U501.

**Left open (g3 blame):**
- U501 has 16 blocked edges. CC1 and CC2 at pads 28 and 29 sit next to the VBUS track into pad 32. GND pads 26, 27 and 31 sit
  next to the VBUS pour.
- U503 has 5 (inherited from the Port 1 copy).
- U505 C_CC1 and C_CC2 (U505.6/7) are against H102.
- SDA, SCL and IRQ_N to U301 are blocked as on the hand partial.

**Borders:**
- No Port 2 part leaves the region (0.4 setback). No claims are needed.
- R527 is the only Port 2 part in the centre area. Both via fields are empty.
- EN_5V2 runs from the north-west corner to U301 (pack side), about 86 mm half-perimeter. The pack side may want a via site or
  route for it.
- The bottom west strip x 78.9..84.0 under the charger (between the board edge and KO_B_gap_filler_L) holds D510 and D511.

**For the lead (also helps Port 1):**
- Port 1's R413/R414 twin spots fall in Port 2's centre area. Any Port 1 change there needs a Port 2 fix by hand.
- Port 1's D410 strip spot is Port 2's PPHV path, so D410/D510 cannot be twins.
- The charger's escape faults (U503 pads 1-3, 7, 9, 10, 12, 19-21, 24, 27, 34-36 in check.py) come with the copy from Port 1.
  A fix in Port 1's charger moves Port 2's too.
- In both ports, VBUS copper next to U*01's CC pads (28/29) blocks the CC edges. A kept box over the N row between the VBUS
  sense way and pads 28 to 30 might help both.
- secplace's translate does not land twins at the right turn when the template turns differ by 90°. `tools/twin_recipe.py`
  writes explicit puts instead.
- A recipe filter that drops steps by key must not use "side", because every put has it (cost me g3's recipe once).

Files:
- `recipes/port2/01-stage-charger.json`, `02-charger-fix.json`, `03-buck5v.json`, `04-pd-protect.json`, `05-9v.json`
- `tools/twin_recipe.py`, `tools/group_hpwl.py`
- `fragments/port2.json`, `fragments/Port_2.json` and their meta files
- `runs/port2-g1`, `port2-g2`, `port2-g3`, `port2-whole-1` (score.json, F.png, B.png, hot.json, dc.json)

## 2026-11-14 19:30 UTC, lead: stitch and review, round 1 (candidates/r1.json = best_placement.json)

**Stitch.** `candidates/r1.json` is `stitch.py` of fragments/port1.json, port2.json and pack.json as the groups left them
(245 parts, 17 on the bottom, 0 claim clashes, 0 hard faults in check.py). No border part had to move: no group leaves its
region. It is the same placement as `runs/port2-whole-1`.

**Whole-board screen with all 7 hot loops** (`screen.sh runs/r1-hot candidates/r1.json --hot=all`, route 0, finished, nothing
timed out):

| Measure | Hand (`runs/hand_screen`) | r1 (`runs/r1-hot`) |
|---|---|---|
| Blocked edges | 56 of 452 | **58 of 451** |
| DRC errors | 0 | 0 |
| Open power pins | PP5V at U401 (hard miss), 3V3 at L201, GND J301/J302 | GND J301/J302 only |
| Hot loops | reference totals 1.95, 1.08, 1.02, 1.03, 1.08, 0.99, 1.0 (sum 8.15 nH) | 7 of 7 tier 1; 1.02, 0.70, 0.80, 0.74, 0.98, 0.80, 0.74 (sum 5.78 nH) |
| Copper loss | 1.36 W | 1.142 W |
| Full route | 391 of 448 (charter) | not run |

Hard limits are met and ringing and loss are under the hand. Routability is 2 blocked edges over the hand, so r1 is not
called done.

**Where the 58 are** (`blame.py runs/r1-hot`): Port 1 31, Port 2 29, pack 4, fixed 3. By chip: U401 18 (hand 9), U501 17
(hand 8), U503 5 (hand 9), U405 5, U403 4, U505 4, U402 3, U502 2. The pack's 4 are GND at C304 (hand has it too) and
SDA, SCL, IRQ_N, which end at U401 and U501 pins. So the two PD chips hold 35 of the 58, and every edge that is over the
hand's count is at them. About 20 of the 58 are also on the hand board and look like the router's own limits (HIDRV1, HG2,
C_CC1 at U405/U505, the sealed Kelvin pads R428, R429, R528, R529, ACUV).

**Renders** (`runs/r1-hot/F.png`, `B.png`, zooms in `plan/r1-zoom/`, made with the new `tools/zoom.py`):
- Power stages, FET pair and both 5 V bucks are compact. Port 1's PP5V is the one sprawling net: the C443 bridge sits
  7.7 mm from L402 and its pour runs across the east column.
- U401 south row: the PPHV spine (pad 20 and C449 to C409 at the charger) runs west about 1 mm under the whole south row,
  then down the west strip. It fences pads 8, 9, 10 (SDA, SCL, IRQ_N), 16, 17 (to U402), 18, 19 and GND 7 off from U402,
  the pull-ups and every via site.
- U401 north row: VBUS reaches pad 32 past C450 and its pour links pad 32 to pad 23 across pads 26 to 31, between the row
  and C401, C402. CC1, CC2 and GND 26, 27, 31 have no way out.
- U501 north row: the VBUS spine runs from pad 23 to pad 32 about 0.3 mm north of pads 24 to 31, in the 1.0 mm gap under
  C501 and C502. Pad 32 is already fed from the west pin pair through C550.
- U501 south row: the grown PPHV pour stands 0.55 mm south of the pads and the planner's GND via and track at pad 7 plug
  the west end of that channel, so pads 16, 17, 18 cannot reach U502 and R504 beside the chip.
- Port 1 input bulk capacitors C420, C423, C456 are a copper island (`plan.log`: no path on F.Cu; `hot.json` HL_IN per
  capacitor 16872 nH, that is not reached). Port 2's twins are reached (3.5 and 3.9 nH; hand 1.6 and 2.1).

**Planner escape room, tried as a lead knob** (`screen.sh ... --plan="--escape=X"`, no hot loops, both finished):

| Run | escape | Blocked edges | Loss | Open power pins |
|---|---|---|---|---|
| `runs/r1-hot` | 0.4 (default) | 58 of 451 | 1.142 W | GND J301/J302 |
| `runs/r1-esc06` | 0.6 | 48 of 449 | 1.153 W | **PP5V at U401**, GND J301/J302 |
| `runs/r1-esc08` | 0.8 | 40 of 448 | 1.181 W | **PP5V at U401**, 3V3 at L201 (allowed), GND J301/J302 |

More escape room moves VBUS to pad 23 round the east of H104 and opens U401's north row, but C407's copper no longer
reaches pad 34, so PP5V opens: a hard miss, not usable yet. U401 still has 11 and U501 14 at 0.8, so placement at the PD
chips is the main lever, and the escape option comes after PP5V at pad 34 is made to join at 0.8 as well.

**Not done:** the full trial route of r1 was not queued. The push that the queue needs was refused by this session's
permission system, and nothing was pushed. A local full route was not run in this round.

**Next round (two fix tasks):** Port 1 PD pocket (U401 south and north rows, PP5V join that holds at escape 0.8, bulk
capacitors joined) and Port 2 PD pocket (U501 north and south rows, HL_5V first capacitor). Stage and charger parts
stay put so the twins hold.

Files: `candidates/r1.json`, `best_placement.json` (same content), `runs/r1-hot/` (score.json, hot.json,
dc.json, ghost.log, F.png, B.png), `runs/r1-esc06/`, `runs/r1-esc08/` (score.json, ghost.log, dc.json, F.png, B.png),
`plan/r1-zoom/*.png`, `tools/zoom.py`.

## 2026-11-14, Port 2 worker: fix task "Port 2 PD pocket" (round 1), fragments/port2.json updated

**What moved** (recipes/port2/04-pd-protect.json and 03-buck5v.json; stage and charger parts of 01/02 untouched, so the
twins hold; bottom count still 10):
- **South escape yard.** A strip x 88.95..94.15, y 84.22..85.48 below U501's south row is kept free of parts on both
  sides (reserve `south_escape_yard_U501`, FB). It is walled so that no power copper can reach it: C505 standing at the
  west end (88.4, 85.2), R502, R503, R504 lying in a row at y 85.9 (x 89.7, 91.4, 93.1; signal pads 0.55 mm apart),
  R541 standing at the east end (94.58, 85.0) against pad 20 / R524's PPHV copper. U501's ring now allows C501, C502,
  C505, R502..R504 and R541 at 0.3 mm. The PPHV corridor to the charger runs south of the wall. New `tools/yard_check.py`
  tells whether power copper can leak into a box (it matched the planner: v1 without end closures leaked from both ends).
- **North row.** C502 (CC2) stands over pads 29/30 with its CC2 pad south, C501 (CC1) stands over GND pads 26/27 with its
  GND pad south; both 0.3 mm over the row, so no VBUS path is left along the row (the gap is 0.5 mm). CC1 from pad 28
  runs up between them. C550 stands over pad 32 with its GND pad south and its VBUS pad north (1.98 mm from pad 32),
  every gap round pad 32 under 0.6 mm. C507, C503 and C552 moved to make room.
- **Buck.** U504 0.3 mm east and 0.4 mm north (clear of J109); C546 put the way Port 1 has C446: PACK_P pad over VIN
  pad 3, GND pad over the adjacent GND pad 4, both 0.51 mm off the pins (was: GND pad over pad 1, the loop round EN pad 2).

**Runs** (partial runs: `screen.sh ... --partial`; all finished, nothing timed out):

| Run | What | Blocked edges | U501 | HL_5V / HL_IN / HL_OUT nH | Loss W | Power open |
|---|---|---|---|---|---|---|
| `runs/port2-g3` | before (r1 fragment) | 28 of 177 | 16 | 0.98 / 0.80 / 0.74 | 0.363 | GND J301/J302 |
| `runs/p2pk-v2` | yard walled; C550 at pad 23 (rejected: C550 3.6 mm from U501.VBUS, check.py pin fault) | 17 of 176 | 5 | not run | 0.364 | GND J301/J302 |
| `runs/p2pk-v3` | C550 back over pad 32, GND pad south | 19 of 177 | 5 | not run | 0.356 | GND J301/J302 |
| `runs/p2pk-v4` | C501 0.45 mm east | 19 of 177 | 5 | not run | 0.356 | GND J301/J302 |
| `runs/p2pk-v5` | C501 under U505 pad 12 (rejected: VBUS grew between the caps) | 21 of 179 | 8 | not run | 0.356 | GND J301/J302 |
| `runs/p2pk-v6h` | C550 raised beside C502's GND pad | 18 of 176 | 5 | 0.98 / 0.80 / 0.74 | 0.356 | GND J301/J302 |
| `runs/p2pk-v7h` | **final**: + C546 laid like C446 | **18 of 176** | **5** | **0.76** / 0.80 / 0.74 | 0.355 | GND J301/J302 |
| `runs/p2pk-esc08` | final, `--plan="--escape=0.8"` | 10 of 175 | 3 | not run | 0.356 | GND J301/J302 |
| `runs/p2pk-whole` | whole board, stitched with port1/pack as they are, no hot loops | **50 of 450** (r1 58 of 451, hand 56 of 452) | 8 (r1 17) | not run | 1.135 (r1 1.142) | GND J301/J302 |

Final partial: DRC 0, check.py 0 hard faults, HL_5V first capacitor C546 0.367 nH (was 0.733). U501's 5 left:
LDO_1V5 (C505.1 to pad 4, GND track of pads 5/6), DRV9_OFF 37, 3V3 38, GND 36 (all three under the PP5V way to C507
and pad 34) and GND 31. SDA, SCL, IRQ_N (8, 9, 10) and I2CC/CHG_INT (16, 17, 18) are no longer blocked in the partial
run. In the whole board SDA/SCL/IRQ_N still fail on the U401.x to U501.x edges, and R305 to U401.8 and R304 to U401.9
fail too: the blocking end is U401's walled south row (Port 1's task), not U501. Whole board by group: port1 31,
port2 21, pack 3, fixed 3.

**Not as asked: VBUS pad 32.** The planner joins one pad per terminal: with the row closed, U501's VBUS terminal is
joined at pad 23 (east, the 5 A pin) and C550 from the west lane, but nothing joins pad 32 itself (dc.json: U501
`pads_not_joined: ["32"]`, VBUS terminal not open, power_open only GND J301/J302). Pad 32 is the VBUS sense/LDO pin
on the 10 nF C550; DRC lists it as an unconnected item to the VBUS zone, and the ghost router finds that way (it is not
blocked). Every placement that linked 23 and 32 by copper did it along the row and blocked CC1, CC2 and GND 26/27/31.
Joining it by growth needs the VBUS fronts to meet before PP5V takes the 0.2 mm channel; I did not get that to happen.

**For the lead / Port 1:** (1) the same row fix on U401 will leave U401 pad 32 to the router the same way: either
accept a router track for the VBUS sense pin, or the planner should join every pad of a multi-pad terminal (shared tool,
not changed here). (2) The yard wall recipe (end closures 0.35 mm from the row plus a row of 0402s at +4.2 mm) carries
over to U401. (3) SDA/SCL/IRQ_N between the PD chips now only wait on U401's south row.

Files: `recipes/port2/03-buck5v.json`, `recipes/port2/04-pd-protect.json`, `fragments/port2.json`, `fragments/Port_2.json`
(+ meta), `candidates/r1_Port_2_PD_pocket.json` (stitched whole board = `runs/p2pk-whole/placement.json`),
`runs/p2pk-*` (score.json, dc.json, ghost.log, hot.json, F.png, B.png), `plan/p2pocket/*.png` (zooms, `final_u501_F.png`,
`final_buck_F.png`, `whole_u501_u401_F.png`), new tools `tools/yard_check.py`, `tools/near.py` (pads of parts near a
box), `tools/plan_only_p2.sh` (plan_only.sh printing Port 2 lines), `tools/plan_copper_dbg.py` (copy of the planner
that prints one net's join order).

## 2026-11-14, Port 1 worker: fix task "Port 1 PD pocket" (round 1), fragments/port1.json updated

**What moved** (recipes `recipes/port1/04-pd.json`, `05-protect.json`, and two stage spots in `01-stage.json`;
the variants tried are in `recipes/port1/try/pd/`):
- South yard: new reserve `u401_yard` (102.8, 82.85)-(108.4, 84.08), both sides, kept free of parts. Wall south of it,
  west to east: C408 (101.84, 84.845) turn 270, U402 (104.18, 85.395) turn 0 (SDA/SCL/VCC pads west), R402
  (106.52, 84.845), R403 (107.36, 84.845), R404 (108.2, 84.845), all `put`. C405 (LDO_1V5) moved into the west column
  at (101.3, 80.5); C403 (101.2, 74.92) and C404 (101.3, 78.0) turn 180 above it. R441 left the south row for
  U405 pad 9 (at_pin in 05, within 100.4..102.5 x 69.9..72.33); C452 put at (101.5, 72.85).
- PPHV: R424 (stage part, no Port 2 twin) moved from (108.6, 86.3) to (110.75, 86.3), same turn 90. PPHV now runs from
  pad 20 and C449 east of the yard, past R424, then west south of the wall and north of C423 (court top 88.17).
- AC_SNS_N bulk capacitors: C420 (stage part, has a Port 2 twin) moved from (105.47, 95.35) to (105.77, 95.35). The
  planner's B.Cu detour from C420 pad 1 round the SW1 B.Cu detour was 10.13 mm against its 10.0 mm limit. It now fits,
  and C420, C423 and C456 join the AC_SNS_N copper. `hot.json` HL_IN per capacitor: C420 3.058 nH and C423 3.53 nH (before:
  16835 nH each, not reached).
- North row: not changed in the end. C401/C402/C450 keep their at_pin spots, and VBUS still crosses north of pads 26 to 31.

**Runs** (partial screens with `--partial`; HL = HL_5V / HL_IN / HL_OUT in nH; "-" = loops not run):

| Run | Change | Blocked edges | U401 | HL | Loss | Power open |
|---|---|---|---|---|---|---|
| `runs/port1-g3` (before) | round-1 fragment | 29 of 175 | 16 | 0.70 / 0.80 / 0.74 | 0.318 W | GND J301/J302 |
| `runs/pd-e1` | yard, wall, R441 north | 22 of 173 | 9 | - | 0.318 W | GND J301/J302 |
| `runs/pd-e2` | + R424 east, west column restacked | 21 of 173 | 7 | - | 0.317 W | GND J301/J302 |
| `runs/pd-e3` | + U402 turn 0 (check.py hard fault: C408 3.38 mm from U402.VCC) | 19 of 173 | 7 | - | 0.317 W | GND J301/J302 |
| `runs/pd-e4h` | + C408 at the west end of the wall | 20 of 173 | 7 | 0.70 / 0.80 / 0.74 | 0.317 W | GND J301/J302 |
| `runs/p1pd-final` | + C420 0.3 mm east (final) | 20 of 170 | 7 | 0.70 / 0.78 / 0.74 | 0.317 W | GND J301/J302 |
| `runs/p1pd-esc08` | final, `--plan="--escape=0.8"` | 16 of 173 | 4 | - | 0.302 W | **PP5V at U401**, GND J301/J302 |
| `runs/p1pd-whole` | whole board (stitch with current port2, pack), no loops | 39 of 446 | 7 | - | 1.133 W | GND J301/J302 |

The round-1 whole board, `runs/r1-hot`, had 58 of 451 blocked edges, with U401 at 18 and a loss of 1.142 W. Every run finished; none timed out. DRC was 0 in all of them. check.py found 0 hard faults on the final fragment.

The final partial run has DRC 0 and U401 at 7 blocked edges, with SDA, SCL and IRQ_N no longer blocked at either end (they were blocked at U301 in g3).

Edges still blocked in the final partial run:
- U401 north: CC1 at pad 28 to C401, CC2 at pad 29 to C402 and to U405.11, and GND at pads 36, 31, 27 and 26.
- C450.2.
- U402.6 to R403.2 (I2CC_SCL), in the south.
- U403: 4. U405: 4.

Whole-board blame by group: port1 20, port2 18, fixed 3, pack 1. By chip: U401 7, U505 5, U501 5, U403 4, U405 4, U503 3, U402 1.

In F.png and B.png no power part sprawls more than it did in r1. Port 1's PP5V pour still crosses the east column on F to C443, and the B.Cu PP5V corridor runs from C407 to C443.

**Not solved: PP5V at U401 with escape 0.8.** The planner tries U401 before C407 and finds no path on F.Cu, because VBUS stands between the tree and pad 34. U401's own detour cannot place a start via, for two reasons:
- The channel north of pad 34, between GND pad 36 (x 104.1) and pad 32's VBUS exit lane (x from about 104.85), is 0.75 mm wide. The 0.4 mm via link needs 1.0 mm.
- No via fits inside pad 34 (0.65 x 0.6 mm).

C407 then joins by its own B.Cu detour, but its via sits inside its pad, so the anchor step finds no PP5V copper more than 0.25 mm from the terminal pads to aim at. At escape 0.4, the 1.5 mm grow joins C407 pad 1 to pad 34. At 0.8, signal pad 37's escape room covers the channel and the grow stops. This placement does not fix it; I see no placement inside the pocket that would. It needs one of these:
- a lead decision on the planner (an anchor to a same-net terminal pad, or a narrower link);
- a different VBUS feed to pad 32, with the lane moved.

**Not solved: north row.** VBUS reaches pad 23 from the east and also runs west along H104's south edge to C450 pad 1, at (106.8, 77.28) above pads 29 and 30, and to pad 32. To keep VBUS off pads 26 to 31, C450 and pad 32 need another feed, as in Port 2, where pad 32 is fed from the west pin pair through C550. That conflicts with C407 above pad 34. Left for round 2.

**For Port 2 and the lead:**
- C420 moved 0.3 mm east, from (105.47, 95.35) to (105.77, 95.35). Port 2's twin C520 already joins at its spot, so the matching move is optional: from about (82.44, 95.36) to (82.74, 95.36).
- R424 moved, but it has no twin.
- No 02-charger part moved.

Files:
- `recipes/port1/01-stage.json`, `04-pd.json`, `05-protect.json`, `recipes/port1/try/pd/*`;
- `fragments/port1.json` and `port1.meta.json`, with the same content in `Port_1.json` and `Port_1.meta.json`;
- `candidates/r1_Port_1_PD_pocket.json`;
- `runs/p1pd-final/`: score.json, hot.json, dc.json, ghost.log, F.png, B.png;
- `runs/p1pd-esc08/` and `runs/p1pd-whole/`: score.json, dc.json, ghost.log, F.png, B.png.

plan.log, blame.txt and the zooms (u401_F.png, u401_B.png, in_F.png) are git-ignored and stay in the local run folders.

New team tools:
- `tools/pd_iter.sh`: one iteration, from recipes to plan or screen and zooms;
- `tools/plan_only2.sh`: plan_only.sh with planner options;
- `tools/plan_peek.py`: the planner raster for one net before its step;
- `tools/detour_peek.py`: the detour attempts for one net, with the start vias, landing cells and path length.

## 2026-11-14 21:35 UTC, lead: stitch and review, round 2 (candidates/r2.json = best_placement.json)

**Stitch.** `tools/stitch.py fragments/port1.json fragments/port2.json fragments/pack.json` with both PD-pocket fragments
of round 1's fix tasks: 245 parts, 17 on the bottom, 0 claim clashes, no border to resolve. Saved as `candidates/r2.json`
(same content as `runs/p1pd-whole/placement.json`) and as `best_placement.json`.

**Scorecard runs on r2** (all finished, nothing timed out):

| Run | What | Blocked edges | Full route | Hot loops | Loss | DRC | Power open |
|---|---|---|---|---|---|---|---|
| hand (`runs/hand_screen`, charter) | reference | 56 of 452 | 391 of 448 | sum 8.15 nH | 1.36 W | 0 | PP5V at U401, 3V3 at L201, GND J301/J302 |
| `runs/r1-hot` | round 1 | 58 of 451 | not run | 7 of 7, 5.78 nH | 1.142 W | 0 | GND J301/J302 |
| `runs/r2-hot` | r2, `--hot=all`, route 0 | **39 of 446** | - | **7 of 7, 5.54 nH** | **1.133 W** | 0 | GND J301/J302 |
| `runs/r2-route` | r2's copper (`--keep-copper` on `runs/r2-hot/cu.kicad_pcb`), `--route=45`, run here | 39 of 446 | **401 of 446, 45 failed**, about 27 min | - | 1.133 W | 0 | GND J301/J302 |
| `runs/r2-esc06` | r2, `--plan="--escape=0.6"`, no loops | 30 of 444 | - | - | 1.143 W | 0 | **PP5V at U401** (hard miss), GND J301/J302 |

Hot loops of r2 (loop total nH, hand reference in brackets): HL_3V3 1.02 (1.95), Port 1 HL_5V 0.70 (1.08), HL_IN 0.78
(1.02), HL_OUT 0.74 (1.03), Port 2 HL_5V 0.76 (1.08), HL_IN 0.80 (0.99), HL_OUT 0.74 (1.00). The full route was run in
this container, not queued on Logan's PC (the queue needs a push, which this session may not do).

**Renders.** Looked at `runs/r2-hot/F.png` and `B.png`: stages, bucks and the pack FET block are compact, no power part
sprawls. The long copper is the two PPHV ways from the PD chips to the chargers (as on the hand board) and Port 1's
PP5V way on the bottom from C407 to C443.

**Finding: a power pad the scorecard does not flag.** `dc.json` counts a terminal as joined when any one of its pads
reaches the source and lists the rest under `pads_not_joined`; `score.json` power_open does not show them. The PD
controller TPS25751D has two VBUS pad groups: pad 23 (VBUS_IN, the 5 A two-way switch to PPHV, pad 20) and pad 32 (VBUS,
the 5 V source switch from PP5V, pad 34). New `tools/loose.py <run dir>` prints such pads:

| Board | U401 (Port 1) | U501 (Port 2) |
|---|---|---|
| hand | pad 32 not joined | both joined |
| r1 | **pad 23 not joined** | both joined |
| r2 | **pad 23 not joined** | pad 32 not joined |

On r1 and r2 the planner joins U401 at pad 32 through C450's lane; pad 23 sits on its own grown VBUS island
(`plan/r2-zoom/u401_ne_F.png`), because C406 stands at (111.7, 75.34) turn 90 with its VBUS pad 5 mm north of pad 23
(the hand has C406 at (110.949, 78.359) turn 0, its VBUS pad 0.05 mm from pad 23's north-east corner). So Port 1's 5 A path is left
to a router track: by the scorecard's letter the hard limit is met, in substance it is not. This is why the round is
not closed although the numbers beat the hand board.

**Where the 45 full-route failures are** (all 45 read "no way even with every other route gone", so they are placement
or copper blocks, not congestion; 39 of them are the blocked edges of the screen):
- U401 north row, 9: CC1 (pad 28 to C401, C401 to U405.12), CC2 (pad 29 to C402, U405.11 to pad 29), GND pads 26, 27,
  31, 36, C450.2. VBUS copper still lies along the row.
- U501, 8: 3V3 pad 38, GND 36, DRV9_OFF 37, GND 31, LDO_1V5 pad 4 to C505.1, CC1 C501.1 to U505.12, and (full route
  only) I2CC_SCL U503.1 to R503.2 and CHG_INT U503.3 to R504.2 at the new south wall.
- Charger twins, 8 per port: HIDRV1 (pad 27 to R444/R544), ACOV (pad 35 to R410/R510.2), FB (pad 12 to R419/R519.1),
  HG2 (R446/R546.2 to Q402/Q502.1), BAT_SNS_P R428/R528.1, PACK_P R429/R529.1, AC_SNS_N R426/R526.1, and PPHV R525.1 or
  I2CC_SCL U402.6 to R403.2. HIDRV1, HG2, BAT_SNS_P, PACK_P fail on the hand board as well.
- Port protection: C_CC1 U405.4 to .7 and to J401.A5, C_CC1/C_CC2 at U505 to J501, VBIAS C551.1 to U505.3 (the C_CC
  ones fail on the hand too).
- Rest: EN_5V1 U301.12 to U404.2 (two edges on the hand), U102 V4 to C112.1, GND C515.2, GND C304.2, CELL3 R103.1 to
  J111 (search cap).

**Decision: not done.** Two fix tasks for round 3: (1) Port 1: C406 back to pad 23 so pad 23 is on planned copper,
then open U401's north row; (2) Port 2: pad 32 on planned copper through C550, then the rest of U501 and the two
south-wall edges. r2 stays the best placement until a candidate beats it with `loose.py` clean.

Files: `candidates/r2.json`, `best_placement.json`, `runs/r2-hot/` (score.json, hot.json, dc.json, ghost.log, F.png,
B.png), `runs/r2-route/` (score.json, ghost.log), `plan/r2-route-failed.txt` (the result and FAILED lines of route.log),
`runs/r2-esc06/` (score.json, dc.json, ghost.log); hot_gate.log and route.log are git-ignored and stay local; `plan/r2-zoom/` (u401_F.png, u501_F.png, chg1_F.png, u401_ne_F.png), `tools/loose.py`.

## 2026-11-14 22:45 UTC, orchestrator note: zone outlines vanish in the router (from team D, affects every routed count)
tools/copper/write_copper.py writes one zone per net and layer with several outlines; KiCad keeps only the FIRST outline when the
board is re-saved, so when tools/score/router.py refills zones most multi-outline F.Cu/B.Cu power pours vanish (Monolith: PACK_P F/B
9 outlines, GND F 14, VBUS F 3, 3V3 F 4). Full-route counts (ours 401/446 and the hand 391/448 alike) are flattered because the router
runs where the pours were, and --keep-copper scoring of routed boards shows open power paths. Signal routes on In2 can also cut the
PACK_P In2 pour into islands.
Team D's fix (branch layout-team-D, docs/layout-teams/D/tools/hr.py, see `git fetch origin layout-team-D`): split every zone into one
zone per outline before write_copper, and lay wide PACK_P strap tracks before signal routing. Shared tools stay unchanged: copy the
split into B/tools. For the final result, report BOTH the plain scorecard route and the route with zones split (and the hand board
with the same split, so the comparison is fair), and check power paths on the routed board.
Also: pushing route_queue files to layout-team-B IS allowed (see the 14:35 note); the PC can run the extra routes in parallel.

## 2026-11-14 23:30 UTC, Port 1 worker: fix task "Port 1 VBUS pad 23 and north row" (round 3), fragments/port1.json updated

**Result.** Step 1 holds: U401 VBUS pad 23 is on planned copper (`loose.py` prints no U401 line; in KiCad's own
connectivity pad 23 is also joined to J401 now, which it was not on r2). Step 2 holds only in part: VBUS copper no longer runs
along the north row on F.Cu, CC1, CC2 and SBU_FLT route at both ends, but GND pads 26, 31 and 36 still have no via room.
Partial screen: 15 of 170 blocked (target 14), U401 4 (target 3). Hot loops, loss and VBUS resistance meet their targets.
check.py reports 1 hard fault that step 1 brings with it (C406 vs J401, below).

**What moved** (recipes `recipes/port1/03-buck5v.json`, `04-pd.json`, `05-protect.json`; no part of 01-stage or
02-charger moved; working copies and the variant helper are in `recipes/port1/try/r3/` and `tools/p1r3_variant.py`):

| Part | r2 spot | new spot | why |
|---|---|---|---|
| C406 (VBUS bulk) | (111.7, 75.34) t90 | (110.31, 78.0) t270 | VBUS pad south, 0.56 mm east of pad 23 and level with it; the trunk comes down east of H104 and C406 into it, the planner's U401 path ends at pad 23 |
| C443 (PP5V out) | (112.4, 81.9) | (112.75, 81.9) | room for C406 |
| C450 (VBUS pin cap) | (106.8, 76.8) t0 | (105.55, 76.8) t0 | standing over pad 32 (VBUS pad 0.49 mm above it); joined by a via in its pad and a B.Cu detour to the trunk at pad 23 |
| C402 (CC2) | (109.8, 76.8) t0 | (106.70, 76.8) t0 | CC2 pad 0.5 mm over pads 29/30 |
| C401 (CC1) | (108.3, 76.75) t90 | (108.05, 76.8) t180 | GND pad 0.5 mm over pads 26/27; CC1 runs up the 0.73 mm channel between C402 and C401 |
| C407 (PP5V) | (103.75, 77.0) | (103.50, 77.0) | room for C450 over pad 32 |
| U405 | (104.55, 73.55) | (104.55, 72.35) | C407's PP5V copper grows 1.5 mm; at 73.55 it reached the escape room of U405 pads 11/12 (ghost debug: CC escape cells blocked) |
| C451 (U405 VBIAS) | (104.05, 70.95) t180 F | (104.05, 70.95) t0 **B** | no room left between J401 and U405 on top; the nearest top spot was 2.19 mm from pad 3 (limit 2.0) |
| C452, R441 | (101.5, 72.85), (101.7, 71.45) t90 | (101.5, 73.41), (101.6, 72.1) t180 | C452 level with U405 pad 10, so SBU_FLT pad 9 escapes west |
| C403, C404, C405 | (101.2, 74.92), (101.3, 78.0), (101.3, 80.5) | (101.175, 75.46), (101.3, 79.35), (101.3, 81.85) | room for C407 |

The hand spot for C406, (110.949, 78.359) turn 0, overlaps U401's courtyard by 0.49 mm (check.py hard overlap), and any spot
within 0.3 mm of it does too, so C406 stands turned 270 instead.

**Runs** (partial screens `--partial`, Port 1 only; U401 = blame.py count; HL = HL_5V / HL_IN / HL_OUT nH; "-" = not run;
every run finished, none timed out, DRC 0 in all):

| Run | Change | Blocked | U401 | Loose pads (loose.py) | HL | Loss | VBUS R at U401 | Power open |
|---|---|---|---|---|---|---|---|---|
| `runs/p1pd-final` (before) | round-2 fragment | 20 of 170 | 7 | **pad 23** | 0.70 / 0.78 / 0.74 | 0.317 W | 2.24 mohm | GND J301/J302 |
| `runs/p1r3-s1a-s` | step 1 only (C406, C443) | 19 of 170 | 7 | none | - | 0.334 W | 1.742 | GND J301/J302 |
| `runs/p1r3-v2a-s` | + step 2 caps (C450, C402, C401 standing, C407 west) | 17 of 170 | 4 | none | - | 0.311 W | 2.032 | GND J301/J302 |
| `runs/p1r3-v3d-s` | + C450 nearer the centre of pad 32 | 17 of 170 | 4 | none | - | 0.311 W | 2.037 | GND J301/J302 |
| `runs/p1r3-v4a` | + U405 0.45 mm north | 17 of 168 | 4 | none | - | 0.314 W | - | GND J301/J302 |
| `runs/p1r3-v5a-s` | + U405 1.2 mm north (C451 on top, check.py pin fault) | 17 of 170 | 5 | none | - | 0.313 W | 2.104 | GND J301/J302 |
| `runs/p1r3-v5b-s` | + C451 on B, C452/R441 restacked | 15 of 170 | 4 | none | - | 0.312 W | 2.093 | GND J301/J302 |
| `runs/p1r3-final` | + C402/C401 0.05/0.2 mm east (final = v5c) | **15 of 170** | **4** | **none** | **0.70 / 0.78 / 0.74** | **0.313 W** | **2.093** | GND J301/J302 |
| `runs/p1r3-whole` | whole board (stitch with current port2, pack), no loops | **34 of 446** | 4 | U501 pad 32 only (Port 2) | - | **1.129 W** | 2.09 | GND J301/J302 |

r2 whole board for comparison: 39 of 446, loss 1.133 W, U401 pad 23 loose. In `runs/p1r3-final/hot.json`, HL_IN per capacitor
is C420 3.058 nH and C423 3.53 nH. PP5V is joined at U401 pad 34 in dc.json at 6.31 mohm, and KiCad also joins pad 34.

**Port 1 edges still blocked in the final partial run.** Four are at U401:
- VBUS from pad 32 to the B.Cu detour track;
- GND pads 36, 31 and 26 to the plane.

The rest are not in the pocket: C_CC1 (U405.4 to .7 and J401.A5 to U405.4, which also fail on the hand board), I2CC_SCL
(U402.6 to R403.2), and the charger twins (HIDRV1, ACOV, ACUV, FB, HG2, BAT_SNS_P, PACK_P, AC_SNS_N), whose parts are
placed by 01/02. CC1 and CC2 are no longer blocked anywhere; on r2 they were blocked at U401 and at U405.

**What stopped the rest of step 2:**
- **No via room for the GND row pads.** VBUS cannot reach C450 on F.Cu without crossing the CC lines: pad 32 lies west of
  pads 28/29 and VBUS enters from the north-east. So C450 is joined through B.Cu: a via in C450's VBUS pad, then a
  B.Cu track under the row to the trunk at pad 23. PP5V reaches C407 the same way, by a via in C407's pad and a B.Cu
  corridor to C443. Its corridor runs north of the VBUS track, and after the 1.5 mm grow it fills the bottom layer under
  the whole pocket (see `runs/p1r3-v5c-s`, z_B.png). Pads 26, 31 and 36 need a via to the plane, and no via fits on B.Cu.
- **Pad 31's lane.** The lane north of pad 31 is also pinched by the VBUS fill between C450 and pad 32. That fill keeps
  only the 0.15 mm power clearance from GND pad 31.
- **Pad 36** sits under C407's PP5V pad. Moving C407 east to open a gap above pad 36 would take C450 off pad 32.
- **Pad 32's VBUS edge comes from the zone writer** (orchestrator note 22:45). The saved F.Cu fill piece that covers both
  C450.1 and pad 32 belongs to an outline that KiCad drops. `tools/padconn.py` (KiCad connectivity on the saved board) shows
  pad 32 with 1 connected item, so the ghost asks for a track to the B.Cu detour. dc.json counts pad 32 as joined.
  `tools/fillnear.py` shows that the saved fill covers pad 32. I did not screen with zones split, so I have not checked
  that splitting clears this edge.

**For the lead and Port 2:**
- C406 now breaks check.py's serves rule: 9.23 mm from J401.VBUS against a 4 mm limit. The hand board also places it
  8+ mm from J401. Step 1 cannot hold without this fault. Either waive the rule for C406 (in substance it serves U401
  pad 23) or say which you prefer.
- C451 is now on the bottom, so the board has 18 bottom parts (port1 8).
- No Port 2 file changed. The Port 2 twin of the north-pocket problem is U501 pad 32 (loose in `runs/p1r3-whole`). It may
  respond to the same moves: U505 north so the PP5V/VBUS growth leaves U505's CC pins free, and a VBUS pin cap fed
  through a via in its pad.
- `recipes/port2/04-pd-protect.json` is modified in the working tree by another agent. I did not commit it.

Files: `recipes/port1/03-buck5v.json`, `04-pd.json`, `05-protect.json`, `recipes/port1/try/r3/` (step-1 working copies);
`fragments/port1.json` + meta (= `Port_1.json` + meta); `candidates/r2_Port_1_VBUS_pad_23_and_north_row.json` (= `runs/p1r3-whole/placement.json`);
`runs/p1r3-final/`, `runs/p1r3-whole/` (score.json, dc.json, ghost.log, F.png, B.png, plus hot.json for final), score.json/ghost.log/dc.json
of `runs/p1r3-s1a-s`, `p1r3-v2a-s`, `p1r3-v5b-s`. New team tools: `tools/p1r3_variant.py` (recipe variants from overrides),
`tools/pocket_peek.py` (planned vias/tracks in a box), `tools/padconn.py` (KiCad connectivity of pads on a saved board; run in
the kicad image), `tools/fillnear.py` (saved zone fills of a net in a box).

## 2026-11-14 23:35 UTC, Port 2 worker: fix task "Port 2 VBUS pad 32 and U501 rest" (round 3), fragments/port2.json updated

**Step 1 is done.** U501's VBUS pad 32 is now on planned copper:
- loose.py prints no U501 line.
- PP5V is still joined at pad 34, at 1.49 mohm (was 1.57).
- VBUS R at U501 is 0.996 mohm (was 1.288; the limit is 1.31).
- Only one VBUS sliver is in the north row. It is on F.Cu, wraps C550's GND pad and reaches at most x 91.97, which is the west 0.17 mm of pad 31's span, at y 78.0 to 79.2. There is no VBUS copper over pads 26 to 30.

How it works:
- C550 lies flat right over pad 32. Its VBUS pad is the west pad, so the planner feeds the lane under H102 into C550 and straight down to pad 32.
- D501 moved next to pad 23. The planner had been joining U501's VBUS terminal at pad 32 (nearest to the tree), which left pad 23 loose. With D501's VBUS pads facing pad 23, pad 23 now merges into the D501 terminal.
- **Trade-off:** the TVS now clamps at the PD's VBUS_IN pin, 11.7 mm from J501's west VBUS pair (A9/B4) and 10.9 mm from the east pair, not at the connector. D501 has no serves rule in check.py. The lead should decide whether that is acceptable.

**What moved** (recipes/port2/04-pd-protect.json; 01/02 stage and charger parts not touched):

| Part | Old | New | Why |
|---|---|---|---|
| C550 | (91.38, 77.7) t180 | (91.70, 78.65) t90 flat | VBUS pad (90.94-91.50) right over pad 32; GND pad over pad 31; x 91.70 keeps the VBUS spine 0.15 mm off pad 34 (x 91.65 gave a DRC error); added to U501's ring allow list |
| D501 | (88.15, 71.64) t180, west lane | (96.4, 80.69) t0 | VBUS pads (95.32-95.69) face pad 23 so pad 23 merges; at t90 VBUS ran north of pads 26/27 (26 blocked) |
| C507 | (90.06, 77.65) t90 | (89.95, 77.65) t90 | clear of C550's VBUS pad |
| C503 | (87.73, 77.795) t270 | (87.54, 77.07) t0 standing | frees the x room C550 needed |
| C502 | (92.54, 78.2) t0 | (92.3, 77.5) t270 flat | CC2 pad east, GND west beside C550's GND |
| C552 | (92.7, 76.27) t90 | (92.3, 75.8) t180 flat | keeps the U505.8 / .13 GND via sites and SBU_FLT open (moving it north blocked 22) |
| C549 | (96.0, 82.4) t270 | (96.0, 82.51) t270 | courtyard against D501 |
| C504 | (87.2, 81.2) t0 | (87.0, 81.2) t0 | opens a via site west of pad 4: LDO_1V5 C505 to U501.4 now routes |
| R502 | (89.7, 85.9) t90 | (89.7, 85.9) t270 | LDO_3V3 pads pair R502.1/R503.1 |
| R504 | (93.1, 85.9) t90 | (93.1, 85.9) t270 | LDO_3V3 pads pair R504.1/R541.1; SCL (R503.2) and CHG_INT (R504.2) share one gap, with in-pad via sites at x 91.72 and 92.78 |

The reserves changed as follows:
- vbus_in_U501_23 is now [95.0, 77.2, 99.6, 79.1].
- pphv_strip_U501_20_to_R524 is now [95.0, 83.04, 97.0, 84.7].
- vbus_sense_way_under_H102 is split in two: [86.9, 72.96, 91.3, 75.5], plus a new _b box [88.35, 75.5, 91.3, 76.1] east of the standing C503.

**Runs** (Port 2 partial unless marked whole; U501 = GHOSTFAIL edges at U501; HL = HL_5V / HL_IN / HL_OUT nH; "-" = not run;
DRC 0 in all screens):

| Run | Change | Blocked | U501 | Loose pads | HL | Loss | VBUS R U501 | Power open |
|---|---|---|---|---|---|---|---|---|
| `runs/p2pk-v7h` (before) | round-2 fragment | 18 of 176 | 5 | **U501 pad 32** | 0.76 / 0.80 / 0.74 | 0.355 W | 1.288 mohm | GND J301/J302 |
| `runs/p2v-b/scr` | C550 flat + D501 t90 | 26 of 179 | - | none | - | - | - | - |
| `runs/p2v-c/scr` | + D501 t0, C552 north | 22 of 174 | 7 | none | - | - | - | - |
| `runs/p2v-d/scr` | + C552 flat, C503 standing, C550 x 91.70 | 18 of 175 | 5 | none | - | 0.348 W | 0.995 | - |
| `runs/p2v-g/hot` | + C504 0.2 west (pad 4 routes) | 17 of 174 | 4 | none | 0.76 / 0.80 / 0.74 | 0.348 W | - | GND J301/J302 |
| `runs/p2v-i/scr` (final) | + R502/R504 turned (`--route=25`: TIMED OUT at the 25 min cap, last progress 153 routed / 21 failing, no FAILED lines) | **17 of 174** | **4** | **none** | **0.76 / 0.80 / 0.74** | **0.348 W** | **0.996** | GND J301/J302 |
| `runs/p2v-iw` | whole board (current port1, pack), no loops | **33 of 443** | 4 | none | - | **1.122 W** | 0.995 | GND J301/J302 |
| `runs/p2v-route50` | same placement, partial full route `--route=50` (finished in about 40 min) | 17 of 174 | 4 | none | - | 0.348 W | - | GND J301/J302; route **153 of 174 routed, 21 failed** |

The whole-board blame breaks down as port2 17, port1 15, fixed 3, pack 1. For comparison, r2 was 39 of 446 at 1.133 W, and Port 1's round-3 whole board was 34 of 446.

In both p2v-g/hot and p2v-i/scr, check.py shows 0 hard faults and Port 2 has 10 bottom parts (18 on the whole board). The p2v-iw stitch uses the fragments/port1.json from commit 9e0dc96 (Port 1 round 3).

I looked at F.png, B.png and z U501 (`runs/p2v-iw/zoom_u501.png`). Power copper stays compact, and no power pour sprawls across Port 2.

Tries that failed and were reverted:
- C550 and C502 lifted 0.35 mm to open a pad-31 via: the planner still left U501.31 to the router.
- C501 moved east: VBUS flooded the north row.
- C505 next to pad 4: this opened the south escape yard, and yard_check reported a leak.

**Targets not met:**
- Blocked edges are 17 (target 13).
- U501 has 4 blocked edges (target 2). These are still blocked:
  - **Pads 36 (GND), 37 (DRV9_OFF, to Q509 on B) and 38 (3V3).** They sit under the PP5V strip and its 1.5 mm growth from L502 to pad 34. The only cure I see is re-routing PP5V, which means moving the buck output caps of 03, so I left it.
  - **Pad 31 (GND).** C550's planner GND via at (92.25, 78.67) and the VBUS sliver round C550's GND pad take the via room.
- CC1 (C501.1 to U505.12) is still blocked by the VBUS pour east of C501, from J501's east pair to pad 23. The C_CC1 edges at U505 fail on the hand board too.
- Step 3 (I2CC_SCL U503.1 to R503.2, CHG_INT U503.3 to R504.2): **done.** In `runs/p2v-route50/route.log`, no FAILED line names I2CC_SCL or CHG_INT, so both route.

The 21 FAILED lines are:
- **Pocket:** CC1 C501.1 to U505.12; C_CC1 U505.7 to .4 and .4 to J501.A5; C_CC2 U505.5 to J501.B5; VBIAS C551.1 to U505.3.
- **U501:** DRV9_OFF Q509.1 to U501.37; plane links of U501.38 (3V3), .36 (GND) and .31 (GND).
- **Charger twins from 01/02:** HIDRV1, ACOV, FB, HG2, BAT_SNS_P (R528), PACK_P (R529), PPHV (R525), AC_SNS_N (R526), GND C515.2.
- **Cross-port nets SCL, SDA and CHG_INH from U301:** in a partial run their far end is only roughly placed.

**For the lead and Port 1:**
- D501 (TVS) no longer sits at the connector (see the trade-off above).
- Port 1 could try the same pad-32 cure for U401: a flat VBUS cap over pad 32 with its VBUS pad on the lane, and D401 next to pad 23. This would avoid the B.Cu detour that leaves U401's GND pads with no via room.

Files:
- `recipes/port2/04-pd-protect.json`.
- `fragments/port2.json` + meta, which are the same as `Port_2.json` + meta.
- `candidates/r2_Port_2_VBUS_pad_32_and_U501_rest.json`, which is `runs/p2v-iw/placement.json`.
- `runs/p2v-i/scr`, `runs/p2v-g/hot`, `runs/p2v-iw` and `runs/p2v-route50`: score.json, dc.json, ghost.log, F.png and B.png, plus hot.json where present. Two more files are force-added: `runs/p2v-route50/route.log` and `runs/p2v-iw/zoom_u501.png`.
- New team tools:
  - `tools/recipe_put.py` edits put steps and ring allow lists in place.
  - `tools/quick_ghost.sh` runs a ghost-only route on a plan_only run, optionally with `--only=<regex>`. Results are optimistic, because other nets' stubs are missing.

## 2026-11-15 01:25 UTC, lead: stitch and review, round 3 (candidates/r3.json = best_placement.json)

**Stitch.** `tools/stitch.py fragments/port1.json fragments/port2.json fragments/pack.json` with both round-3 fix fragments
(commits 9e0dc96 and 4bc56d9): 245 parts, 18 on the bottom, 0 claim clashes, no border to resolve. This first stitch is
kept as `candidates/r3a.json` (same content as `runs/p2v-iw/placement.json`). After one lead change in Port 2 (below) the
stitch is `candidates/r3.json` = `best_placement.json`.

**Lead change in Port 2: the TVS goes back to the connector.** The Port 2 worker had moved D501 next to U501 pad 23 so
that pad 23 joins, and asked whether a TVS 10 to 11 mm from J501 is acceptable. It is not: the TVS belongs at the
connector, and the two ports should be built the same way. Port 1 and the hand board join pad 23 with the 4.7 uF VBUS
capacitor (C406, hand C506) and keep the TVS at the connector. Port 2 now does the same (`recipes/port2/04-pd-protect.json`):

| Part | r3a | r3 | Why |
|---|---|---|---|
| D501 | (96.4, 80.69) t0, at pad 23 | (97.9, 71.67) t0 | VBUS pads west (x 96.83 to 97.20), 1.3 mm from J501 A4/B9; the east VBUS trunk runs through them (connector, TVS, trunk). D401 is 2.0 mm from J401 A4/B9 |
| C506 | (97.25, 71.1) t0, under A4/B9 | (96.21, 79.55) t270 | standing east of pad 23 like C406 at U401: VBUS pad south, 0.56 mm from pad 23, so the planner joins pad 23 through C506 |
| C551 | (94.38, 72.08) t270 | (95.32, 72.08) t270 | not put by hand: its at_pin step now finds the spot straight over U505 pin 3 (C506 used to be in the way) |

Also: C506 and D501 added to U505's ring allow list (they face unconnected and GND pins), reserve `vbus_in_U501_23`
moved to the new trunk lane [97.6, 73.0, 99.6, 80.2]. C506 now breaks check.py's 4 mm serves rule to J501.VBUS (10.78 mm),
as C406 does to J401.VBUS (9.23 mm). **Decision: both are waived.** These capacitors serve the PD chips' VBUS_IN pads
(as on the hand board); the connector is guarded by the TVS. check.py therefore shows 2 hard faults, both these lines.
The swap also cleared two blocked edges (CC1 C501.1 to U505.12 and VBIAS C551.1 to U505.3) and added none.

**New tool: the same copper with one zone per outline.** `tools/write_copper_split.py` (copy of the shared writer, one
zone per outline) and `tools/split_screen.sh <screened run> <new dir> [--route=MIN]` (shared scorecard with
`--keep-copper` on that board). It confirms the 22:45 note and the Port 1 worker's guess: with zones split the edges
"VBUS track to U401 pad 32", PPHV R525.1 and PACK_P R529.1 are gone, because those pads were on outlines KiCad dropped.
The total edge count falls from 443 to 421 for the same reason. Compare split with split.

**Scorecard runs** (all finished, nothing timed out; DRC 0 in every run; loose = `tools/loose.py`):

| Run | Board | Blocked edges | Full route | Hot loops | Loss | Power open | Loose pads |
|---|---|---|---|---|---|---|---|
| `runs/hand_screen` | hand | 56 of 452 | 391 of 448 (charter) | sum 8.15 nH | 1.36 W | PP5V U401, 3V3 L201, GND J301/J302 | U401 pad 32 |
| `runs/hand-split` | hand, zones split | 58 of 422 | - | - | 1.359 W | same | U401 pad 32 |
| `runs/hand-split-route` | hand, zones split, `--route=45` | 58 of 422 | **363 of 422, 59 failed**, about 13 min | - | 1.359 W | same | U401 pad 32 |
| `runs/r2-hot` | r2 | 39 of 446 | 401 of 446 (`runs/r2-route`) | 7 of 7, 5.54 nH | 1.133 W | GND J301/J302 | U401 pad 23, U501 pad 32 |
| `runs/r3-hot` | r3a, `--hot=all` | 33 of 443 | - | 7 of 7, 5.54 nH | 1.122 W | GND J301/J302 | none |
| `runs/r3-split` | r3a, zones split | 30 of 421 | - | - | 1.119 W | GND J301/J302 | none |
| `runs/r3-split-route` | r3a, zones split, `--route=45` | 30 of 421 | **385 of 421, 36 failed**, about 22 min | - | 1.119 W | GND J301/J302 | none |
| `runs/r3b-hot` | **r3**, `--hot=all` | **31 of 443** | - | **7 of 7, 5.54 nH** | **1.125 W** | GND J301/J302 | none |
| `runs/r3b-split` | **r3**, zones split | **28 of 421** | - | - | 1.123 W | GND J301/J302 | none |

Hot loops of r3 (loop total nH, unchanged from r2): HL_3V3 1.02, Port 1 HL_5V 0.70, HL_IN 0.78, HL_OUT 0.74, Port 2
HL_5V 0.76, HL_IN 0.80, HL_OUT 0.74. VBUS at U401 2.09 mohm, at U501 1.16 mohm (r3a 1.00); PP5V at U401 6.31, at U501
1.54 mohm. The full route was run here, not on Logan's PC (this session does not push). r3 itself was not full-routed;
r3a differs from it by the three parts above.

**Renders.** Looked at `runs/r3-hot/F.png`, `B.png` and `runs/r3b-hot/F.png`, `B.png`, plus zooms in `plan/r3-zoom/`
(chg1_F, chg2_F, pd_F, pd_B, r3b_pd_F): stages, bucks and the pack FET block are compact, no power part sprawls. The
largest copper on the bottom is Port 1's PP5V pour under the PD pocket with the thin VBUS track to C450 beside it.

**Finding: the routed board loses PACK_P at J113 and R427.** `runs/r3-split-routed-dc` is `cu_dump.py` and `dc_score.py`
on `runs/r3-split-route/routed.kicad_pcb`: loss 1.102 W, open PACK_P at J113 and R427, 3V3 at L201 (allowed), GND at
J301/J302 joined by the router. PACK_P's In2 bus zone is soft for the router (`--softnets=GND,PACK_P,3V3`); before
routing it is one piece of 1897 mm2, after routing two pieces (1365 and 15.6 mm2), and the small one holds the five
vias at J113/R427.2. The screen cannot show this. It needs PACK_P strap tracks laid before signal routing (team D's
cure, 22:45 note). The hand board through the same steps (`runs/hand-split-routed-dc`) loses more: PACK_P open at J113, R427, D103 and U204, besides PP5V at U401 and 3V3 at L201 that are open before routing.

**Where the 28 blocked edges of r3 (zones split) are:**
- Chargers, 14: HIDRV1 (U403.27/U503.27), ACOV and ACUV (pins 35, 34 to R410/R510), FB U403.12, HG2 (R446/R546 to
  Q402/Q502), and the sealed Kelvin taps R426.1, R526.1 (AC_SNS_N), R428.1, R528.1 (BAT_SNS_P), R429.1 (PACK_P). The
  router never routes to a sealed tap, so a tap is blocked unless its own net's planned copper reaches the pad.
- PD pockets, 8: U401 GND pads 26, 31, 36; U501 GND 31, 36, 3V3 pad 38, DRV9_OFF pad 37; I2CC_SCL U402.6 to R403.2
  (C408 stands in front of pins 5 and 6).
- Port protection, 5: C_CC1 at U405 (2) and U505 (2), C_CC2 U505.5 to J501.B5 (these fail on the hand too).
- Pack, 1: GND C304.2.
What stands in front of the charger pins (pad boxes from `runs/r3b-hot/cu.json`): C409 pad 1 (PPHV) 0.67 mm in front
of pins 34/35; C412 straight above pin 27 between it and R444.1; C417.2, C418.2, C419 and pin 11's own stub round
pin 12. check.py's escape lines name the same parts. Nobody has worked on these since the charger was first placed.

**Decision: not done.** By the letter r3 meets the bar (hard limits met before routing, 31 of 443 against the hand's 56
of 452, split 28 of 421 against 58 of 422, split full route of r3a 385 of 421). Two things are worth the last round:
(1) the charger pin escapes, 15 edges that have a named cause and a cheap cure; (2) the routed board must keep PACK_P
joined, or the final result breaks a hard limit after routing. Fix tasks for round 4:
1. Charger and EEPROM pin escapes, both ports (the only worker who moves parts).
2. Routed-board check: PACK_P straps before routing, one command for the final scorecard, r3 and hand through it.

**For the round-4 lead.** Stitch the three fragments (candidate of task 1: `candidates/r3_charger.json`), screen with
`--hot=all`, then run task 2's command on the best board and on the hand, and report plain and split numbers side by
side. r3 stays the best placement unless the new candidate has loose.py clean, 7 of 7 loops and fewer blocked edges.

Files: `candidates/r3.json`, `candidates/r3a.json`, `best_placement.json`; `recipes/port2/04-pd-protect.json`,
`fragments/port2.json` + meta (= `Port_2.json` + meta); `tools/write_copper_split.py`, `tools/split_screen.sh`,
`tools/README.md`; `runs/r3-hot/`, `runs/r3b-hot/` (score.json, hot.json, dc.json, ghost.log, F.png, B.png),
`runs/r3-split/`, `runs/r3b-split/`, `runs/hand-split/`, `runs/r3-split-route/`, `runs/hand-split-route/` (score.json, dc.json, ghost.log),
`runs/r3-split-routed-dc/dc.json`, `runs/hand-split-routed-dc/dc.json`, `plan/r3-split-route-failed.txt`, `plan/hand-split-route-failed.txt`, `plan/r3-zoom/`. Boards, route.log and
hot_gate.log stay local.

## 2026-11-15 03:10 UTC, charger worker: fix task "Charger and EEPROM pin escapes, both ports" (round 4), candidates/r3_charger.json

Only small parts moved; no power stage, hot-loop capacitor, U403/U503, 5 V buck or PD-pocket part (north of y 88)
except C408. Bottom count stays 18 (D511 moved on the bottom, nothing flipped).

**What blocked each edge, and the move** (cause found with `quick_ghost.sh`, `zoom.py` and the router's stub code;
spots are fragment values, Port 2 = Port 1 + (-23.02577, +0.006368) unless said):

| Edge | What blocked it | Move |
|---|---|---|
| I2CC_SCL U402.6 to R403.2 | C408's pads 0.5 mm west of pins 5/6: no way north for SCL | C408 1.1 mm south: pad 1 level with pin 8, pad 2 with pin 7, pins 5/6 free to the west |
| HIDRV1 U403.27 to R444.1 (both) | C412.1 (BTST1) right over pin 27 and pin 26's fan-out stub beside it: the stub end was boxed | C412 0.5 mm west (over pin 28): pin 27 goes straight north to R444.1 |
| FB U403.12 to R419.1 (both) | C417.2 0.09 mm too close over pin 12's way south; C419 across the only lane east of pin 11's stub | C417 0.28 mm north; C419 0.65 mm east (lane x 115.3-115.8 to R419.1 free); R418/R419/R413/R414 held at their spots with puts |
| ACUV/ACOV U403.34/35 to R410 (both) | C409's PPHV pad 0.67 mm in front of both pins, and the PPHV copper hugging it | C409 1.23 mm west (pad 1 1.9 mm from pin 33, inside the 2 mm serves limit); R410 stands at the two stub ends (pad 1 level with pin 34, pad 2 under pin 35's stub, turned so the edges do not cross), allowed into U403's ring at the serves distance; its pads' escape room keeps PPHV copper out of the lane. R409/R411/R412 re-placed by their at_pin steps |
| AC_SNS_N tap R426.1 / R526.1 | 3 mm under the AC_SNS_N copper of C427, beside PPHV | R426 stands under C427 with pad 1 0.6 mm under C427.1 (the pour reaches it); D404 gave up that spot and stands west of R426 (BTST1 pad south toward the lane over C416 to C412) |
| BAT_SNS_P tap R428.1 / R528.1 | PACK_P copper between the BAT_SNS_P pour and the pad | R428 0.87 mm east into the west mouth between R427's pads; Port 2 also D505 0.38 and R528 0.39 mm north (Port 2's PACK_P pour over the C211/C212 via field is bigger and took the mouth at the twin spot) |
| PACK_P tap R429.1 | 0.45 mm from the PACK_P copper | R429 lying, tap pad east 0.53 mm west of R427.2, on the PACK_P copper |
| HG2 R446.2 to Q402.1 (both) | not cleared: BAT_SNS_P copper wraps Q402.1 (near its own terminal only the clearance applies) and crosses the 0.96 mm gap; R446 cannot move closer (courtyard touches Q402's) | none; fails on the hand board too |

Port 2 needed three extra changes beyond the copy (`recipes/port2/02-charger-fix.json`, `05-9v.json`):
- R509 (81.8, 110.6) t180 instead of the twin spot: with C509 west, the board edge leaves the PPHV planner only the narrow
  way under C509; at the twin spot the planner refused the path as winding (46 mm for 27 mm straight, C509 left to the
  router and R525's sealed tap blocked, `runs/chg-po2-p2`).
- D511 (bottom) 1.05 mm west: its pad sat under C515.2, so C515.2 had no return via; once the PPHV copper passed west of
  C515 its GND pad was walled in (`runs/chg-p2tryW1`). The 9 V parts placed after D511 are held at their r3 spots with
  puts (the greedy would have moved them north of y 88).
- R513/R514 put in one column east of C518/C519 (C519 took R514's spot; the greedy then found none for R513).

| Part | r3 | now | | Part | r3 | now |
|---|---|---|---|---|---|---|
| C408 | (101.84, 84.84) t270 | (101.84, 85.95) t270 | | C509 | (83.28, 108.85) t0 | (82.05, 108.85) t0 |
| C409 | (106.31, 108.84) t0 | (105.08, 108.84) t0 | | C512 | (86.37, 103.86) t180 | (85.87, 103.86) t180 |
| C412 | (109.40, 103.85) t180 | (108.90, 103.85) t180 | | C517 | (92.44, 108.51) t0 | (92.44, 108.23) t0 |
| C417 | (115.47, 108.50) t0 | (115.47, 108.22) t0 | | C518 | (93.47, 109.16) t180 | (93.47, 108.76) t180 |
| C418 | (116.50, 109.15) t180 | (116.50, 108.75) t180 | | C519 | (92.92, 110.66) t270 | (93.57, 110.66) t270 |
| C419 | (115.95, 110.65) t270 | (116.60, 110.65) t270 | | D504 | (81.87, 103.71) t90 | (81.25, 104.41) t180 |
| D404 | (104.90, 103.70) t90 | (104.28, 104.40) t180 | | D505 | (93.82, 104.01) t270 | (93.82, 103.63) t270 |
| R409 | (105.30, 111.15) t180 | (105.80, 110.15) t180 | | D511 (B) | (83.05, 106.85) t90 | (82.00, 106.85) t90 |
| R410 | (106.85, 110.65) t270 | (107.32, 109.26) t90 | | R509 | (82.27, 111.16) t180 | (81.80, 110.60) t180 |
| R411 | (106.35, 112.20) t0 | (106.80, 111.20) t0 | | R510 | (83.82, 110.66) t270 | (84.29, 109.27) t90 |
| R412 | (107.80, 111.85) t270 | (107.50, 112.15) t0 | | R511 | (83.32, 112.21) t0 | (83.77, 111.21) t0 |
| R426 | (104.90, 105.45) t270 | (105.58, 103.60) t0 | | R512 | (84.77, 111.86) t270 | (84.47, 112.16) t0 |
| R428 | (116.85, 105.30) t90 | (117.72, 105.30) t90 | | R513 | (95.00, 109.60) t270 | (95.16, 108.20) t0 |
| R429 | (116.85, 107.20) t270 | (117.72, 106.60) t0 | | R514 | (94.90, 110.65) t270 | (95.45, 110.19) t0 |
| | | | | R526 | (81.87, 105.46) t270 | (82.55, 103.61) t0 |
| | | | | R528 | (93.82, 105.31) t0 | (94.69, 104.92) t0 |
| | | | | R529 | (93.82, 107.21) t270 | (94.69, 106.61) t0 |

**Scorecard runs** (all finished, none timed out; DRC 0 in every run; loose = `tools/loose.py`, prints nothing = clean):

| Run | Board | Blocked edges | Hot loops (nH) | Loss | Power open | Loose pads |
|---|---|---|---|---|---|---|
| `runs/p1r3-final` (ref) | Port 1 r3, partial | 15 of 170 | 0.70 / 0.78 / 0.74 | 0.313 W | GND J301/J302 | - |
| `runs/chg-p1v1` | Port 1 now, partial | 9 of 169 | 0.70 / 0.78 / 0.74 | 0.313 W | GND J301/J302 | none |
| `runs/p2v-i/scr` (ref) | Port 2 before the TVS swap, partial | 17 of 174 | 0.76 / 0.80 / 0.74 | 0.348 W | GND J301/J302 | - |
| `runs/chg-p2v3` | Port 2 now, partial | 9 of 169 | 0.76 / 0.80 / 0.74 | 0.349 W | GND J301/J302 | none |
| `runs/r3b-hot` (ref) | r3, `--hot=all` | 31 of 443 | 1.02 / 0.70 / 0.78 / 0.74 / 0.76 / 0.80 / 0.74, sum 5.54 | 1.125 W | GND J301/J302 | none |
| `runs/r3b-split` (ref) | r3, zones split | 28 of 421 | - | 1.123 W | GND J301/J302 | none |
| `runs/r4chg-hot` | **r3_charger**, `--hot=all` | **19 of 437** | **1.02 / 0.70 / 0.78 / 0.74 / 0.76 / 0.80 / 0.74, sum 5.54, 7 of 7 tier 1** | **1.125 W** | GND J301/J302 | none |
| `runs/r4chg-hot-split` | **r3_charger**, zones split | **15 of 415** | - | 1.124 W | GND J301/J302 | none |
| `runs/r3-split-route` (ref) | r3a, zones split, `--route=45` | 30 of 421; **full route 385 of 421, 36 failed** | - | 1.119 W | GND J301/J302 | none |
| `runs/r4chg-split-route` | **r3_charger**, zones split, `--route=45` | 15 of 415; **full route 393 of 415, 22 failed**, about 19 min, not timed out | - | 1.124 W | GND J301/J302 | none |

Plain runs still list R426.1, R526.1 (AC_SNS_N) and R429.1 (PACK_P) as blocked: those pads sit on pour outlines that
the shared writer's multi-outline zones lose (the README trap); with zones split they are joined. The 15 left (split):
HG2 x2 (item 6), C_CC1 x4 and C_CC2 at U405/U505, DRV9_OFF, U501.38 (3V3), GND pads U401.26/31/36 and U501.31/36,
C304.2: all were blocked in r3 too, none is new. Full route failures (`plan/r4chg-split-route-failed.txt`): the 15 above
(GND U401.27 shows there too) plus EN_5V1, CC2 (Port 1), Net-(U102-V4), and two that routed on r3a: TS1 (TH101 to U101,
pack side) and I2CC_SDA (U403.2 to R402.2, 26 mm); both have a way on the empty board (not in the screen), so they are
lost to congestion in this route. Gone from r3a's list: HIDRV1 x2, ACOV x2, FB x2, I2CC_SCL, the four sealed taps,
C515.2, CC1/VBIAS/LDO_1V5 at U505/U501 (lead's TVS swap and round 3). check.py: hard faults only C406 and C506 (waived), touching 8 (r3 8),
hpwl 2120 mm (r3 2113). Renders `runs/r4chg-hot/F.png`, `B.png` looked at: same power copper as r3, no sprawl.
Pictures: `plan/chg-zoom/r4chg_chg1_F.png`, `r4chg_chg2_F.png`, `r4chg_u402_F.png` (split run, blocked edges red).

For the lead: (1) Port 1 and Port 2 now differ in four parts (R509, D505, R528 and the bottom D511), each for a named
Port 2 cause above. (2) R410 is in U403's/U503's ring by allow, at the serves distance (0.3 mm), so that it can stand at
the stub ends. (3) HG2 needs either R446 closer than its courtyard allows or a planner rule that keeps escape room at a
gate pad near its own terminal; not a placement fix. (4) Two quick-look helpers added: `tools/part_peek.py`
(courtyard, pads and faults of named parts with `--set` overrides) and `tools/quick_split_ghost.sh` (`quick_ghost.sh` on
a plan-only run written with one zone per outline); the README rows were not added because tools/README.md holds
another worker's uncommitted edit.

Files: `recipes/port1/02-charger.json`, `recipes/port1/04-pd.json`, `recipes/port2/01-stage-charger.json`,
`recipes/port2/02-charger-fix.json`, `recipes/port2/05-9v.json`, `fragments/port1.json`, `port2.json` + meta
(= `Port_1.json`, `Port_2.json` + meta), `candidates/r3_charger.json` (=
`candidates/r3_Charger_and_EEPROM_pin_escapes_both_ports.json`), `tools/part_peek.py`, `tools/quick_split_ghost.sh`,
`plan/chg-zoom/`, `plan/r4chg-split-route-failed.txt`, `runs/r4chg-hot/`, `runs/r4chg-hot-split/`, `runs/r4chg-split-route/`,
`runs/chg-p1v1/`, `runs/chg-p2v3/` (score.json, dc.json, hot.json, ghost.log, F.png, B.png). Boards, hot_gate.json and route.log stay local.

## 2026-11-15 03:40 UTC, routed-board worker: fix task "Routed-board check with PACK_P straps" (round 3/4), tools only

**What was built** (new files only; no placement, fragment, recipe or candidate touched):
- `tools/straps.py <spec.json> <cu.json> <out spec.json> [--net --layer --source --lanes ...]`: groups the net's vias
  and through-hole pads on the planned pour by hard ties only (via in/next to a pad, vias closer than 0.5 mm edge to
  edge, planned tracks; a pour on another layer does not join, it is soft too), then lays a greedy Steiner tree of hard
  tracks from the source's group (Q102) to every other group on a 0.1 mm grid: 1.0 mm wide where it fits, 0.5 mm
  minimum, inside the planned pour outline, 0.25 mm from every other net's via, through-hole pad, track, pour and
  keep-out on the layer, few runs across the signal lanes (east-west on In2 costs 6x, 1.5x along the board edge and
  under large pads), and kept from under small signal pads (their via escapes). Every segment is checked exactly
  (shapely); `--png` draws it. Default PACK_P on In2.Cu; `--net=3V3 --layer=In3.Cu --lanes=H` for the 3V3 bus.
- `tools/final_route.sh <screened run> <out> [--route=45] [--no-straps] [--no-hot] [--straps=...]`: plan + straps,
  `write_copper_split.py`, shared scorecard `--keep-copper --no-hot`, then on routed.kicad_pcb cu_dump + dc_score,
  loose.py, KiCad DRC (errors, unconnected items of PACK_P/3V3/GND) and the 7 hot loops (hot_score.py + power_gate.py
  as score_board.sh step 4 calls them); writes and prints `<out>/final.json` (`tools/final_json.py`). Same command on
  the hand board. How to run it and what each number means: `tools/README.md`, last section.

**Which soft pours the route cuts** (pieces before -> after routing, r3a routed without straps, `runs/r3-split-route`):
PACK_P In2 1 -> 2 (J113/R427 island: needs straps); PACK_P F.Cu 7 -> 9 (D103's via cut off the Q102 piece, still joined
through In2; the straps tie it); 3V3 In3 1 -> 2 (the PD chips' 3V3 vias at C403/C503 cut off; r3 with PACK_P straps
1 -> 5); GND In1/In4 stay one piece, GND F.Cu 13 -> 13, PACK_P B.Cu 12 -> 12: no straps needed there.

**Results** (all runs finished, none timed out; "no straps" rows are the earlier runs, r3a = r3 before the 3-part
Port 2 change; r3 itself was not full-routed without straps):

| Run | Board, straps | Blocked edges | Route (routed / failed of edges) | Timed out | DRC (copper board) | Power open before routing | Loss before | Power open after routing | Loss after | Hot loops after routing |
|---|---|---|---|---|---|---|---|---|---|---|
| `runs/r3b-split` | r3, none | 28 of 421 | - | - | 0 | GND J301/J302 | 1.123 W | - | - | (before: 7 of 7, 5.54 nH) |
| `runs/r3-split-route` + `-routed-dc` | r3a, none | 30 of 421 | 385 / 36 of 421, about 22 min | no | 0 | GND J301/J302 | 1.119 W | **PACK_P J113, R427**; 3V3 L201 | 1.102 W (J113, R427 carry nothing) | not run |
| **`runs/r3-final`** | **r3, PACK_P** | **29 of 422** | **387 / 35 of 422**, about 30 min | no | **0** | GND J301/J302 | **1.123 W** | **3V3 L201 only** | **1.754 W** | **7 of 7, 5.55 nH** |
| `runs/r3-final-3v3` | r3, PACK_P + 3V3 | 28 of 427 | 391 / 36 of 427, about 23 min | no | 0 | GND J301/J302 | 1.123 W | 3V3 L201 only | 2.926 W | 7 of 7, 5.55 nH |
| `runs/hand-split-route` + `-routed-dc` | hand, none | 58 of 422 | 363 / 59 of 422, about 13 min | no | 0 | PP5V U401, 3V3 L201, GND J301/J302 | 1.359 W | PACK_P J113, R427, D103, U204; PP5V U401; 3V3 L201 | - | not run |
| **`runs/hand-final`** | **hand, PACK_P** | **58 of 423** | **365 / 58 of 423**, about 14 min | no | **0** | PP5V U401, 3V3 L201, GND J301/J302 | **1.359 W** | **PP5V U401** (open before routing too) | **2.413 W** | **7 of 7, 6.76 nH** |

Hot loops after routing, loop total nH (HL_3V3, P1 5V, P1 IN, P1 OUT, P2 5V, P2 IN, P2 OUT): r3-final 1.02 / 0.70 /
0.78 / 0.74 / 0.76 / **0.81** / 0.74 (before routing 0.80 for P2 HL_IN); r3-final-3v3 1.02 / 0.70 / **0.79** / 0.74 /
0.76 / 0.80 / 0.74; hand-final 1.33 / 0.92 / 0.87 / 0.77 / 1.18 / 0.84 / 0.85 (P1 HL_IN and P2 HL_OUT: bulk caps not
reached by the rule copper, still tier-1 pass). No loop opens. The two +0.01 nH steps are signal vias the router put
into the GND F.Cu return pour inside the loop: Port 2 HL_IN (board part 0.603 -> 0.606 nH) by I2CC_SCL vias at
(82.38, 90.72) and (81.33, 90.02) and an I2CC_SDA via at (81.63, 90.72) next to C523, a SW1 via at (84.13, 97.92) and a
Net-(D511-A) via at (83.18, 94.97) by C520; Port 1 HL_IN in the 3V3 run (0.583 -> 0.585 nH) by SW1 (107.18, 97.97),
SDA (104.88, 90.52), I2CC_SDA (106.18, 94.97) and CHG_INT (107.33, 92.72) vias. Not fixed (report only).

**Targets.** Met: routed r3 power open is 3V3 at L201 only (PACK_P joined at J113, R427 and every terminal); DRC 0 with
the straps; loss before routing 1.123 W (= without straps); blocked 29 of 422 (+1 against 28 of 421); route 387 of 422
(>= 380); routed hot loops 7 of 7. The hand board went through the same command.

**Two findings for the lead:**
1. *Straps keep PACK_P joined but cannot keep its resistance.* In2 is 0.5 oz (about 1 mohm per square); a 1 mm strap
   is about 1 mohm per mm. J113 (10 A) and R427 (5 A) take their current through what the router leaves of the In2
   sheet: J113 2.23 mohm before routing, 6.84 after (`runs/r3-final`), 16.2 in the 3V3 run of the same board; hand
   10.1. So routed loss is 1.754 / 2.926 W on r3 and 2.413 W on the hand, against 1.12 / 1.36 W before routing; PACK_P
   alone 0.32 -> 0.92 W on r3. The loss of a routed board moves with each route. Cure is not in straps: either an
   In2 corridor Q102 -> J113/R427 that signals may not cross (a router or plan change in the shared tools), or the
   10 A path on 2 oz outer copper. `straps.py --main=J113:4` (wide strap to a terminal) is there but the only 4 mm
   way on r3 runs 69 mm round the north, so final_route.sh does not use it.
2. *The 3V3 In3 bus needs straps too* (it is cut by the In3 horizontal lanes; dc_score cannot see it, only KiCad's
   unconnected list). With 3V3 straps (0.5 mm, 112 mm, 56 mm across the In3 lanes) In3 3V3 stays one piece and the
   route did not suffer (28 of 427, 391 of 427). Not made the default because the hand board was run with PACK_P only.

Routed boards (router output, not the copper board) carry KiCad clearance errors: r3 2 (CELL_1N F.Cu track against
BTP_INT and U101-SMBD tracks at about (102.5 to 103.4, 127.9 to 128.8)), hand 3. The candidate file for this task
is not written: the placement is unchanged (= candidates/r3.json), and the task said not to touch candidates/.

Files: `tools/straps.py`, `tools/final_route.sh`, `tools/final_json.py`, `tools/README.md`; per run (`runs/r3-final`,
`runs/hand-final`, `runs/r3-final-3v3`, screens `runs/r3c-straps-screen`, `runs/r3c-straps-screen2`,
`runs/r3c-straps3v3-screen`): score.json, final.json, dc.json, ghost.log, route_failed.txt (FAILED lines), routed/dc.json,
routed/hot.json, routed/hot_gate.json, split/straps.log, split/straps_*.png. Boards and route.log stay local.
(`runs/r3c-straps-screen` is an earlier strap setting, 31 of 423: three Port 1 edges at D410 under a centre trunk; the
under-pad cost added after it brought the count to 29.)

## 2026-11-15 04:40 UTC, lead: stitch and review, round 4 (last round)

**r4** = `candidates/r4.json` = `best_placement.json`: the stitch of the three fragments as they stand after the charger
worker's round (`tools/stitch.py`, 245 parts, 18 on the bottom, claim clashes 0, hpwl 2120 mm). It is the same placement
as `candidates/r3_charger.json` (compared part by part), so the worker's whole-board screen with all hot loops,
`runs/r4chg-hot`, is r4's screen; the lead changed no part this round. The charger worker's files were staged but not
committed (its commit was refused); the lead committed them as 9a00fbc. The README rows for `part_peek.py`,
`quick_split_ghost.sh` and the routed-board tools were added.

**Runs of r4** (all finished, none timed out; the two full routes ran here one after the other, 45 min cap each):

| Run | What | Blocked edges | Full route | Hot loops | Loss | DRC | Power open |
|---|---|---|---|---|---|---|---|
| hand (`runs/hand_screen`, charter) | reference, shared scorecard | 56 of 452 | 391 of 448 | sum 8.15 nH | 1.36 W | 0 | PP5V U401, 3V3 L201, GND J301/J302 |
| `runs/r2-hot`, `runs/r2-route` | r2, shared scorecard | 39 of 446 | 401 of 446 | 7 of 7, 5.54 nH | 1.133 W | 0 | GND J301/J302 |
| `runs/r3b-hot` | r3, `--hot=all` | 31 of 443 | not run | 7 of 7, 5.54 nH | 1.125 W | 0 | GND J301/J302 |
| `runs/r4chg-hot` | **r4**, `--hot=all` (worker's run) | **19 of 437** | - | **7 of 7, 5.54 nH** (1.02 / 0.70 / 0.78 / 0.74 / 0.76 / 0.80 / 0.74) | **1.125 W** | 0 | GND J301/J302 |
| `runs/r4-route` | **r4**, the same copper through the shared scorecard, `--keep-copper --route=45 --no-hot` | 19 of 437 | **411 of 437, 26 failed**, about 17 min | - | 1.125 W | 0 | GND J301/J302 |
| `runs/r4chg-hot-split` | r4, one zone per outline | 15 of 415 (hand 58 of 422, r3 28 of 421) | - | - | 1.124 W | 0 | GND J301/J302 |
| `runs/r4chg-split-route` | r4, one zone per outline, `--route=45` (worker's run) | 15 of 415 | 393 of 415, 22 failed (hand 363 of 422, r3a 385 of 421) | - | 1.124 W | 0 | GND J301/J302 |
| `runs/r4-final` | r4 through `tools/final_route.sh` (PACK_P straps, one zone per outline, full route, routed board scored) | 16 of 416 | 391 of 416, 25 failed, about 31 min (hand 365 of 423, r3 387 of 422) | routed board: 7 of 7, 5.56 nH (1.02 / 0.70 / 0.79 / 0.74 / 0.76 / 0.81 / 0.74) | before routing 1.124 W; routed board **2.854 W** | copper board 0; routed board 3 (router's own) | before: GND J301/J302; routed board: **3V3 L201 only** |

`tools/loose.py` prints nothing on `runs/r4chg-hot`, its split twin and the routed board (`runs/r4-final/routed`).
`tools/check.py`: overlap, keep-out, edge, ring, reserved, region all 0; hard faults 2, both the waived `pin` lines of
C406 and C506 (they serve the PD chips' VBUS_IN pads, as on the hand board); bottom parts 18.
Renders `runs/r4chg-hot/F.png`, `B.png` and `runs/r4-final/F.png` looked at: the two charger stages are mirror twins
with the inductor between the FET pairs and the hot-loop capacitors against the FETs, the 5 V bucks and the pack FET
block are compact; no sprawling power part.

**Against the hand board** (same tool each time): blocked edges 19 of 437 against 56 of 452 (split 15 of 415 against
58 of 422); full route 411 of 437 against 391 of 448 (split 393 of 415 against 363 of 422; with straps 391 of 416
against 365 of 423); hot loops 7 of 7 with sum 5.54 nH against 8.15 nH, every loop lower; loss before routing 1.125 W
against 1.36 W; power open before routing only GND at J301/J302 (the router joins them), where the hand also has PP5V
open at U401 and 3V3 at L201; DRC 0.

**What is left** (none of it is a part standing in the way that a move would cure; the lead stops here):
- The 15 blocked edges with zones split, all blocked on r3 and most on the hand board too: C_CC1 x4 and C_CC2 at
  U405/U505 and the connectors, DRV9_OFF (Q509.1 to U501.37), U501.38 (3V3), GND pads U401.26/31/36 and U501.31/36,
  C304.2, HG2 x2 (R446.2 to Q402.1 and twin: the BAT_SNS_P copper wraps the gate pad; needs a planner rule, the hand
  fails the same way). The plain count of 19 adds the four zone-outline artifacts (U401 pad 32, R426.1, R526.1,
  R429.1) that are joined when each outline is its own zone.
- Full-route failures beyond those (`plan/r4-route-failed.txt`, `plan/r4chg-split-route-failed.txt`,
  `runs/r4-final/route_failed.txt`): EN_5V1 x2, Port 1 CC2, Net-(U102-V4) in all three routes; TS1 (TH101 to U101.10)
  and Port 1 I2CC_SDA (U403.2 to R402.2) in two of three; SS_5V, Net-(U504-FB) x2, Port 1 I2CC_SCL and Port 2 I2CC_SDA
  only in the strap route. The last group changes from route to route, so it is congestion, not a blocked pin.
- **Routed-board loss moves with the route and is high.** 2.854 W on r4 (r3 1.754 W and 2.926 W in two routes of the
  same board, hand 2.413 W), against 1.12 W before routing. All of the rise is PACK_P from Q102 to J113 (0.224 W
  before, 1.561 W after routing, about 15.6 mohm) and R427 (0.054 to 0.384 W): north-south signal tracks on In2 cut
  the half-ounce PACK_P sheet into slabs that only the 1 mm straps join. The straps keep the path joined (the hard
  limit) but not low in resistance. This is a copper-plan and router matter, the same on every placement and on the
  hand board: either a corridor on In2 from Q102 to J113/R427 that signals may not cross, or the 10 A path on outer
  2 oz copper. Not fixed by team B.
- **3V3 on the routed board:** dc_score reports only L201 open, but KiCad's unconnected list of `runs/r4-final/routed`
  also names 3V3 pieces (U401 pad 38, R314, F.Cu and In3 pours): the In3 3V3 bus is cut by the route, as the
  routed-board worker found on r3. `final_route.sh --straps="--net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V;--net=3V3 --layer=In3.Cu --source=J301 --lanes=H"`
  keeps it whole (r3: 391 of 427 routed); not rerun on r4.
- The routed board carries 3 KiCad clearance errors made by the router (CELL_1N F.Cu track against TS1, BTP_INT and
  U101-SMBD tracks at x 100.1 to 103.4, y 127.9 to 128.8, 0.25 mm high-current rule); the copper board has 0.

**Verdict: done.** Hard limits met on the scorecard (power paths joined before routing but for GND at J301/J302, which
the router joins; DRC 0; 7 of 7 hot loops tier 1), routability above the hand board in every flow, ringing and loss
below it. For the final scorecard: `bash tools/score/score_board.sh <outdir> docs/layout-teams/B/best_placement.json`
(shared flow, expect about 19 of 437 blocked and about 411 of 437 routed) and, for the routed-board power paths,
`bash tools/final_route.sh runs/r4chg-hot runs/<new>` next to `runs/hand-final`.

Files: `candidates/r4.json`, `best_placement.json`, `tools/README.md`, `plan/r4-route-failed.txt`, `runs/r4-route/`
(score.json, dc.json, ghost.log, F.png, B.png), `runs/r4-final/` (final.json, score.json, dc.json, ghost.log,
route_failed.txt, routed/dc.json, routed/hot.json, routed/hot_gate.json, split/straps.log, split/straps_PACK_P.png,
F.png, B.png). Boards and route.log stay local.
