# Worker r5_merge (team A, round 5): one board with all three round-4 wins

All numbers are split-zone copper from `tools/score_board_r5.sh` (copy of `r4_vbus/tools/score_board_r4v.sh` =
team best scorecard + pad_join_check with `r4_vbus/allow.json`; only change: PLANNER defaults to planner M).
"allowed" = power_open is 3V3@L201 and GND@J301/J302 only.

## Result

**Best = m1** (copper identical to m1h, which adds the hot loops).

- Placement: `placement.json` = team build (`final/build.sh` + `final/overrides/*.json`) + `overrides/50_r4_port1.json`
  + `overrides/60_r4_bcu.json` (built with `r4_port1/tools/build_r4.sh`, log `runs/build/build.log`: CHECK clean,
  placed 289/289, 0 placement errors; exactly 30 refs differ from `best_placement.json` = the 7 moved refs of 50
  (R402 already matched) + the 23 of 60; it equals `r4_bcu/placement.json` except the 7 port-1 refs and
  `r4_port1/placement.json` except the 23 stage refs).
- Planner: `tools/plan_copper_m.py`, options in `best_plan_opts.txt`; `source tools/best_env_r5.sh` gives PLANNER, BUS4,
  BUS4B, `$BEST_PLAN_R5`, `$R5_PLACEMENT`.
  `tools/score_board_r5.sh <out> $R5_PLACEMENT --route=0 --plan="$BEST_PLAN_R5"` (or `tools/screen.sh <name> "<extra>"`).

| | m1h (best) | r4_vbus v2sh | r4_port1 v5p | r4_bcu k1 |
|---|---|---|---|---|
| power_open | allowed | allowed | allowed | allowed |
| DRC errors | **0** | 0 | 0 | 0 |
| hot loops | **7/7 tier 1, 6.28 nH** | 6.24 | 6.24 | 6.27 |
| blocked edges | **4 of 364** (m1: 4 of 365) | 5 of 369 | 5 of 365 | 5 of 368 |
| loss | **0.803 W** (m1 0.802) | 0.833 | 0.829 | 0.815 |
| pad_unjoined (not allowed) | C409.1, C509.1 (PPHV VAC caps) | C409.1, C509.1, C521.1 | + VBUS dead pairs | + VBUS dead pairs |
| switch-node B.Cu | 14.3 mm2, 8 vias (= k1) | 84.9 | 84.9 | 14.3 |
| B.Cu non-GND power copper | 174.2 mm2 (k1 156.5 + VBUS straps 8.4 + C521 strap 9.0) | ~430 | ~423 | 156.5 |
| PC full routes | **9 / 14 / 13 failed of 364** (same board 3x, mean 12.0) | 16 of 369 | 9 / 10 of 364 | 12 of 368 |
| local full route | 12 failed of 365, routed DRC 0 | - | (v6p: 10) | stopped |

Hot loops m1h vs k1 (nH): HL_3V3 1.329/1.329, P1 HL_5V 0.465/0.461, P1 HL_IN 0.580/0.579, P1 HL_OUT 0.627/0.628,
P2 HL_5V 0.677/0.677, P2 HL_IN 0.560/0.559, P2 HL_OUT 0.633/0.633 (all_parallel_with_esl); the 0.01 nH over the 6.27
target is P1 HL_5V (C446 0.266 -> 0.274 nH, the r4_port1 R433/R425 swap beside the 5 V buck).

## Build steps and what was found

### 1. Planner M (tools/plan_copper_m.py)
`class PlannerM(PlannerB, PlannerV, PlannerQ)`: the three r4 planners imported unchanged, combined by cooperative
multiple inheritance (MRO M -> B -> V -> Q -> P -> A -> stock). Every overridden method in B, V and Q calls super()
exactly once, so each method runs all three. Decided per method:
- `__init__` (Q only): P's pin/conn escapes, then Q's gate vias.  `pin_escapes`, `return_step` (Q only: --gndtie).
- `hot_loops_step`, `net_step`, `detour`, `mirror_step`, `taps`, `run` (B only).
- `grow_step` (all three), order: B tags no-grow zones -> P stock grow with --nogrow_dead (dead VBUS pair stays an ungrown
  pad) + planner A's taps (B's --tap_max) -> Q's --padjoin stubs -> V's --padpair via + B.Cu link (after the grow, so
  never grown, and it sees Q's stubs as obstacles) -> B untags -> M's own rules.
- One main() parses VOPT, pp.OPT (P + QOPT), OPTB, MOPT and planner A's options; it warns on unknown options.

### 2. Regression (tools/regress.sh, runs/regress/)
Planner M + split_spec + BUS4 + BUS4B (= the scorecard's post-processing, `tools/plan_only.sh`) with one worker's options
on that worker's bare.json: **IDENTICAL** (tools/spec_diff.py) to
`r4_vbus/runs/v2sh/spec.json` (94 zones / 382 tracks / 383 vias), `r4_port1/runs/v5p/hot/spec.json` (94/396/383) and
`r4_bcu/runs/k1/spec.json` (78/344/281). `tools/spec_diff.py` is a copy of r4_general's with invalid zone rings repaired
by buffer(0) for the area check (the k1 spec crashed shapely's symmetric_difference with a TopologyException).

### 3. Merged board screens (all --route=0, outdirs runs/<name>)
| run | options beyond $BEST_PLAN | power_open | DRC | blocked | GHOSTFAIL vs r4 runs | loss | pad_unjoined (not allowed) | hot |
|---|---|---|---|---|---|---|---|---|
| m0 | V + Q + B options | allowed | **4** | 4 of 363 | the common 4 (SCL J302.6, CHG_INH R535, GAUGE_FUSE U101.25, P2 DRV9_OFF); P1 I2CC_SDA R402->U403.2 no longer blocked | 0.800 | C409.1, C509.1, C521.1 | - |
| m1 | m0 + `--gatevia_chk=1 --capjoin=1` | allowed | **0** | 4 of 365 | same 4 | 0.802 | C409.1, C509.1 | - |
| **m1h** | same as m1, hot loops on | allowed | 0 | 4 of 364 | same 4 | 0.803 | C409.1, C509.1 | **7/7, 6.28 nH** |
| m2 | m1 with Q's pinesc on U501 only and no --gndtie (ladder: Q pinesc on U401 vs B's thin PP5V) | allowed | 0 | 4 of 365 | same 4 | 0.801 | C409.1, C509.1 | - |

(m1 and m1h have identical spec.json; their cu.kicad_pcb files differ in fill bytes, which moves the edge total by 1 and
the loss by 0.001 W.)

Interaction found on m0 (the only one): **Q's --gatevia draws the LG2 gate-escape via of r4_bcu's rot-90 Q402/Q502 at
(116.885, 92.08) / (93.859, 92.087), 0.11 mm from the bottom-side AC bulk cap C421/C521 pad 1** (4 DRC errors: HighCurrent
clearance + hole clearance). Q's gate_vias trusts planner A's reserved site, which never checked the other outer layer.
Rule `--gatevia_chk=1`: each gate via is checked on exact shapes against other nets' pads on both outer layers (copper
clearance and 0.2 mm via-hole-to-pad) and other vias; it is slid outward along the escape (0.05 mm steps, up to 0.8 mm),
else dropped. Both LG2 vias were dropped (no legal spot outward); LG2 is left to the router as in k1, where it never
failed. HG1/HG2 gate vias (Q401.1, Q402.1, Q501.1, Q502.1) and Q402.8's port-2 twin keep Q's behaviour.

### 4. Remaining pad joins (`--capjoin=1`)
pad_join_check on m0: C521.1, C409.1, C509.1 still off their main pieces (r4_bcu's stub/mirror options did not change
them). New rule: a shunt terminal pad (cap) off its power net's main piece (V's piece analysis) is joined by (0) a link on
another outer layer from a via already on its island, (1) a same-layer link (straight, L, then a grid path that keeps
escape room, <= --capjoin_len 16 mm and <= 1.5 x straight + 3 mm), (2) new vias at the pad + a link on the other layer.
Failed tries are rolled back fully (tracks, vias, rasters, reserved strips).
- **C521.1 (port-2 68 uF AC bulk, B.Cu): joined** by a 0.8 mm B.Cu strap, 12.6 mm, along y 92.77 from C521's island to the
  C556 bulk-cap pad (which holds AC_SNS_N main-piece vias). Why port 2 differs from port 1: port 1's F.Cu AC_SNS_N tree runs
  over the top of the SW2 pour to C421's stub via (118.55, 90.775); at port 2 the same corridor is closed by the moved
  R554 and the small parts north of Q502 (F.Cu path exists only clearance-only, ~23 mm, through escape room: rejected).
  Blocked edges unchanged (4), loss +0.002 W, edge total +2 (C521's island is now copper).
- **C409.1 / C509.1 (PPHV, 1 uF VAC caps at the charger): not joined.** The PPHV main piece (R424/C449/U401 at the PD chip)
  is 30-31 mm away; no planned path exists that keeps escape room (grid search, 0.25-0.3 mm). They are decoupling caps of
  the charger's VAC sense pins (mA), finished by the router; a 30 mm planned track through port 1's congested column would
  cost routing. Left as a known pad_join finding (not allow-listed).

### 5. Ladder
On the screens there was no interaction cost besides the gate via (m0 -> m1): blocked 4 vs 5 on every r4 board, loss
lower than each r4 board. The one named interaction that could only show in routing (Q's pinesc on U401 against B's
thin PP5V corridor) is m2 (pinesc U501 only, no gndtie), queued twice on the PC: 13 and 15 failed (mean 14.0) against
m1's 9 / 14 / 13 (mean 12.0), and CC1 U401.28 -> U405.12 fails on both m2 routes but on no m1 route. So Q's pinesc on
U401 + gndtie still pays on the merged board; m1 stays the delivered variant. No other option group showed a cost.

## Full routes

PC (Logan's PC, split copper, queued from runs/m1 and runs/m2 cu.kicad_pcb):
| name | board | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|
| r5_merge-m1 | m1 | 355 | **9** | 364 | 84.5 | done |
| r5_merge-m1-rep | m1 (same sha 6a7dde2b) | 350 | 14 | 364 | 98.8 | done |
| r5_merge-m1-rep2 | m1 (same sha) | 351 | 13 | 364 | 95.7 | done |
| r5_merge-m2 | m2 (sha 92334c1c) | 351 | 13 | 364 | 70.4 | done |
| r5_merge-m2-rep | m2 (same sha) | 349 | 15 | 364 | 115.9 | done |
| (ref) r4_port1-v5p / -rep | v5p | 355 / 354 | 9 / 10 | 364 | 112.5 / 88.2 | done |
| (ref) r4_bcu-k1 | k1 | 356 | 12 | 368 | 88.8 | done |

Local full route of m1 (`tools/route_local_r5.sh runs/m1 150`, started 02:48 while the PC routes ran, finished in
~74 min, not timed out): **353 of 365 routed, 12 failed**, routed DRC errors 0, routed_power_open 3V3@L201 only,
routed loss 1.091 W (v6p local 1.165, sc_Z local 1.127).

Failed edges by region:
| region | m1 PC (9) | m1-rep PC (14) | m1 local (12) |
|---|---|---|---|
| P1 PD cluster (U401/U402/R404/R441) | I2CC_SDA U402.5->U401.16, I2CC_SCL U402.6->U401.17, CHG_INT R404->U401.18 | I2CC_SDA U402.5->U401.16, P1_LDO_3V3 R441->U402.8, P1_LDO_3V3 R404->R441 | CHG_INT R404->U401.18, P1_LDO_3V3 R441->U402.8, P1_LDO_3V3 R404->R441 |
| P1 long charger runs | CHG_INT U403.3->R404 | I2CC_SDA R402->U403.2, CHG_INT U403.3->R404 | I2CC_SDA R402->U403.2, I2CC_SCL R403->U403.1, CHG_INT U403.3->R404 |
| P1 stage (U403 north pins) | HIDRV1 U403.27->R444 | BTST1 U403.26->C412, BTST1 D404->U403.26, REGN C410->U403.24, REGN R415->U403.24 | HIDRV1, LODRV2 U403.21->R447 |
| P2 | LODRV1 U503.25->R545 | HIDRV1 U503.27->R544, I2CC_SDA U502.5->U501.16 | LODRV1 U503.25->R545 |
| gauge / MCU / other | SMBC U101.19->R115, SCL J302.6->U301.9, CELL_P C110->R118 | SMBC, SWDIO J301.2->U301.20, SCL J302.6 | SCL J302.6, IRQ_N U401.10->U501.10, CELL3 J111->R103 |

Against r4_port1-v5p (9: P1 LODRV2, HIDRV1, CHG_INT R404->U401.18, BTST1 D404; P2 HIDRV1, I2CC_SDA U502.5; VC2, SMBC, SCL)
and r4_bcu-k1 (12: BTST1 x4, CC1, CHG_INT, HG1, I2CC_SCL, I2CC_SDA, PP5V R433, SCL, CELL3): no CC1, PP5V/R433 or HG1
failures on any route of m1 (k1's port-1 fails that v5p fixed stay fixed); no VBUS/CC/SBU/connector-area fail (the V strap
costs nothing); BTST1 gone on m1 PC and local, back on the rep. Persistent: SCL J302.6 (3/3, needs CELL_P re-planned),
CHG_INT U403.3->R404 (3/3) and the U401.16-18 / R441 cluster (3/3), all congestion in port 1's column (r4_port1 1c-1e).
The identical board gave 9, 14 and 13 failed on the PC: a single route has a spread of about +-3 edges, so the goal
"below 9 failed" is **not met**: best single route 9, mean of three 12.0 (v5p had 9 / 10, k1 12 on one route).
m1-rep2 (13): P1 LODRV1 U403.25->R445, I2CC_SCL U402.6->U401.17, REGN x3 (C410->U403.24, R454->C410, D410->C410),
P1_LDO_3V3 x2 (R441->U402.8, R404->R441), I2CC_SDA R402->U403.2, CHG_INT U403.3->R404; P2 LODRV1; SMBD U101.18->R116,
SCL J302.6, CELL3. REGN at C410 (D410 is one of r4_bcu's re-placed parts) fails on 2 of 3 m1 routes: worth a look next.
m2 (13): P1 HIDRV1, I2CC_SDA U402.5, CHG_INT x2, P1_LDO_3V3 R441, CC1, I2CC_SCL long; P2 LODRV1, REGN x2, ACOV R510;
SMBD, SCL. m2-rep (15): P1 LODRV2, I2CC_SDA x2, CHG_INT x2, REGN x2, P1_LDO_3V3, CC1, I2CC_SCL long; P2 BTST1 x2, REGN x2; SCL.

### Routed-board power check (local route, runs/m1)
- dc_score on routed.kicad_pcb: power_open 3V3@L201 only (allowed), routed loss 1.091 W, routed DRC errors 0.
- pad_join_check on routed.kicad_pcb (routed_pad_unjoined): PPHV C409.1, C509.1 (the router did not finish them either),
  and **3V3 C207.1, C403.1, C503.1**. KiCad lists 11 3V3 unconnected items on the routed board (zone-zone and track-zone).
  dc_score cannot see it (it solves only J301 -> L201; the caps are shunt terminals): before routing L201's island was the
  whole In3 3V3 bus (x 78.7-118.6); after routing it is x 84-95, y 124-130. **The router cuts the In3 3V3 bus pour**
  (3V3 is a soft net in router.py, In3 is its horizontal routing layer). `strapfix/tools/cutmap.py` (img/m1_cut_3V3_In3*):
  3V3 In3 1436 mm2 in 1 piece before routing -> 890 mm2 in 7 pieces after (biggest 818 mm2; islands at 100.6,77.7
  26 mm2 / 88.8,126.7 25 mm2 / 115.0,114.8 17 mm2 ...); main cutters SCL, SDA, P2 REGN, DRV9_OFF, TS4. (PACK_P In2 1 -> 5
  pieces too, but its In4 copy stays 1 piece, as designed.) This is the 3V3 version of the PACK_P cut that
  BUS4 fixed on In4; it was invisible in earlier rounds because no routed-board per-pad check was run. Needs a fix
  before fab: a second copy of the 3V3 bus on a non-routing layer (as BUS4 does for PACK_P), or 3V3 out of --softnets.
- VBUS dead pair: no VBUS pad in routed_pad_unjoined (the strap survives routing).

## Renders (F.png, B.png = m1h; img/m1_*.png 30 px/mm zooms)
- F.Cu: both PD chips directly under their USB-C connectors with the protector between, 5 V buck beside; the port-1 PD
  cluster is the port-2 arrangement (EEPROM U402 south of pins 16/17, pull-ups west, R404/R441 beside pin 18/19), R433 on
  the PP5V pour edge. Stages compact under the inductors: Q401 under L401/L501, Q402/Q502 rot 90 hung beside the inductor
  pad 2 with C438/C538 on the cap edge and the BAT drop to R427/R527; port 2 is a copy of port 1. Nothing stranded.
- B.Cu: same as r4_bcu/B.png (two 0.3 mm SW1 taps and two SW2 bootstrap taps per side, thin PP5V corridors, cell path
  mirror, PACK_P pads) plus the two 0.8 mm VBUS straps under the connector pad rows (r4_vbus) and the new 0.8 mm
  AC_SNS_N strap C521 -> C556 on port 2 (only port 2 needs it). No SW2 pour, no AC_SNS_N / BAT_SNS_P corridors.

## Files
- `placement.json`, `overrides/50_r4_port1.json`, `overrides/60_r4_bcu.json`; `score.json`, `F.png`, `B.png` (m1h).
- `best_plan_opts.txt`, `tools/best_env_r5.sh`.
- `tools/plan_copper_m.py` (planner M), `tools/score_board_r5.sh` (scorecard), `tools/screen.sh`, `tools/plan_only.sh`,
  `tools/regress.sh`, `tools/spec_diff.py`, `tools/route_local_r5.sh` (route_local + routed pad_join_check).
- `runs/`: regress, build, m0, m1 (local route, routed renders), m1h, m2 (board files over 5 MB deleted).
