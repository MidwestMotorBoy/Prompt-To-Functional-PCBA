# 05. Prior art, system architecture, and evaluation without human-made boards

Research agent 5 of 5. Written 2026-11-11. Status: every claim below is tagged in the text as **verified**
(I opened the primary source or ran the code), **vendor** (stated by the seller, not independently shown) or
**not verified** (I did not get to a primary source). Scripts and raw numbers for the one measurement I ran are
in the sibling folder `05-prior-art-architecture-and-evaluation/`.

## 1. Recommendation

Build a **file-driven pipeline of small stage agents around deterministic engines, composing a library of
verified design blocks**, and judge every change to it with an **automated benchmark harness** before it is
allowed into the playbooks.

- The LLM writes and reviews *text artefacts* only: spec, part-fact cards, a netlist-level design in a
  code-like form, constraint declarations, diagnoses. It never emits coordinates or copper. Published 2026
  benchmarks are consistent on this: LLMs route zero large real boards clean, and raw-geometry output fails
  DRC by an order of magnitude more than engine-mediated output.
- State lives in files; each stage starts with a fresh context holding a compact summary (about 10 k tokens
  for a 430-part netlist, against about 3 M for the raw board file). Strong model at design and review
  decisions, cheap or local model for extraction, scripts for everything else.
- The block library (schematic + declared constraints + placed-and-routed fragment + testbench + bring-up
  notes) is the main lever for both cost and quality.
- "Training" means: optimise playbooks against the harness with held-out designs and a no-regression gate,
  tune solver weights, grow the block library, and turn each failure into a check.

Runner-up: adopt a code-first EDA stack with an existing registry (Diode's open-source `pcb`/Zener, or
atopile) as the design representation and reuse their block mechanism instead of building one on KiCad
hierarchical sheets and design blocks.

## 2. Options compared

### 2a. Who has attempted prompt-to-PCB, and what is shown

| System (date checked) | Stage covered | How the LLM is used | Claimed | Independently shown | Fit for us |
|---|---|---|---|---|---|
| **Flux Copilot + AI Auto-Layout** (posts Jun 2025, Mar 2026, Oct 2026) | Spec dialogue to schematic to layout to review, in its own cloud ECAD | Agent with library, calculator and code tools; runs ERC/DRC as it goes; auto-layout engine undisclosed | "Human-style" routing on 2 to 4 layers (vendor) | Nothing. Flux's own post says actions "may only partially complete" and advises wiring two or three parts at a time | Closed, not KiCad-native, credits-metered. A reference for the UX, not a component |
| **Quilter** (Project Speedrun, Dec 2025) | Placement and routing only; input is a finished schematic plus human-written constraints | No LLM in layout. Physics-driven search, many seeded candidates, ranked | 843 parts, 2 boards, 8-layer HDI, 38.5 human hours against a 428-hour quote; 98 % routing completion; ran Linux, no respin (vendor) | A board that booted is real evidence the layout worked. The 428 h baseline is a quote, not a measurement. DeepPCB's rival test (also vendor) got 82 to 94 % completion from public Quilter on three open boards | Shows the winning split: human or LLM writes constraints, engine does geometry. Closed service; power/HV not addressed in what I read |
| **DeepPCB (InstaDeep)** (Apr 2026) | Routing (and placement) as a cloud service | RL router, no LLM | 96 to 99 % completion on three open KiCad boards (vendor) | Only completion and via counts are reported; no DRC, no electrical result | Possible alternative router to trial; outside my track |
| **Diode Computers** (`diodeinc/pcb`, MIT, last commit 2026-11-11) | Schematic as code (Zener), registry of modules with layout fragments, KiCad layout sync | Claude drafts modules from datasheets; programmatic checks and SPICE; engineers review; humans keep routing strategy | About 250 reference designs in two weeks; modules used in volume production (vendor) | No pass rates, token costs or board counts published. Their own blog: models "still trip up on... power delivery" | Closest prior art to our architecture. Open-source toolchain, KiCad output. Strong runner-up for representation |
| **atopile** (MIT, last commit 2026-03-11) | Schematic as code, parametric part picking, package registry, KiCad layout reuse | Publishes EEBench; language designed for agents | n/a | EEBench V1: top agent 75.0 %, held-out tasks, deterministic simulation grading; layout "deliberately out of scope" | Mature idea; repo quiet for 8 months, which needs asking about before depending on it |
| **JITX** (Sep 2025 post) | Code-defined design, constraint-driven topological router | AI writes JITX code, parses datasheets | Moving front end from Stanza to Python (vendor) | Not verified beyond the post | Closed, commercial. Source of ideas only |
| **CELUS** (Siemens blog, Feb 2026) | Block diagram to schematic from vendor-curated blocks (spelled "Kubos" in the Siemens post) | Assistant suggests validated blocks | Requirements to schematic "in hours" (vendor) | Nothing | Confirms that curated blocks are how commercial tools get reliability |
| **Cadence Allegro X AI, Altium, Circuit Mind, SnapMagic Copilot** | Placement/routing generation; part selection; symbol help | Mixed | Vendor only | **Not verified this pass**: I only saw search listings | None needed for v1 |
| **OpenAI GPT-6 Astra KiCad demo** (Sep 2026) | Schematic to routed board in KiCad | LLM drives KiCad | A 15-second clip (vendor) | Hackaday comments: one user reports three Claude-designed boards working first time with "wonky" routing; others report open circuits and discontinued parts recommended | Anecdote, both ways |

### 2b. Open-source agents and MCP servers for KiCad (activity checked by shallow clone on 2026-11-11)

| Project | Last commit | Licence | Approach | What it checks automatically | Maturity note |
|---|---|---|---|---|---|
| `mixelpixx/KiCAD-MCP-Server` v2.8.3 (the one on Logan's PC) | 2026-11-09 | MIT | TypeScript MCP server over a Python pcbnew worker, optional IPC API; about 250 tools; "toolboxes" start at 37 tools | ERC, DRC, exports, Freerouting bridge, JLCPCB part search | Active. README says a dispatcher design was removed because the model invented arguments for tools it had not been shown. Author's new work is moving to an AGPL Rust rewrite |
| `aklofas/kicad-happy` v3.0.1 | 2026-11-06 | MIT | Skills plus pure-Python analysers; LLM reads analyser JSON and datasheets | Power tree, regulator Vout, 40 domain detectors, 44 EMC rules, generated SPICE testbenches, DFM, BOM, a fab release gate; per-part datasheet fact cache with hash-based staleness | Regression-tested on 5,857 public KiCad repos (36,463 schematics, 18,751 boards). Its own words: this "does not prove the output is correct" |
| `lamaalrajih/kicad-mcp` | 2025-10-17 | MIT | Read-mostly MCP (project listing, DRC, BOM) | DRC, netlist extraction | Stale for a year |
| `Seeed-Studio/kicad-mcp-server` | 2026-10-22 | none stated | MCP server | Not examined | Active, no licence file: do not build on it |
| `circuit-synth` | 2026-03-07 | MIT | Python circuit definitions to KiCad, Claude Code agents | ERC | Quiet since March |
| `devbisme/skidl` | 2026-11-07 | MIT | Python netlist DSL; used by PCBSchemaGen | ERC | Old, alive, stable |
| `tscircuit` | 2026-11-10 | MIT | React/TypeScript circuits, npm-compatible registry, own autorouter | Own DRC | Very active; not KiCad-native |

### 2c. Academic work that bears on the architecture (all 2026 unless noted; all verified by opening the paper or page)

| Work | What was measured | Headline result | What it implies |
|---|---|---|---|
| **PCBWorld** (LG AI Research, arXiv 2607.05915; code BSD-3) | Routing on 679 real KiCad boards through 58 engine APIs | Clean-pass on medium real boards: Freerouting 0.80, GPT-5.4 0.65. On large boards: Freerouting 0.78, **every LLM 0.00**. Without engine feedback GPT-5.4 leaves 34.6 DRC violations per board against 1.3 with it. Open-loop plans: 0.19 | The LLM must not route. Engine feedback is necessary but not sufficient at our board size |
| **PCB-Bench** (ICLR 2026) and **OmniRouting** (arXiv 2608.04434) | Placement and routing reasoning questions; 1,681 industrial boards | Weak path planning, design rules not followed, connectivity inconsistently preserved | Same |
| **HWE-Bench** (arXiv 2603.18102) | 300 board-level schematics from scratch, static rules then LTspice | Best model 8.15 % fully correct. Failure modes: pin-role confusion, pin-mux conflicts, "context cognition overload" on large designs | One-shot schematic generation does not work; block-by-block with pin-level checks is required |
| **PCBSchemaGen** (UT Austin power-electronics group, arXiv 2602.00510) | Frozen LLM writes SKiDL; deterministic 5-layer verifier returns pin-level errors; per-IC pin-role cards of about 300 tokens | Removing the part cards drops hard-task pass from 47.1 % to 2.0 %. Pin-level feedback beats pass/fail feedback by 23.6 points. Verifier false-accept 6.7 %. Covers gate drivers, power stages, BMS | Strongest published support for cached part-fact cards plus localised deterministic feedback. Code is PolyForm **Noncommercial**: reuse ideas, not code |
| **SchGen** (Microsoft, arXiv 2605.30345; MIT) | Same model, different output representations | Semantic API with pin names: 60.5 % functional. Raw KiCad file: 3.0 % | Never have the LLM write `.kicad_sch` directly |
| **PCB-QA** (arXiv 2606.23704) | 480 questions on 8 open KiCad boards in three encodings | Purpose-built JSON 84 to 93 % accuracy; native KiCad files 48 to 86 % and about 100 k tokens on the largest board; PDF schematics 43 % | Compact derived encodings are both cheaper and more accurate |
| **EDA Bench** (ICML 2026 workshop) | 35 open boards rebuilt by agents, graded by extracted parasitics, shorts, ngspice | Best harness 4.58 %; 21 of 35 built but failed functional checks | "Parseable" is not "works". Functional grading must be in our harness |
| **PCBInnoBench** (NeurIPS 2026) | 372 expert KiCad modification tasks | 22.0 % pass with an expert trajectory supplied, 7.3 % without | Playbooks roughly triple agent success on ECAD tasks |
| **AutoCircuit-RL** (arXiv 2506.03122, 2025), LaMAGIC | Power-converter topology generation, trained on about 100 k random netlists labelled by ngspice | About 60 % constraint success at 6 to 10 components | Machine-labelled synthetic training works for toy topologies only; not a route to a 430-part design |
| **GEPA** (ICLR 2026 oral) and **"Do Agent Optimizers Compound?"** (arXiv 2607.14004) | Prompt optimisation by reflection on traces | GEPA beats MIPROv2 by over 10 % with few rollouts; but in a continual test its prompt grew from 5 to 195 lines and fell **below baseline** on unseen tasks (54.5 % against 56.8 %) | Prompt optimisation is real but overfits; hold-out and no-regression gates are mandatory |
| **LLMREI** (RE 2025), **OntoAgent** (arXiv 2605.05828) | LLM-led requirements interviews | Free-form LLM interviewer elicited about 74 % of requirements; a slot ontology raised implicit-requirement recall from 0.52 to 0.69 | Drive the spec dialogue from a slot checklist, not free chat |

## 3. Evidence per option

### 3.1 What worked and what failed for others

**Geometry by LLM fails; this is now measured, not just asserted.** PCBWorld is the cleanest evidence because
it grounds scoring in KiCad's own DRC. Three engagement modes were compared: emitting raw segments
(34.58 violations per board), planning then executing blind (0.19 clean-pass), and stepping with engine
feedback (0.65). Even the best mode gets zero large boards clean and takes about 94 s per small synthetic
board where a trained policy takes 0.43 s. The Gemini chat's claim that an LLM asked for raw coordinates will
"hallucinate horribly" therefore **holds** against a primary source. Its companion claim, that LLMs have
"world-class semantic circuit intuition", is only **partly supported**: HWE-Bench's 8 % and EDA Bench's 4.6 %
show that intuition does not survive contact with pin-level detail unless facts are supplied and checked.
The Gemini proposal of a restricted mutation vocabulary (rotate, flip side, inflate courtyard, swap pins)
driven by a text bottleneck report is consistent with all of this, but I found **no published measurement**
of that specific loop; treat it as a design hypothesis to test in the harness. I found no evidence for or
against its claim that multimodal models are "remarkably good" at reading cropped congestion images; PCBWorld
argues the opposite for pixels as the main state. Our own project's evidence is that pictures were how the
agent worked out power-stage geometry, at high cost.

**What the commercial successes have in common.** Quilter (no LLM in layout, human-prepared constraints,
many parallel candidates ranked by physics checks), Diode (LLM composes pre-verified modules that carry their
own layout fragment; humans own routing strategy and sign-off) and CELUS (curated blocks) each got reliability
from the same two things: declared constraints as the interface, and reuse of verified pieces. None shows an
LLM producing a novel, correct power stage layout. Diode's own post lists power delivery among the things
models still get wrong.

**Where users say it fails** (EEVblog thread March 2026, Hackaday comments September 2026, a fab vendor's
write-up; all anecdote): "very little concept of spatial relationships"; KiCad S-expressions are hard for the
model to edit; answers follow the user's framing (a decoupling question agreed with whichever option was
proposed); a non-standard footprint mapped power pins to ground; a discontinued part was recommended as a
replacement for a discontinued part; excess vias and unexplained thin traces from the layout services. The
uses people report as working are checking, BOM and stock work, symbol and footprint drafting from existing
ones, and reasoning about SPICE output. That matches the Monolith experience exactly: review found the serious
bugs, and script-generated symbols were the top source of wiring errors.

### 3.2 LLM-strong and engine-strong stages

| Stage | LLM role | Deterministic engine | Evidence |
|---|---|---|---|
| Requirements dialogue | Strong: asks, summarises, spots gaps | Slot checklist and budget arithmetic decide completeness | LLMREI, OntoAgent |
| Part research | Strong at reading datasheets; weak from memory | Distributor APIs for stock and lifecycle; cached fact cards with source hash | PCB-QA (datasheet questions hardest), Hackaday anecdote, kicad-happy cache |
| Topology and architecture | Strong when choosing among known blocks; weak inventing | SPICE testbench per block | EEBench 75 % on simulated analog blocks; AutoCircuit-RL limits |
| Schematic capture | Medium, only in a code-like netlist form, block by block | Compiler, ERC, pin-role verifier with pin-level messages | SchGen, PCBSchemaGen, HWE-Bench |
| Constraint writing | Strong (which loop is hot, which pair is Kelvin) | Schema validation; solvers consume them | Monolith skills; Quilter's workflow |
| Placement and routing | Diagnosis and choice among discrete mutations only | Placer, router, DRC, loop/DC/coupling solvers | PCBWorld, PCB-Bench, OmniRouting |
| Review | Strong, especially a second model with a different prompt | Seeded-fault tests keep it honest | Diode's review post (vendor); Monolith |
| Fab outputs | None | Scripts | Monolith |

### 3.3 Token cost: one measurement, and what the last project implies

I measured encodings of a real open board (LibreSolar `bms-c1`, 199 parts, 142 nets, 525 pads) with the
GPT-4o tokenizer, because Claude's tokenizer was not reachable from this container. Anthropic documents its
current tokenizer as using up to about 1.35 times as many tokens as the older one, so read these as lower
bounds and re-measure with the `count_tokens` endpoint.

| Encoding | Tokens (199 parts) | Per part | Scaled to 430 parts |
|---|---|---|---|
| Raw `.kicad_pcb` | 1,389,120 | 6,980 | about 3.0 M (does not fit any context) |
| Raw `.kicad_sch`, all sheets | 411,631 | 2,069 | about 890 k |
| Verbose JSON, one object per pin | 20,700 | 104 | about 45 k |
| Compact JSON | 8,291 | 42 | about 18 k |
| Net-centric text plus part list | 6,349 | 32 | about 14 k |
| Component-centric text, two-pin parts on one line | 4,819 | 24 | about 10 k |
| Placement table (ref, footprint, x, y, rot, side) | 4,509 | 23 | about 10 k |
| ICs, FETs, connectors only, passives counted | 2,227 | 11 | about 5 k |

So a full-board netlist is a 10 k-token object if encoded on purpose and a three-million-token object if the
file is read. Per-block views (one hierarchical sheet, 20 to 60 parts) are 0.5 to 1.5 k tokens. The scaling
to 430 parts is linear extrapolation, not a measurement of Monolith.

Why the last project was expensive, read from its own skills: one long conversation carried the board; the
agent "only ever saw the layout through the pictures the script makes", after every pass; knowledge was
re-derived rather than cached; and the tool server exposes about 250 tool definitions. With an agent loop,
every turn re-reads the whole context, so cost grows with (context size) x (turns). Illustration from list
prices in Anthropic's current price table (Opus 5.5 at $4 per million input tokens, cache reads $0.20; Haiku
5.5 at $0.10): 200 turns over a 150 k context is 30 M input tokens, about $120 uncached and about $6 if the
prefix is cached and stable. The same 200 turns over a 15 k stage context is about $12 uncached. Anthropic's
own engineering posts give the general figures: agents use about 4 times the tokens of chat and multi-agent
systems about 15 times, and multi-agent pays only for parallel, loosely coupled work (June 2025); exposing
tools as code and filtering results outside the model cut one workflow from 150,000 to 2,000 tokens
(November 2025). Layout is tightly coupled work, so parallel sub-agents on one board are the wrong tool;
parallel *runs of the engine* are the right one.

### 3.4 Design-block libraries: who does it and how

- **Diode registry** (vendor description, open toolchain): a Zener module, a validated layout fragment and
  manufacturing data, searchable by the agent. Verified by SPICE and netlist checks, then human review, then
  use in products.
- **atopile packages** (`packages.atopile.io`): parameterised `ato` modules with units, tolerances and
  assertions solved at build time; layout reuse into KiCad.
- **tscircuit registry**: npm-compatible packages; layout reuse and licence terms are not described on the
  registry page I read.
- **KiCad design blocks**: schematic blocks arrived in KiCad 9; KiCad 10 (March 2026) "extended the Design
  Blocks feature to the PCB editor". A KiCad forum thread from August 2026 on 10.0.4 shows it works when the
  layout is saved into the *same* block as the schematic and "Group footprints" plus "Apply design block
  layouts to new groups" are on, and that hierarchical sheets are not carried by a block. It is usable but
  young, GUI-oriented, and has no parameters.
- **Manufacturer reference designs**: often in Altium or OrCAD, sometimes KiCad. **Licences not verified this
  pass**; TI and ADI terms generally permit use to build products with their parts but that needs reading per
  design. Treat as inspiration for our own blocks, and record provenance.
- **Open-hardware repos**: licence varies (CERN-OHL-S and CC-BY-SA are share-alike; CERN-OHL-P, MIT and
  Apache are permissive). A block copied from a share-alike board carries the obligation into the product's
  design files. For a personal project this is manageable; the block's metadata must record source and
  licence so it is a decision and not an accident.

Parameterisation that is realistic: values computed from the spec by a script inside the block (feedback
divider, inductor, sense resistor, compensation), a small set of footprint variants, and a *fixed* layout
fragment per variant. Blocks whose geometry must change with parameters (a power stage across current
ratings) should be separate variants, each verified, rather than a generator. A block is "verified" at
graded levels, recorded in its metadata: L0 compiles and passes ERC; L1 testbench passes in SPICE across
tolerance corners; L2 layout fragment passes DRC and its loop/DC/coupling solver budgets in isolation; L3
built and measured on a real board.

### 3.5 Data usable with no human labelling

| Corpus | Size | Licence | Use | Caveat |
|---|---|---|---|---|
| kicad-happy test harness list | 5,857 GitHub KiCad repos, 18,751 boards; 207 tagged power/battery, 315 motor control | Each repo its own | Ready-made, categorised crawl list | The harness repo holds the list; I did not open it. Many KiCad 5 files |
| Open Schematics (Hugging Face `bshada/open-schematics`) | 10 k to 100 k schematics with paired board files, renders, JSON | CC-BY-4.0 for the collection; originals keep their own | Netlist statistics, block mining, retrieval | Quality mixed; 55 % of board images missing |
| PCBWorld D3 (from PCBench) | 679 real boards in `.kicad_pcb` | Code BSD-3; data licence not confirmed | Routing and placement benchmark with DRC ground truth | Routing only |
| PCBSchemaGen benchmarks | 62 + 165 tasks, power-electronics heavy | PolyForm Noncommercial | Schematic-stage evaluation ideas | Noncommercial |
| OSHWA certification directory | 3,352 certifications as of June 2026 | Per project; all must publish design files | Best filter for "was actually built": certification requires a real product | Many are not KiCad; I did not check the API |
| SchGen dataset | 2,105 SparkFun KiCad schematics | CC-BY-SA 4.0 | Small-board schematic tasks | Share-alike |
| OSHWHub / OSHWLab (JLCPCB/EasyEDA) | Large; used by PCB-Bench and HWE-Bench | Per project | JLCPCB-built designs | EasyEDA format, not verified in detail |

Filtering by machine: for power electronics, keyword and part-class detection on the netlist (gate drivers,
MOSFETs above a current rating, inductors, BMS and PD controller part numbers; kicad-happy's detectors already
do this). For "actually built": OSHWA UID present; repository has fab outputs, tagged hardware revisions
(rev B after rev A is strong evidence of bring-up), photos, or a bring-up or errata file; a commercial product
page. No single signal is reliable; a score from several is.

## 4. How this fits the pipeline

### 4.1 Organisation

```
spec/            requirements.yaml, decisions.md (dated), open-questions.md
parts/           one fact card per MPN (pins, roles, limits, source page, PDF sha256), stock snapshot
blocks/          library: block.yaml, netlist source, constraints, layout fragment, testbench, bring-up notes
design/          top-level composition (which blocks, how wired), generated netlist, KiCad project
layout/          floorplan.yaml, constraint set, placer/router configs, candidate runs with scores
verify/          per-stage reports (JSON + 1-page summary), seeded-fault results
runs/            ledger: per stage, per model: tokens in/out/cached, wall time, tool calls, verdict
```

Rules that follow from the evidence:

1. **One stage, one fresh context.** A stage agent receives the playbook for that stage, the spec summary, and
   the compact view it needs, and writes a file plus a hand-off note of fixed shape (what was decided, what is
   open, what the next stage must not change). Nothing is carried by conversation.
2. **Tools as CLIs first, MCP second.** Every operation is a command that reads and writes files and prints a
   short JSON summary; the MCP server is a thin wrapper exposing perhaps 10 to 20 tools per stage. The
   `KiCAD-MCP-Server` toolbox mode (37 tools) is the right default; all 250 loaded is not.
3. **Bulk work never passes through the model.** Placement search, routing, DRC, solver sweeps and candidate
   ranking run as scripts; the model sees a table of the top candidates and the specific failures.
4. **Decision points only.** The model is called to choose a block, write constraints, pick among ranked
   candidates, diagnose a named failure with a restricted action list, and review.
5. **Images by exception.** One floorplan picture at the human gate, and a cropped image only when a text
   bottleneck report has failed to resolve a problem twice. Log whether the image changed the decision, so
   the harness can tell us if images earn their cost.
6. **Caching at three levels.** Part-fact cards keyed by MPN and PDF hash (never re-read a datasheet); block
   library; and API prompt caching with the playbook and spec as a stable prefix.
7. **Model tiers, set per stage in a config file, not in prompts.** Strong model for architecture, constraint
   writing, diagnosis and review; mid model for block instantiation and report writing; cheap or local model
   for datasheet table extraction, with every extracted pin table checked by a second pass against the PDF
   text. EEBench is a warning here: the cheapest model on its board scores 3.5 % where the best scores 75 %,
   so cheap models do extraction, never design. Batch API (half price) for anything not interactive: harness
   runs, bulk datasheet extraction, review passes.
8. **Model-agnostic by construction, and tested.** Playbooks are plain markdown; outputs are schema-validated
   files; the harness runs the same pipeline with each candidate model and reports score and cost per stage.
   A second model from a different vendor is the default reviewer.

### 4.2 Inputs, outputs, checks and gates by stage (summary)

| Stage | Input | Output | Automated check | Human gate |
|---|---|---|---|---|
| Requirements | Problem statement, dialogue | `requirements.yaml` | All mandatory slots filled or waived; power, thermal and cost budgets close arithmetically | Logan signs the one-page summary |
| Research and parts | Spec | Fact cards, candidate list | Pin table cross-checked against PDF; stock and lifecycle from API | Approves part choices |
| Architecture | Spec, cards, block index | Block composition | Every requirement traced to a block or marked open; block interfaces type-check | Approves block diagram |
| Schematic | Composition | Netlist, KiCad schematic | ERC; pin-role verifier; SPICE testbenches; netlist diff against blocks | Reviews deltas from library blocks only |
| Layout | Netlist, constraints, fragments | Board candidates | DRC, loop/DC/coupling budgets, tidiness measure | Looks at the top candidate in KiCad |
| Fab | Board | One labelled file set | Fab release gate | Places the order |

### 4.3 Requirements dialogue

Use the spec template as the ontology (OntoAgent's result is that this, not better prompting, is what raises
recall). For a power board the slots include: sources and their ranges and impedances; each load with
steady, peak and transient current; fault cases and required response; isolation and creepage class; ambient
and enclosure; efficiency and thermal limits; connectors and mechanical envelope; standards; test access;
unit cost and quantity; what Logan will measure at bring-up. Question strategy from the two studies: rank
slots from the opening statement and ask about the highest-value empty one; one question per turn, or two
closely related; yes/no confirmation for a topic only mentioned, open question where a partial constraint
exists; after a few unproductive questions in an area ask one closing question and move on; always end with a
written summary for correction. Offer a proposed default with its consequence instead of an open question
wherever a sensible default exists, because Logan is a reviewer. The spec is complete enough when every
mandatory slot is filled or explicitly waived with a date, the derived budgets close, every requirement has a
verification method (simulation, solver, bench measurement), and a second model asked to find a design
decision the spec does not determine returns nothing above a set severity. The last criterion is my
proposal, not published practice.

## 5. The automated improvement loop

### 5.1 The harness

A command, `bench run --suite S --pipeline P --model M`, that produces a score card and a cost ledger.
Suites, cheapest first:

1. **Part-fact accuracy.** For 200 or so parts with machine-readable ground truth (KiCad library symbols for
   the pin table, distributor parametric data for limits), extract a fact card from the PDF and score pin
   name/number/role agreement. Metric: fraction of parts with a perfect pin table. This targets the top bug
   source of the last project and needs no human labels.
2. **Seeded-fault detection.** Take known-good open designs and inject faults by script: swapped pins, wrong
   feedback divider, missing bootstrap capacitor, undersized trace on a current path, Kelvin tap moved onto
   the power path, decoupling capacitor detached from its pin, creepage violation, net-class downgrade.
   Metric: detection rate and false-alarm rate per fault class, for the deterministic checks alone and for
   checks plus LLM review. This is the most trustworthy suite because ground truth is exact.
3. **Stage tasks on held-out blocks.** Given a spec fragment and fact cards, produce a block netlist; grade
   by ERC, pin-role checks and a SPICE testbench at tolerance corners (the EEBench and PCBSchemaGen method).
4. **Re-derivation of held-out open boards.** A script-plus-LLM pass writes a spec from an existing built
   board (function, rails, loads, connectors, envelope) with the design withheld; the pipeline designs to the
   spec; score against the original on functional checks first (testbenches, rail and protection behaviour),
   then solver metrics, DRC, BOM cost and part count. Netlist similarity (graph or Jaccard) is recorded but
   not optimised, because many correct circuits differ from the original (HWE-Bench makes this point).
5. **Layout-only tasks.** Strip placement and routing from real boards (PCBWorld's D3 set, plus power boards
   from the crawl list), re-lay them with our engines and declared constraints, and compare with the human
   layout using the Monolith solvers and tidiness table. This suite needs almost no LLM tokens and can run
   in very large numbers on the desktop.
6. **Requirements suite.** A simulated stakeholder holds a hidden checklist derived from a real board's
   spec; score the fraction of items elicited and turns used (IRE and TKQR from OntoAgent).
7. **Cross-model agreement.** Same task, two models: disagreement on a fact or a review finding flags the
   item for the stronger check. Agreement is a triage signal, not a correctness metric.

Every run logs tokens (input, cached, output), wall time and tool calls per stage, so "cost per passing
design" is a first-class metric next to quality.

### 5.2 What "training" can honestly mean here

| Method | Evidence | Verdict |
|---|---|---|
| Growing the block library; every block verified to a recorded level | Diode and CELUS practice (vendor); PCBSchemaGen ablation (part cards 2 % to 47 %) | Highest value. Do first |
| Distilling each failure into a deterministic check, with a seeded-fault test that proves the check fires | Monolith practice; kicad-happy's 175 bug-fix guards | High value, compounding, no overfitting risk |
| Tuning placer/router cost weights by black-box search against solver scores on suite 5 | Standard practice in placement research; other agents cover it | Sound; pure compute |
| Playbook and prompt optimisation against the harness (GEPA or DSPy style) | GEPA: over 10 % gain over MIPROv2 with few rollouts. Counter-evidence: prompt bloat and below-baseline transfer in a continual test | Use with a train/validation/test split of designs, a size cap on playbooks, and a rule that no change ships if any held-out suite regresses |
| Playbooks at all | PCBInnoBench: 22.0 % with expert trajectory against 7.3 % | Proven; we already have 16 |
| Fine-tuning a small model on public schematics | SchGen: fine-tuned 20B model beat prompted frontier models in-distribution, lost validity out of distribution | Speculative for us; small boards only; defer |
| RL for topology or routing on synthetic data | AutoCircuit-RL (10 components); PCBWorld's PPO policy beats Freerouting on medium boards, loses on large (0.45 against 0.78) | Promising research, not a v1 dependency |
| Self-play on full prompt-to-board | None found | Speculative |

### 5.3 Where machine metrics will mislead

- **Nothing has been powered.** All Monolith numbers are modelled. The harness inherits every modelling
  error: a solver bias is optimised *into* the design. Until a board is measured, calibrate each solver
  against a published figure (an app-note loop inductance, a datasheet evaluation-board efficiency curve).
- **SPICE passes that the bench fails**: vendor models that omit start-up, protection and thermal behaviour;
  layout parasitics missing from the testbench; magnetics saturation; firmware and configuration defaults.
- **Similarity to the original board rewards copying its mistakes** and penalises better designs.
- **Public boards are mostly hobby boards**, few are power electronics, and a public repository is not
  evidence of a working board. Scores on them may not transfer to HV work.
- **Verifiers have error rates.** PCBSchemaGen measured 6.7 % false accept on its own verifier. Ours must be
  measured the same way by the seeded-fault suite.
- **Optimisers exploit graders.** Any metric that can be satisfied without being right will be. Keep one
  suite the optimiser never sees.
- **Tidiness and "looks right"** have no ground truth beyond Logan's eye; the tidiness table is a proxy
  built from two of his objections.
- **Contamination**: public boards may be in model training data, so re-derivation scores flatter the model.
  Prefer boards published after the model's cutoff and compare across models with different cutoffs.

### 5.4 What must still be validated on hardware, and getting the most from few boards

Only a bench can confirm: loop inductance and switch-node ringing, efficiency and temperature rise, control
loop stability under real load steps, protection thresholds and timing, current-sense accuracy, start-up and
brown-out behaviour, EMI, and anything depending on firmware. With perhaps two or three boards a year, each
must be built as an instrument:

- Test points and Kelvin sense pads at every quantity a solver predicted, placed by rule from the constraint
  declarations; a coaxial or spring-ground probe point at each switch node; zero-ohm links or jumpers that let
  each block be powered alone; a loop-injection resistor in each feedback path; footprints for an optional
  snubber and gate-resistor variants.
- A bring-up plan generated from the netlist before ordering (the `bringup-planning` skill exists), in which
  every step has a predicted value with tolerance taken from the same models the harness uses.
- Results entered as data against those predictions. Each one updates three places: the solver calibration
  (measured against modelled), the block's verification level (L2 to L3) and bring-up notes, and the spec if
  a requirement turned out wrong.
- Prefer a small **block coupon** board early: a panel of the library's riskiest blocks (one power stage, one
  sense chain, one protector) with full instrumentation. One cheap order then calibrates the solvers and
  promotes several blocks, which is worth more to the tool than one more complete product board.

## 6. Risks, unknowns, and the spike

| Risk | Why it matters | Mitigation |
|---|---|---|
| Block library is slow to reach useful coverage | Until it does, the pipeline re-derives, which is the expensive and error-prone path | Seed from Monolith's own sheets first (they exist, were reviewed, and will be built); then the blocks the next board needs |
| The representation choice (other agent's track) determines whether blocks can carry layout | KiCad 10 PCB design blocks are young and unparameterised; Diode's and atopile's mechanisms are more mature but add a toolchain | Decide jointly with the representation track; the block metadata schema proposed here is independent of that choice |
| Harness optimises modelled numbers that are wrong | Nothing has been measured | Coupon board; solver calibration against published figures |
| Prompt optimisation overfits | Shown in a 2026 continual test | Hold-out, size cap, no-regression gate |
| Spec written from an existing board leaks the design | Inflates re-derivation scores | Spec writer sees function and interfaces only; a leak check greps the spec for part numbers and values |
| Cheap or local models corrupt part facts | Top bug source last time | Extraction always double-checked against PDF text; fact-accuracy suite gates any model change |
| Licence contamination from mined blocks | Share-alike terms follow the design | Provenance and licence fields mandatory in block metadata |
| atopile's repository has been quiet since March 2026 | Affects the runner-up | Ask before depending on it; Diode's `pcb` is active as of today |
| Vendor claims in this report | Most commercial numbers are unverified | Marked as such; none of the recommendation depends on them |

Biggest unknown: **whether block composition plus small stage contexts actually cuts cost and raises quality
on a design of Monolith's kind**, as opposed to on benchmarks. Smallest spike that would settle it:

1. Take one Monolith sub-circuit that exists twice or is self-contained (one buck or buck-boost power stage
   with its controller, about 40 parts).
2. Package it by hand as a block: netlist source, declared constraints (hot loop, gate loop, Kelvin pair,
   cap-to-pin bindings), the hand-routed layout fragment, a SPICE testbench, and solver budgets.
3. Run two arms on the task "produce this stage for a changed spec" (different output voltage and current):
   arm A, the old way, one long agent conversation with the full tool set; arm B, the stage pipeline composing
   the block, compact views only, tiered models.
4. Run each arm five times on two models. Record tokens, wall time, ERC/DRC, testbench pass, loop and
   coupling solver numbers against the hand-routed original, and the seeded-fault detection rate of the
   review step.

That is a few days of work, needs nothing from Logan but a look at the two results, and gives the first real
cost-per-passing-design figures for both architectures. If arm B is not several times cheaper at equal or
better solver scores, the plan in section 1 needs rethinking before more is built.

What I could not do: reach the GitHub API (activity was checked by shallow clone instead); run the
`kicad-happy` analysers on the test board (execution of downloaded code was blocked in this session; I read
its README and validation notes instead); count tokens with Claude's own tokenizer; open primary sources for
Cadence, Altium, Circuit Mind and SnapMagic; read the first nine pages of the Gemini PDF in detail (it is
image-only; I read pages 10 to 13, which carry the LLM-in-the-loop section).

## 7. Sources

Opened and read (via page fetch unless stated). Dates are as the page gave them.

Benchmarks and papers
- https://arxiv.org/pdf/2607.05915 : PCBWorld. LLM, RL and Freerouting clean-pass rates on real KiCad boards; engine-free against interactive DRC counts.
- https://arxiv.org/html/2603.18102v1 : HWE-Bench. 8.15 % best end-to-end schematic correctness; failure modes.
- https://arxiv.org/pdf/2602.00510 : PCBSchemaGen. Part-card and pin-level feedback ablations; verifier error rates; licences.
- https://www.alphaxiv.org/abs/2605.30345.md : SchGen. Representation ablation (semantic API against raw KiCad).
- https://arxiv.org/pdf/2606.23704 : PCB-QA. Accuracy and token size by netlist encoding.
- https://icml.cc/virtual/2026/77908 : EDA Bench abstract. 4.58 % functional pass; 21 of 35 built.
- https://neurips.cc/virtual/2026/poster/139034 : PCBInnoBench abstract. 22.0 % with guidance, 7.3 % without.
- https://digailab.github.io/PCB-Bench : PCB-Bench composition and data source (OSHWHub).
- https://www.alphaxiv.org/abs/2608.04434 : OmniRouting abstract. 1,681 boards; weak path planning.
- https://arxiv.org/html/2506.03122v1 : AutoCircuit-RL. Synthetic ngspice-labelled training; 4 to 10 components.
- https://arxiv.org/abs/2507.19457 : GEPA abstract. Gains over MIPROv2 and GRPO.
- https://arxiv.org/pdf/2607.14004 : "Do Agent Optimizers Compound?". GEPA prompt growth and transfer regression.
- https://arxiv.org/html/2507.02564v1 : LLMREI. Share of requirements elicited; question types.
- https://arxiv.org/pdf/2605.05828 : OntoAgent. Slot ontology, IRE/TKQR metrics, stopping rules.
- https://www.eebench.org/ and https://www.eebench.org/methodology.html : EEBench scope, grading, held-out tasks, layout out of scope, atopile provenance.
- https://benchlm.ai/md/benchmarks/eebench.md : EEBench leaderboard snapshot of 2026-10-14 (third-party mirror).

Commercial
- https://quilter.ai/project-speedrun : parts, layers, human hours, routing completion, cleanup scope.
- https://www.quilter.ai/blog/llm-pcb-layout-gpt-6-astra : Quilter's argument against LLM layout; pointers to GeoGramBench and EEBench (not opened separately).
- https://www.quilter.ai/blog/an-honest-comparison-quilter-ai-vs-flux-ai-for-professional-pcb-design-in-2026 : workflow and pricing models of both, vendor view.
- https://www.flux.ai/p/blog/flux-copilot-under-the-hood : Copilot tools, grounding, admitted partial execution.
- https://flux.ai/p/blog/ai-assistance-inside-every-ecad-tools : stage coverage; 2 to 4 layer auto-layout claim.
- https://email.flux.ai/p/blog/spring-2026-updates-faster-ai-better-layouts-smarter-sourcing : ERC/DRC in the loop.
- https://deeppcb.ai/deeppcb-vs-quilter-open-source-routing-compared-2026/ : three-board completion comparison (vendor).
- https://blog.diode.computer/llms-full.txt : Diode posts on Claude-drafted reference designs, registry, limits.
- https://cdn.jsdelivr.net/gh/atopile/atopile@main/README.md : atopile features and licence.
- https://blog.jitx.com/jitx-corporate-blog/whats-new-in-jitx-2025 : JITX move to Python, router, AI use.
- https://blogs.sw.siemens.com/electronic-systems-design/2026/02/18/ai-in-the-engineers-seat-speeding-up-pcb-design-without-giving-up-control : CELUS blocks and assistant.
- https://docs.tscircuit.com/registry : tscircuit registry is npm-compatible; no licence or layout detail.

Open-source tools (README read; last commit and licence by shallow `git clone` on 2026-11-11)
- https://cdn.jsdelivr.net/gh/mixelpixx/KiCAD-MCP-Server@main/README.md : tool counts, toolboxes, architecture, limits.
- https://cdn.jsdelivr.net/gh/aklofas/kicad-happy@main/README.md and the cloned repo's `VALIDATION.md`, `how-it-works.md`, `datasheet-extraction.md` : checks, corpus, cache design.
- Shallow clones for date and licence only: lamaalrajih/kicad-mcp, Seeed-Studio/kicad-mcp-server, circuit-synth/circuit-synth, diodeinc/pcb, atopile/atopile, tscircuit/tscircuit, LGAI-Research/PCBWorld, HZou9/PCBSchemaGen_v2, digailab/PCB-Bench, microsoft/SchGen, gepa-ai/gepa, stanfordnlp/dspy, devbisme/skidl.
- https://github.com/LibreSolar/bms-c1 : cloned; the board used for the token measurement.

KiCad
- https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ : design blocks extended to the PCB editor.
- https://forum.kicad.info/t/kicad-10-0-4-design-block-problems/70883 : how PCB design blocks behave in practice.

Data
- https://huggingface.co/datasets/bshada/open-schematics/blob/main/README.md : fields, licence, gaps.
- https://makezine.com/article/technology/open-source/open-source-hardware-certifications-for-june-2026/ : 3,352 OSHWA certifications.

User reports
- https://hackaday.com/2026/09/05/can-ai-now-design-pcbs-that-just-work/ : article and comments.
- https://www.eevblog.com/forum/eda/claude-code-for-pcb-design/msg6216381/ : thread of March 2026.
- https://dev.to/anypcba_official/i-let-ai-design-a-pcb-heres-how-it-went-5e41 : fab vendor's trial of DeepPCB and Quilter.

Agent-system practice
- https://www.anthropic.com/engineering/multi-agent-research-system : 4x and 15x token multipliers; when multi-agent pays.
- https://www.anthropic.com/engineering/code-execution-with-mcp : progressive tool disclosure; 150,000 to 2,000 token example.
- Anthropic model price table as cached 2026-11-03 in the `claude-api` skill bundled with this session: per-token prices, cache-read prices, batch at half price, tokenizer ratio.

Local evidence
- `.claude/skills/pcb-proto-flow/SKILL.md`, `.claude/skills/kicad-tools-and-mcp/SKILL.md`, `tools/battery-bank/groundup/README.md`, `docs/research/README.md`, and pages 10 to 13 of `docs/research/2026-11-10-gemini-autorouter-and-placement.pdf`.

Seen only as search listings, not opened: Cadence Allegro X AI and "AI super agent" coverage, Altium, Circuit Mind, SnapMagic Copilot, Flux funding ($37 M, February 2026), TechRadar and Slashdot coverage of Project Speedrun (which date it to December 2025).
