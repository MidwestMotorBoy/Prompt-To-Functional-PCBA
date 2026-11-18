# Layout team A: report

Branch `layout-team-A`, folder `docs/layout-teams/A/`. All numbers are from scorecard `score.json` files or from
route results of Logan's PC (branch `route-results`). "Split" means the team scorecard copy that writes one zone per
outline (see "Scorecard bug"); every number in this report is split unless it is labelled pre-split.

## Result (round 3; superseded, see "Rounds 4-5" at the end)

Round-5 best: stack S, 4 of 364 blocked, PC 356 / 8 failed of 364, 0.801 W, 7 of 7 at 6.27 nH. The table below is the
round-3 board (now `lead_final/best_placement_r3.json`).

**Round-3 best board: `lead_final/best_placement_r3.json` with the copper recipe of `tools/best_env.sh`** (scorecard outdir
`lead_final/sc_Z`, copied to `score.json`, `F.png`, `B.png`).

| | team A best | hand placement, split | hand reference, pre-split |
|---|---|---|---|
| power_open | 3V3@L201, GND@J301/J302 (allowed only) | + PP5V open at U401 | + PP5V open at U401 |
| DRC errors | 0 | 0 | 0 |
| hot loops | 7 of 7 tier 1, 6.24 nH | not run | |
| blocked edges | 5 of 369 | 58 of 422 | 56 of 452 |
| full route, Logan's PC | 352 routed / 17 failed of 369, 92.2 min, done | 363 routed / 59 failed of 422, 13.7 min | 391 of 448 (57 failed), 18 min |
| full route, local | 351 routed / 18 failed of 369, finished in about 70 min (150 min cap) | | |
| loss before routing | 0.835 W | 1.36 W | 1.36 W |
| after routing: power_open | 3V3@L201 only | not checked | not checked |
| after routing: loss / DRC errors | 1.127 W / 0 | | |

Hard limits:
- power_open only the allowed entries: **met**, before routing and on the locally routed board (3V3@L201 only).
- 0 DRC errors: **met** (before routing 0; routed board 0).
- 7 of 7 hot loops tier 1: **met** (tier-2 sum of loop totals 6.24 nH: HL_3V3 1.55, port 1 HL_5V 0.66, HL_IN 0.79, HL_OUT 0.81, port 2 HL_5V 0.89, HL_IN 0.77, HL_OUT 0.77 nH; reference totals 1.95 / 1.08 / 1.02 / 1.03 / 1.08 / 0.99 / 1.00).
- Route >= 391 of 448: **not met as a count, and it cannot be on this copper.** 391/448 was measured with the
  scorecard bug (pours vanished on re-save, so the router ran through them). With correct copper the hand board
  itself routes 363 / 59 failed of 422. Our board has 369 edges in total because the pours reach more pads;
  it fails 17 edges (PC) / 18 (local) against 59 for the hand board on the same
  scorecard, i.e. 95% routed against 86%.
- No route in the final table timed out. The PC result for the best board arrived 94 min after queueing (past the 75-min mark); the
  local full route had been started at queue time for the routed-board power check and finished first.

Open points Logan should know before trusting the board:
1. 17-18 signal edges still fail to route (list below). The board is not a finished routed board.
2. Each charger stage has an SW2 pour of about 5 x 13 mm on B.Cu under its inductor (stock planner behaviour,
   also on every earlier board). It is switch-node copper on the bottom layer.
3. The connector's second VBUS pin pair (J401 A9/B4, J501 A4/B9) is not joined to the VBUS pour by any planner
   variant, so all VBUS current enters through one pin pair. dc_score does not flag it.
4. The best copper uses team planner rules and an In4 PACK_P bus, not the stock planner. With the stock planner the
   same placement scores 29 of 400 blocked, 1.052 W, 7 of 7 (6.15 nH), PC route 362 / 38 failed of 400.
5. The placement is still built from the groundup scripts (about 127 typed poses) plus a relative stage template and
   four override files. The rule-based placer with 16 typed poses is 16 blocked edges behind and was stopped.

## One command

(Round 3 text; since round 5 `rebuild_best.sh` builds stack S and the round-3 board is rebuilt by
`tools/rebuild_best_r3.sh`.) `docs/layout-teams/A/rebuild_best.sh <workdir>` rebuilds `best_placement.json` from the bare template
`tools/score/template/board.kicad_pcb` in about 2 min and checks that it is identical (verified:
"0 of 245 entries differ"). `--score` adds the scorecard with the best copper recipe (`--route=0`, hot loops on);
`--score="--route=150"` adds a local full route with routed-board checks.

## Scorecard bug (found in round 1, affects every earlier number)

`tools/copper/write_copper.py` writes one zone per net and layer with several outlines; KiCad keeps only the first
outline when the board is re-saved (PACK_P F.Cu 8 outlines -> 1, GND F.Cu 17 -> 1). When the router refills zones
most power pours vanish, so route counts were flattered and routed boards had open power. Fix:
`tools/split_spec.py` (one zone per outline) in `tools/score_board_split.sh`. The shared tools were not edited.
Effect on the same boards (PC routes):

| board | pre-split | split |
|---|---|---|
| hand | 391 of 448 (reference) | 363 / 59 failed of 422 |
| stage B4 | 382 / 51 of 433 | 350 / 48 of 398 |
| groundup rebuild (GND open at Q401/Q501) | 378 / 63 of 441 | 350 / 53 of 403 |
| generic p2t_dropee | 379 / 66 of 445 | 353 / 63 of 416 |

## What was tried, in order

All rows: DRC 0. "Limits" = power_open and hot loops. PC = full route on Logan's PC, routed / failed of total.

| step | board (outdir) | limits | blocked | loss W | PC full route |
|---|---|---|---|---|---|
| start | groundup placement on the template (lead_baseline), pre-split | GND open at Q401, Q501; HL_IN open | 65 of 441 | 1.064 | 378 / 63 of 441 pre-split |
| R1 stage | stage template B4 (stage/runs/sc_B4), pre-split | met, 7/7 6.17 nH | 47 of 433 | 1.108 | 382 / 51 of 433 pre-split; 350 / 48 of 398 split |
| R1 rebuild | v5 port support parts (rebuild/runs/v5_hot), pre-split | GND open Q401/Q501, 5/7 | 55 of 436 | 1.071 | 375 / 61 of 436 pre-split |
| R1 generic | rule placer p2t_dropee (generic/runs/p2t_dropee/score_hot), pre-split | met, 7/7 7.86 nH | 60 of 445 | 1.328 | 379 / 66 of 445 pre-split; 353 / 63 of 416 split |
| R2 merge | merged3 = B4 + v5 + stagefix s3 + pdfix a3 (ports/runs/m3) | met (hot not run) | 31 of 400 | 1.053 | 361 / 39 of 400 |
| R2 ports | b1: 6 port-2 parts moved 0.1-0.6 mm (ports/runs/b1_hot) | met, 7/7 6.16 nH | 29 of 400 | 1.054 | 364 / 36 of 400 |
| R2 stagepwr | v1: stage diodes tidied (stagepwr/runs/sc_v1) | met, 7/7 6.16 nH | 30 of 400 | 1.052 | 363 / 37 of 400 |
| R2 stagepwr | v1 + planner A --sealed --taps (sc_v1A3) | met, 7/7 6.21 nH | 25 of 396 | 1.034 | 358 / 38 of 396; routed locally: PACK_P OPEN at D103, U204, 1.744 W |
| R2 stagepwr | v1 + planner A + In2 PACK_P straps (sc_v1A3S2) | met, 7/7 6.21 nH | 26 of 399 | 1.034 | 355 / 43 of 398; routed locally: power joined, 1.364 W |
| R2 onecmd | rule placer r8 (onecmd/runs/r8/score) | met (hot not run) | 47 of 406 | 1.210 | not queued |
| R3 final | FB = b1 + v1, stock planner (final/runs/sc_a) | met, 7/7 6.15 nH | 29 of 400 | 1.052 | 362 / 38 of 400 |
| R3 final | FB + planner F --sealed --taps --joinfix (sc_c) | met, 7/7 6.21 nH | 19 of 398 | 1.035 | 366 / 32 of 398 |
| R3 final | FB + planner F + In2 straps (sc_d, full_d) | met, 7/7 6.21 nH | 20 of 401 | 1.035 | 363 / 38 of 401; local 364 / 37 of 401, routed power joined, 1.504 W |
| R3 portcu | FB + planner P, stack E (portcu/runs/sc_E) | met, 7/7 6.23 nH | 9 of 371 | 1.034 | 351 / 20 of 371 |
| R3 portcu | FB + planner P, stack G5 (sc_G5) | met, 7/7 6.23 nH | 5 of 369 | 1.035 | 353 / 16 of 369 |
| R3 portcu | G5 + In2 straps (sc_G5S) | met, 7/7 6.23 nH | 5 of 372 | 1.035 | 353 / 18 of 371 |
| R3 strapfix | v1 + planner A + In4 PACK_P bus + B GND fill (strapfix/runs/sc_i4b) | met, 7/7 6.22 nH | 25 of 396 | 0.835 | 358 / 38 of 396; local 360 / 36, routed power joined, 1.092 W |
| **lead** | **FB + planner P G5 + In4 bus + B GND fill (lead_final/sc_Z)** | **met, 7/7 6.24 nH** | **5 of 369** | **0.835** | **352 routed / 17 failed of 369, 92.2 min, done; local 351 routed / 18 failed of 369, finished in about 70 min (150 min cap), routed 3V3@L201 only, 1.127 W** |

PC routes took 45-107 min each; the first round's results arrived after the workers' reports, so some worker
notes say "timed out at 60 min" for routes that later finished (stage-B4, rebuild-*). The table has the finished
numbers. One local scorecard route did time out: stagepwr sc_v1A3 with the default 45 min cap (last count 348
routed, 39 failing of 396, no board saved); it was repeated with `--riptime=600`.

## What worked

1. **Charger stage template** (stage/, R1). Q401 hung from the fixed inductor, first cap centred on the FET's cap
   edge, vertical bulk caps against D1, the LG1 gate resistor in the FET gap, port 2 the same template on L501.
   It closed all four charger loops (loop totals 0.77-0.81 nH against 0.99-1.03 for the reference) and removed the GND opens
   at Q401/Q501 that groundup's placement has under generated copper.
2. **PD chip orientation and support parts** (rebuild v5, pdfix a3, ports b1). U401/U501 turned so VBUS pad 23 and
   PPHV pad 20 face the connector and the charger; sense resistor beside the PPHV pad; the PP5V cap at pin 34;
   TVS at the connector VBUS pins. Blocked edges 65 -> 29 on the stock planner.
3. **Planner rules instead of part moves** (stagepwr planner A, final joinfix, portcu planner P). The last 24 blocked
   edges were caused by copper rules: hot-loop hulls sealing gate pins, GND return joins under I2C pins, QFN GND
   pins without a path to their own exposed pad, a dead VBUS pin pair grown over the protector's CC pins, no exit
   strip at connector pads. 29 -> 5 blocked edges with no part moved; PC failures 38 -> 16.
4. **PACK_P bus on In4 + soft GND fill on B.Cu** (strapfix). The router never routes on In4, so the bus cannot be
   cut. Routed power stays joined at no routing cost and loss drops (0.835 W before routing).
5. **Override files + one build command** (onecmd, final). Each worker's result is a small `{ref: pose}` file, so
   results from disjoint regions merge without code changes.

## What did not work

1. **Reaching 391 routed.** No board of ours or the hand board reaches it on correct copper. Remaining failures are
   listed below; they are spread over ports, stage gate/bootstrap nets and the gauge block.
2. **The rule-based placer** (generic/, onecmd/generic): 60 of 445 pre-split in R1, 47 of 406 in R2, against 31 of
   400 for the scripted placement. It cut typed poses from about 127 to 16 and meets the power and DRC limits, but
   was stopped as 16 edges behind. TVS/LDO parts placed by netlist alone sprawled or found no spot.
3. **In2 strap tracks for PACK_P**: power stays joined but 2-6 more failed edges and a routed loss of 1.36-1.50 W.
4. **Bigger free pockets in front of pin rows** (rebuild v6, generic rings x1.3): the planner's grow step fills them.
5. **Planner lanes through intent.json** for HG1 (stage B6/B7): hot-loop pours ignore lanes.
6. **Moving the PP5V pin cap** (ports b2/b3): opened PP5V at U501.
7. Rejected planner options: nogrow_detour, mirror_minw, grow_viaroom, pin escapes on U401 or on all PD pins.
8. Local full routes inside the 45 min scorecard cap: the router needs 60-70 min on these boards.

## Edges that still fail on the best board

Local full route of the best board (lead_final/sc_Z/route.log), 18 failed of 369. "No way" = no path even with every
other route removed; "pulled" = blocked by routes that were ripped up too often. The PC route (17 failed) lists the
same nets in its log tail.

| area | edge | kind |
|---|---|---|
| port 1 PD | I2CC_SCL U402.6 -> U401.17; I2CC_SCL R403 -> U402.6 | no way; pulled |
| port 1 PD | CHG_INT R404 -> U401.18; CHG_INT U403.3 -> R404 (28 mm) | no way |
| port 1 PD | CC1 U401.28 -> U405.12; CC1 U405.12 -> C401 | no way; pulled |
| port 1 PD | I2CC_SDA R402 -> U403.2 (27 mm) | no way |
| port 1 PD | PP5V R433.1 -> PP5V pour (a 3 mm stub at a resistor, not the U401.34 power pin; routed power_open has no PP5V entry) | no way |
| port 1 PD | P1_LDO_3V3 R441 -> R404 | no way |
| port 1 stage | HG1 Q401.1 -> R444; BTST1 D404 -> U403.26; REGN C410 -> U403.24; REGN U403.24 -> R415 | no way; no way; pulled; no way |
| port 2 | I2CC_SDA U502.5 -> U501.16; HIDRV1 U503.27 -> R544; HG1 Q501.1 -> R544 | pulled |
| gauge / MCU | CELL3 J111 -> R103 (52 mm from the fixed connector); SCL J302.6 -> U301.9 (TC2030 pad closed in by the H103 peg and the CELL_P pour) | no way |

Port 1 is clearly worse than port 2 (13 against 3), although the placement is a copy: the port-1 PD chip has the
EEPROM/pull-up cluster and the charger's I2C/CHG_INT runs on its south side. That is the next thing to fix.

## Renders (lead's own reading of F.png and B.png of the best board)

- F.Cu: both charger stages are compact blocks directly under their inductors (AC caps | Q401 | Q402 | BAT caps),
  port 2 a translated copy of port 1, SW1 straight up into the inductor. Each PD chip sits just below its USB-C
  connector with the protector between, VBUS stem into the chip, PPHV out to the sense resistor, the 5 V buck
  beside it. Gauge and protection FETs at the bottom centre. No power part is stranded; nothing I would call sprawl.
- B.Cu: the soft GND fill covers the side. Cut into it are, per port, a PP5V detour blob north of the PD chip, a
  short VBUS/PPHV stub, an AC_SNS_N corridor of roughly 15-20 mm from the sense resistor down to the stage, a
  BAT_SNS_P patch, the SW2 pour of about 5 x 13 mm under the inductor and one thin SW1 tap track. These are the weak
  spots a reviewer will see: bottom-layer switch-node copper and the AC_SNS_N corridors.
- In4.Cu (lead_final/sc_Z/In4.png): one PACK_P region inside the GND plane: a wide pour over the Q102 -> J113/R427
  area and 3 mm bands up to the port-1 top and along the bottom to U204. The rest of In4 stays GND.

## Typed coordinates (generality)

| flow | typed |
|---|---|
| groundup scripts as found | about 116 typed poses, 97 typed search centres, 102 pin maps, about 20 mechanical numbers |
| best placement (rebuild_best.sh) | 127 put/sp poses (34 replaced by the relative stage template), 28 override poses in 4 files, 91 typed search centres, 56 keep_vias spots |
| rule placer (onecmd/generic) | 16 typed poses + 2 x,y-only, 8 enclosure numbers, 19 relative template poses per port; no rule names a ref |

## Files

- `best_placement.json`, `score.json`, `F.png`, `B.png`: the deliverable (from `lead_final/sc_Z`).
- `rebuild_best.sh`: the one command. `tools/`: split_spec.py, score_board_split.sh, score_board_best.sh,
  best_env.sh, route_local.sh, gu_to_score.py. `queue_route.sh`, `route_result.sh`: PC routes.
- Worker folders with their own NOTES.md: stage, rebuild, generic (R1); ports, stagepwr, onecmd (R2); final, portcu,
  strapfix (R3); stagefix, pdfix, lead_merge (interrupted work that was merged). Planners:
  stagepwr/tools/plan_copper_a.py -> final/tools/plan_copper_f.py -> portcu/tools/plan_copper_p.py; In4 bus:
  strapfix/tools/bus4.py.
- Routed/ghost board copies over 5 MB were deleted from the outdirs; logs, score.json and pngs are kept.

## Rounds 4-5

### Result after round 5

**Best board: `best_placement.json` = stack S** (the round-3 build + override files 50 r4_port1, 60 r4_bcu,
70 r5_north, 80 r5_gauge, in `best_overrides/`) **with the round-5 copper recipe** (planner M,
`r5_merge/tools/best_env_r5.sh`, `$BEST_PLAN_R5`; In4 PACK_P bus, soft B.Cu GND fill). Scorecard outdir
`lead_r5/sc_S` (scorer `r5_merge/tools/score_board_r5.sh`, split zones, per-pad join check), copied to
`score.json`, `F.png`, `B.png`. No worker scored this full stack; the lead did.

| | stack S (round 5 best) | lead-Z (round 3 best) | hand placement, split | hand reference, pre-split |
|---|---|---|---|---|
| power_open | 3V3@L201, GND@J301/J302 (allowed only) | allowed only | + PP5V at U401 | + PP5V at U401 |
| DRC errors | 0 | 0 | 0 | 0 |
| hot loops | 7 of 7 tier 1, 6.27 nH | 7 of 7, 6.24 nH | not run | |
| blocked edges | 4 of 364 | 5 of 369 | 58 of 422 | 56 of 452 |
| full route, Logan's PC | 356 routed / 8 failed of 364, 95.1 min, done; repeat (same sha) 356 / 8, 95.3 min, same failed list | 352 / 17 of 369, 92.2 min | 363 / 59 of 422, 13.7 min | 391 of 448 (57 failed), 18 min |
| full route, local (150 min cap) | 357 routed / 7 failed of 364, about 37 min, not timed out | 351 / 18 of 369 | | |
| loss before routing | 0.801 W | 0.835 W | 1.36 W | 1.36 W |
| routed board: power_open / DRC / loss | 3V3@L201 only / 0 / 1.070 W | 3V3@L201 only / 0 / 1.127 W | not checked | |
| pads off their copper (pad_join_check) | C409.1, C509.1 (PPHV 1 uF VAC caps) | + VBUS J401 A9/B4, J501 A4/B9, AC_SNS_N C521.1 | | |

Hard limits on stack S:
- power_open only the allowed entries: **met** before routing and on the locally routed board (3V3@L201 only).
- 0 DRC errors: **met** (placed board 0, routed board 0).
- 7 of 7 hot loops tier 1: **met**, 6.27 nH tier-2 sum (round 3: 6.24; the 0.03 nH comes from the turned Q402/Q502
  stage of round 4, which removed the B.Cu switch-node pours).
- Route >= 391 of 448: **not met as a count**, for the reason in "Result" above (that reference used vanished pours).
  On correct copper stack S fails 8 edges on Logan's PC (twice) and 7 locally, against 59 for the hand board on the
  same scorecard (97.8% routed against 86%). No route of stack S timed out.
- The dead VBUS pin pair of round 3 is fixed (in-pad vias + 0.8 mm B.Cu strap per connector).

Open points before fab (not hard limits on the scorecard, but real):
1. **3V3 and PACK_P pads cut off by routing.** On the routed board pad_join_check lists 3V3 C207.1, C403.1, C503.1
   and PACK_P C213.1 off their net's main copper (the router cuts the soft In3 3V3 pour into pieces; r5_merge
   measured 1 piece -> 7 on m1). dc_score misses it because it solves only J301 -> L201 for 3V3 and caps are shunt
   terminals. Fix: a 3V3 copy on a non-routed layer (as the In4 PACK_P bus) or 3V3 out of the router's soft nets.
2. C409.1 / C509.1 (charger VAC 1 uF caps) are joined only by router tracks; the PPHV pour is 31 mm away.
3. Failed edges. PC (both routes): port-1 I2CC_SDA U402.5 -> U401.16, R402 -> U402.5, R402 -> U403.2,
   I2CC_SCL R403 -> U403.1, P1_LDO_3V3 R441 -> U402.8 and R404 -> R441, SMBC U101.19 -> R115, SCL J302.6 -> U301.9.
   Local route: port-1 PD cluster (I2CC_SDA U402.5 -> U401.16 and R402 -> U402.5,
   P1_LDO_3V3 R441 -> U402.8 and R404 -> R441, CHG_INT U403.3 -> R404), SCL J302.6 -> U301.9, CELL_1N J118 -> TH104.
   The charger north-row stage pins (BTST1, HIDRV1, LODRV, REGN, HG1) no longer fail.

Why stack S and not r5_north v6g (the best single-board route numbers): v6g failed 6 and 9 of 368 on the PC and 7
locally; stack S fails 8 and 8 of 364 on the PC and 7 locally, which is the same within the +-3 edge spread of one
route. Stack S is the only board that has all of: the VBUS dead-pair fix (v6g is built on k1, which lacks it), the
port-1 PD cluster fix, the turned stage and the north-row fix, 4 blocked edges against 5, and lower loss (0.801 against
0.815 W). Its remaining failures are all in the port-1 PD cluster / long port-1 I2C runs and two gauge/MCU edges.

### What was tried in rounds 4-5 (all split copper, all DRC 0, all power_open allowed only)

| round / task | board (outdir) | change | hot loops | blocked | loss W | PC full route (routed / failed of total, minutes) |
|---|---|---|---|---|---|---|
| R3 best | lead_final/sc_Z | | 7/7 6.24 nH | 5 of 369 | 0.835 | 352 / 17 of 369, 92.2 |
| R4 vbus | r4_vbus/runs/v2sh | dead VBUS pin pair joined (padpair 2, live 1) | 7/7 6.24 | 5 of 369 | 0.833 | 353 / 16 of 369, 84.2 |
| R4 port1 | r4_port1/runs/v5p/hot | port-2 PD cluster copied to port 1, R433/R425 swap; padjoin, gatevia, pinesc U401+U501, gndtie | 7/7 6.24 | 5 of 365 | 0.829 | 355 / 9 of 364, 112.5; repeat 354 / 10, 88.2 |
| R4 port1 | r4_port1 v6p | v5p + R404 in front of pin 18 | | | | 345 / 19 of 364, 106.4 (local 354 / 10): rejected |
| R4 bcu | r4_bcu/runs/k1 | Q402/Q502 turned beside the inductor (SW2 F.Cu only) + B.Cu tidy rules | 7/7 6.27 | 5 of 368 | 0.815 | 356 / 12 of 368, 88.8 |
| R4 general | r4_general/runs/sc_pkg | planner chain as a general package (spec IDENTICAL to sc_Z) | 7/7 6.24 | 5 of 369 | 0.835 | no-tuned-data variant 348 / 21 of 369, 70.1 |
| R5 merge | r5_merge/runs/m1h | 50 + 60 + planner M (V+Q+B, gatevia_chk, capjoin) | 7/7 6.28 | 4 of 364 | 0.803 | 355 / 9, 84.5; 350 / 14, 98.8; 351 / 13, 95.7 (of 364); local 353 / 12 of 365, routed 1.091 W |
| R5 merge | r5_merge m2 | m1 with pinesc on U501 only | | 4 of 365 | 0.801 | 351 / 13, 70.4; 349 / 15, 115.9: rejected |
| R5 north | r5_north/runs/v6gh | k1 + override 70 (charger north row) + gatevia | 7/7 6.27 | 5 of 368 | 0.815 | 362 / 6, 93.6; 359 / 9, 83.2 (of 368); local 361 / 7, routed 1.093 W |
| R5 gauge | r5_gauge/runs/g0/hot | v5p + override 80 (C101, C106 nudged) | 7/7 6.24 | 5 of 365 | 0.829 | **timed out at 150 min** (350 / 14); repeat 356 / 8 of 364, 113.2 |
| R5 gauge | r5_gauge g8 | g0 + 1.1 mm F lane through CELL_P for SCL J302.6 | 7/7 6.24 | 4 of 364 | 0.911 | 355 / 9 twice: rejected (CELL_P +83 mW) |
| R5 general | r5_general/runs/all_hot | package with the round-4 rules (spec IDENTICAL to m1) | 7/7 6.27 | 4 of 364 | 0.803 | 356 / 8 of 364, 44.0 |
| **lead R5** | **lead_r5/sc_S** | **50 + 60 + 70 + 80, planner M** | **7/7 6.27** | **4 of 364** | **0.801** | **356 / 8 of 364, 95.1; repeat 356 / 8, 95.3; local 357 / 7 of 364, routed 1.070 W** |

### What worked in rounds 4-5
1. **Copying the fixed twin** (r4_port1): port 2 had the round-2 PD cluster fix, port 1 never did. Copying the
   relative poses (+21.0 mm) and the copper rules (pin escapes on both PD chips) took the port-1 failures from 13 to 4.
2. **Turning the switch FET so its SW exit faces the inductor** (r4_bcu): SW2 on F.Cu only, B.Cu switch-node area
   84.9 -> 14.3 mm2, SW2 coupling to PACK_P 3546 -> 892 fF, loss -0.02 W, hot loops +0.03 nH.
3. **Pin table for the charger north row** (r5_north): bootstrap cap over its own pins, diode above it. All
   north-row stage edges route on every route since.
4. **Small nudges for gauge lanes** (r5_gauge, 0.1 and 0.3 mm): VC2/SMBC/CELL_1N stopped failing on most routes.
5. **Per-pad join check** (r4_vbus pad_join_check): found the dead VBUS pin pair, the floating port-2 bulk cap and,
   after routing, the cut 3V3 pads. Fixed by in-pad vias + B.Cu strap (padpair) and capjoin.
6. **Merging planner subclasses by multiple inheritance** with a no-op regression first (r5_merge), and the general
   package (r5_general) that reproduces every round-4/5 planner spec-identically. The lead checked that the package
   with `r5_general/monolith_r5.rules.json` also gives a spec IDENTICAL to stack S (78 zones / 356 tracks / 288 vias).

### What did not work in rounds 4-5
1. Single-route numbers: identical copper gave 9 / 14 / 13 / 8 failed (m1 and its package twin; stack S gave the
   same 8 twice on one sha, as did r5_gauge g8, so a same-sha repeat is not always independent) and 19 against 10
   (v6p PC vs local). Every candidate was queued twice; differences of 1-3 edges are noise.
2. A lane through the CELL_P pour for SCL J302.6 (r5_gauge g1-g8): SCL routes, but CELL_P loss +59 to +83 mW and
   other J302/cell edges fail instead. Not stacked. connesc_big at J302 opened CELL_P (r4_port1 v1q).
3. Pin escapes on the charger QFN (r4_port1 v6r, r5_general select=all): cut the bootstrap-cap SW taps (+2-4 blocked).
4. Same-layer F.Cu link for the dead VBUS pin pair: crosses the CC/SBU/DP/DN exits on every path.
5. A no-tuned-data copper recipe (In4 box derived): same screen, routed 348 / 21 and routed loss 1.201 W against
   1.127 W, so the In4 box stays board data.
6. Planner-only changes on the unchanged stage (r4_bcu p1, c1): SW2 B.Cu only down to 27 mm2 at +0.03-0.07 W.

### Renders of stack S (lead's own reading of F.png and B.png)
- F.Cu: each PD chip sits directly under its USB-C connector with the protector between and the 5 V buck beside it;
  the port-1 PD cluster now matches port 2. Charger stages are compact around the inductors with Q402/Q502 turned
  beside the inductor pad, bootstrap diode and caps tight at the U403/U503 north row, port 2 a copy of port 1.
  Gauge and protection FETs at the bottom centre, filters at the gauge pins. No power part is stranded or sprawled.
- B.Cu: almost all soft GND fill. Cut into it: the two VBUS straps under the connector pad rows, two thin PP5V
  corridors, the 0.3 mm SW1/SW2 bootstrap taps (no switch-node pours), the port-2 AC_SNS_N strap (capjoin) and a
  port-1 AC_SNS_N stub, PACK_P pads under the FET row, the FET_MID pour and the cell-path straps at the bottom.
  This is the cleanest bottom side the team has had.

### One command (round 5)
`docs/layout-teams/A/rebuild_best.sh <workdir>` rebuilds stack S from the bare template in about 2 min
(verified 2026-11-16: `CHECK clean`, `0 of 245 entries differ from best_placement.json`); `--score` adds the
scorecard with the round-5 recipe, `--score="--route=150"` a local full route with routed checks. The round-3
board is `lead_final/best_placement_r3.json` (`tools/rebuild_best_r3.sh`).

### Files (rounds 4-5)
- `best_placement.json`, `score.json`, `F.png`, `B.png`, `routed_F.png`, `routed_B.png`: stack S (from `lead_r5/sc_S`).
  `In4.png` is still the round-3 render (the In4 PACK_P bus recipe is unchanged).
- `rebuild_best.sh` + `best_overrides/` (the one command); `r5_merge/tools/` (planner M, score_board_r5.sh,
  best_env_r5.sh, route_local_r5.sh, spec_diff.py); `r5_general/copper_rules/` (the general package, spec IDENTICAL
  to stack S with `r5_general/monolith_r5.rules.json`).
- Worker folders with NOTES.md: r4_vbus, r4_port1, r4_bcu, r4_general (round 4); r5_merge, r5_north, r5_gauge,
  r5_general (round 5); lead_r5 (the lead's build and scorecard of stack S).
- 16 more cu/routed board copies over 5 MB were deleted from old outdirs in round 5.

## Round 6 (last round): every connection closed on the routed board

Goal: 0 failed connections on the full route, every cap joined on the routed board, all hard limits kept.
Placement did not change (stack S); only copper did.

### Result (board m14, `rebuild_best.sh <workdir> --score`)
| check | final board m14 | planned copper before signals (m13) | stack S (round 5) |
|---|---|---|---|
| power_open | none | 3V3@L201, GND J301/J302 (allowed) | same allowed |
| DRC errors (custom rules on) | 0 | 0 | 0 |
| hot loops | 7 of 7, 6.41 nH | 7 of 7, 6.27 nH | 7 of 7, 6.27 nH |
| loss | 1.241 W (all copper) | 0.865 W | 0.801 W (routed 1.070 W) |
| KiCad unconnected items | 0 | 334 (signals) | 24 after routing |
| pads off their pour | none | PPHV C409.1, C509.1 | 3V3 C207/C403/C503, PACK_P C213 |
| local full route | 0 of 0 edges, 0 failed | 340 of 341, 1 failed (about 25 min, not timed out) | 357 / 7 |
| PC full route | lead6-m14 and -rep: 0 of 0 edges, 0 failed, unconnected after fill 0 (0.2 min) | lead6-m13-rep: 339 / 1 failed of 340, 54.6 min, 4 open items (lead6-m13 not returned) | 356 / 8 |

How it was reached, said plainly: **the final board is a frozen route, not a fresh one.** The router never
delivered a board with 0 open connections by itself. The best planned board (m13) routes locally to 340 of 341 with
4 KiCad open items (5 with the stock router), and on the PC its predecessors m9 and m11 route to 339/1, 339/1,
338/1, 337/2 (the same short port-2 PD hop fails each time: P2 I2CC_SDA or I2CC_SCL, "pulled too often").
I then copied the complete local route of m13 (`runs/m13e`, 3319 tracks and 400 vias) into a fix file
(`r6_merge/fixes/frozen_m13e.json`, tool `prelay.py --net=.`) and closed what was left by hand
(`tools/freeze_fix.py` -> `fixes/frozen_final.json`), each edit checked by KiCad DRC:
1. P2 CHG_INT R504.2 -> U501.18: a 0.15 mm F.Cu track through the 0.45 mm gap between the SCL via and R541.2
   (0.15 mm each side, exactly at the rule), with the SBU_FLT pin-19 stub straightened to make room.
2. PACK_P TP106.1 and its F.Cu pour piece: one via to the PACK_P planes.
3. 3V3 J301.1 island: 0.6 mm track and a via into the In3 pour / In4 band.
4. 3V3 R417.2 island: via beside the pad and a 3.9 mm In4 track into the In4 3V3 band.
5. Four clearance errors at the gauge (CELL_1N stubs at U101 pins 9, 16, 17 against the 0.25 mm
   high-current rule): stub ends shortened or narrowed to 0.15 mm.
A router run on the final board (local and PC) therefore has nothing to route; it is a check, not a routing result.
The proof that the board is closed is KiCad's DRC on it: 0 errors, 0 unconnected items, plus no islands on 3V3,
PACK_P or GND (`tools/net_islands.py`) and no pad off its pour (`routed_pad_unjoined`, `routed_allpad_off` empty).

### What the merge needed (m1 to m13, details in `r6_merge/NOTES.md`)
- Both worker fixes merged: r6_routes escape fixes (CP5 list) + r6_caps capfix E (3V3 copy on In4, cap stubs,
  PPHV VAC links). The plain merge (m1/m4) routed 342/1 on the PC but left 9 to 13 KiCad open items.
- "0 failed" from the router is not "0 open": it counts an escape stub that touches its own island as routed,
  skips Zone|Zone items and makes zero-length routes for Zone|Pad items of non-plane nets. r6r-sccp5 (350/0) had 15
  open items. From m4 on, the judge was KiCad's unconnected list on the routed board.
- Lead fixes on top (r6_merge/fixes): VBUS pin-32 links (vbus32b), port-1 VAC link moved off ACUV's via site
  (p1vac), charger VAC pin bridge (vac_p2), R314 3V3 via, R418.1 via-in-pad, port-1 PPHV pull-back, BTST1 and NRST
  pre-lays. Rejected: port-2 cluster pre-lay (p2self, p2scl: failures move), J301.1 3V3 via (j301_3v3: J301.5 GND
  loses its way, 600 rip-ups), EN_5V1 pre-lay (shorts), finish passes with the router on a routed board (adds DRC
  errors, does not converge).

### Scorecard gap found
The routed-board DRC of rounds 4-6 ran without the custom rules file (no `routed.kicad_dru` beside
`routed.kicad_pro`), so earlier "routed DRC 0" claims did not check the 0.25 mm high-current rule, the hole rules or
the edge margin. With the rules on, the m13 routed board had 4 errors (item 5 above). Fixed in
`route_local_r6m.sh` and `score_board_r6m.sh`; the final board is clean with the rules on.

### What remains open
- Nothing on the hard limits or the connection list of the final board.
- The router alone still leaves 1 failed edge and 4 to 5 open items on the planned copper (m13), so a changed
  placement or netlist needs the freeze-and-finish step again (about 30 min by hand).
- The CHG_INT track sits at exactly 0.15 mm on both sides; fine by the rule, no margin.
- Loss rose from 0.801 W (stack S plan) to 0.865 W planned (escape cuts, capfix) and 1.241 W with signals routed
  through the soft pours (stack S routed: 1.070 W). Ringing: 6.27 nH planned, 6.41 nH on the final board.
- Hot loops and loss were not re-tuned this round; `r5_general/upstream.diff` is still not applied.

### Renders (lead's own reading)
- F.png (planned copper): unchanged compact layout; each PD chip under its USB-C connector, charger stages at the
  inductors, gauge and FETs bottom centre. No sprawl.
- routed_F.png: fully routed, signal tracks dense around the two PD chips and the MCU; power pours intact.
- routed_B.png: GND fill with signal runs cut into it, densest around the gauge (the fill is chopped there but
  joined, no GND island); one long run follows the west board edge. No power part moved.
