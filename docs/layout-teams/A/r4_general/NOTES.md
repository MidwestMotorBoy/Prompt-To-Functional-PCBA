# Worker `r4_general` (team A, round 4): the copper rules as one general add-on

All numbers are split-zone copper from scorecard runs in `runs/`. "allowed" = power_open is 3V3@L201 and
GND@J301/J302 only.

## What was built (all in `docs/layout-teams/A/r4_general/`)
- `copper_rules/plan_rules.py`: ONE planner entry point. It imports the stock `tools/copper/plan_copper.py` and adds
  15 rule classes (12 kept, 3 rejected) behind their own options. Each class has a name (= option), a default, a
  status, its parameters and a docstring that states the rule in board terms. `--list=1` prints the table,
  `--stock=1` turns every rule off, `--rules=<file.json>` reads a rules file, `--<rule>=0|1` and
  `--<rule>_<param>=V` override it.
- `copper_rules/split_zones.py` (= `A/tools/split_spec.py`, importable), `copper_rules/bus_layer.py` (generalised
  `strapfix/tools/bus4.py`: net, source layer, target layer and box derived from the plan, the router's layer list
  and the constraints), `copper_rules/score_rules.sh` (copy of `A/tools/score_board_best.sh` driven by
  `--rules=<file>`; same outputs and routed-board checks; hot-loop list from constraints.json; softnets derived;
  `--check=<script>` and `copper_rules/checks/*` add checks that print `CHECK {json}` into score.json),
  `copper_rules/checks/plan_summary.py` (which rules ran, which ICs pinesc picked), `copper_rules/README.md`.
- `monolith.rules.json` (board data: input paths, and ONE tuned value, the In4 copy box), `general.rules.json`
  (same, box derived), `tools/spec_diff.py` (plan comparison), `tools/dcq.sh` (2-min power check of one plan),
  `upstream.diff`, `SKILL-NOTES.new.md`, `score.json` / `F.png` / `B.png` (regression run, = runs/sc_pkg).

## Regression (acceptance test)
`copper_rules/score_rules.sh runs/sc_pkg ../best_placement.json --rules=monolith.rules.json --route=0` against
`lead_final/sc_Z`:
- `tools/spec_diff.py runs/sc_pkg/spec.json ../lead_final/sc_Z/spec.json` -> **IDENTICAL** (94 zones, 380 tracks,
  379 vias; every ring, track and via equal to 1e-4 mm). The final code (after the two round-4 rules below were
  added) was planned again on the same bare board and diffed: IDENTICAL too (`runs/pkg_walled/plan_final.log`).
- Scorecard: same numbers as sc_Z (table below). The GHOSTFAIL list is the same 5 edges.
- `dc.json` and `hot.json` differ from sc_Z only in low digits: KiCad's zone filler does not give bit-identical fills
  (21 net/layer fills differ in vertex count, largest area difference 0.05 mm2). The F.png / B.png renders show the
  same copper (Read both, next to docs/layout-teams/A/F.png and B.png); 3171 / 194 pixels differ, all at net-name
  labels, which render.py puts at the fill piece with the most vertices.

## Results
| variant | board | power_open | DRC | hot loops | blocked | loss W | full route |
|---|---|---|---|---|---|---|---|
| reference lead_final/sc_Z | best placement | allowed | 0 | 7 of 7, 6.24 nH | 5 of 369 | 0.835 | PC 352 / 17 failed of 369, 92.2 min, done |
| **package, monolith.rules.json** (runs/sc_pkg) | best | allowed | 0 | 7 of 7, 6.24 nH | 5 of 369 | 0.835 | not needed: spec IDENTICAL to sc_Z |
| general.rules.json, box derived (runs/sc_gen) | best | allowed | 0 | 7 of 7, 6.23 nH | 5 of 369 | 0.834 | PC 348 / 21 failed of 369, 70.1 min, done; local 355 / 14 failed of 369 (about 61 min, 150 min cap), routed power_open 3V3@L201 only, routed DRC 0, routed loss 1.201 W |
| pinesc on every IC with 2+ power nets (select=all, runs/sc_all) | best | allowed | 0 | 7 of 7, 6.23 nH | 9 of 373 | 0.824 | not queued (4 worse) |
| general.rules.json, first version (runs/sc_hand_v1) | hand (template) | allowed + PP5V@U401 + **AC_SNS_N@R424, AC_SNS_N@R524, GND@U404** | 0 | not run | 40 of 380 | 0.858 (opens) | |
| **general.rules.json, final code** (power_first + joinfix hot_fallback, runs/sc_hand) | hand (template) | allowed + PP5V@U401 (= hand reference) | 0 | 7 of 7, 6.83 nH (hand-copper reference 8.15 nH) | 45 of 381 | 1.155 | not queued |
| hand reference, stock planner, split (A REPORT) | hand | allowed + PP5V@U401 | 0 | not run | 58 of 422 | 1.36 | PC 363 / 59 failed of 422 |
| stock planner + bus layer, planner only + dcq (runs/hand_diag s0) | hand | allowed + PP5V@U401 | 0 | | | 1.148 | |

Code versions: sc_pkg, sc_gen, sc_all and sc_hand_v1 ran before `power_first` and `joinfix_hot_fallback` were added;
sc_hand ran with the final code. On the best placement the final code's plan is IDENTICAL to sc_pkg's (so sc_pkg and
sc_gen stand for the final code); sc_all was not re-run with it.

## What remains board data in monolith.rules.json, and why
1. Paths of this board's inputs (`board.constraints`, `template`, `netlist`, `power_gate` limit files, `hand_hot`).
   They say where the data is; no rule reads a value from them that is not in constraints.json.
2. **The In4 copy box `"96,100,122,140"`.** It was tuned by strapfix in round 3 on routed loss (fastcu screens).
   The derived box (`"box": "auto"` = pads of the bus net's series terminals carrying >= half its current, grown
   by the band width) gives `91.5,102.95,123.51,119.28` here: same blocked edges and hot loops, loss before routing
   0.834 W against 0.835 W, In4 copy 614 against 659 mm2. Whether it is as good after routing is only visible on a
   routed board (see the local route of sc_gen below). So the tuned box stays as board data for the exact
   regression, and `general.rules.json` (auto) is the default for a new board.
3. Nothing else: no ref list, no net name, no layer name. pinesc's `--pinesc_refs=U501` is gone (next section);
   the bus net (PACK_P), its source layer (In2), the target layer (In4), the return net (GND) and its fill layer
   (B.Cu) are derived; the router softnets `GND,PACK_P,3V3` are derived from spec.json (return net + plan buses).
   The band width 3 mm is the rule's default (strapfix measured w = 3, 4, 6, 10), not board data.

## pinesc: why the port-2 PD chip and not port 1 (the general predicate)
portcu found pinesc on U501 only = 5 of 369, on U401 + U501 = 7 of 371, on all pins worse. The two PD chips are
placed as copies, so a per-chip geometric property (pin count walled, pins near a power pad) is the same on both;
the near-power candidate pins are the same 8 numbers on both chips. The difference is the copper around them: on
port 2 the planner sends PP5V over a B.Cu detour under U501's north pin row, and with the VBUS stem on F.Cu the CC
pins 28/29 have no way out on either layer. On port 1 PP5V stays on F.Cu and the same pins can leave.
So the predicate is a property of a first plan, not of the part: `select=walled` plans once without pinesc and
picks the ICs with at least one candidate pin in a closed pocket (free cells at least the clearance from every
other net's copper, connected to the pin, reach < 3 mm and hold no via site on both outer layers). On the best
placement it finds exactly U501.28 and U501.29 and so selects U501 (all 8 candidate pins reserved, as the hand-picked
list did): the spec is IDENTICAL. Tried first and rejected: a straight-strip via-site test (flags U401, U403, U404,
U501, U503, U504 alike) and pockets with a 0.05-0.1 mm track (flags U401.17, U404.2, U504.2 too); only the
"any opening" pocket (room >= 0) separates them. Cost: one more planner run (about 70 s) when pinesc is on.
`select=all` (every IC with pins of 2+ >= 1 A power nets: U401, U403, U501, U503) is 9 of 373: it blocks both
bootstrap taps C412/C512 -> SW1 and leaves two GND pin-pair tracks floating. Recommended default: `walled`.

## Two rules added in round 4 (found by the hand-placement test)
The first hand-placement run opened three power terminals that the stock planner joins. Planner-only ladder on the
hand bare board (`runs/hand_diag/ladder.txt`, power checked with `tools/dcq.sh`, `dcq.txt`):
- `gate_escape`/`sealed` reservations (gate resistors R444/R446/R447 sit inside the hand board's loop hulls) cut
  the 5 A AC_SNS_N tree: R424 and R524 (the sense resistors) "no path". -> **`power_first`** (default on): when a
  series terminal of a power net is lost, plan once without reservation rules; reservations that touch that net's
  copper there are withheld; plan again. On the hand board 5 reservations were withheld and AC_SNS_N joined as in
  the stock plan. On the best board no series terminal is lost, so it does nothing (spec IDENTICAL).
- `joinfix` left the 5 V buck's PGND pin U404.4 (a hot-loop return pin) without a join. -> **`joinfix_hot_fallback`**
  (default 1): a hot-loop return pad whose escape-room join fails gets the stock tight join. Hand board: U404.4
  joined. Best board: never triggers (no hot-loop return pad is left).
Final code on the hand board, full scorecard (runs/sc_hand, hot loops on): power_open = allowed + PP5V@U401 (= the
hand reference), DRC 0, 7 of 7 tier 1 at 6.83 nH, blocked 45 of 381 (stock planner, split: 58 of 422), 1.155 W
(stock 1.36 W; the stock planner + bus layer alone gives 1.148 W, so the loss gain is the bus layer and fill, not the
rules). The two safety rules cost 5 blocked edges there (first version 40 of 380 with three power opens). pinesc
`walled` picked U404 (the port-1 5 V buck) on this placement, no PD chip.

## Hardcoding grep (package code: copper_rules/*.py, *.sh, checks/*)
```
$ grep -nE 'U[0-9]|J[0-9]|PACK_P|Monolith|monolith' copper_rules/*.py copper_rules/*.sh copper_rules/checks/*
(no output, exit 1)
$ grep -nE '\b[0-9]{2,3}\.[0-9]+ *, *[0-9]{2,3}\.[0-9]+|\b[0-9]{2,3},[0-9]{2,3},[0-9]{2,3}' copper_rules/*.py copper_rules/*.sh copper_rules/checks/*
(no output, exit 1)
```
Layer names appear only in docstrings and in the scorecard's F/B render step. README.md (documentation) names the
reference board in its "measured" column on purpose. Part kinds come from reference-designator letter prefixes
(`CLASSES`: connector J/CN/X, ic U/IC, transistor Q), as the stock roles.py does; a board with other prefixes sets
`"classes"` in its rules file.

## Stock functions overridden (RulePlanner(pc.Planner)) and why
Every override calls the stock method; only `grow_step` copies stock code.
| stock method | override | why |
|---|---|---|
| `__init__` | stock, then each rule's `setup()` | reservations (gate_escape/sealed, pinesc, connesc) must exist before any copper |
| `run` | sets grow to 1e-9 when taps is on and grow is 0 | taps hang off the grow step |
| `hot_loops_step` | rules' `before_loops()` first | gndpair / epstrip tracks are drawn before any power copper |
| `net_step` | stock, then `after_net()` | directjoin |
| `return_step` | hides pads served by rule tracks (epstrip) from the stock step | no via search / return join for them |
| `return_join` + `path` | tight=False while return_join runs; tight retry for hot-loop pads | joinfix + hot_fallback |
| `room` | stock, then rules' `room()` | gndesc |
| `clip_others` | stock, then the reservation cut, then rules' `clip()` | every rule's reservations, gndesc |
| `mirror_step` | stock, then `after_mirror()` | mirror_minw (rejected rule) |
| `grow_step` | stock when no grow rule is on; else `_grow_with_rules` (a copy of the stock loop with per-zone hooks) | nogrow_dead (and rejected nogrow_detour, grow_viaroom); then `after_grow()` = taps |
Name clash found: the stock Planner already has `self.reserve` (exit-lane raster); the add-on's method is
`keep_clear`. `upstream.diff` proposes the hooks (keep list honoured by clip_others, `join_tight`,
`return_served`, `room_extra`, `clip_extra`, `grow_frozen/base/cut`) so that the grow-loop copy and most overrides
go away, plus the one-line write_copper fix (one ZONE per outline). The diff was made against the stock files but
not run.

## Full routes
| name | board | queued (UTC) | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|---|
| r4_general-gen (`A/r4_general-gen-bd2e2df2.json`) | runs/sc_gen (general.rules.json, derived In4 box) | 00:10 | 348 | 21 | 369 | 70.1 | done (arrived about 01:22, 72 min after queueing) |

Local full route of the same board (`docs/layout-teams/A/tools/route_local.sh runs/sc_gen 150`, started 00:32,
finished 01:33): 355 routed / 14 failed of 369, routed power_open 3V3@L201 only, routed DRC 0, routed loss 1.201 W
(PACK_P 0.361, GND 0.357 W). Reference sc_Z: PC 352 / 17, local 351 / 18, routed loss 1.127 W (PACK_P 0.313, GND
0.330 W).

Reading: before routing the derived box is as good as the tuned one (0.834 vs 0.835 W, same blocked edges and loops).
After routing it is 0.074 W worse (1.201 vs 1.127 W; the smaller In4 copy leaves more PACK_P current on the cut
In2 pour), still joined and at the 1.2 W target. Route counts of the two boards differ by -4 (PC) and +4 (local)
failed edges although the router's layers (F, In2, In3, B) carry the same copper: that spread is router noise
between runs, not an effect of the In4 box. So: keep the tuned box for Monolith (board data, it is measured
better after routing), and use `"box": "auto"` on a new board until a routed-loss screen tunes it.
No route was needed for the package board itself: its spec is IDENTICAL to sc_Z (PC 352 / 17 failed of 369).

## Renders
Read runs/sc_pkg/F.png and B.png next to docs/layout-teams/A/F.png and B.png: the same board (port tops compact
under the USB-C connectors, PD chips with the VBUS stem and PPHV east, stages under the inductors, SW2 B.Cu pours
under the inductors as before). runs/sc_hand/F.png shows the hand placement's own layout (long PPHV/VBUS runs along
the left edge, as on the hand board).

## Cleanup
Deleted (literal paths): runs/sc_gen/routed.kicad_pcb, runs/sc_hand/cu.kicad_pcb, runs/sc_hand_v1/cu.kicad_pcb,
runs/sc_all/cu.kicad_pcb, runs/sc_gen/cu.kicad_pcb (queued copy is route_queue/r4_general-gen.kicad_pcb),
runs/sc_pkg/cu.kicad_pcb (its copper = sc_Z), and the template copies runs/*/in.kicad_pcb (sc_all, sc_gen, sc_hand,
sc_hand_v1, sc_pkg). `runs/exp_walled.py` is the experiment that chose the pinesc pocket test.
