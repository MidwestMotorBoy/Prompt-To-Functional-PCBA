# Replacement text for SKILL-NOTES sections 5-7 (round 5, r5_general)

Paths are relative to `docs/layout-teams/A/`. The package is now `r5_general/copper_rules/` (r4_general's copy plus
the round-4 rules); `r5_general/monolith_r5.rules.json` is the delivered recipe (every kept rule on, merged
placement), `r5_general/monolith.rules.json` is the round-4 base recipe (= lead_final/sc_Z), `general_r5.rules.json`
is the same rule set with no tuned board data.

## 5. Copper rules (`r5_general/copper_rules/plan_rules.py`, one class each, run in this order)
`plan_rules.py --list=1` prints each rule with default, status, parameters and statement. Options:
`--<rule>=0|1`, `--<rule>_<param>=V`, `--stock=1` (all off), `--rules=<file>`.

### 5a. Base rules (on by default; blocked edges on the best placement, each on top of the rows above)
| order | rule | trigger -> effect | blocked |
|---|---|---|---|
| | (none: `--stock=1`) | stock planner | 29 of 400 |
| setup | `gate_escape`, `sealed` | signal pad inside a hot-loop pad hull (switch gate pins, any small part's pad) -> escape strip + via site | 24 of 396 (with taps) |
| setup | `pinesc` (select=walled) | signal pin within 1 mm of a foreign power pad, on an IC whose pin a first plan leaves in a closed pocket -> strip + via site on both layers | 5 of 369 (with gndpair) |
| setup | `connesc` | fine-pitch connector signal pad -> 0.4 mm exit strip 1 mm | 7 of 371 |
| before loops | `gndpair`, `epstrip` | neighbouring return pins joined pin to pin; return pin within 0.8 mm of the IC's exposed pad -> track into the EP | 15 of 374 (epstrip) |
| return | `joinfix` | return join under a fine-pitch IC keeps the signal escape room (hot-loop pads fall back to the stock join) | 19 of 398 |
| net | `directjoin` | power terminal "no path", copper <= 2 mm -> straight track | 15 of 373 |
| room/clip | `gndesc` | return pads of connectors / fine-pitch ICs -> signal escape room | 9 of 371 |
| grow | `nogrow_dead` | pad-only connector piece -> not grown | 10 of 373 |
| after grow | `taps` | small part's switch-node pad > 3 mm from its pour -> thin tap after the grow | (with gate_escape) |
| re-plan | `power_first` | a reservation cost a series power terminal its path -> withheld, plan again | best: no change; hand: AC_SNS_N kept |

### 5b. Round-4 rules (default off; turn on per board from the measurements in 5c)
| order | rule | trigger (roles and geometry) -> effect | measured (round 4, own board) |
|---|---|---|---|
| setup (after reservations) | `gatevia` (chk=1) | gate_escape site of a discrete switch -> track + through via drawn there; chk slides the via out (<= 0.8 mm) or drops it if it is within clearance of another net's pad on either outer layer | HG gate routes on every route; without chk 4 DRC errors on the merged board |
| after loops | `ret_band` (mm 1.6, vias 4) | discrete-switch loop with < 4 return vias at its return-pin row -> return band out of the row + vias | HL_OUT 0.98 -> 0.83 nH, -0.07 W |
| net | `sw_detour` (untested) | switch-node detour width / via count | not screened |
| after return | `gndtie` | IC return pin left floating by pinesc's via sites -> via with pinesc's raster margin relaxed | blocked 7 -> 5 |
| grow | `pw_nogrow` | non-switching detour corridor not grown | +0.010 W, 27.8 -> 3.3 mm2 per port |
| grow | `stub_nogrow` | other-side via stub not grown | part of k1 |
| grow | `sw_nogrow` (off on Monolith) | switch-node detour not grown | +0.028 W when the switch node must detour |
| mirror | `mirror_skip_supply` | no mirror copy for discrete-switch loop supply nets | +0.031 W, B.Cu -56 mm2 |
| mirror | `mirror_maxa` (10 mm2) | added mirror patches < 10 mm2 dropped with vias | bus loss unchanged |
| after grow | `tap_max` (16 mm) | taps allowed up to 16 mm (stock detour limit 10) | blocked tap edge gone |
| after grow | `padjoin` (4 mm) | 2-pad part's power pad off its pour, pour <= 4 mm -> thin straight / L track | FB stub stops failing |
| after grow | `padpair` (mode 2, live 1) | source terminal with several pad groups of which the plan feeds only some -> in-pad vias + strap on the other outer layer | VBUS dead pair joined, PC 17 -> 16 failed |
| after grow | `capjoin` | shunt cap pad off its net's main piece -> link from its island via / same-layer link / new vias + link | bulk cap joined, blocked unchanged |
| setup option | `pinesc twins=1` | IC that is a translated copy of a selected IC with its whole signal neighbourhood -> same reservations | picks port 1's PD chip only where its cluster is a copy (r4_port1 / merged placement) |

The after-grow order taps -> padjoin -> padpair -> capjoin is fixed: each later join sees the earlier ones as
obstacles, and nothing drawn after the grow is ever grown. It is the order of the round-5 merged planner M, and the
package reproduces planners V, Q, B and M spec-identically (r5_general/NOTES.md).

Rejected (kept, default off): `nogrow_detour` (15 -> 15, +0.05 W), `mirror_minw=0.5` (10 -> 10), `grow_viaroom=1.0`
(5 -> 5), `pinesc_select=all` (worse), **`connesc_big`** (r4_port1 v1q: the TC2030 pad strips cut the only strip of
the 10 A CELL_P pour from its fuse: power open), **`mirror_minw2=1.5`** (r4_bcu d2: dropped the cell-path mirror,
+0.05 W, blocked unchanged). Always confirm 7 of 7 hot loops after a planner change.

### 5c. How to pick options from the measurements
1. Score the base recipe (`score_rules.sh <out> <placement> --rules=monolith.rules.json --route=0 --no-hot`).
2. `pad_unjoined` in score.json (checks/pad_join_check.py; allow list = rules file "pad_join"."allow"):
   - a series terminal's pad group listed (connector pin pair) -> `padpair` mode 2, `live=1` if twin ports should get
     the same bridge;
   - a cap pad listed -> `capjoin` (C409/C509-type small VAC caps 30 mm from their pour stay router work);
   - a 2-pad part's rail pad that fails on routes ("no way" stub) -> `padjoin`.
3. `r4_bcu/tools/bcu_area.py <outdir> --nets` lists every other-side piece with its zone kinds:
   `detour` on a switch node -> fix the placement (switch gate edge toward the inductor), `sw_nogrow` only as a
   stopgap; `detour` on a low-current rail -> `pw_nogrow`; `mirror` on a loop supply net -> `mirror_skip_supply`;
   small `mirror` patches -> `mirror_maxa`; `via stub` blobs once mirrors are gone -> `stub_nogrow`.
4. Hot loops: a discrete-switch loop with one return via at its row (hot_gate.log, plan.log ret_band report) ->
   `ret_band`. A bootstrap tap "left to router" with a long distance -> `tap_max`.
5. Routing failures at a FET gate that had a reserved site -> `gatevia` (keep chk=1). Failing CC / I2C pins at a
   PD chip whose twin has pinesc -> make the cluster a copy, then `pinesc twins=1` + `gndtie`.
6. Port-1 column effects show only on routes: use the sub-route screen (`r4_port1/tools/route_sub.sh <outdir> <work>
   [box]`, 16-35 min, one core) for differences of 3+ edges, and the PC full route (2-3 routes of one board: the
   spread of one route is about +-3 edges) for the rest.

## 6. Planner traps (they decide many blocked edges)
1. A pin within NEAR_TERM_MM (1 mm) of a power terminal's pad gets no escape room from that pour. `pinesc` gives it
   a via site, but only on ICs where a first plan leaves such a pin sealed (or a twin of one). Reserving on every IC
   costs edges: the reservations take return pins' via sites (use `gndpair`, and `gndtie` when pinesc is on 2 chips).
2. GND pins of a 0.4 mm QFN rarely get their own via; the stock return_join runs a tight track under the I2C pins.
   `joinfix` and `epstrip` fix it.
3. `--grow 1.5` turns any free pocket within 1.5 mm of power copper into power copper, and a pad-only piece grows
   too (`nogrow_dead`). Anything that must stay thin is drawn after the grow (taps, padjoin, padpair, capjoin) or
   frozen by zone kind (sw/pw/stub_nogrow).
4. Lanes from intent.json are not honoured by the hot-loop pours.
5. Loss is not comparable between boards with different power opens.
6. Hot-loop pours are convex hulls of all loop pads with clearance only: gate pins inside are sealed
   (`gate_escape` / `sealed`), and a reserved site is only free on the planner's layers: draw it (`gatevia`).
7. A reserved via site is checked against the switch's own layer only. A part turned 90 degrees can put it over an
   other-side pad: keep `gatevia chk=1` (merged board: 4 DRC errors without it).
8. The router searches a 6 mm window round a DRC end point: a pad > 6 mm from its pour is "blocked" although free
   (`taps`, `tap_max` past 10 mm).
9. A `GHOSTFAIL GND Track ... -> Zone plane` line means a planner GND track was left floating: a regression.
10. Check `dir(pc.Planner)` before naming a new planner method or attribute (`reserve`, `keep` already exist).
11. The r4_vbus grid link appended the router path goal-to-start, so its length check rejected every grid path;
    `link_to(grid_fix=1)` (capjoin) is the corrected form, padpair keeps the old form for spec identity.
12. Removing a power net from `d.power` (mirror_skip_supply) re-orders the dict on restore: iterate nets sorted.

## 7. Power must survive routing (do not trust a route count alone)
1. router.py routes on F, In2 (vertical), In3 (horizontal) and B and may cut the soft nets (return net + the plan's
   bus nets: `--softnets=GND,PACK_P,3V3`). Without the bus copy the In2 PACK_P pour went 1 -> 3 pieces (PACK_P open).
2. The bus layer step (rules file "bus_layer") copies every >= 3 A bus net onto the unrouted plane away from the hot
   loops (In4) + a soft return fill on the far outer layer. The box "96,100,122,140" is the one tuned value; "auto"
   for a new board.
3. r5_merge found the same cut on **3V3 In3** after routing (1 piece -> 7, C207/C403/C503 off the main piece in
   routed_pad_unjoined) although dc_score saw nothing: it solves only J301 -> L201 and caps are shunt terminals.
   Run `pad_join_check` on routed boards (score_rules.sh does it when a route saves routed.kicad_pcb) and fix with a
   3V3 copy on a non-routing layer or 3V3 out of the softnets before fab.
4. Do NOT use In2 strap tracks unless no unrouted layer exists (cost 2-6 routed edges).
5. A "no tracks" keep-out is closed to vias too in the router.
6. Check: `tools/route_local.sh <outdir> 150` or `score_rules.sh ... --route=150` writes routed_power_open,
   routed_loss_W, routed_drc_errors and (round 5) routed_pad_unjoined. The PC route returns only logs: no routed
   board, so no routed power check for PC numbers.
7. Compare routed loss only with routed loss; compare failed edges and the edge total, not routed counts.
