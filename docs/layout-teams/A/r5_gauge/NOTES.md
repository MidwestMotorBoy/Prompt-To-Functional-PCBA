# Worker r5_gauge (team A, round 5): gauge / MCU failed edges

Base = r4_port1 v5p (placement `A/r4_port1/placement.json`, planner `A/r4_port1/tools/plan_copper_q.py`, BEST_PLAN +
`--padjoin=4 --gatevia=1 --pinesc_refs=U401,U501 --gndtie=1`): 0.829 W, 7/7 at 6.24 nH, blocked 5 of 365, PC route
355 / 9 failed of 364 and repeat 354 / 10. All copper below is split-zone (`score_board_best.sh` through
`A/r4_port1/tools/score_r4.sh`).

Gauge / MCU failures of the base on the PC (FAILKEY, `git show origin/route-results:A/r4_port1-v5p[-rep]-c11115b2.log`):
- v5p: `Net-(U101-VC2)` U101.4 -> C102.2 (starts 23, seen 28, pulled), `Net-(U101-SMBC)` U101.19 -> R115.1 (starts 21,
  seen 27, pulled), `SCL` J302.6 -> U301.9 (seen 621, no way even with every other route gone).
- v5p-rep: `CELL_1N` U101.33 -> U101.16 (goals 65 at pin 16, seen 187, no way), SMBC (same), SCL J302 (same).
- r4_bcu-k1: `CELL3` J111.1 -> R103.1 (52 mm, seen -12000001 = node cap 12 M exhausted), SCL J302.
- r4_bcu-v6r: CELL_1N, SCL J302.

## 1. Walls (renders in `img/`, 30-80 px/mm; router free-cell maps from `ports/tools/dbg.sh`)
| edge | wall |
|---|---|
| VC2 U101.4 -> C102.2 | Gauge cell inputs leave the west pin row at 0.4 mm pitch: pins 3 (VC3), 4 (VC2), 5 (VC1). Straight west of pin 4 (y 120.8) the column of filter caps at x 93.25 leaves 0.5 mm between C101.2 (VC3, y 120.43) and C106.2 (SRN, y 121.52); a 0.2 mm track needs 0.6. So VC2 has to go round C101 or C106 and is the middle one of three neighbours that all go west: once VC3 and VC1 are laid its start cells are 23 (seen 28) and it is "pulled too often". (`img/u101_F_60.png`, `img/base_routed_u101_4L.png`.) |
| SMBC U101.19 -> R115.1 | The east pin row (17-24) faces the FET_MID pour of Q101/Q102 (drains, 10 A) that the planner draws up to the 0.4 mm escape room: no via site between the pins and the pour, so SMBC/SMBD must leave along that 0.4 mm strip (where the CELL_1N pins 17/23/24 and SMBD sit) or inward to a via under the QFN, and then cross FET_MID on an inner layer to R115 east of Q102. Start region 21 cells. (`img/smbc_F.png`.) |
| SCL J302.6 -> U301.9 | TC2030 pads are F only, 0.48 mm apart (track + clearance needs 0.6), NPTH pegs at 110.49,130.76 / 132.79 beside pad 6: the north-row pads (2 CHG_INH, 4 NC, 6 SCL) can only leave north. North of them runs the 10 A CELL_P tree Q101 -> F102.2 on F (1 mm strip between the pad row and H103 / J118) and its B.Cu mirror under it; CELL_P is HighCurrent (track clearance 0.3 mm from it). Rule q1 (connesc_big) cut both copies with its via site and opened CELL_P at F102. (`img/j302_F_60.png`, `img/j302_inner_strip.png`.) |
| CELL3 J111 -> R103 | not walled: 52 mm diagonal from the top-right wire pad to the gauge filter; the router's node cap (12 M) runs out. R103 is the cell-3 input filter and must stay at U101 pin 3; J111 is fixed. Not changed. |
| CELL_1N U101.33 -> U101.16 | EP (1.4 mm) to the corner pin 16: the pin's inner end is 0.85-1.0 mm from the EP edge and a straight track passes 0.11 mm from pin 15 / pin 18; the router finds it on some routes only (2 of 4 logs). planner P's --epstrip reaches only pins <= 0.8 mm from the EP (tried as g4 `--epnets=U101`: 0 strips drawn). Not changed. |
| (ghost-blocked, not a full-route failure) GAUGE_FUSE U101.25 -> R126.2 | R126 sits in a pocket between the CELL_P_RAW pour and the board-edge notch (F walled, no via). Moving R126 next to Q104's gate (tried in build1) frees the pad but the ghost screen still fails it (25 mm, search cap). It routes on every PC log, so R126 was left where it is. |

## 2. Fixes
### Placement: `overrides/80_r5_gauge.json` (2 parts, gauge filter caps only)
- C101 (VC4-VC3 filter) 93.25,119.95 -> 93.25,119.85 (rot 270 unchanged); C106 (SRP-SRN filter) 93.25,122.0 ->
  93.25,122.3 (rot 90 unchanged). The lane at y 120.8 for VC2 opens from 0.5 to 0.9 mm. Both caps stay in the same
  column 1.75 mm from the gauge pins (C106.2 SRN is now level with pin 6 SRN; C106.1 SRP 0.28 mm below pin 8).
  Kelvin: constraints.json `kelvin` lists only the charger sense resistors (R424/R427/R524/R527); the gauge sense
  pair SRP/SRN keeps its filter cap at the pins.
- Build: `A/r4_port1/tools/build_r4.sh <work> A/r4_port1/overrides/50_r4_port1.json r5_gauge/overrides/80_r5_gauge.json`
  -> `CHECK clean`, 289/289 placed; differs from r4_port1/placement.json in C101, C106 only. Copy in `placement.json`.
- Disjoint from `A/r4_bcu/overrides/60_r4_bcu.json` (C431 C434 C438 C531 C534 C538 D405 D410 D505 D510 Q402 Q502 R427
  R428 R429 R446 R447 R527 R528 R529 R546 R547 R554): no shared refs.

### Planner: `tools/plan_copper_g.py` (subclass of PlannerQ; no g option = identical to plan_copper_q.py)
- g3 `--pinvia=U101.19:1.0`: planner P's pin-escape reservation (strip + via site 1.0 mm past the pad, which power
  copper keeps clear of) for a named pin, whatever its neighbours. Puts a via site at 100.1,121.6 between the SMBC pin
  and the FET_MID pour. Cost: FET_MID 4.1 -> 4.3 mW.
- g6 `--fcut_path=109.22,130.9/109.78,129.55/110.75,128.3/110.75,126.4 --fcut_w=1.1 --fcut_vias=10`: after the grow
  step, a 1.1 mm lane is cut out of the F power copper from J302.6 north-east between H103 and the J302 peg, then north
  between H103 and J118; planner vias in the lane go (CELL_P 110.75,129.375); every cut net piece next to the lane that
  also has B copper gets up to 10 new vias toward the lane (6 fit, west side). CELL_P keeps its B mirror across the
  lane (B-only for ~1.5 mm). The lane width matters: 0.7 mm (g4) was still closed for the router (HighCurrent
  clearance 0.3 + track 0.1 > 0.35); 1.1 mm opens it.
- g7 `--bfill=CELL_P@104.8,128.8,109.7,131.75`: CELL_P B copper also fills the free B area under J302 (its pads are F
  only; B held only the soft GND fill) to win back part of the lane's loss (+8.7 mm2).
- Tried and dropped: g1 `--fkeep` (block the whole F band north of J302 so the stock detour() takes CELL_P on B only):
  CELL_P 0.123 -> 0.392 W, and CHG_INH J302.2 took the freed lane; `--viasite` for J302.2 broke the detour (CELL_P open
  at F102 again); g4 `--epnets=U101` drew nothing (pins > 0.8 mm from the EP).

## 3. Variants (scorecard `tools/screen.sh` = score_r4.sh with PLANNER_Q=plan_copper_g.py, --route=0 --no-hot)
| run | placement | planner extra | power_open | DRC | blocked | CELL_P / FET_MID / PACK_P / CELL_N mW | loss W | ghost-blocked gauge/MCU |
|---|---|---|---|---|---|---|---|---|
| base v5p/hot | r4 v5p | - | allowed only | 0 | 5 of 365 | 122.8 / 4.1 / 131.2 / 8.8 | 0.829 | SCL J302.6, CHG_INH J302.2, GAUGE_FUSE |
| g1_viasite | 80 + R126 move | fkeep + viasite J302.2 + pinvia + epnets | **CELL_P open F102** | 0 | 4 of 367 | - | 0.702 | rejected |
| g1 | 80 + R126 move | fkeep + pinvia + epnets | allowed only | 0 | 5 of 364 | **392.1** / 4.3 | 1.098 | CHG_INH, GAUGE_FUSE, new C117->U102.7; SCL free |
| g0 | 80 | - | allowed only | 0 | 5 of 364 | 122.6 / 4.1 / 131.2 / 8.9 | 0.828 | same as base |
| g6 | 80 | pinvia U101.19 | allowed only | 0 | 5 of 364 | 122.8 / 4.3 / 131.2 / 8.8 | 0.829 | same as base |
| g2 | 80 | fcut boxes + pinvia | allowed only | 0 | 4 of 364 | 209.7 | 0.916 | SCL free |
| g3 | 80 | fcut_path w0.7, vias 6 + pinvia | allowed only | 0 | 5 of 365 | 190.4 | 0.896 | SCL still blocked (CELL_P via 110.75,129.38 in the lane) |
| g4 | 80 | g3 lane re-drawn, via removal, vias 10 | allowed only | 0 | 5 of 364 | 216.5 | 0.923 | SCL still blocked (lane 0.7 mm < HighCurrent clearance) |
| g5 | 80 | g4 with fcut_w 1.1 + bfill | allowed only | 0 | 5 of 366 | 182.1 | 0.888 | SCL free; CHG_INH x2 (J302.2 gets a 2nd edge) |
| **g7** | 80 | g5 with lane end 126.4 (keeps C304's GND via) | allowed only | 0 | 5 of 364 | 182.1 / 4.3 / 131.2 / 8.8 | 0.888 | SCL free; CHG_INH R435/R535 -> J302.2, GAUGE_FUSE, DRV9_OFF, I2CC_SDA |

| **g8** | 80 | g7 with bfill box 107.4,128.8,109.7,131.75 (keeps the B via spot north of J302.2) | allowed only | 0 | **4 of 364** | 205.4 / 4.3 / 131.2 / 8.8 | 0.911 | SCL free; CHG_INH R535->J302.2 (as base), GAUGE_FUSE, DRV9_OFF, I2CC_SDA |

Hot loops (scorecard without --no-hot, copper identical to the screened/queued board):
- `runs/g7/hot`: 0.888 W, power_open allowed only, DRC 0, **7 of 7 pass, 6.24 nH**, blocked 5 of 364.
- `runs/g8/hot`: 0.911 W, power_open allowed only, DRC 0, **7 of 7 pass, 6.24 nH**, blocked 4 of 364 (spec.json
  zones/vias/tracks identical to runs/g8/sc, the PC-queued board).

Loss: g0 / g6 (placement + pinvia) are loss-neutral (0.828 / 0.829 W). Every variant that opens SCL's lane raises
CELL_P (10 A, Q101 -> F102): the current crosses the lane on B only, through the ~1 mm neck between H103 and the
J302 peg at 110.49,130.76 (both NPTH, keep-outs on every layer), plus via transfers. Best found: +59 mW (g7, bfill
from x 104.8); g8 +83 mW. **This breaks the "CELL_P loss not higher than base" screen rule**, so the lane options are
delivered as an optional set, not as part of the default.

### Sub-route screen (`tools/route_sub.sh`, box `88,113,101.5,127;104,115,121.6,134` = gauge + J302/MCU/R115, 128 edges)
- base: 127 / 1 failed (SCL J302.6, no way) in 15 min. VC2 and SMBC route in the sub-route (they fail only under full-board congestion), so the sub-route only tests SCL.
- g1: 124 / 4 failed in 54 min: SCL J302.6 now "blocked by routes pulled too often" (no longer no way) - CHG_INH J302.2 took the lane (`img/g1_routed_j302_4L.png`) - plus three 36-37 mm MCU runs from port 1 (SDA/SCL U401 -> R304/R305, EN_5V1) on the node cap.
- The first box (86,110,121.6,137.2, 203 edges) timed out at 40 min (`runs/base_sub`); g0/g2/g3 sub-routes were stopped by me to free the CPU (not timeouts).

## 4. Full routes (Logan's PC, one thread each; split copper; FAILKEY lists from the result logs)
Gauge/MCU column = non-port FAILKEYs (`tools/faildiff.sh <name>`). U101 edges = VC2 / SMBC / SMBD / CELL_1N.

| name | board | routed / failed of edges | minutes | status | gauge / MCU failed edges |
|---|---|---|---|---|---|
| (base) r4_port1-v5p | v5p | 355 / 9 of 364 | 112.5 | done | VC2 U101.4, SMBC U101.19, SCL J302.6 |
| (base) r4_port1-v5p-rep | v5p | 354 / 10 of 364 | 88.2 | done | CELL_1N U101.33->16, SMBC U101.19, SCL J302.6 |
| r5_gauge-g0 | 80 (placement only) | 350 / 14 of 364 (at timeout) | 150.0 | **timed out at 150 min** (no failure list) | - |
| r5_gauge-g0-rep | 80 | **356 / 8 of 364** | 113.2 | done | SCL J302.6, IRQ_N U401.10->U501.10 (PD-PD, not gauge) |
| r5_gauge-g6 | 80 + pinvia U101.19 | 350 / 14 of 364 | 137.7 | done | SMBC U101.19, SMBD U101.18, SCL J302.6, GAUGE_FUSE, U102-OUT U102.8->R124, RFIO, CELL_P C110->R118 |
| r5_gauge-g6-rep | 80 + pinvia | 352 / 12 of 364 | 129.2 | done | SCL J302.6, EN_5V1, EN_5V2, CELL1, CELL3 (long runs, node cap / congestion) |
| r5_gauge-g7 | 80 + pinvia + fcut lane + bfill 104.8-109.7 | 354 / 10 of 364 | 130.0 | done | CHG_INH R435->J302.2, CHG_INH R535->J302.2, IRQ_N |
| r5_gauge-g7-rep | same | 354 / 10 of 364 | 80.7 | done | CHG_INH x2, CELL3 |
| g7 local (`tools/route_local.sh runs/g7/hot 150`, fallback: no PC result 75 min after queueing) | same | 353 / 11 of 364 | ~50 | done (not timed out) | CHG_INH x2, CELL3; routed_power_open 3V3@L201 only, routed DRC 0, routed loss 1.168 W |
| r5_gauge-g8 | 80 + pinvia + fcut lane + bfill 107.4-109.7 | 355 / 9 of 364 | 115.2 | done | CHG_INH R535->J302.2, CELL1 J109->R101, CELL3 J111->R103 |
| r5_gauge-g8-rep | same | 355 / 9 of 364 | 114.6 | done | identical list to g8 |

Reading:
- **U101 pins (VC2, SMBC, CELL_1N)**: failed on both base routes (2 each). After the C101/C106 nudge they routed on 7 of
  8 finished full routes (g0-rep, g6-rep, g7 x2, g7 local, g8 x2); the exception is g6 (SMBC + SMBD, pins 19/18 of
  the east row). VC2 and CELL_1N did not fail once after the nudge.
- **SCL J302.6** fails on every route without the lane (base x2, g0-rep, g6 x2) and routes on every route with it
  (g7 x2 PC + local: F track from pad 6 north-east through the lane, up between H103 and J118, via at ~110.9,126.6).
- **CHG_INH J302.2** (never failed on the base): with g7's bfill box (B CELL_P under J302 from x 104.8) both CHG_INH
  edges fail on all three g7 routes. Wall: on the base the router drops a via right north of pad 2 (106.7,130.4) into
  the soft B GND fill (`img/base_routed_j302_F.png`); the bfill made that spot hard CELL_P copper. g8 starts the bfill
  at x 107.4 (east of pad 2), which keeps that via spot (CELL_P 182 -> 205 mW).
  g8 brings it back to one CHG_INH edge (R535 -> J302.2, the edge the base ghost screen already calls blocked; the
  base routes reached it through a fan-out via just north of pad 2). Why that one still fails on g8 is not proven
  (no routed g8 board here); the likeliest wall is the new fcut via at 106.65,129.575 next to that via spot.
- CELL3 / CELL1 (52 mm diagonal cell taps from the top wire pads, "seen -12000001" = node cap) fail on g6-rep, g7-rep,
  g7 local and both g8 routes, not on g0-rep or the base; also on r4_bcu-k1. They are search-limit failures of a 52 mm
  run, not walled pads; R101/R103 stay at U101 pins 5 / 3 (filters at the gauge).

### Before / after, gauge-MCU edges named in the task
| edge | base v5p / rep | g0-rep (80 only) | g6 / g6-rep (80 + pinvia) | g7 / g7-rep / g7 local | g8 / g8-rep |
|---|---|---|---|---|---|
| VC2 U101.4 -> C102 | fail / ok | ok | ok / ok | ok / ok / ok | ok / ok |
| SMBC U101.19 -> R115 | fail / fail | ok | **fail** / ok | ok / ok / ok | ok / ok |
| SCL J302.6 -> U301.9 | fail / fail | fail | fail / fail | ok / ok / ok | ok / ok |
| CELL3 J111 -> R103 | ok / ok | ok | ok / fail | ok / fail / fail | fail / fail |
| CELL_1N U101.33 -> 16 | ok / fail | ok | ok / ok | ok / ok / ok | ok / ok |
| (new) CHG_INH -> J302.2 | ok / ok | ok | ok / ok | 2 fail each | 1 fail each |

## 5. Conclusion / what to stack
- **Default: `overrides/80_r5_gauge.json` (C101, C106), no planner option.** Loss-neutral (0.829 W), 7/7 at 6.24 nH,
  blocked 5 of 365, power_open allowed only, DRC 0 (`runs/g0/hot`, copied to `score.json`, `F.png`, `B.png`). Its one
  finished PC route is the best of this worker: 356 / 8 of 364 (the first copy timed out at 150 min with 350 routed).
  VC2 / SMBC / CELL_1N did not fail on it; SCL J302.6 still does.
- `--pinvia=U101.19:1.0`: not shown to help (g6 lost SMBC + SMBD on one of two routes; g7/g8 with it never failed
  SMBC). Optional, loss-neutral; not recommended on its own evidence.
- **SCL J302.6 option set (g8)**: `--pinvia=U101.19:1.0 --fcut_path=109.22,130.9/109.78,129.55/110.75,128.3/110.75,126.4
  --fcut_w=1.1 --fcut_vias=10 --bfill=CELL_P@107.4,128.8,109.7,131.75` with PLANNER=`r5_gauge/tools/plan_copper_g.py`.
  It fixes SCL on all 5 routes that had it (g7 x3, g8 x2) and keeps 7/7, but costs CELL_P +83 mW (0.911 W total) and
  on g8 one CHG_INH edge plus CELL1/CELL3 failed, so the PC count is 355 / 9 (= base), not better. Use it only if
  SCL to the gauge's TC2030 must route; next step would be to keep the fcut vias out of the 1 mm round J302.2's fan-out
  via spot (106.7,130.4) and re-queue.
- The planner rule options run from `A/r4_port1/tools/score_r4.sh` with `PLANNER_Q=.../r5_gauge/tools/plan_copper_g.py`
  (that is what `tools/screen.sh` does).

Traps found here (for SKILL-NOTES):
- A lane cut out of a HighCurrent pour must be >= 2 x (0.25 clearance + 0.1 HighCurrent extra + half track) + grid
  margin: 0.7 mm stayed closed, 1.1 mm opened it.
- Planner vias of the cut net inside the lane must go too (the CELL_P via at 110.75,129.375 closed the first lane).
- A B.Cu pour added under a TC2030 (pads F only) removes the router's via spots for the connector's pads (CHG_INH).
- The stock planner's detour() takes a whole 10 A tree onto one layer when the main layer is blocked: 3x the loss.
- route_sub.sh on 203 edges (box 86,110,121.6,137.2) does not finish in 40 min; 128 edges (two boxes) take 15 min.
- On this board VC2 / SMBC failures are full-board congestion: the sub-route routes them every time, so only PC
  routes test them.

## Files
- Score dirs: `runs/g0/hot` (default deliverable, hot loops on), `runs/g8/hot` (SCL option set, hot loops on; renders
  copied to `img/g8_F.png`, `img/g8_B.png`, `img/g8_score.json`), `runs/g7/hot` (+ local full route: route.log,
  routed_F/B.png, score.json with routed_* fields; the routed board was deleted, > 5 MB). Screens: `runs/g*/sc`.
- `overrides/80_r5_gauge.json`, `placement.json` (build of r4 v5p + 80), `tools/plan_copper_g.py`, `tools/screen.sh`,
  `tools/route_sub.sh` + `tools/router_sub.py` (copies, box default changed), `tools/specplot.py` (matplotlib view of a
  spec.json), `tools/dccmp.py` (per-net loss table), `tools/faildiff.sh` (PC FAILKEY vs both v5p logs).
