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

## 1. Rebuild the best placement from the bare template (one command)
1. `docs/layout-teams/A/rebuild_best.sh <workdir>` (about 2 min). It runs `final/build.sh` (dump -> groundup placer
   with the v5 port scripts -> stage template B4 on both ports -> `final/overrides/*.json` in name order ->
   scorecard format -> courtyard/edge/peg check) and then compares with `best_placement.json`.
   Expect `CHECK clean`, `placed 289/289` and `0 of 245 entries differ from best_placement.json`.
   (The "6 differ of 289" lines above it are the diff against stagepwr's v1 and are expected: the 6 ports-b1 parts.)
2. Add `--score` for the scorecard with the best copper recipe (`--route=0`, hot loops on, about 8-13 min), or
   `--score="--route=150"` for a local full route with routed-board power check (1.5-2.5 h).
3. To add an improvement, drop a `{ref: [x, y, absolute rot]}` file into `final/overrides/` with a name that sorts
   last. Refs of different files should not overlap; later names win.

Traps:
- Run `apply_stage.py` with GAP/RING **unset** (build.sh does). With them set, D410 finds no spot and overlaps.
- `keep_vias.json` (56 via spots) is a real input of the groundup placer. Without it place_bot.py fails at Q103.
- `rebuild.sh --exact` must not be combined with a variant that places C549 itself.
- groundup's placement format is `{ref: [x, y, absolute rot]}`; the scorecard wants
  `{ref: [x, y, quarter turns relative to the template]}`. Convert with `tools/gu_to_score.py`.

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

## 5. Copper rules that worked (planner options, all in `portcu/tools/plan_copper_p.py`)
Apply one option per screen, in this order; numbers are blocked edges on the best placement.
| option | rule | blocked |
|---|---|---|
| (stock planner) | | 29 of 400 |
| `--sealed=1 --taps=1` | escape strip + via site for gate / small-part pads sealed inside a hot-loop hull; thin tap from a bootstrap cap's SW pad to the SW pour when it is > 3 mm away (draw taps AFTER the grow step) | 24 of 396 |
| `--joinfix=1` | QFN GND return joins keep escape room (tight=False) instead of running under the neighbour pins | 19 of 398 |
| `--epstrip=1` | each QFN GND pin gets a straight or L strip into its own exposed pad | 15 of 374 |
| `--directjoin=1` | small power pin joined to its own cap by a 0.3 mm track (PP5V pin 34) | 15 of 373 |
| `--nogrow_dead=1` | the grow step skips pad-only pieces (the connector's unused VBUS pin pair) | 10 of 373 |
| `--gndesc=1` | GND pins of connectors and fine-pitch ICs get escape room | 9 of 371 |
| `--connesc=1` | each connector signal pad keeps a straight exit strip (0.2 mm + 2 x 0.25 mm) | 7 of 371 |
| `--pinesc=1 --pinesc_refs=U501 --pinesc_near=1 --gndpair=1` | via-site reservation for PD-chip signal pins within 1 mm of a power pad; pin-to-pin link between neighbouring GND pins | 5 of 369 |

Rejected: `--nogrow_detour`, `--mirror_minw=0.5`, `--grow_viaroom=1.0`, pinesc on U401 or on all pins (worse).
Always confirm 7 of 7 hot loops after a planner change.

## 6. Planner traps (they decide many blocked edges)
1. A pin within NEAR_TERM_MM (1 mm) of a power terminal's pad gets no escape room from that pour. Plan its exit on
   the side away from the pour, or put a pull-up in front of it.
2. GND pins of a 0.4 mm QFN rarely get their own via. return_join runs a `tight` track (up to 6 mm) to the nearest
   GND zone piece with a via, often straight under the I2C pins (ports: freeing it gave -5 edges).
3. The planner's `--grow 1.5` turns any free pocket within 1.5 mm of power copper into power copper. More room next to
   a pour does not help (v6).
4. Lanes from intent.json are not honoured by the hot-loop pours (stage B6/B7).
5. Loss is not comparable between boards with different power opens: an open terminal carries no current.
6. Hot-loop pours are convex hulls of all loop pads and keep clearance only. A gate pin inside the hull (HG1 beside
   the big D1 pad) is sealed: use `--sealed=1`.
7. The router searches a 6 mm window round a DRC end point. A pad more than 6 mm from its pour (bootstrap cap to SW)
   is "blocked" although free: use `--taps=1`.
8. A thin track drawn before the grow step grows into a blob. A via site only 0.05 mm over the via size still blocks.
9. A `GHOSTFAIL GND Track ... -> Zone plane` line means a planner GND track was left floating: a regression.

## 7. Power must survive routing (do not trust a route count alone)
1. router.py routes on F, In2 (vertical), In3 (horizontal) and B. It may cut the "soft" nets GND, PACK_P, 3V3.
   On the no-strap board the In2 PACK_P pour went from 1 piece to 3 after routing: PACK_P open at D103/U204, loss
   1.03 -> 1.74 W.
2. In1 and In4 are never routed on. Put a second copy of the cut bus on In4:
   `BUS4="--mode=strip+copy --w=3 --box=96,100,122,140"` (strapfix/tools/bus4.py: 3 mm bands along a spanning tree
   over the PACK_P via groups, plus the pour copy in the 10 A box), and give GND back its area with a soft fill on
   B.Cu: `BUS4B="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1"`. Costs the router nothing.
3. Do NOT use In2 strap tracks (`STRAPS=`, stagepwr/tools/straps.py) unless In4 is unavailable: they keep PACK_P
   joined but cost 2-6 routed edges and a 1.5 mm strap carries 10 A (routed loss 1.36-1.50 W).
4. A "no tracks" keep-out is closed to vias too in the router; it costs as much as a strap.
5. Check: `tools/route_local.sh <outdir> 150` (adds the full route to a `--route=0` outdir and writes
   `routed_power_open`, `routed_loss_W`, `routed_drc_errors` into score.json), or
   `stagepwr/tools/routed_dc.sh <outdir>` on an outdir that holds routed.kicad_pcb.
   `strapfix/tools/cutmap.py cu.kicad_pcb routed.kicad_pcb cu.json <out> PACK_P In2.Cu` draws where a pour was cut.
6. Fast copper loop (1-2 min): `strapfix/tools/fastcu.sh` injects new zones into an already routed board and gives
   the routed loss without re-routing (exact for In1/In4 zones, an estimate for outer-layer fills).
7. Compare routed loss only with routed loss.

## 8. Candidates: hot loops, renders, full route
1. Candidate = better than the best screen by 4 or more edges, hard limits met. Run the scorecard with hot loops
   (`--route=0`, no `--no-hot`). Require "7 of 7 pass"; note the nH sum (tier 2).
2. Read F.png and B.png (the Read tool on the image). Check:
   - each PD chip just below its USB-C connector, the protector between, 5 V buck beside it;
   - stages compact under their inductors, port 2 a copy of port 1, SW1 straight into the inductor;
   - nothing stranded (diodes, LDOs, TVS far from their IC; gauge parts mid-board);
   - B.Cu: long power detours (AC_SNS_N round the stage, PP5V crossing the VBUS stem), switch-node copper.
   Logan rejects sprawl on sight even when the numbers pass.
3. Queue the full route on Logan's PC: `queue_route.sh <outdir> <taskkey>-<name>` (new name per changed board; it
   commits only the route_queue files). Poll `route_result.sh <name>` from a background until-loop with a bounded
   timeout. PC routes took 45-107 min here, usually past the nominal 75. Queue several at once.
4. For the deliverable also run one local full route for the routed-board power check (`tools/route_local.sh`).
   The scorecard's default 45-min cap kills the router before it saves a board; use 150 min. Start long jobs with
   `setsid nohup ... &`; background tasks of the agent harness are killed after 2 h.
5. Report routed / failed / edges / minutes / status, and say when a route timed out.

## 9. Generic (rule) placer, for reference
`onecmd/generic/run_rules.sh <workdir> [--score]` (1 min): placement from rules with 16 typed poses instead of
about 127. It meets the power and DRC limits but screens 47 of 406 blocked against 31 of 400 for the build.sh
placement on the same stock planner, so it was not carried further. Rules and traps are in onecmd/NOTES.md and
generic/NOTES.md (corridor boxes only at the largest pad of a net; caps at their pins need courtyard gap 0;
TVS/LDO placed by netlist alone sprawl; legalise anchors that land on fixed TPs).

## 10. Other traps
- Never edit a bash script while a loop that calls it is running.
- `cd x && nohup cmd &` backgrounds the whole list; the cd does not apply to later lines.
- Planning the same board twice gives the same copper but a different file sha; a PC result is keyed by the queued
  file's sha.
- Never `rm` with a variable in the path; use literal paths or `find ... -delete`.
- Loss is not comparable between boards with different power opens: an open terminal carries no current.
- The blocked count of one board varies by 1-2 between planner variants that should be equal; treat +-2 as noise.
- The connector's second VBUS pin pair (J401 A9/B4, J501 A4/B9) is not joined to the VBUS pour by any planner
  variant; dc_score does not flag it. It needs a fix before fab.
