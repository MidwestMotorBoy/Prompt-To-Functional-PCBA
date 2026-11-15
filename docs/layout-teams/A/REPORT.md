# Layout team A: report

Branch `layout-team-A`, folder `docs/layout-teams/A/`. All numbers are from scorecard `score.json` files or from
route results of Logan's PC (branch `route-results`). "Split" means the team scorecard copy that writes one zone per
outline (see "Scorecard bug"); every number in this report is split unless it is labelled pre-split.

## Result

**Best board: `best_placement.json` with the copper recipe of `tools/best_env.sh`** (scorecard outdir
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

`docs/layout-teams/A/rebuild_best.sh <workdir>` rebuilds `best_placement.json` from the bare template
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
