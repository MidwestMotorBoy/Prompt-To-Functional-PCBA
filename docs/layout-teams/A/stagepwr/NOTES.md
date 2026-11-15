# Worker `stagepwr` (team A, round 2): charger-stage blocks under split-zone copper

All numbers in this file are from split-zone copper (`docs/layout-teams/A/tools/score_board_split.sh` or the
stagepwr copy `tools/score_board_split_a.sh`, which is the same script plus two optional env switches). Older
numbers are marked pre-split.

## Result

Best placement = **v1** = `lead_merge/merged3_gu.json` + the stagefix s4 diode moves (D404/D405/D410/R416 and the
port-2 copies beside U403/U503 and the stage). Files: `best_gu.json`, `best_score.json`, `best_overrides_gu.json`
(8 refs that differ from merged3: R416, D404, D405, D410, R516, D504, D505, D510).

Best copper = **planner A** (`tools/plan_copper_a.py --sealed=1 --taps=1`, see "Planner change"). The stock planner
on the same placement is reported beside it, as required.

| v1 placement | planner | power_open | DRC | hot loops | blocked edges | loss | outdir |
|---|---|---|---|---|---|---|---|
| merged3 (ports worker, ports/runs/m3) | stock | allowed only | 0 | (not run there) | 31 of 400 | 1.053 W | ports/runs/m3 |
| v1 | stock | allowed only | 0 | 7 of 7 tier 1, 6.16 nH | 30 of 400 | 1.052 W | runs/sc_v1 |
| **v1** | **A (sealed + taps)** | allowed only | 0 | **7 of 7 tier 1, 6.21 nH** | **25 of 396** | **1.034 W** | **runs/sc_v1A3** |
| v1 | A + PACK_P In2 straps, Kruskal only | allowed only | 0 | (not run) | 25 of 397 | 1.035 W | runs/sc_v1A3S |
| **v1** | **A + straps, all joined (recommended)** | allowed only | 0 | 7 of 7 tier 1, 6.21 nH | 26 of 399 | 1.034 W | **runs/sc_v1A3S2** |

"allowed only" = 3V3@L201, GND@J301/J302.

Stage edges left blocked: none on v1A3 (merged3 had C412.2/C512.2 SW1, C410-R454 REGN, Q401.1/Q501.1 HG1). The
remaining 25 are port-top / gauge edges (CC, I2CC_SDA R402-U403.2, DRV9_OFF Q509, CHG_INH, U401/U501 GND, ...).

## Split-copper PC routes (Logan's PC, routed / failed / edges / minutes / status)

Queued with `queue_route.sh` from `score_board_split.sh` (or the stagepwr copy) outdirs; results from branch
route-results. The PC router has no 45-min cap here (3 rip phases of up to 25 min each), so minutes run to 45-102.

| board | name | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|
| hand placement (no placement arg) | stagepwr-split-hand | 363 | 59 | 422 | 13.7 | done |
| stage B4 (splitcheck_B4) | stagepwr-split-B4 | 350 | 48 | 398 | 102.0 | done (result came 100+ min after queueing) |
| rebuild base | stagepwr-split-rebuild-base | 350 | 53 | 403 | 75.0 | done |
| generic best | stagepwr-split-generic | 353 | 63 | 416 | 41.5 | done |
| **v1, stock planner** | stagepwr-v1-stock | **363** | **37** | 400 | 62.6 | done |
| v1, planner A | stagepwr-v1A3 | 358 | 38 | 396 | 90.1 | done (result came >75 min after queueing; local route run, see below) |
| v1, planner A + straps (Kruskal only, 3 pieces left) | stagepwr-v1A3S | 354 | 42 | 396 | 74.0 | done |
| **v1, planner A + straps (all joined)** | stagepwr-v1A3S2 | **355** | **43** | 398 | 45.4 | done |

Pre-split references (broken copper, not comparable): hand 391/448, stage-B4 382/433 (74.8 min), stagefix-s3
380/430, rebuild-base 378/441. Under split copper the hand board fails 59 of 422; v1 fails 37 of 400 (stock
planner) and 43 of 398 with straps. Note the 391 target was set on pre-split copper and is not reached by any
split board, the hand board included (363).


## Local full route and power on the routed board

Heavy local routing used: three router runs, not one (the 45-min scorecard route timed out without saving a board,
so a riptime-600 rerun of the same board was needed, and Part 3 asked for the strapped board's routed power too). They ran
one at a time, with nothing else heavy from this worker alongside.


1. Scorecard full route (`score_board_split_a.sh runs/full_v1A3 runs/v1_score.json --route=45`, planner A, hot on):
   **TIMED OUT at 45 min; last 348 routed, 39 failing of 396**. The scorecard's `timeout` kills the router before it
   saves, so a timed-out scorecard route leaves NO routed board to check power on.
2. So the router was run again by hand on the same cu.kicad_pcb with `--riptime=600` (same router, shorter rip
   budget per phase, so it finishes and saves; `runs/full_v1A3/route_rt600.log`): **355 of 396 routed, 41 failed**,
   routed-board DRC 0 errors. `tools/routed_dc.sh` (cu_dump + dc_score on routed.kicad_pcb):

| board | power_open | loss | PACK_P loss | GND loss |
|---|---|---|---|---|
| v1A3 before routing (cu.kicad_pcb) | allowed only | 1.034 W | 0.222 W | 0.334 W |
| v1A3 routed, no straps | **PACK_P open at D103 and U204** | 1.744 W | 0.884 W | 0.374 W |
| v1A3S2 before routing (straps) | allowed only | 1.034 W | 0.222 W | 0.334 W |
| v1A3S2 routed, straps (`runs/sc_v1A3S2`, riptime 600) | **3V3@L201 only** (J301/J302 GND joined by the router) | 1.364 W | 0.515 W | 0.368 W |

   So team D's finding holds here: In2 signal routes cut the soft PACK_P In2 pour and opened PACK_P on the routed
   board; with 41 tracks / 120 mm of 1.0-1.5 mm PACK_P straps on In2 the routed board keeps every power path.
   PACK_P loss still rises (0.22 -> 0.52 W) because the pour between the straps is cut up; wider/more straps or a
   second PACK_P layer would recover more.
3. Router edges with and without straps: blocked screen 25 of 396 (no straps) vs 26 of 399 (straps); PC full
   route 358/396 (38 failed) vs 355/398 (43 failed); local riptime-600 route 355/396 (41 failed) vs 352/399 (47
   failed). Straps cost about 3-6 routed edges.


## Per-variant blocked edges (quick screens, split copper, stagepwr/tools/qrun.sh)

| variant | planner | blocked | stage edges blocked |
|---|---|---|---|
| merged3 (ports/runs/m3, scorecard) | stock | 31 of 400 | C412/C512 SW1, C410-R454 REGN, HG1 P1, HG1 P2 |
| v1 = merged3 + s4 diodes | stock | 30 of 400 | same 5 |
| v1A (escapes R454/HG + taps, taps before grow) | A | 31 of 398 | taps grew into SW1 blobs on B.Cu: new HIDRV1 x2, BTST1 x4 blocked; HG1 P1 |
| v1A2 (taps after the grow step) | A | 26 of 396 | HG1 P1 only |
| v1A3 (via site of the escape widened 0.05 -> 0.25 mm) | A | 25 of 396 | none |
| v1A3 + straps (scorecard, --no-hot) | A + straps | 25 of 397 | none |

Split references (scorecard, --route=0 --no-hot): hand 58 of 422 (1.36 W, PP5V open at U401 as before), B4 42 of
398 (splitcheck_B4, 1.108 W), rebuild base 54 of 403 (1.064 W, GND open at Q401/Q501: fails the hard limit as
before), generic best 59 of 415 (1.33 W).

## Renders (runs/sc_v1A3/F.png, B.png, read)

F: both charger stages sit compact under their inductors (AC caps | Q401 | Q402 | BAT caps), port 2 is a translated
copy of port 1, SW1 goes straight up into the inductor, D404 now sits left of C412 next to the bootstrap pins,
D410/D405 beside C411/C413 right of the stage, R416 left of U403; nothing of the stage is stranded near J113 any
more. B: the PACK_P/AC_SNS_N/BAT_SNS_P stitching under each stage as before, plus the new thin switch-node taps:
one 0.3 mm SW1 track and one SW2 track per port, ~6-10 mm, from the bootstrap cap's vias up into the switch-node pour
(B.Cu, between the stage's via columns). No SW blobs on B.Cu.

## Planner change (tools/plan_copper_a.py; the stock tools/copper/plan_copper.py is imported unchanged)

1. Gate escapes: a FET gate pin of a hot loop whose centre lies inside the loop's supply or return pad hull (Q401.1
   HG1 next to D1, Q402.1 HG2) gets a 0.6 mm strip outward (the package-edge normal with most free room) plus a via
   site (via + 0.25 mm) at its end; every other net's power copper keeps the clearance from it (in clip_others).
2. --sealed=1: the same for any small part's signal pad sealed inside a loop hull (R454.1/.2 between C420/C423/C430).
3. --taps=1: switch-node taps, run after the grow step: a small part's pad on a switching net that is not a planned
   terminal and sits > 3 mm from the pour (bootstrap caps C412/C413/C512/C513 SW pads) gets the planner's own
   detour (vias + 0.3 mm corridor on B.Cu + vias into the pour). Reason: the router searches a window of 6 mm round
   the edge's DRC end points, and KiCad reports a zone end at the pad, so a pour 6 mm away is never found.
4. Hot loops still 7 of 7 tier 1 (6.21 nH vs 6.16 stock); loss 1.034 vs 1.052 W.
5. Straps (tools/straps.py, env STRAPS in tools/score_board_split_a.sh): after split_spec, hard In2 tracks
   (1.0-1.5 mm) join the PACK_P bus via groups (Kruskal: straight or L strap first, then a 0.1 mm grid path inside
   the pour for pieces still apart). DRC stays 0; it is what keeps PACK_P joined on the routed board.

## Skill notes (for a cheaper model)

1. Score the base first with `docs/layout-teams/A/tools/score_board_split.sh <out> <placement> --route=0 --no-hot`
   and list the stage GHOSTFAIL lines of ghost.log (grep Q4/Q5, R4xx, C41x, D4, U403, SW, HG, REGN).
2. For each blocked stage edge, run `stagepwr/tools/dbg.sh <outdir> <net> x0,y0,x1,y1 out.png '<net regex>'`
   (router debug copy, ~10 s, only that net's edges). Read the DBGEDGE line: `starts`/`goals` = 0 means a pad
   sealed by copper; `gmask [13,0,0,0]` on a Zone end means the pour lies outside the router's 6 mm window
   (KiCad reports a zone end at the pad). Look at out.png: white = via possible, yellow = F+B free but no via.
3. Placement fixes first (cheap, mk.py + overrides json + courtyard check): here only the diode tidy (stagefix s4)
   was needed; it is routing-neutral (30 vs 31 blocked) and fixes the sprawl Logan rejects.
4. Copper fixes in a team copy of the planner (subclass in stagepwr/tools/plan_copper_a.py; never edit tools/):
   gate/sealed-pad escapes (strip + via site >= via + 0.25 mm) and switch-node taps (run AFTER the grow step).
5. Quick screen each change: `stagepwr/tools/qrun.sh <name> <placement_score.json> [--sealed=1 --taps=1]`
   (~5 min, one at a time). Then a candidate gets the scorecard copy with hot loops on:
   `PLANNER=.../plan_copper_a.py stagepwr/tools/score_board_split_a.sh <out> <placement> --route=0 --plan="--sealed=1 --taps=1"`,
   plus the stock `score_board_split.sh` on the same placement for comparison.
6. Read F.png and B.png, then `queue_route.sh <out> <unique-name>`; poll with `stagepwr/tools/poll.sh` from a
   background loop that writes to a file (not grep -q on a pipe).
7. Power after routing: route locally with `--riptime=600` (the scorecard's 45-min timeout kills the router
   before it saves), then `stagepwr/tools/routed_dc.sh <outdir>`. If a bus net opens, add straps
   (`STRAPS="--net=PACK_P --layer=In2.Cu"` env on score_board_split_a.sh) and re-check DRC 0 and routed power.

Traps:
- Never edit a bash script while it runs (bash reads it as it goes; an edit shifts the offset). Copy, then edit.
- The planner's grow step grows every hard zone, including a thin detour: a switch-node tap drawn before grow became
  a 12 mm SW1 blob on B.Cu and blocked 6 new edges. Draw taps after grow.
- An escape via site of via + 0.05 mm is not enough: the router needs via radius + 0.15 clearance + raster margin
  of free F.Cu; use via + 0.25 mm.
- A scorecard full route that times out leaves no routed.kicad_pcb.
- Edge totals differ between boards (396-422) because pours join pads; compare failed counts, not only routed.
- The PC takes 45-102 min per board with this router (no cap); B4 took 102 min. Queue early.
- Straps that only join via groups by straight / L tracks left 3 PACK_P pieces (D103, U204 area); a grid path
  fallback inside the pour joined all 15 groups.
- Port 2 of merged3 is not a pure copy of port 1 outside the stage (C420/C520 rotation, R454/R554, U406/U506 are
  mirrored centre parts): check `mk.py` renders of both ports.

