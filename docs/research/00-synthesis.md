# Research synthesis: what the five deep dives say, taken together

Written 2026-11-11. This reads across reports 01 to 05 in this folder. It is a proposal for Logan to accept,
change or reject. Nothing here has been built or measured on hardware.

## The one-paragraph answer

The LLM should write and review text, and never touch coordinates or copper. The circuit is written as code,
one small file per block, compiled to a netlist that is the source of truth, with the KiCad schematic generated
from it and proven equal. Part facts come from a knowledge base in the repo where every fact has a datasheet
page and quote and two sources that agree. Placement is done by a constraint-driven placer that reads an
intent file the LLM writes. Routing is split by net type: power copper is generated and checked by the DC
solver, critical loops come from templates scored by the loop solver, and plain signals go to Freerouting.
Verified, reusable blocks (circuit, constraints, laid-out fragment, testbench) are the main lever on both cost
and quality. Every change to the tool is judged by an automated benchmark before it is kept.

## Where all five reports agree

1. **No coordinates from the LLM.** Reports 02, 03 and 05 each reached this from separate evidence. On the
   PCBWorld benchmark (arXiv 2607.05915) an LLM driving a router segment by segment cleared 0 % of larger real
   boards, where Freerouting cleared 78 %. The LLM's job is semantics: which cap serves which pin, which nets
   switch, which loop is hot, why a route failed.
2. **The block is the unit of work, not the board.** Published whole-board schematic generation is about 8 %
   fully correct (HWE-Bench); block-level generation with a verifier is 80 % and up (PCBSchemaGen, SchGen).
3. **Small contexts and files, not one long conversation.** Report 03 read the Battery-Bank worklog: 396 million
   cache-read tokens against 2.3 million output tokens. The money went on re-reading a long context every
   turn. A compact netlist of a 430-part board is about 10 k tokens; the raw board file is about 3 M.
4. **Declared constraints in the design source.** What the last project typed into tools as lists (hot loops,
   Kelvin pairs, cap-to-pin bindings, currents) must be declared with the circuit, so placement, routing and
   the solvers all read one file.
5. **Keep the Battery-Bank check loop.** Real DRC, the DC, loop and coupling solvers, the tidiness measure and
   accept-or-revert are the most valuable thing carried over. They become the contract every engine is judged by.
6. **Build little, and only where nothing exists.** No new router. No reinforcement learning. The Gemini
   chat's case for a new Rust engine and its "memory wall" do not hold at our board sizes.

## Recommendation by stage

| Stage | Recommendation | Runner-up | Report |
|---|---|---|---|
| Circuit source of truth | Code per block on SKiDL 3.0, plus a thin layer for constraint declarations. Build emits netlist, constraints and a generated KiCad schematic; build fails unless KiCad's own netlist of that schematic matches | Diode's Zener (`pcb` CLI) | 01 |
| Part facts | Part knowledge base in the repo. Each fact: datasheet hash, page, verbatim quote. Accepted only when two independent sources agree. Deterministic PDF table read first, LLM read of the pin pages second | Adopt kicad-happy whole, add the two-source pin check | 04 |
| Schematic checks | Deterministic netlist rule engine reading the knowledge base, ERC, spec lint, fresh-context reviewer whose citations are checked by code | | 04 |
| Simulation | ngspice for what matters on a power board (inrush, startup, protection thresholds, loop stability where a model exists) | | 04 |
| Placement | Extend the Battery-Bank placer into a constraint-compiled, hierarchical one: power stages from parametric templates ranked by the loop solver, support parts per block with CP-SAT, a small annealer for the floorplan with corridors reserved | NVIDIA Cypress as floorplanner | 02 |
| Power copper | Build a generator (pours, via arrays, Kelvin taps from declared currents) grown against the DC solver. Nothing existing does this | | 03 |
| Critical nets | Templates, candidates scored by the solvers | | 03 |
| Plain signals | Freerouting 2.5/2.6 headless, then the existing cleanup passes | KiCadRoutingTools | 03 |
| System shape | File-driven pipeline of small stage agents, tiered models, block library, benchmark harness | | 05 |

## Where the reports disagree or leave a gap

1. **What a "block" is made of.** Report 01 makes code the truth and the KiCad sheet a generated view. Report
   05's first choice builds blocks on KiCad hierarchical sheets and design blocks, with code-first as runner-up.
   These need to be one decision. My read: follow 01 (code is truth), and store each block's laid-out fragment
   as a KiCad file keyed to the code's reference designators. The spike below tests whether that link survives
   a design change.
2. **SKiDL or Zener as the kernel.** 01 could run SKiDL but not Zener (download blocked). Zener's claimed
   advantage is that Claude was trained on it, which matters less if the tool must work with any LLM. Start on
   SKiDL, keep our layer thin, and test Zener on Logan's PC.
3. **A readable schematic.** Every existing schematic drawer 01 ran, bar one, produced sheets a reviewer would
   reject, and two were electrically wrong. Our own drawer is new work and the largest risk to "Logan reviews
   a readable schematic". The fallback is plain label-on-pin sheets plus a pin table per block.
4. **Freerouting is not enough for power nets.** In 03's own run it left 8 power-class connections open on a
   small charger and did not converge on an 804-pin four-layer board in 18 minutes. That is why power copper
   is generated separately and Freerouting only gets plain signals. Whether it copes with Monolith's signals
   after the power copper is in place is untested.
5. **Corridors between blocks.** The one thing the scripted Monolith never recovered from was a missing lane
   between the two power stages. 02 proposes corridor reservation in the floorplan, and says it is untested.
6. **Our own solvers read optimistic.** 04 tested them against known answers. The DC copper solver reads low
   by one grid cell of width (about 5 % on a 2 mm strip, about 17 % on a 0.5 mm neck). The loop solver reads
   10 to 20 % under a hand value, and needs a FastHenry cross-check to say how much is real. Fix or calibrate
   before any number from them gates a design.

## How the tool improves without Logan making boards

All five reports were held to this constraint. What they propose, in order of how much evidence backs it:

1. **Seeded faults (strong).** Take known-good designs, inject known bugs (swapped pins, missing pull-up,
   undersized trace), and measure which gate catches each. This scores the whole verification stack by machine.
   Monolith's five historical bugs are the first test set.
2. **Re-route and re-place public boards (strong).** 1,142 PCBench boards with human-routed references sit in
   Freerouting's repository, and PCBWorld adds 679. Score completion, DRC, via count, length and solver numbers
   against the human version. Few of them are power boards.
3. **Re-derive held-out designs from a written spec (moderate).** Score netlist similarity, solver metrics and
   BOM cost against the original. The spec writer must not leak the design.
4. **Tune weights and playbooks against the harness (moderate, with a warning).** It works, and it overfits: one
   2026 test saw optimised prompts fall below baseline on unseen tasks. Needs held-out designs and a
   no-regression gate.
5. **Grow the block library (the main lever).** Each verified block removes a re-derivation.

What machines cannot tell us: whether a board works. Nothing from Battery-Bank was ever powered. The few boards
Logan does build should carry test points and a bring-up log that feeds measured numbers back into the solvers
and the block library.

## Proposed spikes, in order

Each is small, uses Monolith, and settles one decision. None needs Logan to build anything.

| # | Spike | Settles | Size |
|---|---|---|---|
| 1 | Write two Monolith blocks as code (one power stage, the twice-used USB-C port). Generate KiCad sheets, require zero netlist diff, change one part and check "Update PCB" keeps the layout. Logan compares the sheets with his own | Source of truth, readable schematic, block-to-layout link | about 2 days |
| 2 | Build the part knowledge base for Monolith's roughly 25 ICs. Replay the five historical bugs plus fifty random mutants. Measure detection per gate and tokens per part | Verification stack, cost of grounding | about 2 days |
| 3 | Corridor capacity against crossing-net demand on the hand-routed and scripted Monolith boards: does the measure flag where the 258 mm of track cut the ground plane? | Whether the placement score can see the failure that mattered | about 1 day |
| 4 | Strip Monolith's plain signals, keep the hand-drawn power copper, route with Freerouting, KiCadRoutingTools and the existing router. Score all three with the same DRC, tidiness and solvers | Bulk routing engine | about 2 days |
| 5 | One block, changed spec, old way against the new pipeline, five runs on two models. Record tokens, time and solver scores | Whether the architecture is actually cheaper and better, and model-agnostic | a few days, after 1 and 2 |

Before spike 4, calibrate the two solvers (gap 6).

## What to treat with care

- Paper figures were read through a fetch tool that summarises pages. The four benchmarks leaned on most are
  PCBWorld (arXiv 2607.05915), PCBSchemaGen (2602.00510), HWE-Bench (2603.18102) and SchGen (2605.30345). Re-read
  the PDFs before any figure goes into the spec as fact.
- Several things could not be run in the cloud container: Zener, kicad-happy, KiCadRoutingTools, Cypress, edg.
  Running downloaded code was blocked, or a host was. These need Logan's PC.
- Commercial tools: no prices are published. Quilter's own documentation says above 48 V is unsupported and
  above 10 A is not well supported, which rules it out for this project's power work.
- atopile: the old release refuses to run and the new one stops at part picking and asks for a sign-in; its
  repository has been quiet since March 2026.
- KiCad 11 will remove the SWIG `pcbnew` interface the Battery-Bank scripts use, and adds a headless API and a
  schematic API. Pin the tool to KiCad 10 for now and plan the move.
- A real defect found on the way: `tools/battery-bank/schematic-tools/tpd6s300.py` lists pin 7 twice in its
  docstring (as RPD_G1 and as GND) and omits pin 8; the code puts GND on pin 8. I confirmed the docstring
  error. Which pin the datasheet gives was not checked (ti.com was blocked).
