# Team A method, step by step (draft for the lead)

This draft merges the skill notes in rebuild/NOTES.md, stage/NOTES.md, generic/NOTES.md, ports/NOTES.md and
stagepwr/NOTES.md with onecmd's.

## 0. Ground rules
1. Only the scorecard counts. Use `docs/layout-teams/A/tools/score_board_split.sh`, never the stock
   `tools/score/score_board.sh`. The stock one writes one zone per net and layer with several outlines, and KiCad
   keeps only the first outline on re-save, so routed boards lose their pours. Label any older number "pre-split".
2. Use the Docker daemon that is already running (kicad/kicad:10.0). Never stop dockerd and never use groundup/dk.sh.
3. Run one CPU-heavy job at a time: a scorecard, the router or a hot-loop solve. The hot-loop solver can run out of
   memory in parallel; the scorecard already runs it loop by loop.
4. Never edit `tools/` or another worker's folder. Copy what you change into your own folder.
5. Hard limits come before anything else:
   - power_open holds only 3V3@L201 and GND@J301/J302
   - DRC errors are 0
   - 7 of 7 hot loops pass tier 1

   Then route count, then tier-2 nH, then loss.

## 1. Rebuild the team's best placement from the bare template (one command)
1. Run `docs/layout-teams/A/onecmd/build.sh <workdir>` (about 2 min). It does dump -> groundup placer with the v5
   port scripts -> stage template B4 on both ports -> `onecmd/overrides/*.json` in name order -> scorecard format ->
   placelib check -> diff against `lead_merge/merged3_gu.json`. Expect "0 differ of 289".
2. To add a worker's improvement, drop its `{ref: [x, y, absolute rot]}` override file into `onecmd/overrides/`
   with a name that sorts after the others (`30_...`, `40_...`). Rebuild and read the diff lines.
3. Add `--score` for the split screen (`--route=0 --no-hot`, about 5 min), or `--score="--route=0"` for hot loops
   too (40-60 min).

Traps:
- Run `apply_stage.py` with GAP/RING **unset**. The placer's GAP=0.25 RING=0.4 make the eviction re-placement fail:
  D410 finds no spot and leaves an overlap.
- `rebuild.sh --exact` must not be combined with a variant that places C549 itself.
- `keep_vias.json` (56 hand-copper via spots) is a real input of the groundup placer. Without it place_bot.py fails
  at Q103.
- groundup moved 6 TPs (TP109, TP412, TP512, TP106, TP113, TP301) away from the template, against the charter. Any
  flow that keeps TPs fixed will see L402, L201 and U403 collide with them.

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

## 4. Generic placer, one command
1. `docs/layout-teams/A/onecmd/generic/run_rules.sh <workdir> [--score]` (about 1 min) runs dump -> place_rules.py
   (anchors_rules.json, stage_template_u403.json, fixed_parts.json, enclosure.json) -> scorecard format.
2. The anchors file holds `pose` (typed), `pd_chip` (typed x, y; rotation derived), `rule: sense|tvs`, `stage`
   and `auto`. Every anchor chosen by the anchor rule must have an entry.
3. Read `place.log`. Check the "legalised anchor" lines (an anchor that hit a fixed part) and every part placed more
   than about 5 mm from its block (the "cost" column is high: e.g. Q103 cost 44 in the middle of the board means a
   bad target).
4. Draw the placement before scoring:
   `python3 generic/showp.py <workdir>/base.json <workdir>/placement_gu.json out.png F [x0 y0 x1 y1 scale]`.
   Then Read the png.

## 5. Screening
1. Run `score_board_split.sh <out> <placement.json> --route=0 --no-hot` (about 5 min, one at a time). Read
   score.json: power_open, drc_errors, blocked_edges.
2. Split blocked edges by area with `python3 docs/layout-teams/A/rebuild/tools/blocked.py <outdir>` (stage / p1 /
   p2 / other). List them with `grep GHOSTFAIL <outdir>/ghost.log`.
3. For a power open, read `plan.log` ("left to router ['REF (why)']"). The winding detail is in
   `spec.json` placement_failures ("path 38 mm for 19 mm straight"). "Path winds" means a part blocks the straight
   way: find it in the placement picture.
4. Compare blocked counts, not ratios; the edge total changes with the placement. The same placement varies by 1-2
   edges. One unrelated rule change can move the count by 5-8 (r8 47 -> r9 55), so screen every change.
5. Run hot loops (`--route=0` without `--no-hot`, 40-60 min) only for real candidates. Required: 7/7 tier 1.

## 6. Reading renders (always, before calling a board good)
1. In F.png check:
   - each PD chip beside its USB-C connector, with the protector between
   - stages compact under their inductors
   - SW1 straight up into the inductor
   - nothing stranded: diodes or filters far from their IC, gauge parts in the middle of the board
2. In B.png check for long power detours: AC_SNS_N loops round the stage, VBUS tracks along the edge, PP5V crossing
   the VBUS stem.
3. Logan rejects sprawl on sight: a power part far from its partner is a fail even when the numbers pass.

## 7. Full routes on Logan's PC
1. Queue with `docs/layout-teams/A/queue_route.sh <split scorecard outdir> <taskkey>-<name>`. Use a new name for
   every changed board.
2. Poll with `docs/layout-teams/A/route_result.sh <name>` from a background until-loop, never a foreground sleep.
3. If nothing arrives 75 min after queueing, fall back to one local `--route=45` and say so.
4. Routes are one thread on the PC, about 60-100 min. Report routed / failed / edges / minutes / status, and say
   when a route timed out.
5. A route count is only trusted on split copper. Check power on the routed board (dc_score) when possible: a
   failed PP5V edge means the pin hangs on the pour alone.

## 8. Known planner traps (they decide many blocked edges)
1. A pin within NEAR_TERM_MM (1 mm) of a power terminal's pad gets no escape room from that pour. Plan its exit on
   the side away from the pour, or put a pull-up in front of it.
2. GND pins of a 0.4 mm QFN rarely get their own via. return_join runs a `tight` track (up to 6 mm) to the nearest
   GND zone piece with a via, often straight under the I2C pins (ports: freeing it gave -5 edges).
3. The planner's `--grow 1.5` turns any free pocket within 1.5 mm of power copper into power copper. More room next to
   a pour does not help (v6).
4. Lanes from intent.json are not honoured by the hot-loop pours (stage B6/B7).
5. Loss is not comparable between boards with different power opens: an open terminal carries no current.
