# copper_rules: rule add-on for the stock copper planner

A small package that adds team A's copper rules to the stock planner `tools/copper/plan_copper.py` without copying
it. The rule code names no part, net or coordinate of any board. What is specific to a board goes in a rules file
(`*.rules.json`).

| file | what it does |
|---|---|
| `plan_rules.py` | the planner: imports the stock `Planner`, adds one class per rule, each behind its own option |
| `split_zones.py` | one zone per outline (KiCad keeps only the first outline of a zone on re-save) |
| `bus_layer.py` | protected copy of the high-current bus on a layer the router never routes, + soft return fill |
| `score_rules.sh` | the team scorecard driven by `--rules=<file.json>`; `--check=<script>` adds checks |
| `checks/` | every `*.sh` / `*.py` here runs as a check after scoring (pad_join_check.py, plan_summary.py) |

## Use it on a new board (numbered steps)
1. Declare the circuit in `constraints.json` (the circuit build writes it): power nets with `current_a` and `kind`
   (`power` / `switching`), hot loops (`supply`, `ret`, `switch_pins`, `caps`, high-frequency cap first), Kelvin
   resistors. The rules read only these roles plus pad geometry. Use standard reference prefixes (J connector,
   U/IC chip, Q transistor). If your board uses others, set `"classes"` in the rules file.
2. Copy `general.rules.json` (one level up) to `<board>.rules.json`. Set `board.constraints`, `board.template`,
   `board.netlist` and `board.power_gate` to your board's files. Leave every rule at its default.
3. Plan once and read the log:
   `python3 copper_rules/plan_rules.py bare.json constraints.json spec.json --rules=<board>.rules.json`
   Check `left to router`, `hot loops` and the `rules` line (what each rule did, e.g. which ICs pinesc picked).
4. Screen: `bash copper_rules/score_rules.sh <out> <placement.json> --rules=<board>.rules.json --route=0 --no-hot`.
   Read `score.json`: `power_open` first, then `drc_errors`, then `blocked_edges`.
5. Switch rules one at a time (`--plan="--<rule>=0"`) and diff the `GHOSTFAIL` lists of two screens
   (`diff <(grep -o 'GHOSTFAIL.*' a/ghost.log | sort) <(grep -o 'GHOSTFAIL.*' b/ghost.log | sort)`).
6. Candidate: the same command without `--no-hot`. Require every hot loop tier 1. Read `F.png` and `B.png`.
7. Full route: queue the outdir on the route PC, or `docs/layout-teams/A/tools/route_local.sh <out> 150`.
   Check `routed_power_open` before trusting a routed count.
8. Only if a tuned value really is board data (it cannot be derived), put it in the rules file with a `_why`.

`plan_rules.py --list=1` prints every rule with its default, status, parameters and statement.
`--stock=1` turns every rule off (= the stock planner). Command-line options override the rules file:
`--<rule>=0|1`, `--<rule>_<param>=V` (for example `--pinesc_select=all`, `--taps_far=4`).

## Rules
Measured column: blocked edges on Monolith's best placement, each rule added on top of the rows above it (team A
SKILL-NOTES section 5, split scorecard). All rules are on by default except the rejected ones.

| rule (option) | trigger (board-independent) | effect | default | measured on Monolith |
|---|---|---|---|---|
| (none, `--stock=1`) | | stock planner | | 29 of 400 |
| `gate_escape` | signal pad of a hot loop's discrete switch (transistor) inside the loop's supply/return pad hull | strip 0.6 mm wide, 0.9 mm out of the package in the freest direction, + via site (via + 0.25 mm); other power copper keeps clear | on | with sealed + taps: 24 of 396 |
| `sealed` | signal pad of any small part (<= 4 pads) inside a hot-loop hull | same strip + via site | on | (in the row above) |
| `taps` | small part's pad on a switching net, not a terminal, > 3 mm from the net's pour | MIN_W detour to the pour, drawn after the grow step | on | (in the row above) |
| `joinfix` | return pad with no via that needs a return join | the join keeps the signal escape room (tight=False); a hot-loop return pad whose join fails gets the stock tight join (`hot_fallback=1`) | on | 19 of 398 |
| `epstrip` | return pin of an IC (12+ pads, pin <= 0.45 mm) within 0.8 mm of its own exposed pad | straight / L / neighbour track into the EP before any power copper; return step skips the pin | on | 15 of 374 |
| `directjoin` | power terminal left "no path" with its net's copper <= 2 mm away | straight 0.5/0.3/0.2 mm track | on | 15 of 373 |
| `nogrow_dead` | outer pour piece < 3 mm2, no via, no track, only connector pads | not grown | on | 10 of 373 |
| `gndesc` | return pad (<= 0.65 mm, <= 1 mm2) of a connector or an IC with 8+ pads | gets the signal escape room | on | 9 of 371 |
| `connesc` | signal pad (<= 0.35 mm) on the edge of a connector with 6+ pads | 0.4 mm strip 1.0 mm straight out, kept free | on | 7 of 371 |
| `gndpair` | two return pins of one part (8+ pads) <= 0.55 mm apart | pin-to-pin track, one via serves both | on | with pinesc: 5 of 369 |
| `pinesc` | signal pin (<= 0.45 mm) within 1 mm of a foreign power pad of the same IC, on an IC chosen by `select` | pin-width strip 0.9 mm out + via site (via + 0.2 mm) on both outer layers | on, `select=walled` | walled picks the port-2 PD chip only: 5 of 369 (identical to the hand-picked ref list) |
| `power_first` | a series terminal of a power net left "no path" | plan without reservation rules; withhold reservations that touch that net's copper; plan again | on | best: no change; hand placement: AC_SNS_N R424/R524 joined again |
| `nogrow_detour` | pour that is only a detour corridor | not grown | off, rejected | 15 -> 15 of 373, +0.05 W |
| `grow_viaroom` | grown copper near fine-pitch IC signal pins on the other layer | keeps 1.0 mm clear | off, rejected | 5 -> 5 of 369 |
| `mirror_minw` | mirror piece thinner than 0.5 mm (2 area / perimeter) | dropped with its vias | off, rejected | 10 -> 10 of 373 |

`pinesc select`: `walled` (default) plans once without pinesc and picks every IC with at least one candidate pin in a
closed pocket: the free room connected to the pin (cells at least the clearance from all other copper) reaches
less than 3 mm and holds no via site. `walled_pins` reserves only those pins. `all` takes every IC with pins of two
or more >= 1 A power nets (on Monolith worse, see NOTES.md). `refs` takes the list in `refs` (board data).

Bus layer (`bus_layer.py`, rules file `"bus_layer"`): the router cuts soft inner bus pours; a copy on a layer the
router never routes (In4 on Monolith, derived from router.py's LAYERS and the hot-loop side) keeps the bus joined.
Monolith: loss before routing 1.035 -> 0.835 W, routed power joined (strapfix: routed 1.092 W against an open
PACK_P at 1.744 W without it). Net, source layer and target layer are derived; the copy box is derived (`auto`) or
board data.

## Add a rule
1. Subclass `Rule` in `plan_rules.py`: set `name` (= option), `default`, `status`, `params` (defaults, each becomes
   `--<name>_<param>`), `measured` (fill in after the screen).
2. Write the docstring as the rule in board terms: trigger (roles from constraints.json, pad geometry), the copper
   it adds or withholds, default numbers and where they come from. No refs, net names or coordinates.
3. Implement only the hooks you need: `setup` (reservations: call `P.keep_clear(net, layer, shape)`),
   `before_loops` (tracks drawn before any power copper: `P.draw_track`), `after_loops`, `after_net`, `detour_args`,
   `return_skip`, `after_return`, `join_tight`, `room`, `clip`, `mirror_hide`, `after_mirror`, `grow_prepare` /
   `grow_frozen` / `grow_base` / `grow_cut` (set `grows = True`), `after_grow`.
4. Append the class to `RULES` at the point of the order where it must run (hooks of one kind run in list order).
5. Screen it alone on top of the current stack (one option per screen), diff the GHOSTFAIL list, confirm all hot
   loops tier 1, and record before/after numbers in the docstring `measured` and in NOTES.md.
6. A check that the scorecard should run (for example a per-pad join check) goes in `checks/` or `--check=`; it
   prints `CHECK {"name": value}` lines that land in `score.json["checks"]`.

## Round-4 rules (ported in round 5, all default off; one rules-file entry each)
Measured column: the round-4 worker's screen on its own board (r4_vbus: best placement; r4_port1: v5 placement;
r4_bcu: stage-move placement), split scorecard. Each class reproduces its source planner spec-identically on that
worker's board (r5_general/NOTES.md, regression).

| rule (option) | trigger (board-independent) | effect | default / params | measured (round 4) |
|---|---|---|---|---|
| `gatevia` | gate_escape / sealed reservation of a discrete switch's signal pin | track + through via drawn at the reserved site; `chk=1` checks the via on exact shapes on both outer layers (slide out 0.05-0.8 mm, else drop) | off; chk 1 | HG gate routes on every PC route; without chk a turned FET gave 4 DRC errors |
| `gndtie` | return pin of an IC (8+ pads) left without a via by the return step, with pinesc on | one via placed with pinesc's raster margin relaxed (shapes still kept) | off | blocked 7 -> 5 (pin pair beside a reserved CC pin) |
| `padjoin` | pad of a 2-pad part on a power net, off its net's outer copper, copper within mm | 0.3-0.2 mm straight or L track after the grow step | off; mm 4 | FB-divider stub no longer fails |
| `padpair` | series terminal with 2+ pads, some off the main piece (source terminal with several pad groups of which the plan feeds only some) | in-pad vias + strap on the other outer layer (mode 2), pad-to-pad bridge (live 1) | off; mode 2, live 0, w 0.8..0.4 | VBUS dead pair joined, 5 -> 5 blocked, -0.002 W, PC 17 -> 16 failed |
| `capjoin` | shunt terminal pad (cap) off its net's main piece | existing island via + link / same-layer link / new vias + link, rolled back if it fails | off; vias 2, len 16 | bottom-side bulk cap joined (12.6 mm strap), blocked 4 -> 4 (r5_merge) |
| `ret_band` | discrete-switch hot loop with < vias return vias at its return-pin row | return band mm deep out of the row + return vias | off; mm 1.6, vias 4 | HL_OUT 0.98 -> 0.83 nH, 0.857 -> 0.789 W |
| `tap_max` | switch-node tap longer than the stock 10 mm detour limit | taps allowed up to mm | off; mm 16 | bootstrap tap drawn instead of a blocked edge |
| `sw_nogrow` | switch-node detour zone (kinds = detour) | not grown | off | +0.028 W, SW B.Cu 84.9 -> 27.7 mm2 (forced detour only) |
| `pw_nogrow` | non-switching power detour zone | not grown | off | +0.010 W, 27.8 -> 3.3 mm2 per port |
| `stub_nogrow` | via-stub zone on the other outer layer (other-side terminal) | not grown | off | part of k1 (B.Cu 325 -> 157 mm2) |
| `mirror_skip_supply` | supply nets of discrete-switch hot loops | no mirror copy | off | +0.031 W, B.Cu -56 mm2, blocked same |
| `mirror_maxa` | piece the mirror step added, < mm2 | dropped with its vias | off; mm2 10 | bus-net loss 0.1348 -> 0.1335 W |
| `sw_detour` | switch-node detour inside its net step | corridor width w / vias per end | off, untested | not screened |
| `connesc_big` | connector signal pad 0.35-0.9 mm on the outer row | strip + via site | off, **rejected** | opened a 10 A cell-path pour (CELL_P at its fuse) |
| `mirror_minw2` | added mirror piece thinner than mm | dropped | off, **rejected** | dropped the cell-path mirror, +0.05 W |

`pinesc twins=1`: with select walled / refs, an IC that is a translated copy of a selected IC *together with its
signal neighbourhood* (same footprint, rotation, side; every part sharing a signal net with a pad within twin_d = 3 mm
at the same offset within 0.15 mm, both ways) gets the same reservations. It picks port 1's PD chip on the r4_port1
and merged placements (port-1 cluster copied from port 2) and not on the best or k1 placements (cluster differs), which
is exactly where round 4 measured pinesc on that chip as a gain or a loss.

## Hook order (one order reproduces all three round-4 planners)
The three round-4 planners each overrode `grow_step`; the package runs them as hooks around one grow loop:
1. `__init__` -> `setup()` in RULES order: gate_escape/sealed, pinesc (records its reservation mask for gndtie),
   connesc, connesc_big, gatevia (needs gate_escape's report, after every reservation).
2. `hot_loops_step` -> `before_loops()` (gndpair, epstrip) -> stock loops -> `after_loops()` (ret_band).
3. `net_step(net)` (sets `_in_netstep`; `detour()` asks `detour_args()`: sw_detour) -> `after_net()` (directjoin).
4. `return_step` (return_skip: epstrip) -> `after_return()` (gndtie) ; `return_join` -> joinfix.
5. `mirror_step`: `mirror_hide()` pops nets from the power list (mirror_skip_supply), the pre-mirror zones are
   recorded, stock mirror, nets restored, then `after_mirror()` in order mirror_minw (rejected), mirror_maxa
   (mirror_minw2 in the same pass).
6. `grow_step`: `grow_prepare()` (nogrow_dead dead pieces; sw/pw/stub_nogrow and nogrow_detour frozen sets, decided
   before the loop from zone kinds), the hooked loop (frozen zones skipped like mirror copies; nogrow_dead base/cut),
   then `after_grow()` in RULES order: **taps** (with tap_max's limit) -> **padjoin** -> **padpair** -> **capjoin**.
   This is the order of the merged planner M (B tags -> P grow + A taps -> Q padjoin -> V padpair -> M capjoin):
   padpair sees padjoin's stubs as obstacles, capjoin sees padpair's straps, and none of them is ever grown.
7. power_first re-plans (whole plan) when a series terminal is lost.
Shared helpers (`cu_pieces`, `net_state`, `main_on`, `link_obs`, `link_to`, `via_sites_exact`, `snap`/`restore`)
are the r4_vbus / r5_merge exact-shape piece and link code.

## Checks
`checks/pad_join_check.py` (from r4_vbus): per-pad power join of every power and return net on the scored board, and on
routed.kicad_pcb when a full route saved one. Allow list = rules file `"pad_join": {"allow": {net_substring: [REF |
REF.PAD]}}` (board data). score.json gets `pad_unjoined` (not allowed), `pad_unjoined_all`, `routed_pad_unjoined`.
Single-board use: `pad_join_check.py <board> <cu_dump.json> <constraints.json> [out.json] --allow=<file>`.
