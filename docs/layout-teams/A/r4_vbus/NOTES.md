# Worker r4_vbus (team A, round 4): join the second VBUS pin pair of J401/J501, and a per-pad power-join check

All numbers are split-zone copper from `tools/score_board_r4v.sh` (a copy of `../tools/score_board_best.sh` with
the pad-join check added; same arguments) on `../best_placement.json` (unchanged, no overrides) with the team best
copper recipe (`source ../tools/best_env.sh`), planner `tools/plan_copper_v.py` (subclass of
`portcu/tools/plan_copper_p.py`). "allowed only" = power_open is 3V3@L201 and GND@J301/J302 only.

## Result

Best = **v2s**: `$BEST_PLAN --padpair=2 --padpair_live=1` (full string and env in `best_plan_opts.txt`).
Each connector gets a via in the dead pin pair's pad (J401 A9/B4 at 104.1, 69.175; J501 A4/B9 at 95.9, 69.175), a
via in the live pair's pad (108.9 / 91.1, 69.175) and a 0.8 mm B.Cu strap between them, under the connector pad row.
F.Cu is unchanged: the dead pair stays an ungrown pad, U405/U505 CC pins and the connector exit strips are untouched.

| | blocked | ghost list vs base | power_open | pad_unjoined (not allowed) | DRC | hot loops | loss |
|---|---|---|---|---|---|---|---|
| reference lead_final/sc_Z | 5 of 369 | - | allowed only | VBUS J401.A9/B4, J501.A4/B9; C409.1, C509.1 (PPHV); C521.1 (P2 AC_SNS_N) | 0 | 7 of 7, 6.24 nH | 0.835 W |
| **v2s (best)** | **5 of 369** | **identical** | allowed only | C409.1, C509.1, C521.1 (VBUS gap gone) | **0** | **7 of 7, 6.24 nH** (v2sh) | **0.833 W** |

PC full route (split copper, Logan's PC): **v2s 353 routed / 16 failed of 369, 84.2 min, done** (reference lead-Z 352 / 17 of 369). Details under "Full routes".

## Screens (all `--route=0 --no-hot` unless noted; outdirs under `runs/`)

| screen | plan options added to $BEST_PLAN | outdir | power_open | pad_unjoined (not allowed) | DRC | blocked | GHOSTFAIL list vs sc_Z | loss | hot loops |
|---|---|---|---|---|---|---|---|---|---|
| base (reproduce) | - (score_board_best.sh) | runs/base | allowed only | (check run separately: same as sc_Z) | 0 | 5 of 369 | identical | 0.835 W | |
| V1 mode 1, F.Cu strip | `--padpair=1` | (plan only) | | | | | | | |
| V1 mode 2, via + B.Cu link | `--padpair=2` | runs/v2 | allowed only | C409.1, C509.1, C521.1 | 0 | 5 of 369 | identical | 0.834 W | |
| V1 mode 2, candidate | `--padpair=2` (hot on) | runs/v2h | allowed only | same | 0 | 5 of 369 | identical | 0.834 W | 7 of 7, 6.24 nH |
| V1 mode 2, pad-to-pad bridge on both ports | `--padpair=2 --padpair_live=1` | runs/v2s | allowed only | same | 0 | 5 of 369 | identical | 0.833 W | |
| **same, candidate** | `--padpair=2 --padpair_live=1` (hot on) | **runs/v2sh** | allowed only | same | 0 | 5 of 369 | identical | 0.833 W | 7 of 7, 6.24 nH |

- Mode 1 (same-layer F.Cu strip): no legal link. Every path from the dead pair to the live pour crosses the
  CC/SBU/DPDN exit strips (`--connesc`) or the escape room of the signal pads; nothing is drawn, so the board equals
  base (not screened). A first draft that checked only P's `obstacles()` drew an L under the whole pad row at y 70.97
  (straight across every CC/DPDN exit): the link check must include `blockgeom` (exit strips, pin escapes) and the
  signal escape room. Fixed before any screen.
- Mode 2: the stock `place_vias` found no via site in the pad (its raster margin RAST_MM needs 0.325 mm of room, the
  pad leaves 0.275 mm to the GND and CC2 pads on each side). `_via_sites` checks exact shapes instead: a 0.45/0.3 via
  centred in the 0.6 x 1.0 mm pad keeps 0.275 mm to both neighbours (DRC min 0.2; the 0.25 HighCurrent rule does not
  apply pad to via), 0.475 mm from the board edge, 1.05 mm from the GND in-pad via. One via per pad (a second does not
  fit the 0.75 pitch / edge margin inside the pad).
- Port 2 in mode 2 (v2): no VBUS copper on B.Cu within 10.8 mm of J501 (the B.Cu VBUS copy exists only at port 1), so
  the rule falls back to a second in-pad via in the live pair and a pad-to-pad strap. `--padpair_live=1` (v2s) does
  that on both ports, so port 2 is a copy of port 1. Same blocked list, 0.001 W lower loss, port 1 dead-pair path
  4.74 mOhm instead of 5.71 mOhm.
- Mode 3 (thin / inner-layer link) was not needed: 0.8 mm fits on B.Cu.

## Current sharing (tools/pair_share.py, dc_score's grid solver on the real copper)

dc_score holds every pad of the source terminal (the connector) at the same potential, so it cannot see a pin pair
that is fed only through the plug. `pair_share.py` solves the VBUS net once per pad group alone and once with a plug
model: one node tied to each pad group through its contacts (2 contacts per coincident pad pair, rc per contact).

| board | port | R live pair alone | R dead pair alone | R with plug, rc 10 mOhm | share live/dead (10 mOhm) | share (30 mOhm) |
|---|---|---|---|---|---|---|
| base | 1 | 1.48 mOhm | open | 6.59 mOhm | 100 / 0 % | 100 / 0 % |
| base | 2 | 1.86 mOhm | open | 6.97 mOhm | 100 / 0 % | 100 / 0 % |
| v2 | 1 | 1.48 | 5.71 | 4.49 | 63 / 37 % | 56 / 44 % |
| v2 | 2 | 1.86 | 6.36 | 5.26 | 66 / 34 % | 57 / 43 % |
| **v2s** | 1 | 1.38 | 4.74 | 4.47 | 62 / 38 % | 55 / 45 % |
| **v2s** | 2 | 1.87 | 6.36 | 5.26 | 66 / 34 % | 57 / 43 % |

R = connector pads to the PD chip's VBUS pad (U401/U501.23). At 5 A the busiest contact pair falls from 2.5 A per
contact (base: 2 contacts carry everything) to about 1.6 A (rc 10 mOhm) / 1.4 A (rc 30 mOhm); USB-C VBUS contacts
are rated about 1.25 A each in a 5 A cable, so the board is now within ~1.3x of even sharing. VBUS loss from
dc_score does not rise (port 1 0.037 -> 0.034 W, port 2 0.0465 -> 0.0467 W: dc_score's source model).
The connector-contact resistance values are assumptions (USB-C LLCR limits are tens of mOhm), stated, not measured.

## Part 1: the per-pad power-join check (tools/pad_join_check.py)

`pad_join_check.py <board.kicad_pcb> <cu.json> <constraints.json> [out.json] [--allow=allow.json]`: per power net and
return net (roles.py, as plan_copper / dc_score), exact shapely copper per layer (filled zones, tracks, vias, pads,
merged at 0.001 mm: a 0.2 mm gap stays a gap), joined across layers only by vias and plated holes; pads of one
footprint are not joined for free. The main piece is the one holding pads of the most terminal parts. Reports every
terminal pad (series or shunt) off the main piece; non-terminal pads of parts with 2+ pads on the net go to `info`.
Exit 1 when a terminal pad is off the main piece and not in `allow.json`. Runs in about 1.5 s.
`score_board_r4v.sh` runs it after dc_score (score.json `pad_unjoined`, `pad_unjoined_all`) and on routed.kicad_pcb
when a full route saved one (`routed_pad_unjoined`).

Findings on the old best board (lead_final/sc_Z), all cross-checked against KiCad's unconnected items in drc.json:

| net | pad(s) | class | why |
|---|---|---|---|
| P1 VBUS | J401.A9, J401.B4 | **real gap (target)** | second VBUS pin pair, pad-only F.Cu piece; all 5 A through A4/B9. KiCad lists it as a VBUS zone-zone unconnected item |
| P2 VBUS | J501.A4, J501.B9 | **real gap (target)** | same at port 2 |
| P2 AC_SNS_N | C521.1 | **real gap, NEW** | port 2's 68 uF / 35 V input bulk cap (B.Cu, 7343) sits on a 5.3 mm2 B.Cu AC_SNS_N island with a via that lands on no F.Cu AC_SNS_N copper; plan.log: "left to router ['C521 (via array path winds)']". dc_score does not solve shunt terminals, so power_open misses it. Port 1's C421 is joined. The router would close it with a signal-width track at best |
| P1 PPHV | C409.1 | real but minor, NEW | 1 uF / 50 V VAC decoupling cap at the charger U403's VAC pins 32/33: not on the PPHV pour, joined only by router tracks (drc unconnected: C409.1 - track - U403.33) |
| P2 PPHV | C509.1 | real but minor, NEW | same at port 2 (C509 - U503.33 / R509) |
| P1/P2 VBUS | U401.32, U501.32 | expected (allow-listed) | the PD chip's small VBUS_32 supply pin (IC supply current, mA); roles.py calls it a terminal by pad size; the router joins it; dc_score already lists it as pads_not_joined |
| 3V3 | J301.1 | expected (allow-listed) | the allowed 3V3@L201 open seen from the other side (the J301 piece and the L201 piece are separate) |
| GND | J301.5, J302.5 | expected (allow-listed) | the allowed test-connector GND |
| info: P1/P2 PPHV | U403.32/.33, U503.32/.33 | expected | charger VAC pins (small, non-terminal), router-finished |
| info: 3V3 | U301.6/.7 | expected | MCU supply pins, router-finished |
| info: GND | U301.1/.2/.24, U402.7, U502.7 | expected | IC GND pins without a via/strip; the router joins them (KiCad lists the same pairs) |

No exposed-pad-vs-pin or parallel-FET-pad gaps were found: every FET's parallel drain/source pads and every QFN EP are
on their net's main piece on this board.

On the new board (v2s) the two VBUS gaps are gone; C521.1, C409.1, C509.1 remain (not this task's rule; see "Left").

## Full routes (Logan's PC, split-zone copper from score_board_r4v.sh outdirs)

| name | board | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|
| lead-Z (reference, lead_final/sc_Z) | old best | 352 | 17 | 369 | - | done |
| r4_vbus-v2 | runs/v2 | 351 | 18 | 369 | 75.6 | done |
| **r4_vbus-v2s** | runs/v2s (best) | **353** | **16** | 369 | 84.2 | done |

Failed-edge lists (FAILKEY from the PC logs) vs lead-Z: same edge total (369). The connector-area failures CC1 (P1) and
SBU_FLT (P1) were already in lead-Z and stay; no new D+/D-/CC/SBU, U405/U505 C_CC1/C_CC2/VBIAS or VBUS-area edge fails.
The rest is reshuffling between router runs: v2s loses CELL3, CELL_1N, BTST1(P1), LODRV2(P1), LODRV1(P2), U101-SMBC,
I2CC_SCL, one P1_LDO_3V3, and gains REGN(P1), REGN x2(P2), BTST1(P2), HG1(P2), U101-SMBD, I2CC_SDA, all far from the
connectors, so this is router-order noise. The PC returns only logs, not the routed board, so routed_pad_unjoined /
routed power_open could not be run on these routes (no local 150-min route was started because the PC results came back).

## What the renders show (v2s; F.png, B.png, img/v2s_p1_*.png, img/v2s_p2_*.png)
- F.Cu at both connectors looks the same as the old best: the live VBUS pair (A4/B9 at J401, the mirror pair at J501)
  feeds the VBUS stem strip down to the TVS/C459 and the PD chip; the dead pair is still a bare pad with a via in it,
  with no grown blob. U405/U505 CC pins and the CC/SBU/D+/D- exit strips are clear.
- B.Cu: a straight 0.8 mm VBUS strap runs under the connector pad row from the dead pair's in-pad via to the live pair's
  in-pad via, inside the GND pour's clearance; port 2 is the mirror copy of port 1. Nothing else on B.Cu moved.
- Whole board: the power parts are not spread out more than before. The PD chips, protectors and TVS stay next to their
  connectors.

## Files
- `tools/pad_join_check.py`: the check. `allow.json`: expected findings, with the reason.
- `tools/score_board_r4v.sh`: scorecard copy with the check (pad_unjoined / routed_pad_unjoined in score.json).
- `tools/plan_copper_v.py`: planner V = planner P + rule V1 (`--padpair=1|2|3`, `--padpair_live`, `--padpair_w`,
  `--padpair_vias`, `--padpair_len`, `--padpair_minpad`); env R4V_DUMP=<file> pickles the planner state before the
  rule (for fast debugging of the rule alone, about 2 s instead of 75 s per try).
- `tools/pair_share.py`: per-pin-pair resistance and current share with a plug-contact model.
- `tools/screen.sh <name> "<plan opts>" [scorecard opts]`: one screen with the best recipe + planner V.
- `best_plan_opts.txt`: env and --plan string of the best variant.
- `score.json`, `F.png`, `B.png`: of v2sh (best variant, hot loops on). `img/`: zooms (old_p1_*, v2_p*, v2s_p*;
  50 px/mm, port 1 window 100-113 x 67-80, port 2 87-100 x 67-80).
- `runs/`: base, v2, v2h, v2s, v2sh outdirs (cu.kicad_pcb deleted in v2 and v2s, >5 MB; kept in v2sh; the queued boards are in ../route_queue/) (logs, score.json, ghost.log, pad_join.json, pair_share.json, renders).

## Left / for the lead
- C521 (port 2 input bulk 68 uF, B.Cu) is not joined to AC_SNS_N power copper: a real power-copper gap on a 5 A net
  that power_open does not flag (shunt terminal). It needs its own rule (a via array from the C521 B.Cu island to the
  F.Cu AC_SNS_N pour, or a B.Cu strap to the stage) or a small placement move; port 1's C421 shows it can be joined.
- C409/C509 (1 uF VAC caps at the charger) are joined by router tracks only; acceptable for decoupling, but the
  power pour could reach them.
- The check's allow-list names refs (U401.32 etc.); it is a per-board file, the check itself names none.
