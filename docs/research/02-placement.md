# Track 2: Component placement

Research agent report, 2026-11-11. Scope: placement for power-electronics and mixed-signal boards of 50 to 500
parts, driven by an LLM plus deterministic engines. Scripts and raw results from the three small experiments are
in `02-placement/`. "Verified" below means I opened the source or ran the code; everything else is marked.

## 1. Recommendation

Build, do not adopt. Extend the Battery-Bank placer into a **constraint-compiled, hierarchical placer** with four
layers, all driven by one placement-intent file that the LLM writes and code validates:

1. **Intent file** (per schematic sheet): fixed parts, blocks, bindings of support parts to pins with rank, hot
   loops, Kelvin pairs, repeated blocks, nets that cross block boundaries, side and height limits.
2. **Block solver**: power stages from parametric templates, with candidates ranked by the existing loop solver;
   support parts placed jointly per block by CP-SAT (greedy as fallback). A finished block is a rigid macro with
   declared exits.
3. **Floorplanner**: 10 to 30 macros plus fixed parts, simulated annealing, with corridors for crossing nets
   reserved as real area.
4. **Scorer**: legality, shortest-tree length, airwire crossings, corridor capacity, hot-loop inductance on a
   quick pour, then a trial route.

The LLM never emits coordinates. It writes intent, reads text reports, and calls about eight mutation tools.

**Runner-up**: NVIDIA's Cypress (GPU analytical placer, Apache-2.0) as the floorplanner behind the same intent
file. It is the strongest open PCB placer, but it does not handle height, alignment or critical power parts, and
at our part counts its speed is not needed.

## 2. Options compared

| Option | Maturity, last activity | Licence | How an LLM uses it | Checks it gives | Token cost | KiCad / JLC fit | HV / power fit | Needs from a human |
|---|---|---|---|---|---|---|---|---|
| **A. Extend Battery-Bank placer** (intent file, CP-SAT blocks, SA floorplan, solver scoring) | Greedy core works on one board; the rest is to build | Ours | Writes intent file, calls mutation tools | Courtyard, enclosure, mech fit, tree length, crossings, loop nH | Low once pin targets and `at=` hints stop being typed | Native; already reads and writes `.kicad_pcb` | Best: loop and Kelvin are first-class | Floorplan gate, power-stage gate |
| B. Cypress (NVlabs) | ISPD 2025 best paper; 746 commits; last-commit date not retrievable here | Apache-2.0 | Would have to wrap; input is a YAML IR with a KiCad translator | HPWL, net crossings, density | Low | KiCad translator exists (per paper); needs GPU and a DREAMPlace build (Python 3.5 to 3.9) | Poor: paper says it does not handle high-current paths, height or alignment | All power-stage geometry |
| C. SA-PCB (UCSD / OpenROAD) | **Archived 1 July 2026** | BSD-3 | Bookshelf files | HPWL, overlap | Low | Eagle/Bookshelf only | None | Everything else |
| D. RL placers (RL_PCB, PCBAgent, DeepPCB-style) | RL_PCB: research code, Python 3.8 / CUDA 11.7; PCBAgent: no code found | MIT / none | PCBAgent: LLM turns user text into commands for the RL agent | HPWL proxies | Training compute high | None native | None | Training set of boards |
| E. atoplace | Alpha, 1 star, 76 commits; **not on PyPI** though README says `pip install atoplace` | MIT | MCP server, 26 to 40 tools, free-text constraints | Overlap, DRC, a "confidence" score | Unknown | KiCad 8+/9 IPC | Not stated | Unknown; could not run |
| F. tscircuit packer (`calculate-packing`) | Active: v0.0.90, 23 Sep 2026; core updated 10 Nov 2026 | (repo) | React-style code; `pcbPack`, `pcbFlex`, `pcbGrid` | Overlap | Low | Exports to KiCad, not native | None; docs call auto-layout beta | Power stages |
| G. KiCad built-ins (auto-place, pack-and-move, Repeat Layout, PCB design blocks) | Shipping in KiCad 9/10 | GPL | Through MCP or `pcbnew` | DRC | Low | Native | Neutral | Channel 1 layout |
| H. JITX / atopile code placement | JITX commercial, active; atopile 0.12.6, MIT | Mixed | Code: `place(obj, pose)` relative to parent | Their own DRC | Low | atopile writes KiCad; JITX exports | Neutral | Coordinates per block, once |
| I. Quilter | Commercial, Series B Oct 2025 | Proprietary; free non-commercial tier; commercial priced by pin count, no public price | Upload board, set constraints in UI | Physics scorecard | None for us | Accepts KiCad | **Docs: above 48 V not supported, above 10 A "not well supported", no symmetric multi-channel** | Review of candidates |
| J. Allegro X AI, Zuken AIPR, Flux | Commercial | Proprietary | Not scriptable by us | n/a | n/a | Not KiCad (Flux is its own editor) | Not published | n/a |

## 3. Evidence per option

### 3.1 The existing Battery-Bank placer (read in full)

Files: `tools/battery-bank/groundup/placelib.py` (129 lines), `fpdb.py` (40), `place.py`, `place_*.py`, `run.py`,
`apply_place.py`, `mechcheck.py`, `placescan.py`. The dump `base.json` holds 289 footprints (277 front, 12 back,
15 locked), not the 430 parts quoted for the board; I did not find the reason and assume the rest are
non-footprint BOM lines or were excluded from the dump.

**What it does, precisely.**

- `fpdb.DB` turns the board dump into local pad coordinates and an axis-aligned courtyard box per reference, so a
  candidate `(x, y, rot)` gives world pad positions in numpy with no KiCad in the loop.
- A placement is a dict `{ref: (x, y, rot)}`. `put()` writes a typed coordinate. `auto()` places one part: it
  scans a 0.05 mm grid inside a square of half-width 4 mm (then 8, then 14 if nothing is free), times four
  rotations, about 26,000 positions per rotation at the first radius. It masks positions whose courtyard box
  overlaps another box by more than 0.05 mm, hits an enclosure limit, a "ghost" box or a reserved via site. It
  scores the rest by the summed Manhattan distance from each pad to its target, plus a weak pull toward a search
  centre, and takes the minimum. One part at a time, no look-ahead, no backtracking.
- `run.py` executes the scripts twice so that typed parts are reserved before automatic ones.
- `check()` reports courtyard overlaps and enclosure hits. `mechcheck.py` re-poses per-footprint meshes and runs
  the enclosure model's own checks. `apply_place.py` writes the dict into the board through `pcbnew`.

**What is general.** The footprint database and rotation convention, placement as data, the masked grid scan,
per-pad targets, plane nets ignored as targets, clear bands round ICs, reserved via sites, the two-pass reserve,
ghost boxes for a translated copy, `check()`'s overlap test, and the idea of `mechcheck`.

**What is hard-coded.**

- Enclosure geometry (edge, lips, pegs, notch) as literals, written twice (`check()` and `_auto()`).
- The fixed-part list, the plane-net set `{'GND','PACK_P','3V3'}`, the clear-band table, and the port 1 to port 2
  mapping as a regular expression on reference numbers (`4xx` to `5xx`) with one x offset.
- About 77 typed coordinates (`put`/`sp`) covering every IC, FET, inductor, bulk capacitor and sense resistor.
- 105 typed pad targets in 91 `auto()` calls. **Nearly every `auto()` call also carries a typed `at=(x, y)` search
  centre.** So the "automatic" part is closer to snap-to-nearest-legal-spot round a position the agent chose from
  a picture than to placement. This is where the tokens went.
- Call order is the priority order, also typed.
- Side is whatever the dump says; the placer never chooses a side. No height zones, no thermal term, no loop
  term, no corridor concept, no global objective.

**What it takes to make it data-driven.** The core loop needs little change. The work is in what feeds it:

1. Enclosure limits, keep-outs and height zones from a data file (one polygon list), used by one function.
2. Bindings, rank and plane nets from the intent file and net classes instead of `pins=` literals.
3. Search centres computed (the default, the centroid of the targets, already exists) instead of typed.
4. Repeated blocks from sheet instances, with a general rigid transform instead of an x shift.
5. A joint solve per block, a floorplan step above it, and a score. These are new.

**Three small experiments on the Monolith data** (scripts in `02-placement/`, all run here):

- *Can pin targets be derived without typing?* (`spike_pintargets.py`) A naive netlist rule ("the target is the
  pad on the same net that belongs to the part with the most pads") reproduces the parent part for **68 of the 105
  typed targets (65 %)**. All 105 typed targets are on the same net as the pad, so a same-net validity check costs
  nothing. The 37 misses are all semantic: an EEPROM's pull-ups belong at the EEPROM and not at the PD controller
  on the same bus; an enable pull-down belongs at the receiver; bootstrap diodes belong at their capacitors;
  Kelvin filter resistors at the shunt. This is the LLM's job, and it is a small one: a binding table per sheet.
- *Would cheap pre-route metrics have flagged the scripted placement?* (`spike_metrics.py`) On 159 non-plane nets,
  hand placement against scripted: HPWL 2017 against 2461 mm (+22 %), Manhattan shortest tree 2132 against 2624 mm
  (+23 %), crossings between shortest-tree edges of different nets **383 against 581 (+52 %)**. The project record
  has 1516 against 1937 mm on its own set of 144 nets, and after routing a detour ratio of 1.20 against 1.54. All
  three proxies rank the two placements correctly; crossings separate them most. This is two placements of one
  board, so it is an anchor and not a validation.
- *Does a joint solve beat one-at-a-time greedy?* (`spike_cpsat.py`) The 24 passives of the port 1 charger
  controller, same 32 pad targets, same obstacles, four rotations, 0.05 mm grid. OR-tools 9.15 CP-SAT with
  `AddNoOverlap2D` and optional intervals for rotation: **72.6 mm against greedy's 92.2 mm (21 % lower) in 60 s on
  4 cores; with a 0.8 mm clear band round the IC, 99.7 against 125.3 mm (20 % lower) in 120 s.** Both results pass
  the project's own `check()`. CP-SAT did not prove optimality (lower bounds 35.9 and 44.5 mm), so better answers
  may exist. Pad distance is not routed quality; this shows the formulation is practical at block size, no more.

### 3.2 Algorithms

**Sequence pair or B\*-tree with simulated annealing.** A topological code that always decodes to a
non-overlapping packing; annealing permutes the code. Suits rectangles of very different sizes and discrete
rotation. It packs toward a corner, so fixed parts, keep-outs and "this pad next to that pad" are awkward and are
usually added as penalties. Two-sided needs one code per side. The closest published use to our problem is
Dong and Wang (IEEE DMC 2023): B\*-tree annealing of one phase leg of a three-phase converter with FastHenry loop
inductance as the objective, from above 50 nH for a random layout to 23 nH, then the leg copied to the other
phases by translation and the bus capacitors packed with MiniZinc. That is a power-stage template search with a
field solver as judge, the same shape as what `pcb-proto-flow` lists as missing piece 5. (I did not re-open the
original sequence-pair and B\*-tree papers; the description is from memory of Murata et al. 1996 and Chang et al.
2000.)

**Analytical and electrostatic (ePlace, RePlAce, DREAMPlace, Cypress).** All parts move at once under a smooth
wirelength term and a density term solved by FFT. Cypress (Zhang lab, Cornell, with NVIDIA; ISPD 2025) is the PCB
adaptation, verified from the paper: objective is wirelength plus density plus a smoothed **net-crossing** term;
discrete orientations by Gumbel-Softmax; Tetris then Abacus legalisation per side; the side of each part is given
by the designer and not optimised. Benchmarks: 10 open designs of 41 to 476 parts synthesised from functional
groups of commercial boards, plus five proprietary ones above 5,000 parts. Against SA-PCB it reports HPWL lower by
75 to 98 % and routed track 3.6 to 19.7 times shorter, with FreeRouting 1.9.0 on two layers as the judge. Limits
the authors state: no height or alignment constraints, no handling of high-current paths or high-speed signals,
thermal and EMC not encoded. There is no ablation showing that the crossing term alone improves routed results;
adding it cut crossings to 0.31 of baseline at 13 % more HPWL on the proprietary set. DREAMPlace itself is alive
(v4.3.0, BSD-3, CPU-only possible) but has no orientation support and is built for row-based cells.

**Force-directed.** Springs on nets, repulsion on overlap. Easy to write, handles fixed parts naturally, gives a
plausible seed. No guarantee of legality and poor at "exactly here". atoplace uses it with an Abacus-style
legaliser. Useful to seed the floorplan, not as the engine.

**Constraint programming and MILP (OR-tools CP-SAT).** States the rules directly: no-overlap, rotation as
optional intervals, side as a boolean, keep-outs and height zones as forbidden rectangles, "within d of", "left
of", alignment, and same-pose for repeated blocks. It handles exactly the hard, discrete rules that the other
families treat as penalties. It does not scale to a whole board with a wirelength objective, and loop inductance
is not linear. Verified at block scale in the experiment above. NS-Place (Cheng, Ho, Holtz, ASP-DAC 2022) uses
MILP only for legalisation after a net-separation optimisation and reports up to 25 % less routed wirelength and
up to 50 % fewer vias on 14 boards.

**Hierarchical clustering with satellite passives.** Bind each support part to its parent pin, place the parent
with room reserved, then pack the satellites. This is what the Battery-Bank placer already does by hand, what
Quilter documents as automatic bypass-capacitor, crystal and switching-converter detection, and what PCBAgent
reports as its largest single gain: placing chip-centred groups in order cut HPWL by 30 % and 22 % against
net-count and area orderings on 17 industrial boards of 18 to 414 parts. tscircuit's packer is the same idea
stated as "sequential optimal packing"; its author notes the two weaknesses we saw: order matters, and the fix
is to harden a group into a fixed unit.

**Reinforcement learning.** For chips, the independent record is against it. Cheng, Kahng et al. (arXiv 2302.11014 v3)
found simulated annealing gave the better proxy cost in 6 of 9 cases against the released AlphaChip, at about
900 CPU-hours against about 20,000; Markov's CACM review concludes the Nature paper did not advance the
state of the art. Their most useful number for us: Kendall correlation between the proxy cost and routed
wirelength was 0.40, and with timing under 0.1. For PCBs: RL_PCB (Vassallo, DATE 2024, MIT) trained on six
circuits and its own figures show residual overlaps; Lim (arXiv 2602.23540) places 8 to 24 passives round one IC
and its table does not support its own claim of beating the human layouts; PCBAgent (ASP-DAC 2025) reaches 1.04
times human HPWL on 17 boards with a Decision Transformer but no routing was run and no code is published. None
handles side, height or loop rules. Not recommended.

**Routability-driven placement with congestion feedback.** Standard in chip placers (RePlAce, DREAMPlace since
2.2 with a global router). For PCBs the published version is weaker: Cypress and NS-Place optimise crossing or
separation proxies and route only to evaluate. Quilter says it routes inside its loop. The Battery-Bank record is
the best evidence we have that feedback is needed: a connection that fails with nothing else routed is a
placement fault, and moving one resistor fixed a 204 mV coupling that no re-route could.

**Fit to our rules, in short.**

| Family | Irregular sizes | Rotation | Two sides | Keep-outs, height zones | Hard geometry (hot loop, Kelvin) |
|---|---|---|---|---|---|
| Sequence pair / B\*-tree + SA | Good | Good | One code per side | Penalties | Only with a solver as cost, at block scale |
| Analytical (Cypress) | Good | Relaxed, then snapped | Side fixed by user | Fixed blocks yes; height no | No |
| Force-directed | Fair | Poor | Poor | Poor | No |
| CP-SAT / MILP | Good | Exact | Exact | Exact | Geometric stand-ins (max distance, adjacency, order) are exact; nH is not |
| RL | Grid-bound | 4 angles | Not shown | Masks | No |

### 3.3 Existing tools, tried or checked

- **Cypress**: repo and paper read. Not run: it needs a GPU and a DREAMPlace build that pins old Python and
  PyTorch. GitHub's API and commit pages were not reachable from this session, so I could not get a last-commit
  date for this or the other GitHub projects.
- **SA-PCB**: archived read-only on 1 July 2026. Rule it out.
- **atoplace**: `pip install atoplace` fails, no such distribution on PyPI (checked). Alpha, one star. Its design
  (force-directed plus legaliser, an MCP server with placement actions, a lock file so positions survive
  rebuilds) is the nearest open project to what we want, so it is worth reading for its tool list, not adopting.
- **kicad-parts-placer** 0.1.4 (May 2024, MIT): installs. It applies a centroid CSV to a board and groups the
  parts. It is the same job as our 12-line `apply_place.py`. I installed it, saw it pulled a spreadsheet stack
  into the system Python, removed it, and did not run it on a board (no `pcbnew` in this container).
- **KiCad**: 9 has Auto-Place Footprints, Pack and Move, and multichannel Repeat Layout driven by placement rule
  areas; 10 adds design blocks that hold PCB layout, and pin and gate swap with back-annotation. Forum threads
  report Repeat Layout failing when sheet pins connect to different external nets, so repeated blocks should
  stay in our own code and be checked by diff. I did not find the Repeat Layout section of the manual in what I
  could fetch.
- **JITX**: placement is code. `self.place(obj, (x, y), on=Side.Bottom)` places relative to the enclosing
  circuit, and placed children form a "kinematic tree" that moves, rotates and flips with the parent. That is
  the right data model for a block template: a pose tree, not world coordinates.
- **atopile** (0.12.6, MIT): reusable modules and a package registry; layout is done in KiCad and the compiler
  updates the board. Its README does not describe automatic placement. **tscircuit**: `pcbPack`, `pcbFlex` and
  `pcbGrid` layout modes; documentation calls them beta and gives no constraint list.
- **Quilter** (docs read): accepts KiCad. Controls are close to our intent list: schematic clustering, anchors,
  placement regions, pre-placed parts treated as fixed, vias left on the board block parts, automatic bypass,
  crystal and switching-converter detection, proximity constraints, current per power net. Stated limits:
  above 48 V unsupported, above 10 A not well supported, no symmetric multi-channel layout, under 5,000 pins
  advised. Says it is not trained on human boards. Free for non-commercial use; commercial price by pin count,
  not published.
- **DeepPCB**: its own KiCad page (opened) says "the engine only routes; it doesn't move your parts", placement
  in development. Quilter's comparison page says DeepPCB does both. I take DeepPCB's word.
- **Allegro X AI**: the only technical statement I found is "physics-based algorithms combined with generative
  AI", from a vendor article. **Zuken AIPR** and **Flux**: not opened beyond search results and Quilter's
  comparison, which describes Flux Auto-Layout as routing after manual placement. No prices found for any of
  the three.

### 3.4 Reusable placed-and-routed blocks

Who does it: Altium (reuse blocks), Cadence (design reuse), EasyEDA (reuse templates), KiCad 10 (PCB design
blocks, Repeat Layout), JITX (pose tree in code), Flux (modules; I could not open the page that describes them).
All of these store **fixed geometry for fixed footprints**. None that I found is parameterised: change the FET
package or the inductor and the block is redrawn by hand.

That is the gap, and the Battery-Bank record says how to fill it. A power-stage template should be a small
**generator**, not a stored layout:

- Inputs: the roles (high-side FET, low-side FET, inductor, hot-loop capacitors by rank, bulk capacitors, shunt,
  controller, bootstrap parts), their actual footprints, the nets, the stack-up.
- A handful of named topologies per stage type (for a buck: FETs side by side with the capacitor across the
  outer pads; FETs end to end; capacitor on the back under the FETs with vias), each a pose tree with a few
  free dimensions.
- The generator enumerates poses, drops illegal ones, draws quick pours, and ranks by the loop solver. The record
  gives the target: 0.37 to 0.39 nH with capacitors at the pads and ground vias beside them, against 0.78 to
  0.93 nH at 1.3 to 2.3 mm.
- Output: the block as a rigid macro with a courtyard, reserved via sites, and declared exits (side and layer per
  crossing net).

A template survives a part change because it is re-solved, and the solver score says whether the new part made it
worse. Templates worth writing first, from the Monolith circuit: synchronous buck or buck-boost stage, gate-drive
group, shunt with Kelvin filter, USB-C front end (connector, TVS, CC protector, PD controller), QFN with
decoupling. Dong and Wang's annealed phase leg is published evidence that the search step works with a PEEC
judge. Nothing here has been tried on our code.

### 3.5 How the LLM should express intent, and the Gemini claims

Published work, all opened:

- **OmniLayout** (arXiv 2607.03261, 1,681 boards): asked for placements directly, frontier models reach an
  end-to-end pass rate of 15 to 43 %. Claude Sonnet 4.6 has an overlap score of 0.49 zero-shot and 0.004 when
  given a geometry-check tool that names the conflicting parts. Schematic context improved functional grouping
  in all 15 comparisons. Few-shot examples did not help. Text overlap reports worked better than a scalar score
  for Claude.
- **PCB Gym** (NeurIPS 2026 workshop): frontier agents produce a DRC-clean, fully routed board on 32.1 % of
  attempts and "route power rails like ordinary signals".
- **PCB-Bench** (ICLR 2026): "substantial gaps" in spatial reasoning and constraint following.
- **PCBAgent**: the LLM turns the user's words into commands and weight changes for a placement engine.
  **LayoutCopilot** (analog ICs): the LLM emits a fixed command set (`deviceMove`, `deviceSwap`, `symAdd`,
  `arrayAdd`, ...) that an editor executes; 94 to 97 % of command sequences pass a syntax and logic check.

So the direction of the Gemini PDF's section 4 holds: LLMs are poor at geometry and useful at semantics, and
checking tools close most of the gap. Claim by claim:

| Gemini claim (pages 9 to 13) | Finding |
|---|---|
| "80 % of routing failures are placement failures in disguise" | No source found. Unverified. The Battery-Bank record agrees in kind, not in number |
| Quilter, Allegro X AI, Circuit Training and "Instacart/UC San Diego PCB-Place" solve placement and routing as a coupled loop | Quilter says so itself. Circuit Training is chip macro placement with no router in the loop. I found no "PCB-Place" and no Instacart link; the UCSD work is SA-PCB and NS-Place. Treat as wrong |
| Sequence pairs always decode to an overlap-free packing | True (standard result) |
| "20,000+ placements per second", "< 50 µs for 150 components" | No source. Unverified |
| Weighted-average wirelength and FFT electrostatics | Correct description of ePlace-family placers |
| `sin²(2θ)` penalty snaps rotation to 90° steps | Not what Cypress does (Gumbel-Softmax over legal orientations). No source found |
| RL "learns non-obvious foresight"; use it for the 10 to 30 core ICs | Not supported by the independent chip record or by the PCB RL papers |
| Bind satellites to parent pins before global placement | Supported: PCBAgent ordering result, Quilter docs, tscircuit, our own placer |
| Airwire crossings are "the single highest-leverage heuristic" | Partly. Cypress and NS-Place optimise crossing or separation and report better routed results, but neither isolates the term. On Monolith, crossings separated the two placements more than HPWL did |
| Inflate courtyards where the router is congested, then re-legalise | Standard in chip placers. I found no PCB paper that tests it |
| Hungarian-matching pin swap inside the router | Not checked (routing track). KiCad 10 now has pin and gate swap with back-annotation, which makes it usable |
| LLM writes constraints and picks from a small mutation set, never raw coordinates | Supported by OmniLayout, PCBAgent and LayoutCopilot |
| Text bottleneck report plus cropped picture | Text reports are supported (OmniLayout). The value of the picture is untested; on Battery-Bank pictures were the expensive part |
| Write the placer in Rust | Not needed for placement. The CP-SAT and numpy code above runs in seconds to minutes at our size |

**Proposed intent vocabulary** (a YAML file per sheet, checked by code before any geometry runs):

- `fixed`: part, pose, source (enclosure, owner's choice).
- `block`: name, parts, template (or none), repeat-of.
- `bind`: part.pad to target part.pad, rank at that pin, maximum distance, same side or opposite side allowed.
- `hot_loop`: supply and return nets, switch pads, closing capacitors by rank, limit in nH.
- `kelvin`: shunt, tap pads, filter parts.
- `orient`: part side faces block or part.
- `between`: part sits between A and B.
- `separate`: aggressor block or net, victim, minimum distance.
- `corridor`: nets that cross from block A to block B, layer.
- `zone`: polygon, side, maximum height, allowed blocks.
- `thermal`: part, dissipation, keep-away list.

Validation that needs no judgement: every reference and pad exists, bound pads share a net, each two-pad part is
bound at most once per pad, every switching net named in the schematic belongs to a hot loop, every sheet
instance is a block.

**Mutation tools** (each returns a text delta of the score): `set_binding`, `set_rank`, `rotate_part`,
`flip_side`, `swap_blocks`, `move_block_toward`, `widen_corridor`, `set_clear_band`, `choose_template_variant`.
There is no `move_to(x, y)`.

### 3.6 Scoring a placement before routing

| Score | Cost | Evidence that it predicts routed quality |
|---|---|---|
| Courtyard, enclosure, height, mechanical fit | Seconds | Legality only. Battery-Bank: needed after every change |
| Sum of shortest trees (or HPWL) over signal nets | About 1 s | Battery-Bank: 28 % longer trees at placement became a detour ratio of 1.54 against 1.20. Chips: Kendall 0.40 with routed wirelength (Kahng). Useful, weak alone |
| Airwire crossings | About 1 s | Monolith: +52 % on the worse placement. Cypress and NS-Place use it. Not isolated in any paper |
| Nets crossing each block boundary against corridor capacity | About 1 s | Battery-Bank: the failure the scripted board never recovered from (258 mm of signal track cut into a ground plane) was exactly this, and no other score here would have seen it |
| Clear band and escape check per fine-pitch IC | Seconds | Battery-Bank: without bands the router failed at exactly those pins |
| Hot-loop and gate-loop inductance on a quick pour | Seconds to minutes per loop | Battery-Bank: the score that matched what the owner cared about; capacitor position moved it by a factor of two |
| Pad-to-pin distance for bound parts, by rank | Milliseconds | Battery-Bank: feedback resistor 5 mm from its pin gave 204 mV per edge; fixed only by moving the part |
| Thermal spreading | Not built | No evidence either way in the record; nothing was powered |
| Trial route of inter-block nets with the existing router | Minutes | The only direct measure. Record: "a connection that fails with nothing else routed is a placement fault" |
| Silkscreen room | Seconds | Record: 14 designators could not be shown |

Order of use: legality, then the one-second scores on every candidate, then loop solver per power block, then the
trial route on the few survivors.

## 4. How this fits the pipeline

**Inputs from earlier stages.** Netlist with sheet hierarchy and net classes; the declarations of
`pcb-proto-flow` section 3 as symbol fields (switching nets, Kelvin pairs, hot loops, currents); footprints with
courtyards and heights; enclosure limits and fixed parts as data; stack-up. The Monolith schematic already carries
intent in prose: its symbol `Notes` fields say things like "gate resistor LODRV2 to LG2, low side". The LLM
should turn those into `bind` and `hot_loop` entries once.

**Steps and who does what.**

| Step | LLM | Code |
|---|---|---|
| Intent file per sheet | Writes it from schematic, notes and datasheet layout sections | Proposes bindings by the netlist rule (65 % right on Monolith), validates |
| Block solve | Picks template variant; reads score table | Enumerates, places, runs loop solver |
| Floorplan | Proposes zone order in power-flow order; reads crossings and corridor report | Anneals macros, reserves corridors and via sites |
| Diagnosis | Reads "block X: 9 nets cross toward Y, corridor holds 6"; calls a mutation | Re-solves only what changed |

**Outputs.** `placement.json`, the board with parts moved, reserved corridor and via-site keep-outs, a score
table with the previous run beside it, and renders of both sides.

**Automated check.** Legality, schematic parity, mechanical fit, every binding within its distance, every hot
loop under its limit, corridor capacity at least equal to demand, trial route of inter-block nets complete.

**Human gates.** Two, both on pictures with a table: the floorplan (zones and corridors, before any support part
is placed) and each power-stage template result. Logan's objections become intent rules or score terms.

**Token cost.** The expensive loop on Battery-Bank was look at a render, type a coordinate, re-render. Remove it:
no typed coordinates, text score deltas by default, pictures only at the two gates and for a cropped region when
a diagnosis fails twice. Solve a repeated block once. Cache block results by a hash of parts and intent so an
unchanged block costs nothing on the next run.

## 5. Automated improvement loop (no human-made boards from Logan)

**What can be scored by machine.** Everything in 3.6, plus after routing: completion, via count, detour ratio,
plane cuts, loop inductance, coupling per edge. These already exist in `groundup/compare/`.

**Data.**

- Monolith itself: hand placement against scripted, with full routed and solved results. The only power board,
  the only one with a known-good answer.
- Public boards in KiCad format: PCBWorld-Bench has 679 real open-source boards as `.kicad_pcb` (built for routing
  research). OmniLayout has 1,681 schematic-coupled boards from SparkFun, Adafruit, Arduino and others (EAGLE
  origin; the paper says CC-BY-4.0, project page only). PCB-Bench has 174 OSHWHub projects (licence not named).
- Synthetic: our own block templates instantiated with different parts.

**Loops, cheapest first.**

1. *Binding inference.* On public boards, the human layout gives a weak label: the pin each two-pad part sits
   nearest to on a shared net. Fit and test the netlist rule against that. Metric: agreement. Raises the 65 %.
2. *Proxy calibration.* Strip routing from public boards, perturb the placement in controlled ways (swap,
   rotate, shift blocks), route each variant with the same router, and regress routed results on the proxies.
   This tells us the weights and which proxies are worth computing. Metric: rank correlation per board.
3. *Weight tuning.* Bayesian optimisation of cost weights with the trial router and solvers as judge, the
   method Cypress takes from AutoDMP (30 trials per design there, router not in their loop).
4. *Template search.* Per stage type, enumerate and anneal poses with the loop solver as judge across a set of
   real FET, inductor and capacitor footprints. Keep the winners as defaults.
5. *Re-place and compare.* Re-place each public board from its netlist, route ours and the original with the
   same router, compare. Monolith is the held-out exam.

**Where the metrics mislead.**

- A router as judge rewards placements that suit that router. Kahng's chip result (proxy to routed wirelength,
  Kendall 0.40) is the caution. Cypress and OmniLayout both judge with FreeRouting on default settings.
- Public boards are mostly low-voltage hobby boards with few switching stages. They can calibrate signal
  routability, not hot loops, creepage or thermal.
- Human placements are not optimal, and "similar to the reference" is not a goal (OmniLayout says so too).
- Every electrical number is modelled. A placer tuned against an uncalibrated solver learns the solver's errors.
- Wire-length proxies say nothing about lanes and bundles, which is what the owner's eye caught.

## 6. Risks and unknowns

1. **Corridors.** The one unrecovered failure was a missing lane. Reserving corridors from boundary-crossing
   nets is an idea in the skills, untested. Sizing, layer choice and via fields at both ends are open.
2. **Templates may not generalise.** A buck stage with one FET package is easy; the Monolith stage is a
   four-switch buck-boost with shared sense resistors.
3. **Intent errors pass validation.** A binding to the wrong pin on the right net is legal. The same-net check
   catches none of the 37 semantic cases.
4. **CP-SAT scale and objective.** Proven only at 24 parts, with a distance objective, without proof of optimum.
5. **n = 1.** Every Battery-Bank number is one board, modelled, not built.
6. **Crossing count as a predictor** rests on two placements here and on papers that did not isolate it.
7. **Side choice** (parts under an IC on the back) is in no open placer and not in ours.

**Smallest spike for the biggest risk (1).** Take the Monolith hand board and the scripted board. Write the block
list (five sheets) and compute, for each pair of adjacent blocks, the nets that cross and the free width on each
signal layer between them. If the capacity-against-demand number is comfortable on the hand board and short on
the scripted board at the place where the 258 mm was cut, the score is real and the floorplanner can be built
round it. One day, no new placer, existing dumps. If it does not separate the two boards, corridor planning needs
a trial route instead, and the floorplan loop becomes minutes per candidate and not seconds.

Second spike: one buck-stage generator with three topologies and the loop solver, checked against the 0.37 to
0.39 nH that hand placement reached.

## 7. Sources

Local (read in full): `.claude/skills/pcb-scripted-placement/SKILL.md`, `pcb-layout/references/placement.md`,
`pcb-proto-flow/SKILL.md`, `tools/battery-bank/HANDOFF.md`, `groundup/placelib.py`, `fpdb.py`, `place*.py`,
`run.py`, `apply_place.py`, `mechcheck.py`, `placescan.py`; `groundup/README.md` (placement lines);
Gemini PDF pages 8 to 13.

Opened on the web:

- https://www.csl.cornell.edu/~zhiruz/pdfs/cypress-ispd2025.pdf : Cypress method, benchmarks, results, limits.
- https://github.com/NVlabs/Cypress : licence, usage, 746 commits. https://github.com/tapegoji/Cypress : fork, no stated changes.
- https://github.com/The-OpenROAD-Project/SA-PCB : features; archived 1 July 2026.
- https://arxiv.org/abs/2210.14259 : NS-Place, net separation, MILP legalisation, results.
- https://github.com/limbo018/DREAMPlace : v4.3.0, BSD-3, features, CPU-only.
- https://arxiv.org/html/2302.11014v3 : Cheng, Kahng et al., annealing against AlphaChip, proxy correlation, compute.
- https://cacm.acm.org/research/reevaluating-googles-reinforcement-learning-for-ic-macro-placement : Markov's review.
- https://github.com/LukeVassallo/RL_PCB : RL_PCB method, setup, limits.
- https://arxiv.org/html/2602.23540v1 : Lim, RL for passives round one IC; table against claims.
- https://www.cse.cuhk.edu.hk/~byu/papers/C247-ASPDAC2025-PCBAgent.pdf : PCBAgent division of labour and results.
- https://arxiv.org/html/2406.18873v3 : LayoutCopilot command set and accuracy.
- https://arxiv.org/abs/2607.03261 and https://arxiv.org/html/2607.03261 : OmniLayout tasks, per-model results, tool effect.
- https://iclr.cc/virtual/2026/poster/10009621 and https://github.com/digailab/PCB-Bench : PCB-Bench scope and data.
- https://neurips.cc/virtual/2026/161602 : PCB Gym, 32.1 % result.
- https://arxiv.org/abs/2607.05915 : PCBWorld, 679 real KiCad boards, routing environment.
- https://arxiv.org/html/2603.18102v1 : HWE-Bench (schematic only; not placement).
- https://arxiv.org/pdf/2606.17074 : survey of GenAI in PCB design; few placement works.
- https://curent.utk.edu/2024IndustryConference/papers/Conference_PE_18.pdf : Dong and Wang, B\*-tree annealing of a phase leg with FastHenry.
- https://par.nsf.gov/servlets/purl/10595462 : PowerSynth 2, constraint-graph layout of 2-layer converters.
- https://github.com/glovepost/atoplace : design, MCP tools, alpha status.
- https://pypi.org/project/kicad-parts-placer/ : what it does, 0.1.4, May 2024.
- https://docs.tscircuit.com/guides/tscircuit-essentials/automatic-pcb-layout : pack, flex, grid modes; beta.
- https://hn.jakechampion.name/reader/https://blog.autorouting.com/p/sequential-optimal-packing-for-pcb : tscircuit packing algorithm and its limits.
- https://cdn.jsdelivr.net/gh/atopile/atopile@main/README.md : atopile scope, MIT, layout in KiCad.
- https://docs.jitx.com/en/4.0/essentials/physical_design/index.html and .../kinematic-tree.html : code placement, pose tree.
- https://docs.quilter.ai/llms-full.txt and https://www.quilter.ai/llms.txt : Quilter controls, limits, tiers.
- https://www.quilter.ai/blog/the-2026-guide-to-autonomous-pcb-design-quilter-vs-deeppcb-vs-flux-ai : vendor comparison (Quilter's view).
- https://deeppcb.ai/kicad-autorouter-alternative/ : DeepPCB routes only; limits.
- https://semiengineering.com/ai-pcb-design-how-generative-ai-takes-us-from-constraints-to-possibilities : Allegro X AI, vendor description.
- https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/index.html : PCB design blocks, pin and gate swap.
- https://docs.kicad.org/9.0/en/pcbnew/pcbnew_editing.html : auto-place, pack and move, multichannel intro.
- https://forum.kicad.info/t/kicad-10-0-6-multichannel-with-repeat-placement/71678 : Repeat Layout user reports.

Could not open: Flux module documentation (two URLs returned an unrelated page), GitHub commit pages and API
(blocked in this session), Zuken AIPR pages (search results only). Registry checks run here: `ortools` 9.15,
`calculate-packing` 0.0.90, `@tscircuit/core` 0.0.2331, `atopile` 0.12.6, `atoplace` absent from PyPI.
