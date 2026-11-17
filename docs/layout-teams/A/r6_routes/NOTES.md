# Team A round 6: r6_routes (close the last failed connections)

Base: stack S (`best_placement.json`, unchanged: no part was moved in this round), copper recipe planner M
(`r5_merge/tools/best_env_r5.sh`), split-zone scorecard. All fixes are copper escape rules applied to the planned
spec after `split_spec.py`; the PC router (stock `tools/score/router.py`, stock options) treats them as fixed copper.

## Tools (r6_routes/tools)
- `specfix.py spec.json fix1.json[,fix2.json]`: zone cuts (rect / circle / segment, per layer and net regex) plus fixed
  tracks and vias added to a planned spec.
- `score_board_r6.sh`: copy of `r5_merge/tools/score_board_r5.sh` + env `SPECFIX=<fix files>` (run after split and straps).
- `quick.sh <base outdir> <new outdir> <fixes> [--ghost] [--only=RE]`: copper-only screen on a base outdir's spec
  (write copper, DRC, DC, pad join, optional blocked-edge screen), 30 s without --ghost.
- `zoom.py`: 4-layer zoom render (F, In2, In3, B) of a window with pad labels and a net legend.
- `copy_p2.py`: copies the router's port-2 copper of chosen nets in a window to port 1 (+dx, nets renamed) as a fix file.

## What blocked each failed edge (base S, local route reproduced 357/7, identical to the lead's)
- SCL J302.6 -> U301.9 (blocked on the ghost screen too): J302 is the TC2030 pad grid; pad 6 is boxed by pad 4,
  pad 5, the TC2030 hole and the F.Cu CELL_P pour 0.4 mm above it. No room for the router's via.
  Fix `fixes/scl.json`: fixed 0.94 mm F.Cu stub north to a via at 109.22,130.20 (0.82 mm from pad 6, 1.39 mm from the
  hole); KiCad's fill clears CELL_P F/B and GND around it.
- SMBC U101.19 -> R115.1: the F.Cu FET_MID pour sits 0.6 mm from the gauge's east pin row (pins 17-24), too close
  for a via; SMBD took the only escape. Fix `fixes/smbc.json`: FET_MID F.Cu pulled back to x 100.45 beside pins 17-22
  (rect 99.3..100.45 x 119.75..122.65, no FET current there) + fixed escape track and via at 99.85,121.60.
- Port-1 PD cluster (U402.5 -> U401.16, R441.1 -> U402.8, R404.1 -> R441.1, R402.2 -> U402.5): port 1 is a +21.0 mm
  copy of port 2, but port 1's AC_SNS_N F.Cu pour reaches up the east side of R441/R404 (port 2's lies further south),
  so the via column port 2 uses east of R541/R504 does not exist on port 1. Fix A `fixes/p1lane.json`: AC_SNS_N F.Cu
  cut back from x 107.9-109.5, y 83.2-87.6 (+10 mW). Fix B `fixes/p2copy_b.json`: the router's own port-2 solution
  for I2CC_SDA/SCL, LDO_3V3, CHG_INT, SBU_FLT inside the cluster (75 tracks, 13 vias) copied +21 mm to port 1 as fixed
  copper (one inner-layer LDO run dropped: it hit a port-1-only GND via at 101.3,82.3).
- Long port-1 I2CC_SDA/SCL and CHG_INT runs to U403.1/2/3 ("no way even with every other route gone"): U403's pins
  1-3 are boxed on the port-1 side by the PACK_P via field and the main SDA/SCL/EN_5V1 traffic to the MCU.
  Fix `fixes/u403_a.json`: port 2's U503 pin escapes (SDA via under pin 2, SCL via 1.2 mm south, CHG_INT east stub)
  copied +23.026 mm (U403 - U503) as fixed copper.
- CELL3 J111 -> R103 (new failure once the port-1 fixes moved other routes: A* hit its 12 M node cap on this 50 mm
  HighCurrent-class edge): `fixes/cell3.json` lays the router's own S0 route of CELL3 first as fixed copper.

- R433.1 -> port-1 PP5V pour (new failure with CELL3 laid first: CELL3's In2 jog at y 83.37 took the via spot,
  "goals 0"): `fixes/r433.json` lays S0's own R433 join (F.Cu stub, via 112.075,82.97, In2 north, via 112.075,81.27).

Best = **cp5** = stack S + `fixes/CP5_LIST.txt` (scl, p1lane, smbc, p2copy_b, u403_a, cell3, r433), rebuilt and scored
by `tools/score_r6_best.sh <outdir>` (verified: spec identical to runs/sc_cp5).
Scorecard outdir: `runs/sc_cp5` (score_board_r6.sh = split-zone scorecard, --route=0, hot loops on); local full route
in `runs/L_sccp5` (copy of sc_cp5 + route_local_r5.sh, routed.kicad_pcb kept, 7 MB).

## Results (real numbers; PC = Logan's PC route server, stock router; local = route_local_r5.sh, 150 min cap)
Edge totals fall from 364 because pre-laid copper (the copied port-2 cluster, U403 escapes, CELL3, R433 join) is
already connected when the router starts; a pre-laid connection is not counted as routed by the router.

| board | what | blocked | PC route | local route | loss W (pre-route) |
|---|---|---|---|---|---|
| S0 = stack S (base) | lead_r5/sc_S copy | 4 of 364 | lead5-S 356/8 (x2) | 357/7, 37 min (this round, identical to the lead's) | 0.801 |
| scl1 (quick) | + SCL escape | - | 352/12, 126.8 min | - | 0.807 |
| lane1 (quick) | + SCL + AC_SNS_N cut | - | 360/4, 83.9 min (P1 I2CC_SCL, SMBC, P1 CHG_INT, CELL3) | - | 0.817 |
| smbc1 (quick) | + SMBC escape | - | 360/4, 53.2 min (P1 I2CC_SCL x2, I2CC_SDA, CHG_INT: cluster + U403 side) | - | 0.817 |
| cp2 (quick) | + port-2 cluster copy | 3 of 353 | 351/2, 51.8 min (P1 I2CC_SCL long to U403.1, CELL3) | 347/6 (90 min cap reached in phase 3) | 0.818 |
| cp3 (quick) | + U403 pin escapes | - | 352/1, 77.1 min (CELL3 only: node cap); repeat 352/1, 134.6 min (U503-ACOV only) | - | 0.820 |
| cp4 (quick) / sc_cp4 | + CELL3 laid first | 4 of 351 | 347/4 (CELL_1N, TS3, IRQ_N, P1 PP5V) / 349/2 (TS1, P1 PP5V) | sc_cp4: 348/3 (VC3, VC1, P1 PP5V) | 0.824 |
| cp4n (quick) | cp4 without AC_SNS_N cut | - | 350/1 (P1 PP5V) | - | 0.814 |
| **sc_cp5** | + R433 join | **3 of 350** | **r6r-sccp5 350/0, 49.0 min**; repeat r6r-sccp5-rep 349/1, 52.7 min (TS1 TH101->U101.10); same copper from the quick path (q_cp5, r6r-cp5) 350/0, 75.4 min | **350/0, about 31 min, not timed out** | **0.824** |
| cp5n (quick) | cp5 without the AC_SNS_N cut | - | r6r-cp5n 350/0, 42.5 min | - | 0.814 |
| cp6 (quick) | cp5 + S0 routes of TS1, VC1, VC3 laid first | - | 343/0, 34.6 min | - | 0.828 |

sc_cp5 scorecard (--route=0, hot on): loss 0.824 W, power_open 3V3@L201 + GND@J301/J302 (allowed), DRC 0,
hot loops 7 of 7 pass at 6.27 nH (unchanged), blocked 3 of 350 (CHG_INH R535->J302.2, GAUGE_FUSE U101.25->R126,
P2 DRV9_OFF: all three route in the full route), pad_unjoined C409.1 / C509.1 (as before).
Local routed board (runs/L_sccp5): routed_power_open 3V3@L201 only, routed DRC errors 0, routed loss 1.152 W
(S0 routed 1.070 W: GND +46 mW, PACK_P +19 mW, the soft pours are cut by more routes), routed_pad_unjoined
3V3 C207.1/C403.1/C503.1 + PACK_P C213.1 + PPHV C409.1/C509.1 (the same list as S0's routed board: not new).
Routed-board DRC unconnected 17 (S0 24): 3V3 x8, PACK_P, PPHV x2, P2 PP5V, VBUS x2, NRST, BTST1 x2, all present on
S0's routed board too (pour-join items, not signal opens).

## Caveats
- The router is not deterministic between runs (rip-up is wall-clock limited): cp3 and cp3-rep are the same file and
  gave different failures; local and PC results differ for the same board. A repeat PC route of sc_cp5 was queued as
  r6r-sccp5-rep: 349/1 (TS1). So cp5 copper routed 0-failed in 2 of 3 PC runs and the 1 local run.
- Several fixes are the router's own earlier output frozen as fixed copper (port-2 cluster copy, U403 escapes, CELL3,
  R433). They pass KiCad DRC on the placed board and hot loops are unchanged, but they are copied routes, not new
  placement. The SCL and SMBC escapes and the two pour pull-backs are the only hand-designed copper.
- AC_SNS_N pull-back (p1lane) costs about 10 mW pre-route; cp4n shows the cluster copy routes without it (only the
  R433 edge failed there, which r433.json fixes), so a cp5 without p1lane is worth one more PC route if loss matters.
- No placement change; F.png/B.png of sc_cp5 checked: power parts where stack S has them.

## Next steps (not done)
- Most robust candidate to try next: cp5n (no AC_SNS_N cut, 0.814 W, PC 350/0 once) + `fixes/gauge3.json` (S0's TS1,
  VC1, VC3 routes laid first; on cp5 this gave PC 343/0 once). Needs a hot-loop scorecard (score_board_r6.sh with that
  SPECFIX list) and 2-3 PC routes to confirm, since single runs vary.
- Before fab: the 3V3 / PACK_P routed_pad_unjoined items from round 5 are still open (unchanged by this round).
