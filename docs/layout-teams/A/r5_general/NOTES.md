# Worker `r5_general` (team A, round 5): round-4 rules ported into the general copper_rules package

All numbers are split-zone copper (`copper_rules/score_rules.sh` = team scorecard driven by a rules file).
"allowed" = power_open is 3V3@L201 and GND@J301/J302 only.

## Result in one table
| check | result |
|---|---|
| regression (planner only, spec_diff) | v2sh IDENTICAL, v5p IDENTICAL (pinesc refs as board data), k1 IDENTICAL, sc_Z IDENTICAL (new rules off), r5_merge m1 IDENTICAL |
| merged placement, all rules (monolith_r5.rules.json, runs/all_hot) | power_open allowed, DRC 0, 7/7 tier 1 at 6.27 nH, blocked 4 of 364, 0.803 W, pad_unjoined C409.1 / C509.1 |
| hand template, all rules (general_r5.rules.json, runs/hand_all) | allowed + PP5V@U401 (= hand reference), DRC 0, blocked 44 of 372, 1.161 W, pad_unjoined 15 -> 4 |
| PC full route r5_general-all | 356 / 8 failed of 364, 44.0 min, done |

## What was built (all in `docs/layout-teams/A/r5_general/`)
- `copper_rules/` = copy of `r4_general/copper_rules/` (the r4 copy is untouched) plus:
  - `plan_rules.py`: 15 new rule classes, each behind its own option, default off, docstring in board terms, no
    refs / net names / coordinates in package code (grep below):
    `gatevia` (r4_port1 q3, with r5_merge's gatevia_chk as param `chk`, default 1), `gndtie` (q4), `padjoin` (q2),
    `connesc_big` (q1, **rejected**), `ret_band`, `tap_max`, `sw_nogrow`, `pw_nogrow`, `stub_nogrow`,
    `mirror_skip_supply`, `mirror_maxa`, `mirror_minw2` (**rejected**), `sw_detour` (B's sw_w / sw_vias, untested),
    `padpair` (r4_vbus V1), `capjoin` (r5_merge M). pinesc got a `twins` option (see below).
    New hooks: `after_loops`, `detour_args` (+ `_in_netstep`), `after_return`, `mirror_hide`; `after_mirror` gets the
    pre-mirror zones; `after_grow` now runs taps -> padjoin -> padpair -> capjoin. Shared helpers (from V and M):
    `cu_pieces`, `net_state`, `main_on`, `link_obs`, `link_to` (grid_fix 0 = V's behaviour, 1 = M's corrected grid
    link), `via_sites_exact`, `snap` / `restore`. All names checked against `dir(pc.Planner)` (no clash; `detour` is
    a deliberate override that calls the stock method).
  - `checks/pad_join_check.py`: r4_vbus's per-pad join check made general (stock dir found like plan_rules, allow
    list is data: rules file `"pad_join": {"allow": ...}`), outdir mode for the scorecard, routed-board mode
    (routed.kicad_pcb + routed.json when a full route saved them). `score_rules.sh` lifts `pad_unjoined`,
    `pad_unjoined_all`, `routed_pad_unjoined` to the top level of score.json.
  - `README.md`: new rules table, the one hook order for V/Q/B/M, the checks.
- Rules files: `monolith.rules.json` (round-4 base = lead_final/sc_Z, + pad_join allow list), `general.rules.json`
  (same, no tuned data), **`monolith_r5.rules.json`** (every kept rule on, merged placement),
  `general_r5.rules.json` (every kept rule on, default parameters, derived In4 box, pinesc walled + twins),
  `runs/regress/reg_{v,q,b}.rules.json` (one per round-4 target).
- Tools: `tools/plan_only.sh` (planner + split + bus layer = the scorecard's copper, no KiCad), `tools/spec_diff.py`
  (r5_merge's copy of r4_general's, buffer(0) repair), `tools/dcq.sh`, `tools/twin_probe.py`, `tools/twin_probe2.py`.
- `upstream.diff`: r4_general's hooks + the new ones (after_loops, after_return, detour_args, `detour_max` instead of
  the module DETOUR_MAX_MM, `mirror_skip`, after_mirror(n0, before), after_grow). Checked: it applies to the stock
  files with `patch -p1`, and the patched stock planner gives a spec IDENTICAL to the unpatched one on sc_Z's bare
  board (85 zones / 337 tracks / 381 vias): the hooks are no-ops.
- `SKILL-NOTES.new.md`: replacement text for SKILL-NOTES sections 5-7.

## Regression (planner only, `runs/regress/run.sh`, spec_diff against the round-4 outdir's spec.json from its bare.json)
| target | rules file | verdict |
|---|---|---|
| (a) r4_vbus/runs/v2sh (planner V, padpair 2 live 1) | reg_v | **IDENTICAL** (94 zones / 382 tracks / 383 vias) |
| (b) r4_port1/runs/v5p/hot (planner Q, padjoin 4, gatevia, gndtie, pinesc U401+U501) | reg_q | **IDENTICAL** (94 / 396 / 383) |
| (c) r4_bcu/runs/k1 (planner B, 6 options) | reg_b | **IDENTICAL** (78 / 344 / 281) on the first try |
| (d) lead_final/sc_Z, all new rules off | monolith | **IDENTICAL** |
| (e) r5_merge/runs/m1 (planner M = B+V+Q + gatevia_chk + capjoin), merged placement | monolith_r5 (scorecard run all_nh) | **IDENTICAL** (78 / 362 / 290) |
(b) first ran with `pinesc select=walled, twins=1`: DIFFERENT (10 net/layer entries, all round U401: PP5V B.Cu, VBUS
vias, GND pin vias) because only U501 was selected. With `select=refs, refs=[U401, U501]` (board data) IDENTICAL.

### pinesc on both PD chips: board data, not a derived property
The walled predicate (r4_general) picks only U501.28/29 on the v5p and merged placements too: U401's pins are not
sealed by planned copper; round 4 found them walled by *routed* neighbours (congestion in port 1's column), which a
planner-only predicate cannot see. Tried: "twin" = an IC that is a translated copy of a selected IC with its
neighbourhood. All neighbours: fails on every placement (power caps differ). Parts on the candidate pins' nets within
3 mm of those pins (`twins=1`, `tools/twin_probe2.py`): 4 of 5 match on the v5p / merged placements (U402, R404, R441,
R455; the west cap C404 vs C504 differs: the r4_port1 cluster copy did not move it), 1 of 5 on best / k1 placements.
A threshold between those would be tuned on two data points, so the option stays (`twin_frac`, default 1.0 = strict,
adds nothing here) and Monolith keeps `select=refs` with a `_why` in monolith_r5.rules.json.

## Merged placement, all rules on (`runs/all_nh`, `runs/all_hot`)
Placement: `A/r4_port1/tools/build_r4.sh runs/build A/r4_port1/overrides/50_r4_port1.json A/r4_bcu/overrides/60_r4_bcu.json`
-> CHECK clean, placed 289/289, 30 refs differ from best_placement.json; byte-identical to r5_merge/placement.json.
| run | power_open | DRC | hot loops | blocked | loss W | pad_unjoined (not allowed) |
|---|---|---|---|---|---|---|
| all_nh (`--no-hot`) | allowed | 0 | - | 4 of 365 | 0.802 | C409.1, C509.1 (PPHV VAC caps) |
| **all_hot (hot on)** | allowed | 0 | **7/7 tier 1, 6.27 nH** (HL_3V3 1.329, P1 5V 0.461, P1 IN 0.580, P1 OUT 0.627, P2 5V 0.677, P2 IN 0.560, P2 OUT 0.633) | 4 of 364 | 0.803 | C409.1, C509.1 |
| r5_merge m1h (reference, same spec) | allowed | 0 | 7/7, 6.28 nH | 4 of 364 | 0.803 | C409.1, C509.1 |
gatevia chk dropped both LG2 gate vias (P1 116.885,92.08 / P2 93.859,92.087, over the bottom-side bulk cap pads);
capjoin joined C521.1 (port-2 bulk cap) by a 0.8 mm B.Cu strap; C409.1 / C509.1 not joined (PPHV main piece 30 mm away),
as r5_merge found. Comparison with r5_merge (`tools/spec_diff.py ../r5_merge/runs/m1/spec.json runs/all_nh/spec.json`):
IDENTICAL, so nothing to explain; the score matches m1 (edge total 365 = m1, m1h 364: fill bytes).

Renders (Read runs/all_nh/F.png, B.png): F.Cu: each port top is compact under its USB-C connector (PD chip with the
VBUS stem and PP5V east of it, PPHV south), the charger stages sit round their inductors with the turned Q402/Q502
beside the inductor, the cell path (FET_MID, CELL_P) bottom centre. B.Cu: GND fill everywhere except thin items: the
two VBUS straps under the connectors, two PP5V corridors (not grown), the SW1/SW2 0.3 mm bootstrap taps, the AC_SNS_N
strap at port 2 (capjoin) and the port-1 AC_SNS_N stub, PACK_P via stubs, the FET_MID / CELL_P / CELL_N cell-path
mirror. No sprawled power part.

## Hand template placement, all rules (general_r5.rules.json, `runs/hand_all`, --no-hot)
`copper_rules/score_rules.sh runs/hand_all --rules=general_r5.rules.json --route=0 --no-hot` (no placement = the
template as it is; no tuned data: derived In4 box, pinesc walled + twins, every kept rule on with default parameters).
| run | power_open | DRC | blocked | loss W | pad_unjoined (not allowed) |
|---|---|---|---|---|---|
| r4_general sc_hand (round-4 package, base rules) | allowed + PP5V@U401 | 0 | 45 of 381 | 1.155 | 15: P1 PP5V C407.1, U401.34; P1 VBUS C450.1, D401.4-6, J401.A9/B4; P2 VBUS D501.4-6, J501.A4/B9; GND C449.2, C549.2 (re-written from its spec.json in runs/hand_r4ref) |
| **hand_all (all rules)** | **allowed + PP5V@U401 (= hand reference)** | **0** | **44 of 372** | 1.161 | **4**: P1 PP5V C407.1, U401.34 (the known PP5V@U401 open); GND C449.2, C549.2 (same as round 4) |
No new power open. power_first fired as in round 4 (AC_SNS_N R424/R524 lost with reservations, joined after
withholding); pinesc walled picked U404 (as round 4); padpair joined both VBUS dead pairs (J401 by a pad-to-pad
B.Cu strap) and the TVS pads with them; capjoin joined C450.1 (via + 0.3 mm B.Cu link) and could not join C407.1;
gatevia chk moved/dropped nothing; ret_band drew a 0.9 mm2 band at each HL_OUT but no via fitted (added 0). No ladder
was needed (no new open).

## Full route (Logan's PC)
| name | board | queued (UTC) | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|---|
| **r5_general-all** (`A/r5_general-all-925ee6da.json`) | runs/all_nh | 07:39 | **356** | **8** | 364 | 44.0 | done (arrived about 08:25, 46 min after queueing) |
Same copper as r5_merge m1 (spec IDENTICAL; the KiCad file differs only in fill bytes, sha 925ee6da vs 6a7dde2b), which
routed 9 / 14 / 13 failed of 364 on three PC routes: with this fourth route the board's mean is 11.0 failed (spread
about +-3 per route), so 8 is router-order luck on the same copper, not an effect of the package.
Failed (8): P1 LODRV1 U403.25->R445 (pulled), P1 CHG_INT R404->U401.18 (pulled) and U403.3->R404 (no way), P1 I2CC_SDA
R402->U403.2 (no way), P1 REGN R454->C410 (no way), P2 REGN C510->U503.24 (pulled) and R515->U503.24 (no way),
SCL J302.6->U301.9 (no way). All are the known port-1 column congestion / REGN / SCL fails of r5_merge; no VBUS, CC,
gate (HG/LG) or power-stub fail. No local full route was run (the PC result came back in 46 min). The PC returns
only logs, so routed_power_open / routed_pad_unjoined could not be run on it.

## Hardcoding grep (package code)
`grep -nE 'U[0-9]{3}|J[0-9]{3}|PACK_P|Monolith|monolith' copper_rules/*.py copper_rules/*.sh copper_rules/checks/*.py`
-> no hits (one docstring said "Monolith"; changed to "the reference board"). Refs appear only in the rules files.

## Cleanup
Deleted: runs/hand_all/cu.kicad_pcb (5.8 MB), runs/hand_r4ref/{bare,cu}.kicad_pcb, every runs/*/in.kicad_pcb, the
build work dirs runs/build/{b,ov}. Kept (< 5 MB): runs/all_nh/cu.kicad_pcb (queued board, also route_queue/r5_general-all.kicad_pcb),
runs/all_hot/cu.kicad_pcb. score.json / F.png / B.png in this folder = runs/all_hot.
