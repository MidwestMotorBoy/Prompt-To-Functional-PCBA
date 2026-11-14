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
