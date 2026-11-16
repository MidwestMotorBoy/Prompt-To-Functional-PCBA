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
| `checks/` | optional: every `*.sh` / `*.py` here runs as a check after scoring |

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
   `before_loops` (tracks drawn before any power copper: `P.draw_track`), `after_net`, `return_skip`, `join_tight`,
   `room`, `clip`, `grow_frozen` / `grow_base` / `grow_cut` (set `grows = True`), `after_mirror`, `after_grow`.
4. Append the class to `RULES` at the point of the order where it must run (hooks of one kind run in list order).
5. Screen it alone on top of the current stack (one option per screen), diff the GHOSTFAIL list, confirm all hot
   loops tier 1, and record before/after numbers in the docstring `measured` and in NOTES.md.
6. A check that the scorecard should run (for example a per-pad join check) goes in `checks/` or `--check=`; it
   prints `CHECK {"name": value}` lines that land in `score.json["checks"]`.

Round 4 rules from other workers go in as one class each:
(round 4: r4_vbus / r4_port1 / r4_bcu result goes here)
