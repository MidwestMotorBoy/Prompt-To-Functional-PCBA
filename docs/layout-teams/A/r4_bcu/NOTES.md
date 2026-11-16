# Worker `r4_bcu` (team A, round 4): switch-node and detour copper off the bottom layer

All numbers are split-zone copper from `tools/score_board_best.sh` (team A best recipe: `tools/best_env.sh` =
BUS4 PACK_P copy on In4 + BUS4B soft GND fill on B.Cu + `$BEST_PLAN`), run through `tools/screen.sh` with
PLANNER = `tools/plan_copper_b.py` (this folder). "allowed" = power_open is 3V3@L201 and GND@J301/J302 only.
B.Cu areas are this task's own metrics (`tools/bcu_area.py`, lower is better): union of hard zone outlines + tracks
from the scorecard's spec.json (after split_spec and bus4); the soft GND fill is not counted.

## Result

**Best: k1** = stage move `overrides/60_r4_bcu.json` (Q402/Q502 rot 90 beside the inductor, 23 refs) + `tools/best_plan_opts.txt`
(`$BEST_PLAN --tap_max=16 --ret_band=1.6 --pw_nogrow=1 --mirror_skip_supply=1 --stub_nogrow=1 --mirror_maxa=10`), outdir `runs/k1`,
copied to `placement.json`, `score.json`, `F.png`, `B.png` here.

| | base (team best, sc_Z recipe) | **k1** |
|---|---|---|
| power_open | 3V3@L201, GND@J301/J302 | same |
| DRC errors | 0 | 0 |
| blocked edges | 5 of 369 | 5 of 368 (same 5 edges; the placement has 368 signal edges instead of 369) |
| copper loss | 0.835 W | **0.815 W** (-0.020) |
| hot loops | 7/7 tier 1, 6.24 nH | 7/7 tier 1, **6.27 nH** |
| switch-node copper B.Cu | 84.9 mm2 (28 vias) | **14.3 mm2** (-83 %), 8 vias: only the two 0.3 mm bootstrap taps per port |
| switch-node copper F.Cu | 159.3 mm2 | 151.8 mm2 |
| B.Cu non-GND power copper | 423.2 mm2 | **156.5 mm2** (-63 %; 90 mm2 of it is the cell-path mirror, not in scope) |
| PC full route | 17 failed of 369 (lead-Z) | **12 failed of 368** (88.8 min) |
| SW2 self-capacitance (coupling solver, H 0.05) | P1 17.9 pF / P2 19.6 pF | **10.2 / 10.7 pF** |

Hot-loop totals, base -> k1 (nH): HL_3V3 1.55 -> 1.53, P1 HL_5V 0.66 -> 0.66, P1 HL_IN 0.79 -> 0.78, **P1 HL_OUT 0.81 -> 0.83**,
P2 HL_5V 0.89 -> 0.88, P2 HL_IN 0.77 -> 0.76, **P2 HL_OUT 0.77 -> 0.83**; sum 6.24 -> 6.27 (limit ~6.4). HL_OUT is 0.02/0.06 nH longer
(the HF cap now sits on the side cap edge of a rot-90 switch, with the GND return reaching vias beside C438), the rest are equal or shorter.

### B.Cu copper, before / after (mm2, per net; `tools/inv_table.py runs/base runs/v6r runs/k1 runs/p1`)

| net (B.Cu) | base | v6r | k1 | p1 |
|---|---|---|---|---|
| /Cells and Gauge/CELL_P | 13.0 | 13.0 | 13.0 | 13.0 |
| /Cells and Gauge/CELL_P_RAW | 12.2 | 12.2 | 12.2 | 12.2 |
| /Cells and Gauge/FET_MID | 51.6 | 51.6 | 51.6 | 51.6 |
| /USB Port 1/AC_SNS_N | 48.7 | 50.3 | 12.4 | 10.6 |
| /USB Port 1/BAT_SNS_P | 16.0 | 29.7 | - | - |
| /USB Port 1/PP5V | 27.8 | 27.8 | 3.3 | 3.3 |
| /USB Port 1/PPHV | 4.5 | 4.5 | - | - |
| /USB Port 1/SW1 | 3.4 | 3.6 | 3.2 | 3.2 |
| /USB Port 1/SW2 | 38.6 | 3.9 | 3.9 | 10.5 |
| /USB Port 1/VBUS | 9.1 | 9.1 | - | - |
| /USB Port 2/AC_SNS_N | 49.2 | 51.2 | 12.7 | 10.6 |
| /USB Port 2/BAT_SNS_P | 14.1 | 29.6 | - | - |
| /USB Port 2/PP5V | 27.0 | 27.0 | 2.9 | 2.9 |
| /USB Port 2/PPHV | 3.3 | 3.3 | - | - |
| /USB Port 2/SW1 | 3.4 | 3.6 | 3.3 | 3.3 |
| /USB Port 2/SW2 | 39.5 | 3.9 | 3.9 | 10.4 |
| /USB Port 2/VBUS | 2.8 | 2.8 | - | - |
| CELL_N | 13.1 | 13.1 | 13.1 | 13.1 |
| PACK_P | 45.6 | 41.1 | 21.0 | 21.0 |
| **switch-node B.Cu (SW1+SW2, both ports)** | 84.9 | 15.0 | 14.3 | 27.4 |
| **total B.Cu non-GND** | 423.2 | 381.5 | 156.5 | 165.7 |
| switch-node F.Cu | 159.3 | 151.8 | 151.8 | 159.3 |

(v6r = stage move only; k1 = stage move + copper rules; p1 = copper rules on the unchanged team placement, rejected for loss.)

## Step 1: what was on B.Cu and why (reference lead_final/sc_Z = runs/base)

Base screen re-run (runs/base): power_open allowed, DRC 0, 0.835 W, blocked 5 of 369 (same list as sc_Z).

| B.Cu copper (per port) | mm2 P1 / P2 | planner step and reason |
|---|---|---|
| SW2 pour under the inductor | 38.6 / 39.5 | `detour` of the switch-node net: Q402 sits at rot 180 under L401.2, so its SW pad's only F.Cu exit (between the gate pins, the gate edge) faces away from the inductor; the cap edge toward the inductor is closed by C438 and the HL_OUT supply/return pours that join D1 and S2 across it (topologically every F.Cu path from the SW pad to L401.2 must cross the HL_OUT loop). net_step finds no F.Cu path even with clearance only, draws vias in/at the SW pad + a 1.8 mm corridor (roles.width_mm(6 A, 2 oz)) on B.Cu + vias under L401.2, and the grow step widens it by 1.5 mm |
| SW1 tap | 3.4 / 3.4 (0.3 mm x 9.5 mm) | planner A `--taps`: bootstrap cap C412.2 (SW1) sits 7 mm from the SW1 pour; the router only searches 6 mm round an edge's DRC end points. F.Cu impossible for the same reason as SW2 (Q401's SW pad leaves only through its gate edge, upward) |
| PP5V detour blob north of the PD chip | 27.8 / 27.0 | `detour` of PP5V (1.5 A): the F.Cu tree from the buck to U401/U501 pin 34 and C407/C507 cannot cross the VBUS stem on F.Cu, so it detours on B.Cu (0.43 mm corridor) and the grow step blows it up to ~12 x 5 mm |
| VBUS / PPHV stubs | 9.1+4.5 / 2.8+3.3 | `mirror` (step 5: nets >= 3 A copied onto the other outer layer where free) |
| AC_SNS_N corridor | 48.7 / 49.2 | `mirror` of the AC_SNS_N F.Cu tree (R424 sense resistor -> stage input caps) + `via stub` of the bottom-side AC bulk caps C421/C456 (C521/C556): AC_SNS_N is NOT a sense-only net: constraints.json declares it a 5 A power net, it is the HL_IN supply (charger input after the sense resistor; the Kelvin taps are ACP_F/ACN_F). The corridor round the stage is the mirror copy of the F.Cu tree plus the way to C421.1, a bottom-side cap pad at the board edge |
| BAT_SNS_P patches | 16.0 / 14.1 | `mirror` of the BAT_SNS_P tree (5 A power net, HL_OUT supply, charger output before the BAT sense resistor R427; Kelvin taps SRP_F/SRN_F) |
| PACK_P mid-board patch(es) | 45.6 (all PACK_P B.Cu) | `mirror` + `via stub` of PACK_P (the In2 bus net) |
| cell path (CELL_P, CELL_P_RAW, FET_MID, CELL_N) | 90 | `mirror` of the 10 A cell path, not this task's area (kept) |

Inner layers: In1/In4 GND planes (In4 also the PACK_P bus copy), In2 PACK_P bus, In3 3V3 bus; no switch-node copper
on any inner layer. Switch-node copper total: F.Cu 159.3 mm2, B.Cu 84.9 mm2, 28 switch-node vias.

Coupling solver: run (copies in `coup/`, pyamg installed on the host; `PCB=<cu.kicad_pcb> TAG=<t> H=0.05 python3 coup.py 0 1 2 3`,
~70 s per group). Aggressor = SW/BTST/HIDRV/HG group at 1 V, coupling to each net in fF (`coup/log_*_h05.txt`, `coup_*_h05.json`):

| group | C_self base -> k1 (pF) | to GND | to PACK_P | to BAT_SNS_P | to AC_SNS_N | to 3V3 |
|---|---|---|---|---|---|---|
| P1 SW1 | 12.1 -> 12.0 | 10307 -> 10273 | 913 -> 906 | 1 -> 0 | 465 -> 437 | 183 -> 182 |
| P1 SW2 | 17.9 -> **10.2** | 13510 -> 8756 | **3546 -> 892** | 234 -> 148 | 195 -> 133 | 175 -> 89 |
| P2 SW1 | 12.0 -> 11.9 | 11031 -> 11033 | 92 -> 90 | 1 -> 0 | 441 -> 390 | 208 -> 209 |
| P2 SW2 | 19.6 -> **10.7** | 17385 -> 9988 | 846 -> 186 | 237 -> 135 | 7 -> 4 | **842 -> 179** |

The SW2 B.Cu pour sat over the In4 PACK_P bus copy / In3 3V3 bus; taking it off cuts SW2's self-capacitance nearly in half and
its coupling into PACK_P (P1) and 3V3 (P2) by 4-5x. Gate/Kelvin victims (LG2, SRN_F/SRP_F) stay in the 0-20 fF range (LG2 14 -> 18 fF,
the LG2 resistor now sits next to the switch).

## Step 2: SW2 on F.Cu

(a) planner rule. The stock net_step already does "F.Cu first, B.Cu only if no F.Cu path of minimum width
exists" (path, then path with clearance only, then detour). The SW2 detour exists because no such path exists
with Q402 at rot 180 (see table). A planner rule cannot fix it without cutting the HL_OUT loop or sealing LG2/HG2.
What the planner can do on this placement is not grow the detour: `--sw_nogrow=1` (screen c1, below):
SW2 B.Cu 38.6 -> 10.5 mm2 per port, loss +0.028 W, blocked unchanged.

(b) placement. The SiZ240DT's SW pad leaves on F.Cu only through its gate edge, so the gate edge must face the
inductor pad. Under the inductor that needs rot 0, which puts D1 (BAT) into the FET gap and has no F.Cu way for
BAT to reach the bulk caps and R427 without crossing GND. Beside the inductor it works: **Q402 rot 90 hung from
the RIGHT side of L401's pad 2** (courtyards abut; gate edge faces pad 2, SW pad 1 mm from it; LG2 pin top-left,
HG2 pin bottom-left; S2 (GND) on top, D1 (BAT) at the bottom, cap edge toward the board edge). Then:
- C438 (HF output cap) centred on the cap edge (offset 2.45 mm = courtyard halves, the template rule), BAT pad over
  D1, GND pad over S2, rot 90; it fits inside the x 120.96 lip.
- BAT drops straight down ~6 mm from D1 to R427 pad 1 (R427 now vertical right below Q402, its PACK_P pad next to
  J113); C431 and C434 horizontal 1210s left of the drop with their BAT pads touching it, GND pads left with vias;
  R428/R429 Kelvin filters left of R427.
- R447 (LG2) straight above the LG2 pin; R446 (HG2) next to U403's HIDRV2 pin (HG2 reaches the gate through the
  planner's gate-escape via below the HG2 pin); D405/D410 re-placed by hand under C434 / between the Kelvin filters
  (the greedy placer threw D405 to (119.4, 111.3) and R446 into the BAT drop).
- Port 2 = the same moves relative to Q501 (pure translation); R554 (port-2 REGN resistor, no stage part) moved
  1.2 mm from its old spot, which C538 now takes.
- Planner: `--tap_max=16` (the C413 bootstrap tap to the SW2 copper is now 11 mm; taps were capped at 10 mm, so it was
  left to the router, which only searches 6 mm) and `--ret_band=1.6` (return band + vias at a discrete switch's
  return-pin row: S2 now faces outward and the hull left 1 GND via at Q402 instead of 3; vias cannot sit right
  above S2 because the bottom-side cap C421's B.Cu pad is there, so the band reaches 1.5 mm past the package and
  the vias land beside C438).

(c) SW2 on In1 between GND planes was not needed (F.Cu path exists with (b)); rejected anyway: In1 is the GND
reference directly under the hot loops.

SW1 tap: Q401's SW pad has the same topology (F.Cu exit only up through its gate edge into L401.1), so C412.2 (next
to U403's SW1 pin 28) cannot reach SW1 on F.Cu; the 0.3 mm B.Cu tap stays (3.2-3.6 mm2).

## Step 3: detours and corridors

(d) AC_SNS_N / BAT_SNS_P carry the charger current (5 A power nets, the HL_IN / HL_OUT supplies); the Kelvin nets are
ACP_F/ACN_F and SRP_F/SRN_F (constraints.json kelvin). Their B.Cu copper is the planner's mirror copy (and AC_SNS_N's
stub to the bottom-side bulk cap C421/C521). `--mirror_skip_supply=1` (no mirror for hot-loop supply nets of
discrete-FET loops) removes the corridors; the F.Cu tree carries the current; no terminal opens.
(e) PP5V: `--pw_nogrow=1` keeps the B.Cu PP5V crossing of the VBUS stem a corridor (0.43 mm, ~7 mm long) instead of
a 12 x 5 mm blob: 27.8 -> 3.3 mm2 per port for +0.010 W. (portcu's --nogrow_detour cost +0.05 W because it also
froze the 6 A SW2 detour; with SW2 on F.Cu that cost is gone.)
(f) the mid-board PACK_P patch: dropped by `--mirror_maxa=10` (mirror pieces under 10 mm2) with no PACK_P loss change
(0.1348 -> 0.1335 W): the In4 bus carries it. `--stub_nogrow=1` keeps the bottom-side caps' via stubs (C421/C456)
from growing into blobs once their mirror corridor is gone.

## Variants (all DRC 0, power_open allowed; blocked list identical to base unless noted)

| outdir | placement | r4_bcu planner options (on top of $BEST_PLAN) | power_open | DRC | blocked | loss W | hot loops | SW B.Cu mm2 | B.Cu non-GND mm2 | PC route |
|---|---|---|---|---|---|---|---|---|---|---|
| runs/base | team best | - | allowed | 0 | 5/369 | 0.835 | (sc_Z) 7/7, 6.24 | 84.9 | 423.2 | ref 17 failed of 369 |
| runs/c1_swnogrow | team best | --sw_nogrow=1 | allowed | 0 | 5/369 | 0.863 | not run | 27.7 | 365.9 | - |
| runs/v3 | pl_v3 (early rot 90) | --tap_max=16 | allowed | 0 | **7/369** (+2 LODRV1) | **1.131** | not run | 15.4 | 386.5 | rejected |
| runs/v6, v6h | pl_v6 | --tap_max=16 | allowed | 0 | 5/368 | 0.857 | 7/7, 6.62 (HL_OUT 0.98/0.98) | 14.6 | 377.9 | - |
| runs/v6r | pl_v6 | --tap_max=16 --ret_band=1.6 | allowed | 0 | 5/368 | 0.789 | 7/7, 6.30 | 15.0 | 381.5 | PC 19 failed of 368 |
| runs/e1 | pl_v6 | v6r + --pw_nogrow=1 | allowed | 0 | 5/368 | 0.799 | not run (copper only off the loops) | 15.0 | 332.8 | - |
| runs/d1 | pl_v6 | v6r + --mirror_skip_supply=1 | allowed | 0 | 5/368 | 0.820 | not run | 14.3 | 325.5 | - |
| runs/d2 | pl_v6 | v6r + --mirror_minw2=1.5 | allowed | 0 | 5/368 | 0.839 | not run | 14.6 | 321.0 | rejected (CELL_P mirror dropped, +0.06 W on the cell path) |
| **runs/k1** | **pl_v6** | **--tap_max=16 --ret_band=1.6 --pw_nogrow=1 --mirror_skip_supply=1 --stub_nogrow=1 --mirror_maxa=10** | allowed | 0 | 5/368 | **0.815** | **7/7, 6.27** | **14.3** | **156.5** | **PC 12 failed of 368** |
| runs/p1 | team best | --sw_nogrow=1 --pw_nogrow=1 --mirror_skip_supply=1 --stub_nogrow=1 --mirror_maxa=10 | allowed | 0 | 5/369 | 0.903 | 7/7, 6.19 | 27.4 | 165.7 | rejected (+0.068 W > 0.05) |

GHOSTFAIL lists (`runs/*/ghost_diff.txt` vs runs/base): identical in every variant but v3 (same 5: SCL J302.6-U301.9,
CHG_INH R535-J302, GAUGE_FUSE U101.25-R126, P2 DRV9_OFF U501.37-Q509, P1 I2CC_SDA R402-U403.2).
Per-net loss k1 vs base: SW2 -0.017/-0.018, BAT_SNS_P -0.008/-0.012 (short straight BAT drop to R427), GND -0.017,
AC_SNS_N +0.015/+0.019 (mirror copy gone; F.Cu tree carries it). p1 vs base: SW2 +0.014/+0.023 (thin detour), AC_SNS_N +0.015/+0.019.
Renders read for base, c1, v3, v6, v6r, e1, d1, k1, p1 (F and B); zooms in `img/`.

## Full routes (Logan's PC)

Queued with `queue_route.sh`; fail lists from the route-results branch logs, diffed against the reference lead-Z (17 failed of 369).

| board | queued | arrived | routed | failed | minutes |
|---|---|---|---|---|---|
| reference lead-Z (team best) | - | - | 352 | **17 of 369** | - |
| r4_bcu-v6r (stage move only) | 21:02 | 23:05 | 349 | **19 of 368** | 120.2 |
| **r4_bcu-k1 (best)** | 21:40 | 23:11 | **356** | **12 of 368** | 88.8 |

- lead-Z fails (17, 92.2 min): CELL3, CELL_1N, P1_LDO_3V3 x2, P1 BTST1, P1 CC1, P1 CHG_INT x2, P1 I2CC_SCL, P1 I2CC_SDA, P1 LODRV1,
  P1 LODRV2, P1 PP5V, P1 SBU_FLT, P2 LODRV1, Net-(U101-SMBC), SCL.
- k1 fails (12): CELL3, P1 BTST1 x2, P1 CC1, P1 CHG_INT, P1 HG1, P1 I2CC_SCL, P1 I2CC_SDA, P1 PP5V, P2 BTST1 x2, SCL. No LODRV / P1_LDO_3V3 /
  SBU_FLT failures any more; BTST1 (the SW1-side bootstrap, unchanged by this task) fails on both ports, and HG1 is new.
  No SW2-side net (BTST2, HG2, HIDRV2, LG2) fails.
- v6r fails (19): CELL_1N, P1_LDO_3V3, P1 BTST2, P1 CC1, P1 CHG_INT x2, P1 FSW, P1 HIDRV1, P1 I2CC_SCL, P1 I2CC_SDA, P1 PP5V, P1 REGN,
  P1 SBU_FLT, P2 HIDRV1, P2 LODRV2, P2 REGN x2, Net-(U503-ACOV), SCL; the k1 copper rules (no PP5V blob, no
  mirror corridors) free the space round U403 that v6r still filled.
- Local fallback: at 22:18 (75 min after the v6r queueing with nothing back) one local `tools/route_local.sh runs/k1 150` was started.
  The PC results arrived at 23:05/23:11, so I stopped the local router container by hand at 54 min (it was in phase 2 at
  351 routed, 14 failing; log `runs/k1/route_local_stopped.log`). The route_local summary line said "TIMED OUT at 150 min"
  because no routed board was written; that is wrong, and score.json carries the PC result instead.

## Rejected / not done

- **Q402 rot 0 under the inductor** (gate edge up toward L401.2): D1 (BAT) lands in the FET gap and BAT has no F.Cu way to the
  bulk caps/R427 without crossing GND. Not built past a sketch.
- **v3** (first rot-90 placement): BAT path ran round C434 (BAT_SNS_P 6 mOhm, loss 1.131 W) and LODRV1 blocked twice.
- **v4/v5**: greedy re-placer scattered D405 (to 119.4, 111.3) and R446 into the BAT drop; fixed by explicit poses + keep_free box (v6).
- **SW2 on In1 between the GND planes** (step 2c): not needed once F.Cu works; In1 is the GND reference under the hot loops.
- **SW1 on F.Cu**: impossible with Q401's SW pad exiting only through its gate edge into L401.1 while C412.2 sits by U403 pin 28;
  the 0.3 mm B.Cu bootstrap tap (3.2-3.6 mm2) stays. Moving Q401 the same way would push HL_IN past the HL_5V block (not tried).
- **d2 `--mirror_minw2=1.5`**: also dropped the CELL_P mirror (+0.06 W); `--mirror_maxa=10` + `--mirror_skip_supply=1` does the job without it.
- **p1 (copper rules only, no stage move)**: SW2 B.Cu only 84.9 -> 27.4 mm2 (thin detour corridor + 10 vias per port) for +0.068 W: over the
  0.05 W allowance; the stage move is what takes SW2 off B.Cu.
- **portcu `--nogrow_detour`**: froze the 6 A SW2 detour too (+0.05 W); replaced by the separate `--sw_nogrow` / `--pw_nogrow`.
- Concerns kept on k1 (not scored): the HG2 gate loop is longer (R446 at U403, HG2 reaches the gate through the gate-escape via) and the
  SW2 bootstrap tap is ~11 mm of 0.3 mm on B.Cu; HL_OUT +0.02/+0.06 nH.

## Files

- `placement.json`, `score.json` (screen + PC route result), `F.png`, `B.png`: k1.
- `overrides/60_r4_bcu.json`: 23 refs (groundup format, with `_rules`); applying it to final best_placement_gu with onecmd/apply_overrides.py
  reproduces `placement.json` exactly.
- `stage/stage_template.json` (team template + r4_bcu poses, keep box, note), `stage/apply_stage.py`.
- `place/mk_place.py` + `place/moves_v6.json` (final moves, anchor Q401, port 2 by translation), placelib copies, `best_gu.json`.
- `tools/plan_copper_b.py` (PlannerB on portcu PlannerP; options stub_nogrow, ret_band, ret_vias, tap_max, sw_nogrow, sw_w, sw_vias,
  pw_nogrow, mirror_minw2, mirror_maxa, mirror_skip_supply; all default off), `tools/best_plan_opts.txt`.
- `tools/bcu_area.py` (metric), `tools/inv_table.py`, `tools/screen.sh` (score_board_best.sh + metric + ghost diff + log line),
  `tools/poll.sh`, `tools/run_base.sh`, `tools/batch1.sh`.
- `coup/` coupling solver copies + results; `img/` zoom renders; `runs/log.txt` one line per screen.
- Deleted board copies: cu.kicad_pcb of runs/base, c1_swnogrow, v3, v6, v6h, d2.

## Skill notes (for a cheaper model)

1. Measure first: `tools/bcu_area.py <outdir> --nets` lists every off-F.Cu net piece with its zone kinds (detour / mirror /
   via stub). The kind says which planner step made it, and that tells you which knob removes it.
2. A `detour` on a switch node means net_step found NO F.Cu path. Do not fight it with planner options: check the switch package's
   F.Cu exit. For SiZ240-type dual FETs the SW pad leaves only through the gate edge (the cap edge is closed by the HF cap joining
   D1 and S2), so the gate edge must face the inductor pad. Rotate/hang the switch beside the inductor pad, not under it.
3. Move parts with an explicit pose list relative to the anchor switch (`place/mk_place.py moves.json out --render`) and a
   keep_free box over the new power path; the greedy re-placer otherwise drops parts into it. Look at p1.png/p2.png before scoring.
4. After a rotation, check the return: if the switch's return pins face a bottom-side part's pad, no via fits there, and HL_OUT
   gets long (v6h 0.98 nH). `--ret_band=1.6` adds a GND band past the package so vias land beside it (back to 0.83).
5. Taps further than 10 mm are left to the router (6 mm search) and become blocked edges: raise `--tap_max`.
6. Mirror copies of hot-loop supply nets (AC_SNS_N/BAT_SNS_P are 5 A supplies, not Kelvin nets; check constraints.json kelvin)
   are not needed when the F.Cu tree is short: `--mirror_skip_supply=1`. Small isolated mirror pieces: `--mirror_maxa=10`.
   Do not use a width-based mirror filter (`--mirror_minw2`); it drops the cell-path mirror and costs 0.06 W.
7. Grown detours of low-current nets (PP5V 1.5 A) become 12x5 mm blobs: `--pw_nogrow=1` (+0.01 W). `--stub_nogrow=1` once mirrors are gone.
8. Screen with `--no-hot` first (6 min), then hot loops only for the finalists (15 min); one job at a time. Diff GHOSTFAIL lists, not counts.
9. Traps: bcu_area polygons need `.buffer(0)`; never round positions in an override diff (fixed parts show up as moved);
   foreground sleep is blocked, use until-loops; the PC route queue can be >75 min behind, so start route_local.sh then.
