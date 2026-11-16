# Worker `r5_north` (team A, round 5): charger north-row stage edges

Base = r4_bcu k1 (team best + `r4_bcu/overrides/60_r4_bcu.json`, planner `r4_bcu/tools/plan_copper_b.py`, options from
`r4_bcu/tools/best_plan_opts.txt`, copper recipe of `tools/best_env.sh`, split scorecard `tools/score_board_best.sh`).
Base numbers: 0.815 W, DRC 0, 7/7 at 6.27 nH, blocked 5 of 368, PC route 356 / 12 failed of 368
(north-row fails: BTST1 x2 on each port, HG1 port 1).

## Result

**Delivered: v6** = placement override `overrides/70_r5_north.json` (12 refs, 6 per port; port 2 = port 1 moved
-23.026 mm in x, the U403 -> U503 offset) + planner `tools/plan_copper_n.py` (= planner B + `--gatevia=1`) with option
string = the r4_bcu k1 line + ` --gatevia=1`:

    --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1 --pinesc=1
    --pinesc_refs=U501 --pinesc_near=1 --gndpair=1 --tap_max=16 --ret_band=1.6 --pw_nogrow=1 --mirror_skip_supply=1
    --stub_nogrow=1 --mirror_maxa=10 --gatevia=1

Build: `r4_port1/tools/build_r4.sh <workdir> r4_bcu/overrides/60_r4_bcu.json r5_north/overrides/70_r5_north.json`
(CHECK clean, identical to `placement.json`). Score: `tools/screen.sh <name> placement.json "--gatevia=1" hot`.
Outdir `runs/v6gh` (hot loops on); `score.json`, `F.png`, `B.png`, `placement.json` here are that run.

| | base k1 | **v6** |
|---|---|---|
| power_open | 3V3@L201, GND@J301/J302 | same |
| DRC errors | 0 | 0 |
| blocked edges | 5 of 368 | 5 of 368 (same 5 GHOSTFAIL edges) |
| loss | 0.815 W | 0.815 W |
| hot loops | 7/7, 6.27 nH | 7/7, 6.27 nH (HL_OUT 0.628 / 0.633, HL_IN 0.580 / 0.560) |
| sub-route port 1 box (37 edges) | 4 failed (2 runs, identical) | **0** (1 min instead of 8) |
| sub-route port 2 box (34 edges) | 1 failed (2 runs, identical) | **0** |
| PC full route | 356 / 12 failed of 368 (5 north-row) | **362 / 6 failed of 368** (93.6 min); repeat 359 / 9 (83.2 min); **0 north-row fails on both** |
| local full route (fallback) | stopped at 54 min | 361 / 7 of 368, routed power_open {} , routed DRC 0, routed loss 1.093 W |

### Moves (port 1; port 2 the same, x -23.026)
| ref | from | to | why |
|---|---|---|---|
| C412 (BTST1/SW1 bootstrap cap) | 109.59, 107.0, 180 | 109.11, 107.0, 180 | pads now straight over pin 28 (SW1) and pin 26 (BTST1); HIDRV1 (pin 27) drops its via between them |
| D404 (BTST1 diode) | 105.0, 107.5, 90 | 109.63, 105.25, 90 | was west of pins 27/28 (BTST1 had to cross SW1, HIDRV1 and the ACN_F/ACP_F Kelvin escapes); now directly above C412.1, BTST1 pad 1 mm from it |
| C410 (REGN cap) | 110.15, 105.55, 90 | 111.45, 104.17, 0 | made room for D404; REGN runs north in the lane between D404 and C411 into its pad |
| C411 (DRV_SUP cap) | 111.64, 106.35, 90 | 111.5, 106.35, 90 | 0.14 mm west: both lanes (REGN+LODRV1 west, LODRV2+BTST2 east) fit |
| C416 (ACN_F cap) | 107.45, 107.05, 180 | 107.25, 107.05, 180 | 0.2 mm west for C412 |
| TH401 | 109.501, 103.298, 90 | 109.501, 102.9, 90 | 0.4 mm north for D404; its GND pad stays the HL_IN return next to C430 |

Not moved: Q401/Q402, HF/bulk caps, inductors, R444/R445/R446/R447, R454.

## Step 1: diagnosis (zooms `img/base_u403_*.png`, 30 px/mm; `img/v6_*` after)
North row of U403 (y 108.84, west -> east): 28 SW1, 27 HIDRV1, 26 BTST1, 25 LODRV1, 24 REGN, 23 DRV_SUP, 22 GND,
21 LODRV2, 20 BTST2, 19 HIDRV2.
| pin | partner (base) | crossing |
|---|---|---|
| 28 SW1 | C412.2 at 109.11 (over pin 27) + B.Cu tap | runs east over pin 27 |
| 27 HIDRV1 | R444.1 at 111.19, 103.2 (east) | trapped under C412.2; must cross LODRV1's way to R445 |
| 26 BTST1 | C412.1 at 110.07 (over pin 25) and D404.1 at 105.0, 108.2 (5 mm west) | BTST1 to D404 crosses the SW1, HIDRV1 and ACN_F/ACP_F escapes -> "no way" on every PC route |
| 25 LODRV1 | R445 at 110.89, 99.8 | trapped under C412.1 |
| 24 REGN | C410 (110.15, 106.03), D410 (east), R454 (inside the HL_IN hull, sealed), R415 (south) | |
| 23 DRV_SUP | C411.1, D404.2 (far west), D405.2, D410.1, D411 | D404.2 crosses everything |
| 21 LODRV2 | R447 at 116.9, 91.2 (17 mm) | competes with BTST2 for the lane between C411 and C413 |
| 20 BTST2 | C413.1 (bottom) and D405.1 (above C413.2) | must go round C413's SW2 pad |
| HG1 | Q401.1 gate sealed in the HL_IN hull | free via site taken by the ACP_F In2 route (r4_port1 1e) |
The round-4 diagnosis holds: D404/D504 west of the 27/28 escapes; in addition C412 sat half a pitch east so its
pads covered pins 27 and 25 instead of 28 and 26.

## Step 2-4: variants (all DRC 0, power_open allowed, blocked 5 of 368, GHOSTFAIL list = k1 unless noted)
Sub-route = `r4_port1/tools/route_sub.sh` via `tools/subs.sh`, box P1 103.5,96.5,118.5,109.3 (37 edges), P2 the same
shifted -23.026 (34 edges). Repeats of k1 and v3b/v5 gave identical fail lists (the screen is close to
deterministic at this size; minutes are a congestion hint too).

| run | placement | planner | loss W | hot loops | sub P1 failed | sub P2 failed | notes |
|---|---|---|---|---|---|---|---|
| k1 (base) | r4_bcu k1 | k1 | 0.815 | 7/7 6.27 | 4 (HIDRV1, LODRV2, HG2, I2CC_SDA long) x2 runs | 1 (HIDRV1) x2 | PC 356 / 12 of 368 |
| v0g | k1 | +gatevia | 0.816 | - | 3 (HIDRV1, REGN x2) | - | gatevia alone |
| v1g | D404 above C412.1, C410 horiz., TH401 +0.4 | +gatevia | 0.815 | (HL_IN P1 0.580) | 1 (BTST1 pin26->C412.1) | 1 (HIDRV1) | |
| v2g | v1 + R444/TH401 swapped | +gatevia | 0.818 | HL_IN P1 0.623 | 2 (LODRV1, I2CC_SCL) | 2 (LODRV2, BTST1) | R444 in TH401's spot loses C430's GND return |
| v3g | v2 + C412 over pins 28/26, D404 above it | +gatevia | 0.817/0.818 | **7/7 6.34** (HL_IN 0.623/0.590) | 1 (BTST2) | 0 | rejected for nH; PC 358 / 10 of 368 |
| v3bg | v3 without the R444/TH401 swap | +gatevia | 0.815 | HL_IN P1 0.580 | 2 (BTST2 C413.1->D405.1, CHG_INT long) x2 runs | 0 | PC 362 / 6 of 368 |
| v4g | v3b + C413 rot 270 | +gatevia | 0.816 | - | 1 (BTST2 pin20->C413.1) | - | BTST2 failure only moves |
| v5g | v3b + C411/C410 0.31 west | +gatevia | 0.816 | 7/7 6.28 (HL_5V P1 0.465) | 1 (LODRV1) x2 runs | 0 | PC 359 / 9 of 368; rejected (6.28 nH) |
| **v6g / v6gh** | v3b + C411/C410 0.14 west | +gatevia | **0.815** | **7/7 6.27** | **0** | **0** | **PC 362 / 6 and 359 / 9 of 368** |

Rules learned:
- A bootstrap cap belongs with its pads straight over the SW and BTST pins (one pitch either side of the HIDRV pin);
  the HIDRV pin then drops a via between the pins and the cap. Half a pitch off and it covers two other pins.
- The bootstrap diode goes directly above the cap's BTST pad, never across the gate-drive escapes.
- A thermistor's GND pad next to the input HF cap was the HL_IN return path: replacing it with a gate resistor cost
  0.044 nH (v2/v3). Check HL_IN after any move next to C430.
- The 0805 DRV_SUP cap sets two lanes: west (REGN + LODRV1) and east (LODRV2 + BTST2). 0.31 mm west starved
  LODRV1 (v5), none starved BTST2 (v3b), 0.14 mm fed both (v6).
- `--gatevia` (r4_port1 q3) ported as `plan_copper_n.py --gatevia=1`, with a pad-clash check: on k1 the LG2 site of
  the rot-90 Q402 lands on the bottom-side C421 pad (4 DRC errors without the check).

## PC routes (Logan's PC; FAILED lines of the route-results logs, diffed against r4_bcu-k1)
| name | routed / failed of 368 | min | status | north-row stage fails P1 | north-row stage fails P2 | other fails |
|---|---|---|---|---|---|---|
| r4_bcu-k1 (base) | 356 / 12 | 88.8 | done | BTST1 D404->U403.26, BTST1 U403.26->C412, HG1 Q401.1->R444 | BTST1 D504->U503.26, BTST1 U503.26->C512 | CC1, I2CC_SCL, I2CC_SDA, CHG_INT, PP5V R433, SCL J302.6, CELL3 |
| r5_north-v3g (rejected, 6.34 nH) | 358 / 10 | 90.9 | done | BTST2 C413->D405 | - | CC1, SMBD, SCL, TS4, I2CC_SDA, CHG_INT, IRQ_N, PP5V R433, CELL3 |
| r5_north-v3bg | 362 / 6 | 113.8 | done | BTST2 C413->D405 | - | CC1, SCL, I2CC_SCL, PP5V R433, CELL3 |
| r5_north-v5g (rejected, 6.28 nH) | 359 / 9 | 81.3 | done | LODRV1 U403.25->R445, BTST2 C413->D405 | - | CELL_1N, CC1, SMBC, SCL, I2CC_SDA, PP5V R433, CELL3 |
| **r5_north-v6g** | **362 / 6** | 93.6 | done | **none** | **none** | CC1, SCL, I2CC_SDA, CHG_INT, PP5V R433, CELL3 |
| **r5_north-v6g-rep** (same copper, other sha) | 359 / 9 | 83.2 | done | **none** | **none** | CC1, SCL, I2CC_SCL, I2CC_SDA, CHG_INT, SDA U401.8->R305, EN_5V1, PP5V R433, CELL3 |
| local route_local.sh runs/v6gh 150 | 361 / 7 | ~50 | done | none | none | I2CC_SCL P2 U502.6->U501.17, CC1, SCL, I2CC_SDA, CHG_INT, PP5V R433, CELL3 |

The local route was started at 06:16 as the fallback (v6g had no PC result 75 min after queueing at 05:00); both PC
results then arrived (v6g at ~06:50). The local routed board keeps every power net joined (routed_power_open empty,
routed DRC 0, routed loss 1.093 W).
All remaining failures on v6 are the PD-cluster / MCU long runs that r4_port1's override 50 fixes (CC1, I2CC_*,
CHG_INT, PP5V R433) plus SCL J302.6 and CELL3 (outside the stage); none is on the charger north row.
Stacking 50 + 60 + 70 + plan options of both (q2/q3/q4 + pinesc on U401 from r4_port1 and gatevia here) was not
scored by this worker; the courtyard check of 50 + 60 + 70 is clean (below).

## 50 + 60 + 70 clash check
`build_r4.sh <w> r4_port1/overrides/50_r4_port1.json r4_bcu/overrides/60_r4_bcu.json r5_north/overrides/70_r5_north.json`:
placed 289/289, CHECK clean (no courtyard overlap; 50 moves C408, U402, R402-R404, R441, R433, R425, none of them ours).

## Renders
F.png / B.png (v6gh; also routed_F.png / routed_B.png of the local route): both charger stages compact under their inductors, port 2 a copy of port 1; the north-row
support parts all sit within 4 mm of U403/U503 pins, D404/D504 now inside the stage block above the bootstrap cap
instead of out by the ACP/ACN filters; B.Cu unchanged from k1 (only the two 0.3 mm bootstrap taps per port, the PP5V
corridors and the cell path). Zooms in `img/` (base_*, v1g_*, v2g_*, v3g_*, v3bg_sub_* (routed sub board), v6_*).

## Files
- `overrides/70_r5_north.json` (delivered), `placement.json`, `score.json`, `F.png`, `B.png`
- `tools/ov.py` (moves -> override both ports, placelib check, renders), `tools/plan_copper_n.py` (planner B + gatevia),
  `tools/screen.sh` (scorecard with k1 recipe + GHOSTFAIL diff), `tools/subs.sh` (sub-route of both stage boxes)
- `runs/v*.json` moves of each variant, `runs/<v>/` scorecard outdirs, `runs/log.txt`, `runs/sub_log.txt`
- deleted: in/bare boards everywhere, cu boards of v0g/v1g/v2g/v4g/v3gh/v5gh, the kept sub-route board.
