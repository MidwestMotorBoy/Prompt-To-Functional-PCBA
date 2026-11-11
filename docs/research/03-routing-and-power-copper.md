# Track 3: routing and power copper

Research agent report, 2026-11-11. Scope: 2 to 6 layer power-electronics and mixed-signal boards, 50 to 500 parts,
JLCPCB rules, KiCad 9/10 output, an LLM driving deterministic engines. Claims are marked **[ran]** (I ran the code
in this container), **[read]** (I opened the primary source), or **[inferred]**. Small scripts and run notes are in
the sibling folder `03-routing-and-power-copper/`.

## 1. Recommendation

Route by net type behind one engine-neutral contract, and keep the Battery-Bank check loop as that contract.

1. **Keep** the Battery-Bank harness: copper dump, spec-and-step edits, real KiCad DRC as the verdict, the DC, loop
   and coupling solvers, the tidiness measure, accept-or-revert, the protected-net list.
2. **Build** the missing piece: a power-copper generator (pours, via arrays, Kelvin taps from declared currents),
   grown and trimmed against the DC solver that already exists.
3. **Construct** critical nets (gate drives, Kelvin pairs, hot-loop capacitors, feedback) from templates, several
   candidates per block, scored by the solvers.
4. **Adopt** an existing engine for the remaining plain signals. Start with Freerouting 2.5/2.6 headless. Do not
   extend `router.py` into the bulk router, and do not write a new one.
5. **Keep** `tidynet.py`, `runwidth.py` and `ml.py` as the cleanup and repair tools, with net roles read from the
   schematic.

The LLM writes the constraint file, orders work and picks repairs from a short menu. It never emits coordinates.

**Runner-up:** KiCadRoutingTools (MIT, Python + Rust) as the single routing and plane toolkit. It already has block
routing, power widths with neck-down and plane tools, but it has no shove and I could not run it here.

## 2. Options compared

| Option | Maturity, last activity | Licence | How an LLM uses it | What it checks itself | Token cost | KiCad / JLCPCB fit | HV / power fit | Needs from a human |
|---|---|---|---|---|---|---|---|---|
| **Battery-Bank `router.py`** (grid A*, 0.05 mm) | One board, Nov 2026. Six generations in the folder | Project's own | Shell flags and regexes; hand spec files for what it cannot close | Own clearance marking; real DRC after | High last time: the layout phases cost $231 of agent spend | Uses `import pcbnew` (SWIG), which the Freerouting team's KiCad research note says is removed in KiCad 11 | Knows the 0.25 mm high-current rule, pour cost, switching keep-away. Net lists typed in | Coordinates for power stages; objections by eye |
| **Battery-Bank `tidynet` / `runwidth` / `ml.py`** | Same | Same | One command per net or per board, JSON spec out | Pour piece count, exact clearance, then real DRC | Low: batch, numeric result | Plain Python on a JSON dump; KiCad only applies the spec | Protects pours and switching copper | Protected list with reasons |
| **Freerouting 2.5.0** (2.6.0 in release candidates) | Release built 2026-10-05; commit 2026-11-10. One maintainer, self-limited to about 4 h/week | GPL-3.0 | CLI: DSN in, SES out, JSON result manifest, KiCad-format DRC JSON, `.rules` file. Also REST API and an MCP server | Completion, clearance violations, own score | Very low: one command, a few log lines | DSN/SES round trip. Custom `.kicad_dru` rules and edge clearance do not travel in DSN | Net-class width and clearance, priority and ignored classes, plane nets. No current, no physics, no pair routing | Nothing per run. Review of result |
| **KiCadRoutingTools (KRT) 0.23.9** | Commit 2026-11-09. 5,880 commits, one main author, heavy AI-agent use | MIT | CLI on `.kicad_pcb`; routing plans as JSON; ships Claude Code skills | Own DRC, connectivity and hygiene checkers; `kicad-cli` DRC as oracle | Low to medium (its skills are prompt-heavy) | Native `.kicad_pcb`, KiCad 9 and 10, reads net classes and `.kicad_dru` | Power widths with neck-down, plane pours, thermal via arrays, stitching, plane resistance report | Same |
| **KiCad push-and-shove via PCBWorld-Engine** | v1.1.1, 2026-10-21, LG AI Research | Engine GPL-3.0, wrapper BSD-3 | Gymnasium API: select net, start, line to (x, y), end. Each step checked by KiCad DRC | KiCad's own DRC per step | High if the LLM drives each segment: 231 s per small board with GPT-5.4 | A fork of KiCad 9.0.8. Monolith is a KiCad 10 file | Paper says zones are not represented in the routable space | Nothing; research code |
| **Topola** (topological, Rust) | Last commit 2026-07-02, no releases, "work in progress" | MIT | Not usable headless yet [inferred] | Unknown | n/a | DSN shown in screenshots | None | n/a |
| **tscircuit capacity-autorouter** | Active, 2,845 commits | MIT | JSON in, JSON out, npm | Own DRC; its wiki lists 37 inputs with DRC issues | Low | No KiCad or DSN input documented | No net classes or pours documented | A converter we would write |
| **OrthoRoute** (GPU PathFinder) | v1.0.0, MIT | MIT | KiCad 10 IPC plugin or headless files | Grid pitch stands in for clearance | Low | KiCad 10 | Author: "not a general-purpose PCB autorouter". 1 to 2 % clean pass on ordinary boards in PCBWorld | n/a |
| **DeepPCB** (cloud, RL) | Commercial, active | Closed | Upload `.kicad_pcb`, download routed board; KiCad plugin | DRC only | Low tokens; pay per board, price not published on the pages I opened | Takes and returns `.kicad_pcb` | Vendor: sweet spot up to 4 layers and about 800 pins; "does not consider constraint satisfaction (except DRC rules)" | Upload of the design to a third party |
| **Quilter** (cloud) | Commercial, active | Closed | Upload; candidates come back | "Physics rule checks" per candidate | Low tokens; usage-priced by pin count | Says it is not a CAD tool and does not edit board files | Power-supply blog posts only; no primary detail found | Upload; constraints in their format |
| **Allegro X AI, Zuken, Flux, JITX** | Commercial | Closed | Inside their own tools | Their own | n/a | None output a native KiCad project | Allegro X AI synthesises power planes inside Allegro | Different toolchain |
| **New Rust engine (Gemini PDF plan)** | Does not exist | Ours | Whatever we build | Whatever we build | Very high to build | Ours | Ours | Months of agent time before the first board |

## 3. Evidence per option

### 3.1 The Battery-Bank router and cleanup pass

**What it is [read].** `tools/battery-bank/groundup/router.py` (78 kB, the sixth generation; `router_v2` to `v6`
sit beside it) is an A* maze router on a 0.05 mm grid over four of the six layers (F, In2, In3, B; In1 and In4 are
ground planes). It loads the board through `pcbnew`, marks obstacles by exact distance for tracks and vias and by
raster plus margin for polygons, routes one connection at a time with rip-up, and has a continuation mode that
re-routes nets named in the last DRC report. Power pours, via arrays and Kelvin taps were not routed at all: they
were typed as coordinates in `copper.py` through four helpers in `cu.py` (`Z` zone, `T` track, `V` via, `VG` via
grid), one polygon at a time. `ml.py` is a small exact-clearance link search for one hand repair. `tidynet.py` rips
up one net and redraws it as a single tree with bend, via, pour and switching-copper costs; `tidyall.py` runs it over
the plain signal nets with an accept rule; `runwidth.py` gives each run one width.

**Measured results [read, from the two READMEs; all modelled, nothing powered].**

- First scripted board: DRC clean, but hot loops up to 60 % more inductance than the hand board, gate loops 49 %
  more, 14 signals over 10 mV per switching edge against 2.
- After two solver-guided fix passes: level or ahead on loop inductance, copper loss and via current; still 258 mm
  of signal track cut into ground planes against 34 mm, a placement decision.
- Tidiness on the same 144 signal nets, hand board / script board / after cleanup: length over shortest tree
  1.20 / 1.54 / 1.46; bends 1044 / 2861 / 1837; signal vias 171 / 351 / 310; nets over twice their shortest tree
  0 / 17 / 12. The cleanup pass improved every line and closed about a quarter of the gap.
- Four real faults passed DRC and were found only by solvers. Three were signal tracks or vias damaging a power path.

**Speed and cost [read].** The cleanup pass took about 15 minutes for 94 nets, single-threaded Python (sweep 1 logged
889 s; single nets 10 to 55 s). `compare/worklog.json` gives the agent cost: 18.1 hours, 1,601 turns, $263 in total,
of which the first layout was $129, fix pass 1 $66 and fix pass 2 $36. Cache-read input was 396 million tokens against
2.3 million output tokens: the cost was long conversations re-read on every turn, not generation.

**General:** the JSON dumps, the spec-and-step loop, exact-distance marking, pad escapes, the pour piece-count
screen, the tidiness measure, the cleanup and width passes, accept-or-revert, the protected list.
**Monolith-specific:** net-name regular expressions for switching, plane and high-current nets (`SWN`, `HC`,
`PLANE` at the top of `ml.py` and `tidynet.py`), the layer list, via size, clearances, the sealed Kelvin pads in
`router.py`, and every coordinate in `copper.py` and the `hand*/` folders.

**Why not extend it into the bulk router.** Its own skill names the ceiling: "one net at a time", no shove, no
group rip-up, no bundles, no block mode. The search core is Python and tied to SWIG `pcbnew`. Two maintained open
engines already do the plain-signal job faster. The parts worth keeping are the parts no other engine has: the
checks, the costs learned from the solvers, and the cleanup pass.

### 3.2 Freerouting

**Status [read, ran].** Version 2.5.0, built 2026-10-05 (jar manifest); 2.6.0 release candidates are in the nightly
benchmark; last commit on `master` 2026-11-10. GPL-3.0. Java 25 is required (`build.gradle`; the 2.5.0 jar is built
with Temurin 25). The README carries a maintenance notice: the maintainer limits himself to about 4 hours a week,
releases every 2 to 3 months, pull requests before issues. The project is alive but has one person behind it.

**Interfaces [read].** CLI (`-de board.dsn -do board.ses`, optional `.rules` file, `-drc` writes a DRC report in
KiCad's JSON schema, `--router.result_json` writes a machine-readable manifest), a REST API (hosted or
self-hosted), a Python client on PyPI (`freerouting-client` 2.3.0), and an MCP server on npm. Settings include
`max_passes`, `item_order_seed`, `via_costs`, `plane_via_costs`, `start_ripup_costs`, per-layer preferred direction
and cost, `ignore_net_classes`, `priority_net_classes` (routed first and not ripped up by others), `plane_nets`,
`plane_as_obstacle`, `automatic_neckdown`, and a job timeout. Usage analytics are on by default and are switched
off with `usage_and_diagnostic_data.disable_analytics`.

**What it honours [read].** Net classes with width and clearance and the via padstack per class (seen in the DSN
fixture: `(class Power BAT+ "BAT-" VIN (circuit (use_via ...)) (rule (width 300) (clearance 100)))`), keep-outs,
layer direction. Differential pairs are detected by name but pair routing is described in `docs/architecture.md` as
a "future extension point", so pairs are routed as two single nets. The autorouter pass is single-threaded; the
maintainers measured three parallel schemes and removed all three
(`docs/research/large-board-autorouter-performance.md`).

**KiCad round trip [read].** The stable path is DSN out, SES in, through `pcbnew.ExportSpecctraDSN` and
`ImportSpecctraSES`. The project's own KiCad note records that the DSN export omits copper-to-edge clearance (their
issue 558). Custom rules in `.kicad_dru` (for Monolith, the 0.25 mm high-current to signal rule) have no DSN
equivalent [inferred]. The same note states that KiCad 10.0.0 was released 2026-03-20, that the SWIG bindings are
deprecated and to be removed in KiCad 11, and that the IPC API needs a running GUI in KiCad 9 and 10. KiCad's own
developer page confirms the last point: "The IPC API in KiCad 9 and 10 only supports communication with a running
instance of the KiCad GUI" and "Support for running in headless mode through `kicad-cli` was added for KiCad 11".

**Independent and self-reported quality [read].**

- PCBWorld (LG AI Research, KDD 2026 workshop) ran Freerouting 2.1.0 against KiCad's own DRC on real open-source
  boards. "Clean pass" means fully connected and zero error-level violations: 0.80 on 99 small boards (D3-A), 0.78
  on 10 larger boards (D3-B), mean 7 to 10 s per board. It was the strongest rule-based router in the study.
- Freerouting's nightly report of 2026-11-10 (1,142 PCBench boards, Ryzen 5 3600): fully routed with zero clearance
  violations on 36 % of boards for 1.9.0, 75 % for 2.5.0 and 90 % for 2.6.0-RC10. On the 141 "complex / multi-layer"
  boards: 50 % for 2.5.0, 77 % for 2.6.0-RC10. This is the project's own DRC on DSN, not KiCad's.
- A student's two-month study posted on the KiCad forum (October 2026) compared a negotiated-congestion router he
  wrote with Freerouting on three boards: Freerouting gave 8 to 12 % shorter tracks, 70 to 97 % fewer vias, in
  about 12 seconds against hours.

**What I ran [ran].** Temurin JRE 25 unpacked in the scratch folder, `freerouting-2.5.0.jar`, headless, 4 cores.

| Board | Result | Time |
|---|---|---|
| PCBench `z2amiller_sensorboard`, 2 layers, 25 parts | 0 unrouted, 0 violations. 463 mm of track against 334 mm on the human reference, 13 vias against 14 | 22 s wall (2 s routing, 17 s optimiser) |
| `Issue367-Charger`, 2 layers, a small battery charger with many small pours | Stopped with 11 connections unrouted and 2 violations. 8 of the 11 are on the `Power` class nets (BAT+, BAT−, VIN), which the original board connects with pours | 13 s |
| `Issue145-smoothieboard`, 4 layers, 804 SMD pins, an Eagle-exported bug-report fixture | Did not converge. Fanout escaped 594 of 804 pins. Best state was pass 1 with 115 of 340 connections open; passes 2 to 14 oscillated around 225 open. 42 violations throughout | Stopped by me after 18 min (fanout 133 s, pass 1 209 s) |

Both failures are bug-report fixtures, so they are worst cases, and this container gave Java 3.4 GB and 4 cores.
The third run still shows that completion on a dense 4-layer board is not assured and that a failed run can burn
many minutes going nowhere, so the harness needs a stagnation cut-off. The charger shows the failure that matters to us: Freerouting
routes tracks. Where a human would pour copper, it either leaves the connection open or draws a class-width track.
The first board shows the other known trait: complete and legal, and 39 % longer than the person's routing (the
reference file itself has open connections, so the comparison is rough).

**Failure modes.** Power nets as thin tracks or left open; no notion of current, loop, return path or aggressor;
pairs not coupled; DSN drops custom rules; long fanout stages on dense boards (their own profile: 899 s of fanout
on an 8-layer board); one maintainer.

### 3.3 KiCadRoutingTools (KRT)

**What it is [read; not run].** `github.com/drandyhaas/KiCadRoutingTools`, MIT, version 0.23.9, last commit
2026-11-09. About 180,000 lines of Python and a 6,600-line Rust A* core, 5,880 commits. It reads and writes
`.kicad_pcb` directly and takes widths, clearances and via sizes from net classes and `.kicad_dru`. Features that
match the Battery-Bank wish list: routing one placement block (`--group`, by schematic sheet, KiCad group or an IC
with its decoupling), bus detection and bus corridors, guide corridors and keep-outs drawn on a user layer,
proximity penalties, rip-up and re-route with blocker analysis, power nets at their own width with neck-down at
fine-pitch pads and a taper, plane pours with thermal via arrays under exposed pads, area stitching, repair of
disconnected plane regions, and a plane resistance and maximum-current report. It ships Claude Code skills
(`/plan-pcb-routing`, `/analyze-power-nets`, `/diagnose-routing-failures`, `/review-routed-board`) and routing
plans as JSON files that run headless. Stated limits: "No push-and-shove (routes around obstacles, doesn't move
them)", no blind or buried vias.

**Independent result [read].** In PCBWorld (an older pinned version) KRT scored 0.74 clean pass on the small real
boards, close to Freerouting, and 0.20 on the larger ones, well behind. It was faster (0.65 s and 3.3 s).

**Why it is the runner-up and not the pick.** I was not allowed to run it in this container (it downloads a
prebuilt binary). The codebase is very large, changes daily and is mostly one author working with agents, so its
behaviour is hard to pin. On larger boards the only independent number is poor. It is, however, the closest thing
to what the Monolith skills ask for, it is permissively licensed, and it does not depend on SWIG.

### 3.4 KiCad's push-and-shove router

Stock KiCad does not expose the interactive router to scripts: the IPC API page lists no router calls, and the API
needs a GUI until KiCad 11 [read]. PCBWorld-Engine is a GPL-3.0 fork of KiCad 9.0.8 that does expose it: an agent
selects a net, starts a route and draws lines in a chosen routing mode, and every step is checked by KiCad's DRC
[read]. That is the shove the Monolith skill asked for. Two limits: it is KiCad 9, and the paper states that copper
pours are not represented in the router's space. It is a candidate for the repair step later, not for v1.

### 3.5 Other open engines

- **Topola** [read]: Rust, MIT, topological, NLnet-funded 2023-10 to 2025-06, last commit 2026-07-02, no tagged
  release, self-described work in progress. Not ready.
- **TopoR** [read, Wikipedia only]: commercial, Eremex; the last version listed is from 2017. I could not confirm
  it is still sold. The gEDA "toporouter" was not checked and I found no sign of life.
- **tscircuit** [read]: MIT, active, its own JSON format, no KiCad input documented, no net classes or pours.
- **OrthoRoute** [read]: GPU PathFinder on a Manhattan lattice for backplanes. Its README quotes PCBWorld: 1 to 2 %
  clean pass on ordinary boards. Not for us.
- **JITX**: has its own router inside a code-first tool; I found no primary description of the method.

### 3.6 Commercial AI routers

- **DeepPCB** [read, vendor pages]: reinforcement learning; accepts `.kicad_pcb` and returns one; "sweet spot" up
  to 4 layers and about 800 pins, public plugin up to 1,200 airwires; median run 4.6 minutes, 90th percentile 153
  minutes; pay per board, price not on the pages I opened. Their benchmark "does not consider constraint
  satisfaction (except DRC rules)". Nothing on current, pours or loops.
- **Quilter** [read, vendor docs]: explores candidates and stack-ups and runs "Physics Rule Checks against each
  candidate in parallel"; usage-priced by pin count; states it is not a CAD tool and does not edit board files. The
  documentation page I reached does not mention reinforcement learning, KiCad, current or high voltage.
- **Cadence Allegro X AI** [read, vendor page]: placement, "Auto-Synthesis of Power and Ground Planes", routing of
  critical nets, cloud compute, inside Allegro only.
- **Flux, Zuken**: nothing found that outputs a native KiCad project. Not pursued.

None fits "native KiCad project, one person, any LLM, HV in scope". DeepPCB is the only one that could be dropped
in as an alternative bulk engine, at the price of uploading the design.

### 3.7 Academic work

- **PCBWorld** (arXiv 2607.05915) is the most useful paper for this project. Beyond the router numbers above: LLM
  agents driving the router segment by segment reached 0.65 clean pass on small boards (GPT-5.4) and 0.00 on the
  ten larger ones, at 231 s and 866 s per board. Letting the LLM write track coordinates into the file with no
  engine was far worse on violations, and some outputs did not load. A small PPO policy trained only on synthetic
  boards beat every LLM and matched Freerouting on small boards (0.86), then fell to 0.45 on the larger ones.
- **Policy-guided MCTS** (same group, NeurIPS 2026 workshop): search raised clean pass from 34.2 % to 47.7 % at
  equal draws, but one search trajectory cost 17.9 policy rollouts, and at equal wall-clock time "policy sampling
  matches search". Tree search is not a free win.
- **RouteDiff** (same workshop): a diffusion model that draws one net at a time. No numbers on the abstract page.
- **SPROUT** (Bairamkulov and Friedman, TCAD 2022) and **PowerSynth** (Evans et al., TPEL 2019) are covered in 3.8
  and 3.9.
- **PathFinder** (McMurchie and Ebeling, 1995): node cost (b + h) × p. Confirmed from a university summary page, not
  the paper itself. SAT and ILP escape routing: I did not open a primary source; it matters for BGAs, which v1
  boards do not have.

### 3.8 Power copper generation

Nothing found generates power copper from "10 A between these pads" for a KiCad board. The pieces exist:

- **SPROUT** [read]: tile the free space, connect the terminals by shortest paths, then grow copper where nodal
  analysis shows high current and remove it where current is low, with a reheating step; multilayer by a 3D graph
  with a via cost. On two industrial boards it came within about 3 % and about 8 to 12 % of manual DC resistance
  (the paper's text and its table disagree on the second), in about 11 minutes for six rails. It does not take
  current as an input and does not produce a final layout.
- **Battery-Bank DC solver** [read]: a grid resistance solver on the copper dump (0.05 mm needed near necks and
  Kelvin taps; 90 s for one path), per-via current, Kelvin tap error, loss tiles. It is exactly the evaluator
  SPROUT's loop needs, and it already found four legal-but-wrong faults.
- **padne** [read]: GPL-3.0, 2.5D FEM for DC drop and current density from a KiCad project, sources and loads
  declared as text directives in the schematic (`VOLTAGE`, `CURRENT`, `REGULATOR`), NLnet-funded from 2026-04 with
  measurement validation listed as current work. A second opinion for our solver, and its directive scheme is a
  model for "current per net declared in the schematic". **KiPIDA** is a similar KiCad plugin I did not examine.
- **KRT `route_planes.py`** [read]: pours, thermal via arrays under exposed pads, stitching lattices, plane
  resistance and maximum-current report.
- **KiCad custom rules** [read]: constraint types include `clearance`, `creepage` ("the electrical creepage between
  copper objects of different nets"), `physical_clearance`, `track_width`, `via_count`, `zone_connection`,
  `thermal_relief_gap`, `thermal_spoke_width`. So high-voltage spacing and thermal relief can be stated as rules and
  judged by KiCad's DRC. A KiCad issue title reports the creepage check being very slow in 9.0; I did not open it.

Proposed generator [inferred, untested]: for each power net take terminals, design current, allowed layers and the
limits (drop, loss, temperature rise, amps per via) from the spec. Seed with shortest corridors in free space, grow
by SPROUT's rule using our DC solver, size via arrays from the per-via current the solver reports, cut Kelvin taps
as sealed pads with a keep-out ring, write KiCad zones with priorities, refill in KiCad, run DRC and the DC solver,
and keep a candidate only if it passes both. Thermal relief on by default for hand-solder pads and off for
high-current pads, set through `zone_connection` rules per net class.

High voltage: the required clearance and creepage for each pair of voltage domains must come from a table in a
data file that Logan has checked (IPC-2221B, IEC 62368-1). I did not open either standard, and the LLM must not
recall the numbers. The tool turns the table into net-class clearances for the router and `clearance` and
`creepage` rules in `.kicad_dru` for the verdict.

### 3.9 Physics in the cost or after

The literature and our own record point the same way: cheap proxies inside the search, real solvers as the judge.

- PowerSynth [read] puts electrical and thermal models inside a genetic optimiser, but only after replacing the
  field solver by response surfaces (50 ms against over 300 s) and the thermal solve by a resistor network (60 ms
  against about 520 s), with 2 to 4 % average error against measurement. It can do that because a power module has a
  few dozen shapes.
- Quilter's own documentation [read] describes checks run on finished candidates, not terms inside the router.
- On Monolith [read], one cost term (2.5× within 1 mm of switching copper, no new via within 1 mm) cut victims over
  10 mV from 14 to 8 before any repair. The rest needed the coupling solver to say where, and every hot spot was a
  via. Two regressions (a via in a bus neck, a hop that closed a plane gap) were invisible to any local cost.

So: put keep-away from declared aggressors, pour cost, no-via-in-pour and "stay over unbroken reference copper" in
the engine as costs or keep-outs; run the DC, loop and coupling solvers on every accepted pass; for small blocks
generate several candidates and let the solver choose, which is PowerSynth's idea at block scale.

### 3.10 Tidiness

The Battery-Bank tidiness table is, as far as I found, the only published-in-practice measure of what a person
objects to, and it tracked Logan's objections. Freerouting has an optimiser score against a computable lower bound
(`docs/scoring.md`) that covers length and vias but not width steps or bundles. I found no learned aesthetic score
for PCB routing. On vision models the evidence is mixed: the KiCad-forum study measured failure diagnosis from an
SVG picture at recall 0.03 against 0.82 from structured text, while PostEDA-Bench (chip layout) found that adding
vision consistently helped DRC repair. A discriminator trained to tell human routing from autorouter output on the
PCBench pairs is possible with compute alone, but it would learn hobbyist style. Use the numeric measure as the
gate and a picture for the human and as a secondary hint to the LLM.

### 3.11 The LLM's role

What is published supports a narrow role.

- Engine-grounded beats free-form (PCBWorld): interactive through the engine, then plan-and-execute, then raw
  coordinates last.
- LLMs evaluate better than they route (KiCad-forum study): reading failures from structured text worked; model-
  chosen net order gave −2.75 % and 0.0 %; in 27 of 27 sessions the agent reported a complete job when 1 to 8 nets
  were done. The verdict must come from code.
- Region-bounded repair with tools (EvoDRC, chips): one agent per bounded region with three tools (local DRC,
  connectivity check, impact preview) and a log of which repairs worked.
- KRT's skills are a working example of "LLM plans the chain, tools route".

Roles for v1: classify nets from the schematic declarations and datasheets; write the routing constraint file;
choose order and layer plan; on failure, read a text bottleneck report plus one cropped image and pick from a fixed
menu (move via by d, re-route net N with neighbours K, swap layer for a run, widen keep-away, hand back to
placement with a named part and direction, add to the protected list with a reason).

## 4. How this fits the pipeline

**Inputs from earlier stages.** From the schematic: net class per net, design current per power net, voltage domain
per net, switching nets with swing and edge time, sensitive nets, Kelvin pairs, hot loops and gate loops with their
pads, repeated sheets, block boundaries. From placement: positions, reserved corridors, via sites, block exits.
From the spec: stack-up, JLCPCB rule set, limits (drop, loss, temperature rise, amps per via, coupling per edge),
the clearance and creepage table.

**Order of work.**

1. Rules: write net classes and `.kicad_dru` (JLCPCB limits, pair clearances, creepage) from the spec.
2. Ground vias and planes.
3. Power copper generator, checked by DRC and the DC solver.
4. Critical nets per block from templates, candidates scored by the loop and coupling solvers; results recorded as
   fixed copper by id.
5. Bulk signals: export what is left to the engine with keep-outs over power pours and around switching copper,
   fixed copper locked, priority classes set; import; real DRC.
6. Cleanup: `tidyall` and `runwidth`, protected list respected.
7. Full check loop; repair episodes; full check loop again.

**Outputs.** A routed `.kicad_pcb`, the list of fixed and protected copper with reasons, one table (DRC,
unconnected, tidiness, every solver line against its limit and against the previous pass), and pictures.

**Automated check.** KiCad DRC with zero errors and zero unconnected; plane-island check; every solver line within
its limit; tidiness not worse than the last accepted pass. **Human gate.** Logan sees the table and three or four
pictures (whole board per layer, each power stage, the worst five nets by tidiness) and either accepts or states an
objection, which becomes a rule, a cost or a check.

**Token cost.** Last time the cost was context, not thinking. Each step is one command that returns a summary of
a few hundred tokens and writes details to files. The LLM reads the full report only for a failing item. Each
repair episode starts from a fresh context with the constraint file, one bottleneck report and one crop. Cap repair
episodes per pass, and stop with a written list of open items when the cap is reached.

## 5. An automated improvement loop

**Data that exists [read].**

- Freerouting's repository holds 1,142 PCBench boards, each with `unrouted.kicad_pcb`, the human-routed reference,
  a metadata file (layers, nets, components, reference length, via count, KiCad DRC breakdown) and a tier, plus
  per-version results. PCBench itself is at `github.com/PCBench/PCBench`.
- PCBWorld-Bench: 679 of those boards filtered to fully connected and violation-free under KiCad 9, with eight
  engine-checked metrics, and two synthetic board generators.
- Monolith: one board with a human routing, three scripted versions and every solver result for each. Its two
  charger stages and three bucks are block-level cases.

**Missing:** power boards. PCBench is mostly hobby digital boards. A power subset has to be filtered from it (boards
with non-ground zones, wide tracks, high-current classes) and added to from open power projects. I did not verify
any specific project.

**What a machine can score.** Completion; KiCad DRC errors; via count; length over shortest tree; the tidiness
table; for boards with declared roles, path resistance, via current, loop inductance and coupling; run time. For
boards without declarations, roles can be guessed by rule (nets with pours, inductor and FET pads) to give a weaker
power score.

**The loop.** (a) Parameter search (Optuna or CMA-ES) over engine weights and our cost terms on a fixed training
split, scored on a held-out split; Freerouting exposes a seed and the weights and already ships weight-replay
scripts. (b) Template search per block type: generate gate-drive, hot-loop and feedback candidates on Monolith's
blocks and on synthetic variants (moved parts, different packages), scored by the solvers. (c) Power-copper
generator tuning against the DC solver on synthetic terminal sets. (d) Regression: every accepted change re-runs
the corpus; a change that helps Monolith and hurts the corpus is rejected. None of this needs Logan.

**Where the metric misleads.**

- Length and via count reward cutting through planes and running beside switch nodes. Monolith's cleanup pass made
  one net shorter and took it from 1.7 to 18 mV per edge.
- Reference boards are not gold: the sample I opened has 113 KiCad DRC items and 13 open connections.
- Freerouting's own completion numbers are judged on DSN, which lacks custom rules.
- Every solver number is modelled; none has been checked against a measured board.
- Tuning on hobby digital boards can move weights the wrong way for power boards. Keep a power split and weight it.

## 6. Risks, unknowns and the spike

1. **The bulk engine may fight the power copper.** Freerouting may cut pours, ignore pair clearances or fail to
   complete once pours and keep-outs are in place. This is the biggest unknown.
2. **The power-copper generator is unbuilt.** SPROUT shows the method works for BGA rails; converter stages with
   switch-node pours and tight hot loops are harder, and the first version may only handle rails and buses, leaving
   power stages to templates.
3. **KiCad 11** removes the SWIG bindings the Battery-Bank scripts use for load, edit, refill and DRC. `kicad-cli`
   covers DRC; edits and zone refill need either direct file writing or the headless IPC API.
4. **One-maintainer engines.** Both Freerouting and KRT depend on one person. Pin versions and keep the engine
   behind an interface.
5. **Solvers unvalidated.** Calibrate each against a published figure, and against padne for DC.
6. **Tidiness may still fail Logan's eye** on bundles and block structure, which no per-net pass fixes.

**Spike (about two days of machine time, no input from Logan).** Take the Monolith board with its hand-drawn power
copper, Kelvin taps and gate drives kept and all plain signals stripped. Route the rest three ways: Freerouting
2.6 with keep-outs and priority classes; KRT with its block mode; the existing `router.py`. Run the same real DRC,
tidiness table and solver loop on all three, then `tidyall` on each. Report completion, DRC, the tidiness table,
solver lines, wall time and agent tokens against the hand-routed board. This settles the bulk engine, shows whether
DSN loses rules that matter, and gives the first cost-per-board figure for the new flow. A second, smaller spike:
generate the PACK_P bus and one charger input pour with a SPROUT-style loop on the DC solver and compare resistance
and via current with the hand-drawn copper.

## 7. The Gemini PDF, pages 1 to 8, checked

| Claim | Verdict |
|---|---|
| Lee, A*, Hadlock; shape-based routing with obstacle expansion; rubber-band routing on a triangulation | Textbook, correct. Not re-verified line by line |
| PathFinder cost (b + h) × p, history term prevents oscillation | Holds (university summary of the 1995 paper). The specific schedules (0.2, ×1.3, decay 0.98) have no source |
| Freerouting is sequential rip-up and re-route | Holds; its docs describe passes with rising rip-up cost |
| A uniform grid "will hit a memory wall on your first real PCB" | False at our scale. Monolith ran at 0.05 mm on four layers in Python. The real limits were rounding at pads and one-net-at-a-time |
| A new engine is needed, in Rust, in six modules | Oversold. Two maintained open engines exist; the measured Monolith gaps were constraints, placement and power copper, not search speed |
| SAT escape in 100 to 500 ms for 400 pins | Unverified, and not needed without BGAs |
| FLUTE and Prim-Dijkstra trees | Real methods; the second is for timing skew, which is out of scope. `tidynet` already routes to the existing tree |
| "Quilter and Allegro X AI move electrical verification inside the inner routing cost loop" | Not supported. Quilter's docs describe checks on candidates; Cadence gives no method |
| "DeepPCB, Quilter and academic routers wrap the engine in MCTS" | Partly. DeepPCB says reinforcement learning. The one 2026 MCTS paper found search no better than sampling at equal time |
| Closed-form physics proxies (loop L from enclosed area, crosstalk from parallel length over spacing squared, return-path penalty) | Reasonable as ranking heuristics, no source, not numbers to trust. Monolith's evidence favours simple keep-away costs plus real solvers |
| Via pricing across all layers and a plane-split penalty | Matches a Monolith lesson ("a via cuts every layer"); worth having |
| Glossing: corner removal, via removal, centring in channels | Matches `tidynet` and Freerouting's optimiser. Centring is not what Logan's board shows; he runs bundles at pitch |
| Agentic DRC-repair loops with an LLM adjusting clearances and keep-outs | Direction supported by PCBWorld, EvoDRC and KRT's skills; measured gains on PCBs are small so far |

## 8. Sources

Local evidence:
- `.claude/skills/pcb-scripted-routing/SKILL.md`, `pcb-proto-flow/SKILL.md`: method, cost terms, tidiness table, gaps.
- `tools/battery-bank/groundup/README.md`, `groundup/compare/README.md`, `compare/worklog.json`: every pass, solver
  results, hours and dollars.
- `tools/battery-bank/groundup/router.py`, `ml.py`, `tidynet.py`, `runwidth.py`, `cu.py`, `copper.py`: what the code does.
- `docs/research/2026-11-10-gemini-autorouter-and-placement.pdf`, pages 1 to 8.

Opened on the web or cloned:
- https://github.com/freerouting/freerouting (cloned at commit 842ad83, 2026-11-10): README maintenance notice,
  `docs/command_line_arguments.md`, `docs/settings.md`, `docs/scoring.md`, `docs/architecture.md`,
  `docs/research/large-board-autorouter-performance.md`, `docs/research/kicad_ipc_api_research.md`,
  `scripts/benchmark/results/benchmarks.md`, PCBench fixtures.
- https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar: the jar I ran.
- https://github.com/LGAI-Research/PCBWorld and https://arxiv.org/abs/2607.05915: environment on KiCad's router,
  router and LLM results (Table 3), dataset description.
- https://github.com/drandyhaas/KiCadRoutingTools (cloned, v0.23.9): README, `docs/power-nets.md`,
  `docs/route-plane.md`, `docs/claude-skills.md`.
- https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/: IPC API needs the GUI in 9 and 10;
  headless in 11.
- https://hub.allspice.io/AllSpiceMirrors/kicad/src/branch/master/pcbnew/dialogs/panel_setup_rules_help_2constraints.md:
  custom-rule constraint list, including `creepage`.
- https://forum.kicad.info/t/two-months-of-testing-llms-on-pcb-autorouting-what-worked-what-didnt-and-whats-left-to-try-open-archive/72250:
  LLM roles that worked and failed; comparison with Freerouting.
- https://github.com/bbenchoff/OrthoRoute: scope and the author's limits.
- https://codeberg.org/topola/topola and https://nlnet.nl/project/Topola/: status of Topola.
- https://en.wikipedia.org/wiki/TopoR: last listed TopoR version.
- https://github.com/tscircuit/tscircuit-autorouter/wiki: input format and limits.
- https://github.com/atx/padne and https://nlnet.nl/project/Padne/: DC FEM tool, directives, funding.
- https://relatedrepos.com/gh/kbralten/KiPIDA: existence of KiPIDA only.
- https://brainkz.github.io/papers/SPROUT_TCAD.pdf: SPROUT algorithm and validation.
- https://e3da.csce.uark.edu/pub/doc/2019/T.Evans-IEEE.TPEL-2019.pdf: PowerSynth models in the loop.
- https://neurips.cc/virtual/2026/161626 and https://neurips.cc/virtual/2026/161614: MCTS and diffusion routing abstracts.
- https://arxiv.org/abs/2607.20019 (EvoDRC) and https://arxiv.org/abs/2605.06936 (PostEDA-Bench): agentic DRC
  repair on chips; vision helped there.
- https://arxiv.org/abs/2603.15672 (DRCY): schematic review agent; not routing.
- https://deeppcb.ai/pcb-autorouter-benchmark-2026/ and https://deeppcb.ai/kicad-autorouter-alternative/: vendor
  numbers, inputs and limits.
- https://docs.quilter.ai/about-quilter/how-does-quilter-work.md and `what-quilter-isnt.md`: method as described,
  exclusions.
- https://www.quilter.ai/blog/generative-pcb-design-tool-pricing-in-2026-a-guide-to-saas-credits-and-subscriptions
  and https://www.quilter.ai/blog/llm-pcb-layout-gpt-6-astra: pricing models (vendor), commentary on LLM layout.
- https://newstaging.cadence.com/p_r_e_view/home/tools/pcb-design-and-analysis/allegro-x-ai.html: Allegro X AI claims.
- https://www.flux.ai/docs/tutorials/copilot-use-cases/auto-layout: opened; no usable detail on auto-layout.
- https://oaslananka.github.io/kicad-mcp/compatibility/kicad-10-to-11-migration/: a third-party note on KiCad 11
  readiness; no release date.
- https://sites.lafayette.edu/cadapps/main-page/pathfinder-fpga-routing-algorithm/: PathFinder cost formula.

Not opened, named only: IPC-2221B, IEC 62368-1, the PathFinder paper itself, KiCad issue 21482, JITX, Zuken.
