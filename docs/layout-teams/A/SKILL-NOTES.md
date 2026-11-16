# Team A method, step by step

Written for a cheaper model. Follow the steps in order. All paths are relative to `docs/layout-teams/A/` unless they
start with `tools/` (the shared tools, never edited in place).

## 0. Ground rules
1. Only scorecard numbers count. Use the team copies, never the stock `tools/score/score_board.sh`:
   - `tools/score_board_split.sh` = stock scorecard + `tools/split_spec.py` (one zone per outline). The stock one
     writes several outlines per zone and KiCad keeps only the first on re-save, so the router runs through vanished
     pours. Every number made without the split is "pre-split" and not comparable.
   - `tools/score_board_best.sh` = the same plus env `PLANNER`, `STRAPS`, `BUS4`, `BUS4B`, `ROUTER_OPTS`, and
     routed-board checks when a full route saves a board. `source tools/best_env.sh` sets the best copper recipe
     and `$BEST_PLAN`.
2. Use the Docker daemon that is already running (kicad/kicad:10.0). Never stop dockerd, never use groundup/dk.sh.
3. One CPU-heavy job at a time (scorecard, router, hot-loop solve). Hot loops run one by one.
4. Never edit `tools/` or another worker's folder. Copy into your own folder; change planners by subclassing
   (`stagepwr/tools/plan_copper_a.py` -> `final/tools/plan_copper_f.py` -> `portcu/tools/plan_copper_p.py`), each
   new rule behind its own option.
5. Order of goals: hard limits (power_open only 3V3@L201 and GND@J301/J302; DRC errors 0; 7 of 7 hot loops tier 1),
   then failed route edges, then tier-2 nH, then loss. Look at F.png and B.png before calling anything good.
6. Compare **failed edges and the edge total**, never routed counts alone: the total changes with the copper
   (369-448), because pours that reach a pad remove its edge.
7. Since round 5 the scorecard of the best board is `r5_merge/tools/score_board_r5.sh` (score_board_best.sh +
   per-pad join check `pad_unjoined`, routed checks in `route_local_r5.sh`); source `r5_merge/tools/best_env_r5.sh`
   and pass `--plan="$BEST_PLAN_R5"`.

## 1. Rebuild the best placement from the bare template (one command)
1. `docs/layout-teams/A/rebuild_best.sh <workdir>` (about 2 min). It runs `final/build.sh --overrides=best_overrides`
   (dump -> groundup placer with the v5 port scripts -> stage template B4 on both ports -> `best_overrides/*.json`
   in name order -> scorecard format -> courtyard/edge/peg check) and then compares with `best_placement.json`.
   Expect `CHECK clean`, `placed 289/289` and `0 of 245 entries differ from best_placement.json`.
   (The "44 differ of 289" lines above it are the diff against the round-3 reference and are expected.)
2. `best_overrides/` holds 10 stagefix s3, 20 pdfix a3, 30 ports b1, 40 stagepwr v1 (round 3) and 50 r4_port1
   (port-1 PD cluster), 60 r4_bcu (stage FET turn), 70 r5_north (charger north row), 80 r5_gauge (gauge caps).
   Each is a copy of the worker's override file; refs do not overlap between 50-80.
3. Add `--score` for the scorecard with the best copper recipe (`r5_merge/tools/score_board_r5.sh` with
   `r5_merge/tools/best_env_r5.sh`, `--route=0`, hot loops on, about 10 min), or `--score="--route=150"` for a local
   full route with routed-board checks (about 1-1.5 h). The copper recipe is planner M
   (`r5_merge/tools/plan_copper_m.py`) with `$BEST_PLAN_R5`; the general package `r5_general/copper_rules/` with
   `r5_general/monolith_r5.rules.json` gives the identical spec (section 5).
4. To add an improvement, drop a `{ref: [x, y, absolute rot]}` file into `best_overrides/` with a name that sorts
   last. Refs of different files should not overlap; later names win. Build a candidate stack in your own folder
   with `final/build.sh <wd> --overrides=<your dir>` first; never edit best_overrides before the stack is scored.
5. The round-3 board is `lead_final/best_placement_r3.json`, rebuilt by `tools/rebuild_best_r3.sh`.

Traps:
- Run `apply_stage.py` with GAP/RING **unset** (build.sh does). With them set, D410 finds no spot and overlaps.
- `keep_vias.json` (56 via spots) is a real input of the groundup placer. Without it place_bot.py fails at Q103.
- `rebuild.sh --exact` must not be combined with a variant that places C549 itself.
- groundup's placement format is `{ref: [x, y, absolute rot]}` (absolute KiCad rotation); the scorecard wants
  `{ref: [x, y, quarter turns relative to the template]}`. Convert with `tools/gu_to_score.py`. Check pad positions
  after a rotation.

## 2. Charger stage: the template rule
1. The stage is a "classic" bridge, mirrored by rotation:
   AC caps | Q401 (rot 0: D1 left, S2 right, gates up) | 1.4 mm FET gap | Q402 (rot 180) | BAT caps.
2. Hang the FET from the **fixed inductor**: SW pad 9 under L401 pad 1, courtyard 1.05 mm below L401's. Port 2 is the
   same template on L501. With the same rotation that is a pure translation; mirroring is impossible for SMD on the
   same side.
3. Centre the first cap (C430/C438) on the FET's cap edge (pads 4/5). The offset is half the FET courtyard plus half
   the cap courtyard (1.945 + 0.505 = 2.45 mm). Supply pad goes over D1, GND pad over S2. On F.Cu a cap can only join
   D1 and S2 across that edge.
4. Bulk caps sit with their supply pad against the D1 side, as vertical 1210s, so that port 2 stays right of the
   x 79.4 lip. GND pads get return vias.
5. Put the LG1 gate resistor inside the FET gap, level with pin 8. This gives LG1 an exit and stops SW2 from wrapping
   round Q402. HG2 and LG2 resistors go directly under Q402's gate pins.
6. Keep every pose relative (dx, dy, drot in the FET frame) with its rule in `stage_template.json`. Apply it with
   `apply_stage.py`, or with `rules.stage_poses()` in the generic flow. Evicted neighbours are re-placed by the
   greedy placer; keep boxes protect the FET gap.
7. Planner side (stagepwr): gate pins inside a loop's pad hull (HG1) need an escape strip plus a via site.
   Bootstrap-cap SW pads more than 3 mm from the pour need a tap, because the router only searches 6 mm round a DRC
   end point.

## 3. Port block rules (what worked, now written as rules in onecmd/generic/rules.py)
1. **PD chip rotation.** Turn the chip so its big power pads (VBUS 23, PPHV 20: >= 3x median pad area, on power nets)
   face the connector VBUS pins and the charger inductor that the PPHV path feeds. No pin row may lie between.
   (v5: port 1 block went from 24 to 16 blocked edges, VBUS loss from 83 to 35 mW.)
2. **Sense resistor beside the PPHV pad.** Place it one shunt-cap length + 0.5 mm out from the pad, then along the
   chip side toward the charger. The shunt cap (C449) sits between the pad and the resistor, never on the far side,
   or it pulls the pour under the pin row. Reserve an exit band from the resistor's far pad to the first stage bulk
   cap of that net.
3. **TVS at the connector's VBUS pins**, at the pin nearest the chip's largest VBUS pad (the east pins for port 1).
4. **A power pin's own decoupling cap goes at the pin**, ignoring the escape band, with courtyard gap 0. Shift it one
   pitch toward the row side with fewer signal pins, with its axis along the row normal. Otherwise the 5 A VBUS
   copper takes the room and PP5V opens (generic g17; ports b2/b3: moving C507 0.5 mm opened PP5V).
5. **A cap on a net that has a big pad on the chip** decouples at the big pad (VBUS pin 32 -> pad 23).
6. **Pull-up in front of a walled pin.** This is a signal pin whose pad edge is < 0.75 mm from a power pad of the
   same IC; the pour gives it no escape room. Put its 2-pad resistor straight out in front of the pin, signal pad
   about 0.9 mm from the pin centre. Do the most-walled pin first and stagger the next one deeper.
7. **Support parts.**
   - Kelvin and RC filters sit at the sense resistor or IC pin they filter: the far pad pulls with weight 0.3.
   - A pad whose net leaves the part's sheet pulls with weight 0.3.
   - Take the search centre from the full-weight targets only.
   - Stage bulk caps are corridor ends, which keeps the AC column free.
   - Corridor end boxes go only on an IC's largest pad of a net.

## 3b. Placement fixes of rounds 4-5 (each one an override file)
1. **Diff twin blocks first** (`r4_port1/tools/portdiff.py`): pose of every 4xx/5xx part relative to its anchor.
   Port 2 had the round-2 PD cluster fix and port 1 never did; copying port 2's relative poses to port 1 (+21.0 mm)
   was the biggest single routing win (override 50). Copy the twin's copper rules too (pinesc on both PD chips).
2. **A resistor boxed behind another 0402 will not route a 2-3 mm stub.** Swap slots with a neighbour that does not
   care (R433 <-> R425, override 50).
3. **Switch FET: the SW pad's only F.Cu exit decides where the FET hangs.** On a SiZ240-type dual FET the SW pad
   leaves only through the gate edge (the HF cap closes the cap edge), so the gate edge must face the inductor pad:
   Q402/Q502 at rot 90 beside L401/L501 pad 2, not under it (override 60). Then SW2 is F.Cu only and the B.Cu
   switch-node pour disappears (84.9 -> 14.3 mm2). Place every stage part with an explicit pose
   (`r4_bcu/place/mk_place.py`) plus a keep box over the new power path, or the greedy placer drops parts into it.
4. **Fine-pitch charger pin row: build a pin table** (pin, partner pad, which escape it must cross). Put two-pad parts
   with their pads straight over their own pins (C412 over pins 28/26, no half-pitch offset), the bootstrap diode
   straight above the cap's BTST pad and never across the gate-drive escapes (override 70). Tune the DRV_SUP cap in
   0.15 mm steps: it sets the lanes on both sides. After a move next to the input HF cap re-solve HL_IN (a
   thermistor's GND pad was C430's return).
5. **A lane of 0.6 mm is a track, 0.5 mm is a wall.** Moving two gauge filter caps 0.1 and 0.3 mm (override 80)
   opened VC2 at U101 pin 4; VC2, SMBC and CELL_1N routed on 7 of 8 finished routes afterwards.
6. Iterate with `r5_north/tools/ov.py` (writes the port-2 copy, dx -23.026, runs the placelib check, renders) or
   `r4_port1/tools/build_r4.sh`; require `CHECK clean` (courtyard tolerance 0.08 mm, keep 0.005 mm margin).

## 4. Screening a change (5 min loop)
1. `tools/score_board_split.sh <out> <placement.json> --route=0 --no-hot` (or `score_board_best.sh` with the env of
   `tools/best_env.sh` and `--plan="$BEST_PLAN"` when you work on the best board). Read score.json: power_open
   first, then drc_errors, then blocked_edges. `blocked_edges` = edges with no path even when no other signal is
   routed; it is the best routability screen.
2. Split blocked edges by area: `V=-v python3 rebuild/tools/blocked.py <outdir>` (stage / p1 / p2 / other), or
   `grep GHOSTFAIL <outdir>/ghost.log`. Diff the full list between two screens, not only the count: a rule often
   frees two edges and blocks two others.
3. Find what walls a blocked pad before moving anything:
   - `ports/tools/dbg.sh <outdir-copy> '<net>' x0,y0,x1,y1 out.png 'x:y;..' '<net>'` and Read `out_ov.png`
     (white = via fits, salmon = F free only, green = B free only, yellow = F and B free but no via). The `dbg at`
     lines name the net that owns each cell. Copy cu.kicad_pcb/drc.json into your own folder first.
   - `ports/tools/joindbg.py <out>/bare.json box` lists the planner's GND return joins;
     `ports/tools/viadbg.py` / `portcu/tools/roomdbg.py bare.json x,y` say why a pad got no via.
   - `plan.log` "left to router [...]" and `dc.json` terminals[].why explain a power open.
4. Decide: placement or copper? If the wall is a planner rule (section 6), no part move fixes it. Team A's last 20
   blocked edges were all copper rules.
5. After every part move check power_open again, not just the blocked count: a cap near a fine-pitch power pin can
   be that pin's only copper (moving C507 0.5 mm opened PP5V at U501).

## 5-7 preface: which planner
The best board is planned by `r5_merge/tools/plan_copper_m.py` (class PlannerM(PlannerB, PlannerV, PlannerQ) on
portcu's PlannerP) with `$BEST_PLAN_R5` from `r5_merge/tools/best_env_r5.sh`. The general package
`r5_general/copper_rules/plan_rules.py` reproduces planners V, Q, B and M spec-identically and is the version to use
on a new board; the sections below describe its rules (written by r5_general, checked by the lead). Planner-chain
history: stagepwr A -> final F -> portcu P -> r4 V/Q/B -> r5 M (and N = B + gatevia, G = Q + gauge lane rules).

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

## 8. Candidates: hot loops, renders, full route
1. Candidate = better than the best screen, hard limits met, `pad_unjoined` no worse. Run the scorecard with hot
   loops (`--route=0`, no `--no-hot`). Require "7 of 7 pass"; note the nH sum (tier 2).
2. Read F.png and B.png (the Read tool on the image). Check:
   - each PD chip just below its USB-C connector, the protector between, 5 V buck beside it;
   - stages compact under their inductors, port 2 a copy of port 1, SW1 straight into the inductor;
   - nothing stranded (diodes, LDOs, TVS far from their IC; gauge parts mid-board);
   - B.Cu: long power detours (AC_SNS_N round the stage, PP5V crossing the VBUS stem), switch-node copper.
   Logan rejects sprawl on sight even when the numbers pass.
3. Routing differences that the ghost screen cannot see (congestion): use a sub-route over a box
   (`r4_port1/tools/route_sub.sh`, `r5_gauge/tools/route_sub.sh`; at most about 130 edges, 1-35 min, one core).
   Its run time is a hint too: 1 min means clean. It ranks changes of 3+ edges, not 1-2.
4. Queue the full route on Logan's PC: `queue_route.sh <outdir> <taskkey>-<name>` (new name per changed board; it
   commits only the route_queue files). **Queue every candidate twice** (`name` and `name-rep`): one route of the
   same board spreads by about +-3 failed edges (r5_merge m1: 9 / 14 / 13 / 8 on identical copper; r4_port1 v6p:
   PC 19 against local 10). Compare means and per-region FAILKEY lists
   (`git show origin/route-results:A/<name>-<sha>.log | grep -E 'FAILED|FAILKEY'`), never one number.
   PC routes took 44-150 min in rounds 4-5, usually past the nominal 75; one timed out at 150 min (r5_gauge g0).
5. For the deliverable also run one local full route for the routed-board power check
   (`r5_merge/tools/route_local_r5.sh <outdir> 150`: adds routed_power_open, routed_loss_W, routed_drc_errors and
   routed_pad_unjoined to score.json). The PC returns only logs, so it cannot check routed power.
   Start it with `setsid nohup ... &`; if you stop it by hand its summary says "TIMED OUT", which is wrong: fix it.
6. Report routed / failed / edges / minutes / status, and say when a route timed out.

## 9. Generic (rule) placer, for reference
`onecmd/generic/run_rules.sh <workdir> [--score]` (1 min): placement from rules with 16 typed poses instead of
about 127. It meets the power and DRC limits but screens 47 of 406 blocked against 31 of 400 for the build.sh
placement on the same stock planner, so it was not carried further. Rules and traps are in onecmd/NOTES.md and
generic/NOTES.md (corridor boxes only at the largest pad of a net; caps at their pins need courtyard gap 0;
TVS/LDO placed by netlist alone sprawl; legalise anchors that land on fixed TPs).

## 10. Other traps
- Never edit a bash script while a loop that calls it is running (bash reads it as it goes). Python is safe.
- `cd x && nohup cmd &` backgrounds the whole list; the cd does not apply to later lines.
- Planning the same board twice gives the same copper but a different file sha; a PC result is keyed by the queued
  file's sha. The same sha can be re-queued under a new name for a repeat.
- Never `rm` with a variable in the path; use literal paths or `find ... -delete`.
- Loss is not comparable between boards with different power opens: an open terminal carries no current.
- The blocked count of one board varies by 1-2 between planner variants that should be equal; treat +-2 as noise.
- dc_score treats all pads of a terminal as one node and does not solve shunt caps: run `pad_join_check`
  (score_board_r5.sh puts `pad_unjoined` in score.json). The dead VBUS pin pair was found only this way.
- Merging planner subclasses: cooperative multiple inheritance, every override calls super() exactly once; the class
  listed later runs its after-grow step first. Prove a no-op first (merged planner with one worker's options on
  that worker's bare.json must give an IDENTICAL spec with `r5_merge/tools/spec_diff.py`).
- Merged options collide geometrically even when refs are disjoint (a gate via on a bottom-side cap pad): run the
  DRC screen after every merge.
- Foreground sleep is blocked: wait with background until-loops. Stop containers with `docker stop <id>`, never
  dockerd. Delete routed/sub/ghost boards over 5 MB when done.
