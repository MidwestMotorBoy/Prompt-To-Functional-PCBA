# Worker `final` (team A, round 3): integrated board FB, planner F, full route + routed power

Every number here comes from split-zone copper (`final/tools/score_board_f.sh`, a copy of
`stagepwr/tools/score_board_split_a.sh`, which is `tools/score_board_split.sh` plus the PLANNER / STRAPS env).
Round-1 numbers are pre-split and are not used.

## Result

Deliverable candidate = **FB-d**: placement FB + planner F (`--sealed=1 --taps=1 --joinfix=1`) + PACK_P In2 straps.
Staged in `deliver/` (README has the commands).

| field | FB-d |
|---|---|
| power_open (pre-route) | 3V3@L201, GND@J301/J302 (allowed only) |
| DRC errors (pre-route) | 0 |
| hot loops | 7 of 7 tier 1, 6.21 nH |
| blocked edges | 20 of 401 (stage 0 / p1 8 / p2 9 / other 3) |
| loss (pre-route) | 1.035 W |
| **local full route** (scorecard, `--route=150`, default riptime, finished, NOT timed out) | **364 of 401 routed, 37 failed**, 79 min wall for the whole scorecard run (route about 66 min) |
| **PC full route** (`final-d-FBA3JS`) | **363 routed / 38 failed / 401 edges, 88.0 min, done** |
| routed-board power_open | **3V3@L201 only** (J301/J302 GND joined by the router) |
| routed-board DRC errors | 0 (KiCad reports 54 unconnected items, mostly the 37 failed edges) |
| routed-board loss | 1.504 W (PACK_P 0.652 W, GND 0.373 W; pre-route PACK_P 0.222 W, GND 0.334 W) |

## Step 1: placement FB, one command

`final/build.sh <workdir>` (copy of `onecmd/build.sh`, scripts taken from `onecmd/`, overrides from
`final/overrides/`: `10_stagefix_s3`, `20_pdfix_a3` (= merged3), `30_ports_b1` (= ports/best_overrides_gu.json, 6 refs
U502 C508 R541 R504 R502 R503), `40_stagepwr_v1` (= stagepwr/best_overrides_gu.json, 8 refs R416 D404 D405 D410 R516
D504 D505 D510)). Build `runs/fb`: 110 s; placelib `CHECK clean`, `placed 289/289`; `ports/tools/pf.py` check `[]`;
diff against `stagepwr/best_gu.json`: **exactly the 6 ports refs differ**. Saved as `fb_gu.json`, `fb_score.json`
(245 refs in scorecard format). Added `--plan="..."` passthrough so `--score` can carry planner options.

## Step 2: planner F

`final/tools/plan_copper_f.py` subclasses `stagepwr/tools/plan_copper_a.PlannerA` (imported unchanged, so `--sealed`,
`--taps`, `--gate_*`, `--all_gates` work as before) and adds `--joinfix=1`: while `return_join` runs, `Planner.path`
is called with `tight=False` (the change of `ports/tools/plan_copper_joinfix.py`, done as a wrapper, no copy of the
stock planner). Check: b vs c differ in exactly the 5 U401 SDA/SCL/IRQ edges the joinfix was meant to free.
`final/tools/score_board_f.sh` adds env `ROUTER_OPTS` (extra router options) and, when the full route saves
`routed.kicad_pcb`, routed-board DRC / power_open / loss into score.json (`routed_*` fields) plus routed renders.

## Step 3-5: variants of FB (all split copper)

Outdirs under `final/runs/`. a/c/d were run with hot loops on (`--route=0`, about 11.5 min each), b with
`--no-hot` (5 min). The blocked count is the same as a `--no-hot` screen (deterministic copper), so the separate
no-hot screens of a/c/d were skipped.

| variant | planner options | blocked (stage/p1/p2/other) | loss | power_open | DRC | hot loops | PC route routed/failed/edges, min, status | local route | routed power |
|---|---|---|---|---|---|---|---|---|---|
| a `sc_a` | stock | 29 of 400 (5/13/9/2) | 1.052 W | allowed only | 0 | 7/7 tier 1, 6.15 nH | `final-a-FBstock`: 362 / 38 / 400, 89.4 min, done | not run | not checked (PC keeps the routed board) |
| b `sc_b` | sealed+taps | 24 of 396 (0/13/9/2) | 1.035 W | allowed only | 0 | not run | not queued (screen only, per brief) | | |
| c `sc_c` | sealed+taps+joinfix | **19 of 398** (0/8/9/2) | 1.035 W | allowed only | 0 | 7/7 tier 1, 6.21 nH | `final-c-FBA3J`: **366 / 32 / 398**, 99.5 min, done | not run | not checked; without straps PACK_P opened on stagepwr's routed v1A3 board |
| **d `sc_d`, `full_d`** | c + PACK_P In2 straps | 20 of 401 (0/8/9/3) | 1.035 W | allowed only | 0 | 7/7 tier 1, 6.21 nH | `final-d-FBA3JS`: 363 / 38 / 401, 88.0 min, done | **364 / 37 / 401, finished** | **3V3@L201 only, DRC 0, 1.504 W** |

No variant was rejected: all have only the allowed opens and 0 DRC. Straps: 15 PACK_P via groups, 14 straps + 2 grid
paths, 41 tracks, 120 mm, `left_apart []`.

Why d and not c as the deliverable: c routes 6 more edges on the PC (32 vs 38 failed), but its routed board was not
checked, and the same planner without straps (stagepwr v1A3) opened PACK_P at D103 and U204 after routing. d is the
only one with a checked routed board, and it keeps every power path. Straps cost about 3-6 routed edges here too (as
stagepwr found).

## Comparison with split baselines (failed and total, not routed alone)

| board | blocked | full route routed / failed / edges | loss | routed power |
|---|---|---|---|---|
| hand placement | 58 of 422 | 363 / 59 / 422 (PC) | 1.36 W, PP5V open at U401 | |
| ports b1 (stock planner) | 29 of 400 | 364 / 36 / 400 (PC) | 1.054 W | |
| stagepwr v1 stock | 30 of 400 | 363 / 37 / 400 (PC) | 1.052 W | |
| stagepwr v1A3S2 (A + straps) | 26 of 399 | 355 / 43 / 398 (PC) | 1.034 W | 3V3@L201 only, 1.364 W (riptime 600 local route 352/47/399) |
| FB-a (stock) | 29 of 400 | 362 / 38 / 400 (PC) | 1.052 W | |
| FB-c (F, no straps) | 19 of 398 | 366 / 32 / 398 (PC) | 1.035 W | not checked |
| **FB-d (F + straps)** | 20 of 401 | 363 / 38 / 401 (PC); 364 / 37 / 401 (local) | 1.035 W | **3V3@L201 only, 1.504 W** |

FB-d vs v1A3S2 (the same planner idea with straps): 5-6 fewer failed edges (38 vs 43 PC), blocked 20 vs 26, same
hot loops. Routed loss is higher (1.504 vs 1.364 W): PACK_P 0.652 vs 0.515 W, because this route cut the In2 PACK_P
pour between the straps more. The charter target 391 of 448 was set on pre-split copper; no split board reaches
it, the hand board included (363 / 59 / 422). FB-d fails 37-38 of 401 against the hand board's 59 of 422.

FB-a vs ports b1 (same placement except the 8 stagepwr diode refs, stock planner): 362/38 vs 364/36 on the PC;
the PC router's run-to-run spread is a few edges, so the diode tidy is about routing-neutral, as stagepwr found.

Remaining failures of FB-d (local route, 37): U401/U501 GND pins 27/31/36 and J401 A1/B12 GND (the QFN GND pins
next to power pins), C_CC/CC at U405/U505 (VBUS stub over the protector), P1 LDO_3V3, port 2 HG1, DSG_G, CELL2,
and others in `runs/full_d/route.log` (FAILKEY lines).

## Renders (read)

- `sc_d` / `full_d` F.png: both charger stages compact under their inductors (AC caps | Q401 | Q402 | BAT caps), port 2
  a copy of port 1, PD chips 9-10 mm under their USB-C connectors with the protectors between, 5 V bucks beside the
  PD chips, D404/D405/D410 next to the stage. No sprawl: no power part stranded away from its block.
- B.png: thin SW1/SW2 tap tracks (planner taps) per port, PP5V detour blob north of each PD chip, AC_SNS_N corridors,
  BAT_SNS_P stitching. There is one SW2 pour per stage on B.Cu under the inductor (about 5 x 13 mm), the same on
  stagepwr v1A3S2 (identical B.png) and on stock (a): it comes from the stock planner's switch-node layer choice.
  Worth a look by Logan, since a switch-node pour on the bottom radiates; it does not break the hot-loop tier.
- Stock (a): port 1 AC_SNS_N detour on B.Cu runs round the left board edge (x about 1-5 mm); planner F removes it.
- `routed_F.png` / `routed_B.png` (full_d): ordinary routed board, signals on both sides, no long power detours.

## Timing (UTC)

- build 110 s; sc_d 690 s, sc_c 698 s, sc_a 683 s, sc_b 294 s (one at a time, 03:08-03:47).
- PC queue: d 03:19 -> result 04:49 (90 min), c 03:31 -> 05:13 (102 min), a 03:42 -> 05:15 (93 min). All past the
  75-min mark but all arrived; the one local full route (d) had been started at 03:47 anyway.
- Local full scorecard run of d: 03:47-05:07 (79 min, route finished inside the 150-min cap with default riptime).

## Skill notes (for a cheaper model)

1. Integrate placements as override files only: copy `onecmd/overrides/` and add each worker's
   `best_overrides_gu.json` as `30_*.json`, `40_*.json` (disjoint refs; later names win). Build with
   `final/build.sh <wd>`; require `CHECK clean`, `placed 289/289`, and a diff against the reference that lists only
   the refs you expect.
2. Combine planner changes by subclassing, never by copying the stock planner: a module-level option of an imported
   planner module must be set as `module.OPT = ...` (the class reads its own module's globals), not as a local.
3. To change one argument of an inner call (here `tight=True` inside `return_join`), wrap the outer method with a
   flag and override the inner method to read the flag.
4. Screen each variant once with hot loops on (`--route=0`, about 11.5 min) when you will queue it anyway; it gives the
   same blocked count as `--no-hot`. Split the blocked list with `V=-v python3 rebuild/tools/blocked.py <out>`.
5. Queue the PC route right after Reading F.png/B.png; queue all candidates together. PC routes took 88-100 min.
6. For the deliverable, run ONE local scorecard with `--route=150` (finished in about 66 min of routing here; the
   45-min default kills the router before it saves). score_board_f.sh then adds routed power and DRC to score.json.
7. Use the strap board as the deliverable: only a routed-board power check proves PACK_P stays joined.

Traps:
- Two identical planner runs give the same zones/vias/tracks but a cu.kicad_pcb with a different item order and
  uuids, so its git blob sha differs: a PC result is keyed by the queued file, not by the copper.
- A `cmd && nohup x &` line backgrounds the whole `&&` list, so a following `chmod` in the same call runs in the old cwd.
- `run_in_background` jobs are killed at 2 h; for a full scorecard run that may pass 2 h, start it with
  `setsid nohup ... &` and watch its log with a bounded until-loop.
- Routed loss rises a lot over pre-route loss (1.035 -> 1.504 W) because In2 signals cut the PACK_P pour; compare routed
  loss only between routed boards.

## Files

- `build.sh`, `overrides/` - one command bare template -> FB
- `tools/plan_copper_f.py`, `tools/score_board_f.sh` - planner F, scorecard copy
- `fb_gu.json`, `fb_score.json` - placement FB
- `runs/sc_{a,b,c,d}`, `runs/full_d` - scorecard outdirs; `runs/pc_poll.txt` - PC results; `runs/*.sh` - chains
- `deliver/` - best_placement.json, best_placement_gu.json, score.json, F.png, B.png, routed_F/B.png, README.md
