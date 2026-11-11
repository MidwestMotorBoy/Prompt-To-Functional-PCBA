# 04. Verification and grounding: catching errors before fab

Research track 4 of 5, written 2026-11-11. Scripts and test files from the runs described here are in
`04-verification-and-grounding/` beside this file.

Labels used throughout: **[ran]** means I executed it in this container; **[opened]** means I read the primary
page or the source code; **[unverified]** means it comes from memory or a secondary summary and needs checking.

## 1. Recommendation

Build a **part knowledge base in the repo** and make every later check read part facts from it, never from the
LLM's memory. Each fact (pin map, absolute maximum, recommended range, required external part)
carries a datasheet hash, a page number and a verbatim quote, and is accepted only when two independent
sources agree: a deterministic PDF table read or a page-limited LLM read, and a library symbol, distributor
record or second reader. Disagreements go to Logan with the page crop.

On top of that, run a **deterministic netlist rule engine** (reuse kicad-happy's MIT analyzers, add the
power rules they lack), the existing **solver loop** once calibrated against known answers, a **spec lint**
and a **fab-output round trip**. Use a fresh-context reviewer of a different model family only where rules
cannot decide, and check each finding's citation by code.

Score the whole stack by **seeded faults**: inject known bugs into known-good designs and count what each gate
catches, at what false-positive and token cost.

Runner-up: adopt kicad-happy whole and add only the two-source pin check and the solver loop. That is less
work, but its extraction is LLM-only and cached per project, and its authors list power electronics as
under-tested.

## 2. Options compared

### 2.1 Datasheet grounding

| Option | Maturity, licence | How an LLM uses it | What it checks by machine | Token cost | Fit | Needs from Logan |
|---|---|---|---|---|---|---|
| Deterministic table read (pdfplumber, PyMuPDF) with page finder | Mature libraries, MIT / AGPL | Not at all on the happy path; LLM writes a per-family column map only when the generic reader fails | Pin number to name for every pin, with page | Zero when it works **[ran: 48 of 48 pins, 7 s]** | Text PDFs only; rotated headers and merged cells break naive code | Nothing unless readers disagree |
| Page-limited LLM read into a schema (the kicad-happy `datasheets` skill pattern, DRCY, datasheet-cli) | kicad-happy v3.0.1, MIT, commit 2026-11-06 **[opened]**; datasheet-cli 0.1.0, GPL-3, Gemini only | Scout finds pages, extractor fills JSON with `evidence.page` | Schema validity, pin count against package, quote present on the cited page (ours to add) | About 3k tokens for the pin pages of a 137-page MCU datasheet against about 70k for the whole file **[ran, chars/4]** | Any PDF, including scans with a vision model | Review of low-confidence facts |
| Whole-PDF single pass | Works on frontier models for value lookup **[opened: Infineon study, 25/25 claims]** | One call per part | Nothing by itself | About 98k tokens per datasheet in that study | Simple, but pays for every page every time | Same |
| Library symbol as second source (KiCad official library, EasyEDA/LCSC through easyeda2kicad, Ultra Librarian, SnapMagic) | KiCad library is reviewed against KLC by volunteers; vendor libraries vary | None | Pin number and name agreement, pad count, pin-to-pad map | Zero | Good for common parts; new power ICs are often missing from the KiCad library | Nothing |
| Distributor parametrics (Digi-Key v4, Mouser, Nexar, LCSC/JLC) | Digi-Key: OAuth2, 120 requests a minute, 1,000 a day **[opened]** | Tool call | Package, pin count, voltage rating, lifecycle, datasheet URL | Small | Cross-check of scalars only; no pin tables | API keys (`.env.example` already lists them) |
| Maker machine-readable data (BSDL, IBIS, SPICE subcircuit pin order, MCU pin databases) | Exists for MCUs, FPGAs, logic; rare for power ICs **[unverified]** | None | Pin number to name where a BSDL or IBIS file exists | Zero | Low coverage for our parts | Nothing |
| Vision model on package drawings for footprints | Poor: general models under 20 % IoU on footprint geometry in the one benchmark I found **[opened]** | Not recommended as a generator | Use only as a reader of the dimension table, cross-checked numerically | High | Use library or generator footprints instead | Sign-off on any custom footprint |

### 2.2 Schematic, simulation, layout, fab, requirements, review

| Option | Maturity, licence | LLM use | Automatic checks | Token cost | KiCad / JLC fit | HV / power fit | Human need |
|---|---|---|---|---|---|---|---|
| KiCad ERC, DRC, parity through `kicad-cli` | KiCad 10.0.7 (2026-10) **[opened]** | Runs it, triages JSON | Pin-type conflicts, opens, shorts, clearances, creepage rule (since 9.0), schematic parity | Low | Native | Creepage needs net voltages declared | Accept or reject exclusions |
| kicad-happy analyzers | v3.0.1, MIT, pure Python, 5,857-repo regression corpus **[opened, not run: the sandbox refused execution of cloned code]** | Agent skill or CLI, JSON out | 71 schematic detectors (rail sources, decoupling, pull-ups, I2C address clash, level domains, derating, sequencing, USB), EMC rules, thermal estimate, gerber completeness, generated ngspice benches | Low for the analyzers; extraction is LLM | KiCad 5 to 10; has JLC and LCSC skills | Authors list power electronics as under-represented in the corpus | Triage; no published false-positive rate |
| KiBot | Mature, AGPL **[unverified this session: its preflight page failed to load]** | YAML config, CI run | ERC/DRC gates, field checks, JLC rotation and offset table, fab outputs | None | Strong JLC support (`rot_footprint` filter, `JLCPCB Rotation Offset` field) **[opened]** | Neutral | Rotation review |
| Our own netlist rule engine (new) | To build on `check_netlist.py` and the review skill | LLM writes declarations, not checks | Abs-max per pin per state, default-state table, copied-block diff, single-source rails, power tree budget | None at run time | Reads `kicad-cli` XML netlist | Written for this domain | Triage of findings |
| Commercial reviewers (Siemens Xpedition Validate/Valydate, CADY, Circuit Mind AVE, AllSpice DRCY, Traceformer) | Active; AVE launched 2026-10-29, DRCY paper 2026-03 **[opened]** | Hosted | Pin-by-pin datasheet review, model-based checks | Paid; Traceformer is pass-through API cost | Traceformer and DRCY read KiCad | Unknown | None publishes detection or false-positive rates |
| ngspice batch | 45.2 (2025-09) upstream; 41 from conda-forge **[ran]** | Writes decks, reads `.meas` | Inrush, filter damping, thresholds with tolerance, gate drive | Low | KiCad embeds ngspice | No encrypted vendor models | Approves what is worth simulating |
| spicelib | 1.6.4 (2026-10), GPL-3 **[opened; installed, not exercised]** | Python API | Drives LTspice, ngspice, QSPICE, Xyce; Monte Carlo and worst case | Low | LTspice native on Logan's Windows PC | Gives access to ADI and many vendor models | None |
| InSpice (PySpice fork) | 1.7.0.7 (2026-09), GPL-3, beta **[opened]** | Python netlist API | ngspice shared library, Xyce | Low | Neutral | Same model limits as ngspice | None |
| Home-made solvers (DC grid, PEEC, Laplace coupling) | One board, never measured | Declares loops and paths; reads tables | Path resistance, Kelvin error, via current, loop L, coupling | None | Reads `.kicad_pcb` directly | Built for power stages | Known-answer calibration **[ran: see 3.4]** |
| padne | KiCad-native 2.5D FEM, NLnet-funded from 2026-04, validation boards planned **[opened]** | `!padne` directives in the schematic, CLI `solve` | DC drop, current density | None | Reads `.kicad_pro` | Good cross-check for the DC solver | None |
| Fill Resistance plugin | KiCad 10 IPC-API plugin, v1.4.2 (2026-08); author reports within 20 % of a micro-ohm meter **[opened]** | GUI first | DC resistance, via currents, multi-source PDN mode | None | Needs KiCad 10.0.1+ running | Cross-check | None |
| FastHenry2 / FasterCap | Old, stable reference codes; LGPL **[unverified]**; Windows binaries, Linux for FasterCap **[opened]** | Text input files | Reference inductance and capacitance for calibration cases | None | No KiCad import; we write the geometry | Reference only | None |
| Gerber round trip (gerbonara + IPC-D-356) | gerbonara 1.6.3 (2026-04), Apache-2.0, has an IPC-356 module **[ran: import only]** | None | Layer set, alignment, connectivity of plotted copper against the exported netlist | None | `kicad-cli pcb export ipcd356` exists **[opened]** | Neutral | Looks at JLC's preview |
| Spec as typed YAML + lint (or StrictDoc) | StrictDoc 0.30.4 **[ran: installed, version only]** | Writes requirements in EARS form | Units, ranges, verification method, trace links, staleness | Low | Neutral | Lets voltage and current classes flow into rules | Approves the spec |
| Fresh-context, cross-model reviewer | Practice, not a product | Reviewer agent per block | Nothing by itself; its findings are citation-checked by code | Bounded per block | Neutral | Catches intent and fault-state errors | Reads the surviving findings |

## 3. Evidence per option

### 3.1 Datasheet grounding

**What I ran.** The AIOC open-hardware project ships the STM32F373 datasheet (137 pages) next to a KiCad schematic
that uses the official `MCU_ST_STM32F3:STM32F373CBTx` symbol. `pin_table_crosscheck.py` finds the pages
containing "pin definitions", reads the tables with pdfplumber, picks the LQFP48 column, and compares pin number
to name against the symbol embedded in the schematic.

- All 48 pins were recovered from pages 33 to 40 in 7.3 s with no LLM. The symbol agreed on all 48 numbers; three
  names differed only by supply suffix (`VDD_2` against `VDD`).
- I then swapped pin numbers 45 and 46 in the symbol. The check reported exactly those two pins.
- The first version of the script found nothing. The header row is printed rotated, and pdfplumber returns it
  reversed (`84PFQL` for `LQFP48`). This is the failure mode to expect: silent, total, and fixed by a small
  per-layout rule. A generic reader must fail loudly when it finds fewer pins than the package has.
- The pin pages are 11.6k characters of text; the whole file is 278k. Sending only the located pages to an LLM
  is roughly a 24-fold saving on this part.

**What the literature says about LLM readers.**

- Value lookup from datasheets is close to solved on frontier models when the right document is in context. An
  Infineon study scored Claude Sonnet 4.6 and GPT-5.1 at 25 of 25 curated claims, three repeats. The same study
  gives the failure modes that matter for us: with no document, Claude still answered 17 of 25 claims, got 7
  right, and attached a fabricated quotation to each; given a decoy datasheet, models read the decoy faithfully.
  It measured about $0.38 per claim for agentic extraction and recommends single-pass reading unless the document
  exceeds the context window. So the two things to enforce by code are **the quote exists on the cited page of
  the hashed file** and **the file is for the right part and package**.
- D2S-FLOW reports exact match 0.86 and F1 0.92 for parameter extraction for SPICE model building, with a
  retrieval scheme that cut tokens by 38 %.
- PCB-QA (480 yes/no questions on 8 KiCad projects) found datasheet questions the weakest category for its best
  input format, and the only one needing retrieval; netlist-as-JSON beat native KiCad text by 7 to 36 points.
- PCBSchemaGen builds a per-IC knowledge graph (about 300 tokens of JSON per part) from the datasheet with a
  32-role pin ontology, reviewed by engineers against pin tables. Removing it dropped hard-task pass rate from
  47.1 % to 2.0 %. Its deterministic verifier agreed with senior engineers at Cohen's kappa 0.91, with 6.7 %
  false accepts and 2.7 % false rejects. This is the strongest published evidence that a small, verified,
  per-part fact file is what makes LLM schematic work correct.
- HWE-Bench (300 board-level tasks with 2,914 datasheets) reports the best model producing a fully correct
  schematic 8.15 % of the time. Generation from datasheets without a verifier is not close to usable.
- Footprints from drawings: on ICGeoQA, GPT-4o scored 11.1 % and Gemini 2.0 scored 4.5 % overall IoU; a
  fine-tuned 7B model reached 71.6 %. The tested models are old, but the error types (spacing read as size,
  pins miscounted across "…") are exactly what produced the 2.8 mm exposed pad on a 1.4 mm package last time.

**Existing tools.**

- kicad-happy `datasheets` skill **[opened source]**: distributor download, a scout pass that finds pages,
  per-category extractor prompts, a typed JSON cache keyed by MPN with `evidence {page, section, confidence,
  method}` per value, PDF hash for staleness, and trust gating (`best(..., min_confidence=)`). Its verifier
  compares extracted limits with net voltages, required externals and decoupling. I did not find a check of the
  schematic symbol's pin numbers against the extracted pinout, and the cache is per project by design.
- AllSpice DRCY **[opened paper]**: five agents, a critic that scores each extraction, up to five attempts,
  k parallel reviewers and a consensus step. No detection numbers are published.
- concur (Adom) **[opened page]**: a consensus check between a datasheet-extracted symbol and footprint and
  vendor libraries on seven axes (pad count, pin count, names, pin-to-pad map, package family, body size), with
  statuses `golden`, `golden_with_variants`, `divergent`. This is the two-source idea already written as an agent
  skill; no licence is stated and no disagreement rates are given.

**A concrete lead from our own repo.** The docstring of `tools/battery-bank/schematic-tools/tpd6s300.py` lists
pin 7 twice ("7 RPD_G1" and "7, 13, 18, 21 (EP) GND") while the code's `PIN_NETS` puts GND on pin 8. That is the
part whose swapped pins put CC1 on ground. I could not fetch the TI datasheet from this container (the proxy
blocks ti.com), so I cannot say which line is right. A machine pin-table check would have settled it in seconds.

**Proposed two-source rule.** A pin map is `verified` when (a) the deterministic table read and (b) one of
{library symbol from an independent origin, a page-limited LLM read by a different model} agree on every pin
number, after a fixed list of benign name differences. A scalar limit is `verified` when the quoted text is
found on the cited page and one independent source (distributor parametric, second reader) agrees within
rounding. Footprints are never generated from a drawing by a model: take them from the KiCad library or a
generator, then check pad count, pitch, body size and exposed-pad size numerically against the datasheet's
dimension table and against a second library where one exists.

**Knowledge base layout.**

```
parts/<MPN>/
  datasheet.pdf            # the exact file; sha256 in facts.yaml
  facts.yaml               # package, pins[], abs_max{}, recommended{}, required_externals[], defaults[]
                           # every value: {min,typ,max,unit,condition,page,quote,sources[],status}
  symbol.kicad_sym, footprint.kicad_mod, checks.json   # the artefacts and the agreement record
  notes.md                 # app-circuit and layout guidance, each line page-cited
```

It lives in its own repository or submodule so that a part is paid for once across projects, and it is the
only place a part fact may be read from. A changed PDF hash makes every fact of that part `stale`.

### 3.2 Schematic checks beyond ERC

**What exists.** kicad-happy is the only open rule engine I found with breadth: its validation document lists 71
schematic detectors with hit counts across 5,857 repositories, including `audit_rail_sources`,
`detect_decoupling`, `validate_pullups`, `validate_voltage_levels`, `analyze_voltage_derating`,
`validate_power_sequencing`, `detect_i2c_address_conflicts`, `validate_feedback_stability`,
`audit_power_pin_dc_paths` and `detect_shorted_two_pin_components`. Its harness is honest about its limit:
"The system primarily tests consistency, not correctness", and its mutation test perturbs analyzer *outputs* to
test assertions, not designs. Open analyzer issues stand at 378. It publishes no false-positive rate.

Commercial tools describe the same idea (model-based or agent-based pin-by-pin review against datasheets) and
give examples (swapped JTAG pins, a feedback divider that does not match the reference voltage, a missing
exposed-pad pin, supply pins on ground while ERC is clean) but no measured rates.

**Which passes of `schematic-design-review` can become code.**

| Pass in the skill | Deterministic part | What stays with a model or Logan |
|---|---|---|
| 1. Pin by pin | Symbol pins against KB pin table; exposed-pad net and size; N.C. pins against the KB's "connect to" note; strap pins decoded to address or mode through a KB table | Whether the chosen strap is the intended one |
| 2. Net by net | One-pin nets; single source per rail; labels on one sheet only; **copied-block isomorphism** (the deleted GPIO6 wire) | Nothing |
| 3. Absolute maximum | For each pin: highest net voltage over declared states against KB abs-max, with the hot-plug overshoot factor as a declared rule | Declaring the states and the overshoot rule once |
| 4. Derating | MLCC DC-bias curve lookup, resistor power, FET V_DS percentage, ripple current sum | Fault-state currents that need circuit reasoning |
| 5. State and fault table | Default level of every enable, inhibit and gate when its driver is high-impedance, computed from pulls in the netlist; back-power paths through pull-ups to unpowered rails | The table's rows (which states matter) and the consequence of each |
| 6. Configuration defaults | KB `defaults[]` listed per part and diffed against the spec | Judgement on each |
| 7. BOM | MPN, LCSC number, footprint against package | Nothing |

Additional rules worth writing because nothing open covers them for power boards: a power-tree solver (each
rail's worst-case load against its source's rating and thermal limit); connector pinout mirroring between mating
boards; Kelvin pairs and hot loops declared in the schematic and checked for completeness (every switch node
has a declared loop and input capacitor).

NetlistBench is a warning for how the LLM should *edit*: the best model passed 82 % overall and fell from 80 %
at 3 chained edits to 26 % at 15. Edits must be small and each followed by a structural netlist diff, which is
what the project already did.

### 3.3 Simulation

- **[ran]** ngspice 41 installed from conda-forge without root. `inrush_known_answer.cir` switches a 16.8 V
  source into 100 µF through 35 mΩ and 50 nH. Measured ∫i²dt was 0.40315 A²s against the closed form
  C·V²/(2R) = 0.4032 A²s; run time 20 ms. My first deck failed (`I(L1)` is not a legal measure target in
  ngspice); the fix was a zero-volt source as ammeter. Syntax differences between simulators are a real cost.
- spicelib drives LTspice, ngspice, QSPICE and Xyce in batch, with Monte Carlo and worst-case helpers. On
  Logan's Windows PC that gives LTspice natively. InSpice is the maintained PySpice fork. Both are GPL-3, which
  matters only if we distribute them inside our tool.
- kicad-happy's SPICE skill generates benches for detected subcircuits (dividers, filters, op-amp stages,
  inrush, snubbers) and is explicit that discrete and regulator models are generic.
- Vendor models **[unverified]**: FET and diode subcircuits are generally plain text and run in ngspice with
  its PSpice or LTspice compatibility modes; controller models from TI are often encrypted PSpice, and ADI
  parts are LTspice-only. I did not check the specific Monolith parts.

**Worth simulating on a power board:** inrush and hot-plug ringing on input networks; input-filter damping
against converter input impedance (the project already does this in numpy in `pack_bus_sims.py`); capacitor
ripple-current sharing; protection and UVLO thresholds with resistor tolerance (Monte Carlo); gate-drive
turn-on, Miller turn-on and dead time with the vendor FET model and the *extracted* gate-loop inductance from
the PEEC solver; snubber sizing; loop gain where the compensation is external and an averaged model can be
written from the datasheet's equations. **Not worth it for v1:** full switching transients of a controller with
no open model, EMI prediction, anything whose answer depends on a model we invented and cannot check.

**How a testbench avoids fooling its author.** (1) The deck is generated from the KiCad netlist export, not
retyped. (2) The expected value and tolerance are written down from a hand formula before the run. (3) Every
deck has a degenerate case with a closed-form answer, as above. (4) Halving the time step must not move the
result. (5) Each model file is recorded with its origin and hash in the KB. (6) A result is evidence for a named
requirement, or it is not kept.

### 3.4 Layout checks beyond DRC

**Known-answer tests of the home-made solvers [ran].**

- DC copper solver (`review-tools/solve.py`) on a synthetic 2 mm by 51 mm strip of 2 oz copper
  (`dc_strip.kicad_pcb`): hand value 6.07 mΩ; solver 5.78 mΩ at 0.1 mm grid and 5.93 mΩ at 0.05 mm. The error is
  exactly one grid cell of extra width (21 cells for 2 mm). It is small on wide pours and becomes about −17 % on
  a 0.5 mm neck at 0.1 mm. This is the same mechanism as the documented "grid bridges gaps" pitfall, and it
  always errs optimistic. Fix: rasterise with centre-sampled cells or correct width by one cell.
- PEEC loop solver (`peec.py` through `loops.hot_loop`) on two 10 mm by 20 mm plates 0.244 mm apart
  (`peec_plates.kicad_pcb`): 0.461 nH at 0.5 mm cells and 0.473 nH at 0.25 mm, so it is grid-converged. The
  wide-plate formula gives 0.55 to 0.58 nH depending on where the pad current is taken to enter; fringing lowers
  it a few percent. The solver reads roughly 10 to 20 % low, and my reference is not sharp enough to say how
  much of that is real. This needs FastHenry on the same geometry.
- The coupling solver I did not test. A plate capacitor in FasterCap or by formula is the obvious case.

**Reuse, validate or replace.**

| Solver | Verdict |
|---|---|
| DC grid | Keep. Fix the one-cell bias. Add a regression set of strips, necks and via arrays with hand answers. Cross-check on one real board against padne (FEM, reads the KiCad project) and, on Logan's PC, the Fill Resistance plugin |
| PEEC loop | Keep for relative comparison, which is how the skills already use it. Calibrate against FastHenry2 on three geometries (plates, a via-closed loop, a published EVM loop) before quoting absolute nH |
| Laplace coupling | Keep. Calibrate against FasterCap or a plate formula |
| openEMS, Elmer | Not for v1. Full-wave and multiphysics answer questions (radiation, RF) outside scope, at much higher setup cost |

**Creepage and clearance.** KiCad 9 added a native creepage constraint **[opened]**, and there is an open report
of slow DRC with it enabled. The missing input is a working voltage per net. Declare it in the schematic as a
net class field and generate `.kicad_dru` clearance and creepage rules from a standards table chosen once by
Logan (IPC-2221B or IEC 62368-1, pollution degree, material group). The table's values must come from the
standard, not from a model's memory.

**Current capacity and thermal.** The skills already reference IPC-2152 through secondary tables that "disagree
slightly". I did not find a maintained open IPC-2152 library **[unverified]**. Pragmatic route: the DC solver's
loss map into the existing thermal model (already done for Monolith), plus a per-via and per-neck current
density limit as a rule.

**JLCPCB and fab outputs.**

- Rotation: KiBot ships a footprint-regex rotation and offset table and reads per-part `JLCPCB Rotation Offset`
  fields; it documents that bottom-side handling differs between KiCad and JLC. Reuse that table.
- A check I propose and have not tested: derive each part's expected rotation by comparing pin-1 position in
  the KiCad footprint with pin-1 in the EasyEDA/LCSC footprint for the same LCSC number.
- Basic against extended parts, stock and package come from the JLC parts data that the KiCad MCP on Logan's PC
  already exposes (`search_jlcpcb_parts`, `get_jlcpcb_part`).
- Round trip: export IPC-D-356 and gerbers separately with `kicad-cli`, read the gerbers with gerbonara,
  flood-fill copper per layer with drills, and compare the resulting connectivity with the IPC-D-356 netlist.
  KiCad writes net attributes into X2 gerbers, a second, cheaper comparison. Add kicad-happy's gerber
  completeness and alignment checks, and a pixel diff of rendered gerbers against a board render. This would
  have caught "pads printed as silkscreen".
- One set rule from `jlc-fab-files` becomes code: the BOM, CPL and gerbers carry the board file's hash, and the
  gate fails when they differ.

### 3.5 Requirements-stage prevention

EARS gives five sentence patterns (ubiquitous, WHEN, WHILE, WHERE, IF/THEN) **[opened]**. StrictDoc offers a text
format with a grammar where fields can be made mandatory and parent links are validated, plus JSON export.
For one person I recommend a typed YAML spec with a JSON Schema and a small linter, because the checks we most
need are numeric and StrictDoc's fields are strings and choices; StrictDoc is the runner-up if a browsable
trace matrix matters more.

**Spec lint checks:** every requirement has an ID, an EARS-form sentence, a quantity with unit and min/typ/max,
the conditions it holds under, a verification method (analysis, simulation, inspection, test) and a link to the
artefact that verifies it; units parse and are dimensionally consistent (`pint`); ranges are ordered; no
"TBD" passes a gate; every rail in the power tree has a voltage range and a maximum current; power in is at
least power out over efficiency; every interface names its standard and version; every requirement is linked
to at least one check and every check to a requirement; a requirement whose text changed after its evidence
was produced is `stale`. The state and fault table of section 3.2 is the lightweight FMEA: rows are blocks,
columns are states, and a cell is either computed from the netlist or signed by Logan.

### 3.6 Independent review

- A critical survey of self-correction concludes that no prior work shows successful self-correction from
  prompted feedback alone except in specially suited tasks, and that it works where reliable external feedback
  exists **[opened]**.
- LLM evaluators recognise and favour their own output; a 2025 follow-up found the harmful part of that
  preference persists when the evaluator is itself wrong, more so for stronger models, and is reduced by longer
  reasoning before judging **[opened abstracts]**.
- Our own record: the challenge round moved about a third of the majors, in both directions.
- I found no controlled study of cross-model against same-model review for hardware. The recommendation to use
  a different model family is an inference from the two results above.

Design: the reviewer starts with no memory of the design conversation. It receives one block at a time (netlist
JSON for that sheet, the KB facts of its parts, the relevant requirements), about 10 to 20k tokens, and must
return findings naming pin, net, KB fact and page. Code rejects any finding whose pin, net or quote does not
exist. After the first full pass it runs only on blocks whose netlist hash changed. Deterministic rule output is
given to it as settled, so it spends tokens on intent and fault states only.

## 4. How this fits the pipeline

| Stage | Automated gate | Catches | Cannot catch | False-positive load | Cost |
|---|---|---|---|---|---|
| Requirements | Spec lint | Missing units, ranges, verification method; inconsistent power budget; untraced items | A wrong requirement that is well formed | Low | Seconds, no tokens |
| Parts | KB build with two-source agreement; distributor cross-check; JLC stock and basic/extended | Wrong pin map, wrong package variant, wrong limit, fabricated fact, obsolete part | An error present in both sources; errata; behaviour not in the datasheet | Low to medium: name-variant noise until the benign list matures | One page-limited read per new part, once; zero on reuse |
| Schematic | ERC; symbol-against-KB; netlist rules (3.2); copied-block diff; default-state table; spec trace | Swapped pins, missing pulls, over-voltage pins, floating enables, address clashes, deleted wires, under-rated parts | Wrong topology that obeys every rule; firmware-dependent behaviour | Medium: decoupling and pull-up heuristics are the noisy ones | Seconds, no tokens; reviewer bounded per block |
| Schematic (selected nets) | Simulation decks tied to requirements | Inrush, ringing, thresholds, damping, gate drive | Anything the model omits; controller behaviour without a model | Low | Seconds of CPU; tokens to write each deck once |
| Placement, routing | DRC with generated creepage and current rules; parity; the solver loop compared with the previous run; tidiness table | Cut pours, pinched necks, Kelvin errors, grown loops, coupling at vias, HV spacing | Absolute accuracy until calibrated; magnetic coupling; part bodies | Low when compared run to run | Minutes of CPU per pass, no tokens |
| BOM and fab | Hash-bound file set; gerber round trip; CPL rotation table; polarity list | Stale packages, missing layers, plot errors, most rotation errors | JLC library quirks not in the table | Low | Seconds |
| Every gate | Fresh-context reviewer on changed blocks | Intent and fault-state errors, missed states | Whatever it shares with the author model | Medium; cut by citation checking | Bounded by block size |

Inputs needed from earlier stages: the schematic declarations of `pcb-proto-flow` section 3, plus two more for
this track: working voltage per net and the operating states per block. Human gates: Logan approves the spec,
resolves KB disagreements from page crops, signs the fault table, looks at the board in KiCad, and checks JLC's
placement preview for the parts on the polarity list.

**Ranking by value per cost** (my judgement, to be replaced by seeded-fault scores):

1. Symbol and footprint against the KB with two-source agreement. It targets the top historical bug source and
   costs nothing after the first read.
2. Netlist rules for abs-max, default states, copied blocks and rail sources.
3. Spec lint and trace. Cheap, and it gives every other check its limits.
4. The solver loop, compared run to run.
5. Fab round trip and file-set hash.
6. Fresh-context reviewer with citation checking.
7. Targeted simulation.
8. Absolute calibration of solvers and thermal estimates. High value only when a number is used as a limit.

**Keeping tokens down:** facts are read once and cached; pages are located by text search before any model sees
them; rules run as code; the LLM sees JSON summaries and diffs, not full netlists or PDFs; reviews are per
block and only on change.

## 5. An automated improvement loop without human-made boards

**Seeded-fault scoring.** Take known-good designs, apply one mutation, run the whole gate stack, and record
which gate first reports it, with what message, and the run's cost.

- **Mutation operators**, drawn from the project's own bug record: swap two pin numbers in a symbol; swap two
  nets on an IC; delete a pull-up, a decoupling capacitor or one wire in one copy of a repeated block; change a
  divider resistor by a decade; move an enable to a higher rail; replace a TVS or FET with a lower-rated part;
  change a strap; shrink an exposed pad; replace the datasheet with a sibling part's; edit one number in a fact
  file; narrow a power track; add a via in a pour neck; move a Kelvin tap onto a pour; rotate a polarised part
  in the CPL; drop a gerber layer.
- **Data:** Monolith at its reviewed commit, with its datasheets, is the best subject. Add open designs with
  datasheets in the repo (AIOC here; the kicad-happy catalogue lists 207 power and battery repositories) and
  vendor reference designs.
- **Metrics:** detection rate per operator and per gate; findings on the unmutated design (the false-positive
  proxy); tokens and seconds per run; the earliest stage that detects each fault.
- **Loop:** an agent proposes a new rule or threshold for an undetected mutant class; the suite re-runs; the
  rule is kept only if detection rises without raising baseline findings. This needs no input from Logan.

A second loop scores extraction: plant decoy datasheets and wrong-package variants and measure how often the
KB build accepts them, following the Infineon study's method.

**Where the metric misleads.** Mutants are not the errors an LLM designer actually makes, so the operator mix
should follow the logged error history. Some mutants are harmless (swapping two ground pins) and inflate the
miss count. Baseline designs contain real bugs, so a "false positive" may be true. Rules can be over-fitted to
the operators. And a perfect score says the stack finds *known kinds* of fault; it says nothing about a board
working. Solver scores are relative until one board is measured.

## 6. Risks and unknowns

1. **False-positive burden is unmeasured everywhere.** No tool I found publishes it. If Logan sees fifty
   heuristic warnings per run, the gates will be ignored.
2. **Power-IC datasheets are harder than the MCU I tested**: pin tables split by package, exposed pads in
   footnotes, limits in conditions. The deterministic reader's hit rate on them is unknown.
3. **Two sources can share an error**, for example a library symbol drawn from the same misprinted table.
4. **Solver accuracy**: the DC bias is understood; the PEEC gap of 10 to 20 % is not.
5. **I could not run kicad-happy** (sandbox policy on executing cloned code), so its noise level on a power
   design is unknown. The same applies to padne and FastHenry.
6. **Vendor model availability** for the Monolith parts is unchecked.
7. **The Gemini PDF** in `docs/research/` is image-only (text extraction returned 12 characters). I did not
   check its formulas; its content is routing and placement, and nothing in the README summary bears on this
   track beyond "physics cost terms", which section 3.4 covers from our own solvers.

**Smallest spike for the biggest risk (items 1 to 3), about two agent-days:** build the KB for Monolith's unique
ICs and protectors (roughly 25 parts) with the deterministic reader first and a page-limited LLM second; record
hit rate, tokens per part and every disagreement. Run symbol-against-KB and the abs-max rule on the reviewed
schematic and count baseline findings. Then replay the five historical bugs (TPD6S300 pins, exposed-pad size,
LDO enable on the pack rail, the 18 V TVS, the deleted GPIO6 wire) plus fifty random mutants and report
detection per gate. Run kicad-happy on the same schematic on Logan's PC for comparison. The result decides
between the recommendation and the runner-up.

## 7. Sources

Opened in this session:

- https://cdn.jsdelivr.net/gh/aklofas/kicad-happy@main/README.md and a clone of github.com/aklofas/kicad-happy
  at commit 7d9d4d9 (2026-11-06): skills, detectors, datasheet cache design, SPICE and gerber analyzers, MIT.
- Clone of github.com/aklofas/kicad-happy-testharness: methodology, "consistency, not correctness", mutation
  test of assertions, power electronics listed as under-represented.
- https://arxiv.org/pdf/2608.28439 : Infineon study of agentic datasheet extraction; 25/25 fidelity, fabricated
  quotes without a document, decoy documents, cost per claim.
- https://arxiv.org/pdf/2602.00510 : PCBSchemaGen; layered deterministic verifier, per-IC knowledge graph,
  kappa 0.91, ablation numbers.
- https://arxiv.org/pdf/2606.23704 : PCB-QA; 480 questions, JSON netlists beat native format, datasheet
  questions weakest.
- https://arxiv.org/html/2603.15672 : DRCY (AllSpice); five-agent datasheet review, no detection numbers.
- https://allspice.io/post/using-ai-in-schematic-design-reviews-what-we-learned-and-what-surprised-us : DRCY
  examples and datasheet source order.
- https://arxiv.org/html/2603.18102 : HWE-Bench; 8.15 % best full-design correctness.
- https://arxiv.org/pdf/2608.12197 : NetlistBench; edit reliability falls with chain length.
- https://arxiv.org/html/2508.03725v1 and https://yichao0319.github.io/assets/publications/icml26_wang.pdf :
  footprint geometry from drawings; general models under 20 % IoU.
- https://arxiv.org/abs/2502.16540 : D2S-FLOW; EM 0.86, F1 0.92.
- https://arxiv.org/pdf/2605.01338 : DiagramNet; block-diagram recognition, not datasheets (not used).
- https://docs.rs/crate/datasheet-cli/0.1.0/source/README.md : Gemini-based extraction CLI, GPL-3.
- https://wiki.adom.inc/kyle/concur/files/SKILL.md : cross-source consensus check for symbols and footprints.
- https://wiki.adom.inc/adom/kicad-board-audit/files/README.md : audit skill; ERC-clean board with floating
  VCAP and supply pins on ground.
- https://hn.svelte.dev/item/46492601 : Traceformer; KiCad input, 40-datasheet cap, pass-through pricing.
- https://iconnect007.com/article/152189/circuit-mind-launches-aipowered-pcb-design-verification-platform/152186/pcb :
  Circuit Mind AVE launch, 2026-10-29, no accuracy figures.
- https://www.siliconexpert.com/cady/ and
  https://blogs.sw.siemens.com/electronic-systems-design/2020/06/22/how-can-i-catch-schematic-errors-more-easily/ :
  CADY and Xpedition Validate descriptions; no rule counts or rates on these pages.
- https://developer.digikey.com/documentation : OAuth2 and rate limits.
- https://ngspice.sourceforge.io/news.html : ngspice 45.2, compatibility modes.
- https://pypi.org/project/spicelib and https://pypi.org/project/InSpice/ : versions, simulators, licences.
- https://gh.r-mj.com/atx/padne and https://nlnet.nl/project/Padne/ : padne method, directives, funding and
  validation plan.
- https://forum.kicad.info/t/resistance-and-pdn-plugin/70648 : Fill Resistance plugin, 20 % claim.
- https://fastfieldsolvers.com/software.htm : FastHenry2, FasterCap, FastCap2 availability.
- https://kicad.org/blog/2025/02/Version-9.0.0-Released and
  https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ : creepage DRC, component classes, custom ERC
  messages, jobsets, graphical rule editor.
- https://docs.kicad.org/10.0/en/cli/cli.html : `pcb export ipcd356`, `pcb drc --schematic-parity
  --refill-zones --format json --exit-code-violations`, gerber options.
- https://kibot.readthedocs.io/en/latest/notes_position.html : JLC rotation filter, tables and fields.
- https://pypi.org/project/gerbonara : 1.6.3, Apache-2.0; the `ipc356` module confirmed by import.
- https://strictdoc.readthedocs.io/en/stable/strictdoc_01_user_guide.html : grammar, required fields, relations.
- https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax : EARS patterns and the 2009 origin paper.
- https://arxiv.org/abs/2406.01297 : survey of LLM self-correction.
- https://arxiv.org/abs/2404.13076v1 and https://arxiv.org/abs/2504.03846v3 : self-recognition and
  self-preference in LLM evaluators.
- https://jlcpcb.com/de/blog/free-dfm-tool : mentions JLCDFM only; no detail obtained.

Failed or blocked: ti.com (proxy), kibot preflights page (site error), running kicad-happy (sandbox policy).
