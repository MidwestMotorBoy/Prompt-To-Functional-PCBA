# Package sides: two-sided placement (cplace/cside.py + flip in cplace/c_apply.py)

## Files
| File | What |
|---|---|
| `../cplace/cside.py` | hook module (`HOOKS=...,cside`): side rule, bottom cost, bottom legality. Knobs in its docstring |
| `../cplace/c_apply.py` | the flip (tagged `# [sides]`), used by `cscore.sh` for any placement with a 4th element |
| `flip_test.sh` (+ `flip_test_gen.py`, `flip_check.py`) | proof that the flip is exact: 32 parts x 4 turns, checked in the saved board |
| `overlaps_side.py` | side-aware copy of `tools/floorplan/overlaps.py` (same output as the original on one-sided placements) |
| `deny_from_ghost.py` | bottom parts the ghost router could not reach (GHOSTFAIL with a B.Cu pad) -> `SIDE_DENY` list |
| `queue.sh` | screens one after another (waits for load < 3; check yourself that no other screen of yours is running) |
| `cu_prior_s4.json` | power copper (hard F.Cu/B.Cu zones, not GND) the planner drew for HOOKS=cpower SEED=4; input for `SIDE_CU` |
| `best_placement_s4_vr.json` (+ `.score.json`) | lowest blocked count of any cside run (56 of 452), see table; NOT better than one-sided in a fair comparison |

## The flip (c_apply.py)
For an entry `[x, y, a, "B"]` on a part the template has on F (or "F" on a B part): want = (x, y) + rotv(-lx, ly, q)
from the template-local pad offsets; `Flip(origin, FLIP_DIRECTION_LEFT_RIGHT)` (mirror in x about the origin: pads,
courtyard, fab, silk, fields go to the B layers, nets kept), `SetPosition(x, y)`, then the quarter turn. The turn is
found, not assumed: the first candidate tried, orientation - 90*q (the same sign as on the top), satisfied the pad
check for all 128 cases of `flip_test.sh` (32 parts with template rotation 0/90/180/-90 x q 0..3, 2-pad passives, SOT-23,
diodes, 21-pad Q102); worst pad error 0.00000 mm; the script stops on any pad off by > 0.01 mm, on a net change or on
a part that carries a moved keep-out. `flip_check.py` re-checks the SAVED board (layer, pad positions from the dump,
SMD copper on B only, no item on an F layer, pad-net list of the whole board unchanged).

## Side rule (veto point for the board owner)
Only chip R/C 0201/0402/0603 (as tall as what may sit under the cup; the cup model is not in this repo), not locked by
cpower, not a hot-loop/draw/Kelvin part, no through pads, and no pad on: a power net >= 1 A, a switching net, a
sensitive net (FB/TS), a Kelvin or current-sense net (max_v <= 0.2 V, SRP/SRN/ACP/ACN), RF match (ANT_IN/RFIO), gate
drive or bootstrap (HIDRV/LODRV/HG/LG/BTST/BST). 98 of 247 parts qualify. Every part moved is a hand-soldered part
(JLC assembly is top-only here): the count is printed by post_place ("parts moved to the other side: N").

## Cost and legality on B
`SIDE_B_MM` 1.0 + `SIDE_VIA_MM` 1.0 per signal pad + `SIDE_GVIA_MM` 0.4 per GND pad + `SIDE_FREE_MM` 6.0 x free
fraction of F.Cu within `SIDE_RING` 2.5 mm (bottom only where the top is crowded). `wiring()`/`near_cost()` are
side-blind (pad-to-pad distance), so the via is charged here. Illegal on B: within `SIDE_PWR_KEEP` 1.0 mm of a pad of
a power (>= 1 A) or switching net of any placed part (planner via arrays/detours). cplace.py itself already keeps B
bodies out of B keep-outs, off the through boxes of top through-hole parts (and the reverse) and apart from each other.

## Traps
- Without cpower (`HOOKS=cside` alone), freeing top room re-shuffles the whole fill: on SEED=2 the blocked count fell
  from 98 to 68-75, but Q502 turned 180 degrees and Port 2 SW2 opened, or the gauge cluster moved into the CELL_P
  path and CELL_P/CELL_P_RAW opened. These are the base placer's power chaos, not bottom parts; judge cside with cpower.
- The ghost router fails some bottom parts every time: U405/U505 VBIAS caps (C451/C551), U102 cell filter caps
  (C112/C113), U403 ACUV/ACOV divider (R410), CC caps. A via next to a fine-pitch pin in a crowded corner is not
  free. Feed them back with `SIDE_DENY=$(python3 deny_from_ghost.py <ghost.log>...)`.
- `overlaps.py` from tools/ is not side-aware (it puts a flipped part's courtyard on its template side); use
  `overlaps_side.py`.
- `queue.sh`'s load gate is not a lock: never start a second queue while one of yours is still running.

## Via sites (added in round 1, second session)
Bottom parts kept failing in the ghost router at fine-pitch pins (VBIAS caps C451/C551, U102 cell caps, R410, CC caps):
a via next to a crowded pin is not free. Knobs (all off by default, recommended set in the cside.py docstring):
`SIDE_VS_MM=1 SIDE_GVS_MM=0.5 SIDE_VS_PWR=1.0 SIDE_VS_HARD=1 SIDE_VRES=1 [SIDE_CU=sides/cu_prior_s4.json]`.
A via site is a free 0.75 mm square on both sides (bodies, cpower reservations, 1 mm round power pads, optional prior
power copper); cost = detour B pad -> site -> top pin; no site within 3 mm of the pin = illegal; the chosen site of every
bottom pad is reserved while the placer runs. `SIDE_POST=N` = one-sided fill, then flip up to N crowded parts in place.

## Measured (screen `cscore.sh <out> <p.json> --route=0 --no-hot`; outdirs under /home/claude/work/C/sides/)
cpower = `HOOKS=cpower`; all runs 0 DRC errors unless noted. "on B" = parts moved to B.Cu (= hand-soldered parts).

| Seed | Run (outdir) | cside setting | on B | Blocked | Loss W | power_open beyond allowed |
|---|---|---|---|---|---|---|
| 3 | s3_cpower | (reference, one-sided) | 0 | 61 of 452 | 1.082 | CELL_P, CELL_P_RAW, P1 PP5V+PPHV, P2 PP5V+PPHV |
| 3 | s3_cpower_cside | defaults (fill) | 30 | 64 of 454 | 2.241 | CELL_P, P1/P2 PP5V+PPHV |
| 3 | s3_cpower_cside_late | SIDE_LATE=1 | 23 | 67 of 457 | 1.080 | CELL_P, CELL_P_RAW, P1 PP5V+PPHV, P2 PPHV |
| 3 | r2/s3_vr | via sites | 14 | 74 of 457 | 1.105 | CELL_P, CELL_P_RAW, P1 PP5V+PPHV, P2 PPHV |
| 3 | r2/s3_cu | via sites + SIDE_CU (s3 spec) | 13 | 74 of 447 | 1.490 | CELL_P_RAW, P1 PP5V+PPHV, P2 PPHV; **1 DRC error** (planner GND x VBUS track crossing at U401) |
| 3 | r2/h_s3_post | via sites + CU + SIDE_POST=30 | 9 | 61 of 452 | 1.044 | as reference |
| 3 | r2/h_s3_postmany | + SIDE_POST_FREE=0.35 SIDE_POST_TOL=8 | 24 | 66 of 465 | 1.058 | as reference |
| 4 | s4_cpower = r2/h_s4_cpower | (reference) | 0 | 58 of 457 | 1.214 | CELL_P, FET_MID, P1 PP5V+PPHV, P2 PP5V+PPHV |
| 4 | s4_cpower_cside | defaults (fill, older cside) | 36 | 59 of 450 | 1.109 | as reference |
| 4 | r2/s4_vr | via sites | 19 | **56 of 452** | 1.121 | CELL_P, FET_MID, P1 PP5V+PPHV, P2 PPHV |
| 4 | r2/s4_cu | via sites + CU | 14 | 58 of 450 | 1.128 | CELL_P, FET_MID, P1 PP5V+PPHV, P2 PPHV |
| 4 | r2/h_s4_post | via sites + CU + SIDE_POST=30 | 11 | 63 of 450 | 2.390 | CELL_P, P1/P2 PP5V+PPHV |
| 4 | r2/h_s4_postmany | + POST_FREE 0.35, TOL 8 | 31 | 70 of 446 | 2.382 | CELL_P, P1/P2 PP5V+PPHV |
| 5 | r2/s5_cpower | (reference) | 0 | 70 of 458 | 2.631 | P1/P2 PP5V+PPHV |
| 5 | r2/s5_cu | via sites + CU | 11 | 71 of 449 | 2.502 | P1/P2 PP5V+PPHV |
| 6 | r2/s6_cpower | (reference) | 0 | 64 of 455 | 1.074 | CELL_P, CELL_P_RAW, P1 PP5V+PPHV, P2 PPHV |
| 6 | r2/s6_cu | via sites + CU | 14 | 62 of 454 | 2.914 | CELL_P, P1 PP5V+PPHV, P2 PPHV |
| 3 | r2/m_s3_ref | HOOKS=cpower,ccorr | 0 | 71 of 439 | 1.268 | P1 PP5V+PPHV, P2 PPHV |
| 3 | r2/m_s3_post | HOOKS=cpower,cside,ccorr, via sites + CU + POST=30 | 7 | 71 of 440 | 1.265 | as reference |

Verdict: no cside setting beats the one-sided placement of the same seed by more than the seed noise (-2 to +13 blocked
edges); few parts on B (7-14) is neutral, many (24-36) is worse. Recommendation: leave cside out of the default HOOKS;
if used, `SIDE_POST=30` + via-site knobs (neutral, 7-11 parts on B). Why it does not pay: the blocked edges sit at the
PD/charger pins walled in by planned power copper, not by top-side crowding, and every bottom part changes the power
copper plan (h_s4_post: 11 flips changed FET_MID, P2 VBUS, P1 PPHV and 3V3 zones by 20-70 mm2 each and new U403 edges
failed although no top part moved).

## More traps
- `cplace.py` is NOT deterministic run to run when a large part is evicted (`place_small` eviction order follows Python
  string hashing): HOOKS=cpower SEED=4 gave two different placements. Run with `PYTHONHASHSEED=0` for A/B comparisons.
- The docker daemon does not come back after a container restart: `nohup dockerd &` (cscore.sh fails at c_apply with
  "Cannot connect to the Docker daemon").
- The power-copper planner is chaotic: compare cside only against the same seed and the same top placement (SIDE_POST),
  and read `spec.json` zone areas before blaming the bottom parts.
