# Track 1: how the LLM authors the circuit, and what the source of truth is

Research date 2026-11-11. Status: research lead, not a decision. "Ran" means I ran it in the cloud container
(Linux, Python 3.13/3.14, KiCad 10.0.8 in Docker). "Read" means I opened the page through a fetch tool that
summarises pages with a small model, so quoted numbers should be re-checked against the PDF before they are
relied on. Token figures are from a local heuristic counter (no tokenizer host was reachable); treat them as
good to about ±30 %.

## 1. Recommendation

**Write the circuit as code, make the netlist the truth, and treat the KiCad schematic as a generated view that
is proven equal to the code.**

- The LLM writes one small Python file per block. Parts come from real KiCad library symbols, so pin names
  and numbers are checked at compile time. Use SKiDL 3.0 (MIT, local) as the connectivity kernel, plus a thin
  layer of our own for the layout declarations of `pcb-proto-flow` section 3.
- Each build writes `netlist.json`, `constraints.json` and a native hierarchical `.kicad_sch`. The build fails
  unless KiCad's own netlist export of that schematic equals the code's netlist. Logan reviews the KiCad sheets.
- Do not use any existing tool's schematic drawer; write our own, driven by relative placement hints and
  guarded by the netlist check.
- Do not author by direct `.kicad_sch` edits or MCP calls. Keep the MCP for ERC, viewing and "update PCB".

**Runner-up:** Diode's Zener (`pcb` CLI). Claude has been trained on it and it syncs KiCad layouts, but it is a
vendor toolchain I could not run here. atopile has the best language but is ruled out for now (section 3.1).

## 2. Options compared

| Option | Maturity, last activity, licence | How an LLM uses it | Automatic checks | Tokens, 400 parts (est.) | KiCad / JLCPCB fit | HV / power fit | Needs from a human |
|---|---|---|---|---|---|---|---|
| **SKiDL 3.0 + our constraint layer** (recommended) | 3.0.0 on PyPI 2026-10-16; MIT; one main maintainer since 2016 | Writes Python; parts from KiCad symbol libs; errors give file:line and pin | Compile errors on unknown part/pin, SKiDL ERC, Python asserts, pytest, netlist diff, then KiCad ERC on the generated sheet | 30k to 40k to write; 12k to 40k to re-read as a compact netlist | Netlist is KiCad-native. Its own schematic drawer is not usable (ran it: 12 of 18 pins lost) so we draw ourselves | Neutral: no built-in power knowledge; we add it | Review of generated sheets; nothing else |
| **Zener / `pcb`** (Diode) (runner-up) | Active (1,960 commits), MIT, vendor-hosted toolchain download, native Windows "experimental" | Writes Starlark (Python-like). Anthropic states Claude Sonnet 4.5+ was trained with Diode on this task | Typed nets (`Power(voltage=)`), `check()`, `voltage_within`, typed `io()`; KiCad layout generation | Similar to SKiDL (not measured) | Generates and updates KiCad 10 layout; schematic drawing not documented | Typed voltages help; no HV features seen | WSL2 on the Windows PC; possibly an account for registry |
| **atopile** | 0.15.9 on PyPI 2026-09-12; MIT; company moved to a hosted app (0.16) | Writes `.ato`; best semantics (units, tolerances, `assert ... within`, solver) | Solver, electrical verification, part picking | About 25 % fewer than Python (measured on a tiny block) | Syncs KiCad layout; **no schematic export; part picking needs sign-in; 0.12 is remotely disabled** (ran it) | Solver is useful for dividers and ratings | An atopile account; acceptance of vendor lock |
| **tscircuit** | Very active (0.0.3148), MIT | Writes TSX | Type checks, its own DRC | Similar to Python (measured 1.2 kB for the buck) | Exports `.kicad_sch`/`.kicad_pcb`; **its schematic was the only generated one that round-tripped correctly and looked like a schematic** (ran it). Uses its own symbols, one-way export | Not a focus | JS toolchain; KiCad is a downstream export, not home |
| **circuit-synth** | 0.12.1, 2026-01-09; kicad-sch-api 0.5.6, 2025-11; PCB generation removed from the open build | Writes Python | Its own netlist; Claude Code agents | Similar to SKiDL | Generated sheets did not match its own netlist (ran it); hierarchy nets not joined | None | Not recommended as kernel; `kicad-sch-api` is useful as a file writer |
| **edg / PolymorphicBlocks** | 0.5.2, 2026-08-17; BSD-3; research project | Writes Python blocks with typed ports | Voltage/current limit propagation, part tables from a 2022 JLC list | Lower (generators size their own passives) | Netlist to KiCad with stable timestamps for ECO; no schematic drawing | Has buck/boost generators; authors say "not a design assurance tool" | JRE download (blocked here, not run) |
| **JITX** | Commercial, active; Python now | Writes Python; vendor pitches "your approved AI" | Constraint solvers, HFSS loop | Unknown | KiCad export not confirmed on the site | Aimed at high-speed | Licence, pricing not public |
| **Direct `.kicad_sch` text edits** (Battery-Bank method) | Proven here for small edits | Edits S-expressions by script | Netlist diff, ERC | 0.7M to 1.7M just to read the sheets once | Native | Neutral | Nothing extra, but no creation from nothing was ever done this way |
| **KiCad MCP server** (on Logan's PC) | Rich: about 70 schematic-side tools by name | One tool call per small step | `run_erc`, `validate_schematic`, lints | Hundreds of calls; context re-read on every call | Native; also offers `sync_schematic_to_board` | Neutral | PC must be on; KiCad state conflicts |
| **KiCad IPC API** | KiCad 9/10: PCB editor only, GUI must be running. Schematic and headless arrive in KiCad 11 (nightly only today) | n/a for schematic yet | n/a | n/a | Revisit when 11 ships | n/a | n/a |

## 3. Evidence per option

### 3.1 atopile

What it is: a declarative language (`.ato`) with units, tolerances, interfaces, `assert x within a to b`, a
constraint solver, parametric part picking from a JLC-backed database, and a build that updates a KiCad board.

What I ran. `pip install atopile` on Python 3.13 gave 0.12.6, and every command printed: "atopile 0.12 is
retired and can no longer run commands. Move to app.atopile.io (0.16+). If you temporarily require the classic
CLI picker, install atopile 0.15.8 and run `ato auth login`." So an installed, MIT-licensed version has been
switched off by the vendor. On Python 3.14 I installed 0.15.9, scaffolded a project and built a small
divider-plus-capacitors block. The first error was good: "Parameter `App.cout[0]|Capacitor.max_voltage` is
assigned to an exact value (25V) instead of being constrained to an interval". After fixing it the build
passed "Verify electrical design" in 1.5 s and then stopped at "Picking parts": "Part picking on atopile 0.15.8
requires sign-in. Run `ato auth login`, or migrate to app.atopile.io (0.16+)." The installed package has
exporters for BOM, power tree, pinout and PCB, and none for a schematic.

What I read. The docs landing page now describes a browser workspace, "pre-release and under heavy
development". A user issue (#1843, October 2026) objects to the move; no maintainer reply was on the page. I
could not read the vendor's own v0.16 blog post (the page returned only metadata).

Assessment. The language is the best fit of anything here for stating intent, and the error messages suit an
LLM. But the project rule is that contracts live in files and CLIs that we control, and this tool has just shown
that it can stop working by remote decision. It also has no drawing for Logan. Not recommended as the source of
truth. Worth copying: `assert ... within`, tolerance-aware values, and interfaces such as `ElectricPower`.

### 3.2 SKiDL

What it is: a Python library. `Part("Regulator_Switching", "TPS54202DDC")` loads the real KiCad symbol;
`u["FB"] += net` connects by pin name or number; `@subcircuit` functions give hierarchy and reuse; `ERC()`
checks drive and unconnected pins; `generate_netlist()` writes a KiCad netlist. 1.7k stars, MIT, supports KiCad
5 to 10.

What I ran (SKiDL 3.0.0, against the symbol libraries copied out of the `kicad/kicad:10.0` image). A ten-part
TPS54202 buck (`01-design-representation/spikes/skidl_buck.py`) compiled first time to a correct six-net
netlist. Custom fields I set on a part (`serves = U1.VIN`, `hot_loop = HL1`) appeared in the netlist, so
symbol-level declarations travel. A wrong pin name gave "No pins found using TPS54202DDC:U1[('CC1',)] @
[nc.py:16]", a wrong part gave "Unable to find part TPS54202XYZ in library Regulator_Switching", both with the
source line. A plain Python `assert` on the divider ratio worked as a design check. Two problems: (a)
`generate_schematic()` produced a `.kicad_sch` that KiCad 10 opened, but KiCad's own netlist export of it had
only 3 real nets and 12 of 18 pins unconnected, and the drawing was cramped and overlapping
(`renders/skidl_generate_schematic.png`); (b) `net.netclass = NetClass(...)` did not show in the netlist in my
test (I did not chase why). The log is also noisy (27 warnings for ten parts), which costs tokens unless
filtered.

What I read. The PCBSchemaGen paper (arXiv 2602.00510) has LLMs write SKiDL and reports, with a deterministic
verifier in the loop, overall pass@1 of 83 % (GPT-5.1), 86 % (Gemini-3-Pro) and 88 % (Gemini-3-Flash) on 23
power-flavoured tasks in its first version (half-bridges, gate drivers, synchronous buck, DAB, LLC), about 23k
tokens and 0.07 USD per task for the cheapest model. Its ablation is the useful part: with feedback that names
the error type and location, hard tasks pass 78 %; with pass/fail only, 57 %. Its two named failure modes are
misunderstanding a pin's function and wrong topology. So frontier models already write SKiDL well, and precise
verifier messages matter more than the model.

Assessment. Good kernel: local, vendorable, pin-checked against real symbols, plain Python that any model
writes. Its drawer must not be used. Bus factor is one person.

### 3.3 Zener and the `pcb` CLI (Diode)

What I read. Zener is Starlark with `Module()`, `io()` (typed ports such as `Power(voltage="3.3V")`), `config()`
(typed parameters; `"10k"` becomes a `Resistance`), `check(condition, message)`, `voltage_within`, `DiffPair`,
and `Board(layers=...)` which selects stack-up, net classes and rules. `pcb build` needs no KiCad; `pcb layout`
writes a KiCad 10 board. The repository is MIT with 1,960 commits. Anthropic's article of 2025-12-12, written
with Diode, says Claude was given a datasheet and asked for a configurable Zener reference design, that the
failure modes were missed datasheet nuance, misread reference-schematic images and misuse of Zener, and that
"Anthropic worked with Diode to improve training for Sonnet 4.5 and later". Diode's engineers preferred Sonnet
4.5 over Sonnet 4 in 82 % of blind comparisons. Designs were graded by a testbench that asserts requirements
("at least 22 µF between power and ground"), not exact parts.

What I could not do. The installer downloads from `pcb.api.diode.computer`, which this container's proxy
refused, so I did not run it. The docs I read do not describe how an existing layout is updated after a design
change, nor any schematic drawing. Native Windows is "experimental; use WSL2".

Assessment. The only option where the model vendor has published targeted training, and the grading idea
(requirement testbench) is one to adopt whatever the language. Risks are the same kind as atopile's: a
start-up's toolchain and download host. Runner-up, to be tried on one block.

### 3.4 tscircuit

What I ran (tscircuit 0.0.3148, `@tscircuit/cli` 0.1.2452 via npm). The same buck in TSX
(`spikes/tscircuit_buck.circuit.tsx`), `tsci export -f kicad_sch`, took 7 s. KiCad 10's netlist export of the
result matched all six nets and 18 pins, and the picture is a real wired schematic
(`renders/tscircuit_kicad_sch.png`), with odd power symbols and 36 off-grid warnings. It also has a
`readable-netlist` export that is a good model for an LLM-facing review format.

Assessment. Proof that a faithful, readable auto-drawn KiCad sheet is achievable. But the symbols and
footprints are tscircuit's own, KiCad is an export target, and the ecosystem is web and low-voltage oriented.
Not the home for a KiCad-native power design; a useful reference for the drawer.

### 3.5 circuit-synth and kicad-sch-api

What I ran (circuit-synth 0.12.1, kicad-sch-api 0.5.6). The buck as a `@circuit` function with nets passed in
(`spikes/circuit_synth_buck.py`). Its own netlist kept `VIN` and `/buck_5v/VIN` as separate nets and listed IC
pins twice. The generated sheets place parts in a row with a hierarchical label on each pin
(`renders/circuit_synth_buck_sheet.png`); KiCad read them back with GND merged onto VIN, EN and FB. The log
ended "KiCad integration not available: PCB generation features are not included in this version. Contact
Circuit Synth for licensing". Some of this may be my misuse in a ten-minute test, but the point stands: its
output cannot be trusted without an independent check. `kicad-sch-api` on its own was useful: see 3.9.

### 3.6 edg / PolymorphicBlocks

What I read. Python blocks with typed ports, parameter propagation of voltage and current limits, abstract parts
refined at the top level, netlist output with stable timestamps so a KiCad layout survives recompiles, JLC BOM
export. The README is frank: errors are "not great", checks are "not a design assurance tool", parts tables
date from 2022, best for "intermediate-level and simpler designs". `pip install edg` worked; the first compile
tries to download a Java runtime, which the proxy blocked, so it was not run. No LLM work found. Worth copying:
typed ports that carry voltage and current ranges, and stable IDs for ECO.

### 3.7 KiCad's own routes

- **kicad-cli 10.0.8** (ran): `sch erc`, `sch export netlist|svg|pdf|bom`, `pcb drc`. There is no command to
  update a board from a schematic. That step is the GUI (F8), the MCP server, or our own board updater.
- **IPC API** (read, KiCad developer docs): "KiCad 9 and 10 only support IPC API plugins in the PCB Editor",
  the GUI must be running, and "KiCad 11 adds support for plugins in the Schematic Editor" and headless use
  through `kicad-cli`. A forum post of September to October 2026 (KiPilot MCP) confirms schematic tooling needs
  a KiCad 11 nightly. So there is no supported schematic API today.
- **Constraint carriers** (read, KiCad 9 release notes and schematic docs): net classes assigned by pattern or
  by directive labels and rule areas; component classes set by a symbol field or a rule area and carried to the
  footprint; hierarchical sheets; design blocks (KiCad 10 extends them to PCB); a multi-channel tool that
  repeats layout between identical channels. These are where our declarations should land.
- **MCP server on Logan's PC**: the tool list visible in this session includes `batch_add_components`,
  `batch_connect`, `connect_to_net`, `create_hierarchical_subsheet`, `run_erc`, `validate_schematic`,
  `sync_schematic_to_board`, and lints such as `find_orphaned_wires`, `find_wires_crossing_symbols`,
  `lint_offgrid`, `repair_flat_symbols`. I did not call it. The lint tools are themselves evidence of the
  failure modes of coordinate-level editing.

### 3.8 Published experience on representation

- **SchGen** (Microsoft Research / UCSD, arXiv 2605.30345). The same model generating schematics as code with
  relative placement and connect-by-pin-name reached 82 % valid and 60.5 % expert-judged functional; with
  absolute coordinates 33 % functional; with absolute wire coordinates and no pin names 6 %; as a raw KiCad file
  32 % valid and 3 % functional. "Representation design matters more than model size." This is the strongest
  direct evidence against having the LLM write `.kicad_sch` or coordinates, and it supports the Gemini chat's
  claim (in `docs/research/README.md`) that the LLM should not output coordinates.
- **pcbGPT** (KIT / Bosch Sensortec, arXiv 2606.01188). Python DSL, compile, ERC, repair loop; pass@1 0.90
  overall, 0.72 on hard tasks; "not yet reliable enough to replace expert review".
- **HWE-Bench** (arXiv 2603.18102). Whole boards from requirements and 2,914 datasheets: the best model
  (Claude Sonnet 4.5) got 8.15 % fully correct. Errors: multiplexed and ambiguously named pins, one MCU pin
  given two functions, and loss of state on designs with hundreds of pins. This is why the unit of work must be
  a block with a few dozen pins, with a pin table in context, not a board.
- **JLCPCB blog, September 2026**: a frontier model driving KiCad by computer use on a 45-footprint amplifier.
  The first parity check found 46 issues. No token or time figures. Anecdote only.

### 3.9 The hybrid, tried

To test the recommendation's weakest link I wrote a 30-line drawer (`spikes/label_on_pin_draw.py`): read the
SKiDL netlist, place each KiCad library symbol on a grid with `kicad-sch-api`, put a net label on every pin,
save. Then `kicad-cli sch export netlist` and a partition diff (`spikes/netlist_partition_diff.py`). Result on
the first run: "truth nets 6, kicad nets 6, identical partition: True"; KiCad ERC showed only missing library
table warnings and two `power_pin_not_driven` (no PWR_FLAG yet). The drawing is correct and ugly
(`renders/label_on_pin_spike.png`). So fidelity is cheap to get and to prove; readability is the work.

### 3.10 Symbols and footprints

The last project's top wiring bug was a generated symbol with two pins swapped. The repo's own generator
(`tools/battery-bank/schematic-tools/tpd6s300.py`) shows why prose does not protect: its docstring lists pin 7
both as RPD_G1 and as GND and never mentions pin 8, while the table below it has 7 = RPD_G1, 8 = GND. A table
can be checked by machine; a sentence cannot.

What the tools do: SKiDL, circuit-synth and Zener read KiCad symbols; atopile and tscircuit fetch parts from
JLC/EasyEDA data into their own formats. `easyeda2kicad` (AGPL-3, 1.6k stars; we would call it as a CLI)
converts an LCSC number to symbol, footprint and 3-D model, and its README says correctness "can't be
guaranteed". A `jlc-mcp` server wraps the same data with a `library_fix` tool for pin corrections. I did not
verify JLC2KiCadLib, SnapEDA/SnapMagic, Ultra Librarian or PartReel in this session.

How it plugs into the representation. Every part used has a **part record** (`parts/<MPN>.yaml`): MPN, LCSC
number, symbol id, footprint id, datasheet file and revision, and a pin table (number, name, electrical type,
absolute maximum, page reference). The datasheet agent's extractor produces the table. The build then checks,
without an LLM:

1. symbol pin numbers = record pin numbers as sets; names equal after normalisation;
2. footprint pad numbers = symbol pin numbers; exposed pad present and on the recorded net;
3. two independent sources agree (KiCad library or EasyEDA import, against the datasheet table). Their errors
   are independent, so agreement is strong evidence and disagreement goes to Logan with the datasheet page;
4. in block code, IC pins are connected by name and the build resolves names through the record, so a pin can
   only be reached through a checked table; "N.C." pins need an explicit `nc()` or a net;
5. symbols are never drawn by the LLM. A new symbol is generated from the record by one deterministic
   generator.

PCBSchemaGen's per-IC record (pin roles from a 32-role list, about 300 tokens instead of a 16k-token datasheet)
is the model for what goes into the LLM's context when it writes a block.

## 4. How this fits the pipeline

**Inputs.** The spec and power tree; the chosen parts with part records; per-IC datasheet notes (typical
application, strap decoding, required capacitances).

**What the LLM writes.** One file per block, 20 to 60 parts each. A block declares ports with types
(`Power(v=(9, 21), i_max=5)`, `Ground`, `Signal`), parts by part-record name, connections by pin name, and the
section 3 declarations as calls: `switching(net, swing, t_edge)`, `sensitive(net)`, `kelvin(shunt, p, n)`,
`hot_loop(name, supply, ret, switch_pins, caps)`, `gate_loop(...)`, `serves(cap, pin, rank)`,
`current(net, amps)`, `fixed(part, xy)`, plus `check(...)` requirement tests. A block instantiated twice is a
repeated block; block ports are the boundary nets.

**Outputs.** `netlist.json` (canonical); `constraints.json` (read by the placer, router and solvers, replacing
the typed lists); the KiCad project: hierarchical sheets, net classes and patterns in the project file,
component classes and `Serves`/`HotLoop`/`Kelvin` fields on symbols; a compact per-block text netlist for
review agents; a netlist diff against the previous commit.

**Automated check (all must pass).** Compile; part-record checks; our ERC and KiCad ERC; `check()` tests
(pytest); generated-schematic netlist equals code netlist; every IC pin connected or declared NC; every
declaration refers to existing pins; diff against the last approved netlist listed pin by pin.

**Human gate.** Logan opens the sheets in KiCad (or the PDF) with the netlist diff and the pin-table report.
The schematic is read-only: electrical changes go back as comments and are made in code. If he moves symbols
to tidy a sheet, a capture command stores positions in a sidecar file and the netlist check proves nothing
else changed (Diode keeps symbol positions beside the source in the same way).

**ECO.** Symbol UUIDs are derived from the block path, so a rebuilt schematic keeps its links to footprints.
The board is updated with KiCad's own "Update PCB from Schematic" (GUI or the MCP's `sync_schematic_to_board`),
then `kicad-cli pcb drc --schematic-parity`, which the Battery-Bank flow already uses.

**Token cost.** Measured: KiCad's demo schematics cost about 1,700 to 4,300 tokens per part to read as
`.kicad_sch` (160-part board: about 370k; 189-part board: about 810k), 630 to 1,090 per part as KiCad XML
netlist, and 30 to 100 per part as a compact `net: ref.pin ...` listing. The buck in SKiDL was about 940 tokens
for ten parts; atopile about 270 for four. So a 400-part design is roughly 30k to 40k tokens of code, written
once, block by block, against 0.7M to 1.7M just to read native sheets once. Keep it down by: one block per
context with only its part records; compiler output filtered to errors; reviewers reading the compact netlist
and diffs; a block library so the second design reuses the first; never loading `.kicad_sch` into a model.
The MCP route was not measured; by construction it needs at least one call per part and per connection group,
with the conversation re-read each call.

## 5. An automated improvement loop without human-made boards

| What is scored | Data | Metric | Where it misleads |
|---|---|---|---|
| Block authoring | PCBSchemaGen benchmarks (227 real-IC tasks on Hugging Face), pcbGPT-Eval, blocks cut from public KiCad projects and the KiCad demos, Monolith as held-out | Pass rate of the full check stack; netlist graph match to reference; tokens and retries to pass | A valid alternative circuit fails a reference match (HWE-Bench notes this); public designs are mostly low-voltage digital, and may be in training data |
| The checks themselves | Known-good designs with injected faults: swapped pin pair, dropped net, wrong strap value, NC tied to ground, cap bound to the wrong pin, missing declaration | Detection rate per fault class; false alarms on the clean design | Only catches faults someone thought to inject; says nothing about function |
| Symbol trust | A few hundred LCSC parts that also have an official KiCad symbol: import, extract, compare | Disagreement rate by source; share resolved without a human | Sources can share an upstream error (both copied the same datasheet typo) |
| Drawing | Every generated sheet | Hard gate: netlist equality. Soft: overlaps, crossings, label collisions, left-to-right flow, parts per sheet; a vision-model legibility score | Geometry scores are not Logan's taste; calibrate with a handful of his accept/reject marks, each turned into a rule |
| Prompt and skill variants | All of the above | Same metrics, per model, so the flow stays model-neutral | Tuning to a benchmark instead of to Monolith |

The loop: change a prompt, a part-record format or a check; run the suite overnight; keep the change if pass
rate rises without the mutation detection rate falling. Nothing here needs a fabricated board. None of it shows
that a circuit works; simulation and bring-up remain separate evidence.

## 6. Risks and unknowns

1. **A readable drawing (largest).** Every existing drawer I ran except tscircuit's produced sheets a reviewer
   would reject, and two were electrically wrong. Our own drawer is new work. *Spike:* write two Monolith
   blocks as code (one buck-boost power stage; the USB-C port sheet that is used twice), generate KiCad sheets
   from relative placement hints, require a zero netlist diff, and have Logan compare them with his own sheets.
   Two days. If the sheets are not acceptable, fall back to label-on-pin sheets plus a per-block pin table and
   decide whether that is enough for review.
2. **ECO link stability.** Unverified that a regenerated schematic with deterministic UUIDs keeps every
   footprint through "Update PCB". Test in the same spike: build, place ten parts, change one resistor and add
   one capacitor, rebuild, update, check that nothing moved.
3. **SKiDL dependence.** Version 3.0 is three weeks old, with one maintainer and noisy logs. Mitigation: we
   use only parts, nets, hierarchy and netlist export; pin the version; keep our layer thin enough to swap the
   kernel (Zener is the candidate).
4. **Zener not evaluated hands-on.** If Claude's training gives it a clear quality lead, the kernel choice
   should flip. *Spike:* the same two blocks in Zener on Logan's PC under WSL2; compare first-pass correctness,
   tokens and error messages.
5. **Constraint schema.** The declaration set comes from one board. The placement and routing tracks must
   confirm they can consume it.
6. **KiCad 11.** A schematic API and headless mode are coming. They would make the drawer and the board update
   cleaner, and do not change the choice of source of truth.
7. **Whole-board coherence.** Block-level success rates are high; published whole-board rates are under 10 %.
   Cross-block errors (rail names, pin assignment on the MCU, address clashes) need their own checks at the
   top level.
8. **Not verified:** JITX's KiCad export and price; JLC2KiCadLib, SnapEDA, Ultra Librarian, PartReel; the
   content of atopile's 0.16 announcement; the Gemini PDF itself (I read only the repo's summary of it).

## 7. Sources

Local evidence: `.claude/skills/{pcb-proto-flow,kicad-schematic-scripting,schematic-design-review,kicad-tools-and-mcp}/SKILL.md`;
`tools/battery-bank/HANDOFF.md`; `tools/battery-bank/schematic-tools/tpd6s300.py`; `docs/research/README.md`.
My scripts and renders: `docs/research/01-design-representation/`.

- https://pypi.org/project/atopile : version 0.15.9, 2026-09-12, Python 3.14, MIT (also PyPI JSON for release dates of SKiDL, circuit-synth, kicad-sch-api, edg).
- https://github.com/atopile/atopile : README features, MIT, 4.0k stars.
- https://www.github.com/atopile/atopile/releases : release list.
- https://github.com/atopile/atopile/issues/1843 : user objection to the web-IDE move; no maintainer reply seen.
- https://docs.atopile.io/ : browser workspace, pre-release.
- https://atopile.io/blog/atopile-v16 : opened; only metadata was returned.
- https://ycombinator.com/companies/atopile : company size and open-core statement.
- https://github.com/devbisme/skidl : features, MIT, KiCad 5 to 10.
- https://arxiv.org/html/2602.00510v1 and https://arxiv.org/html/2602.00510v2 : PCBSchemaGen, SKiDL as LLM target, pass rates, feedback ablation, verifier design.
- https://github.com/HZou9/PCBSchemaGen : benchmark task levels.
- https://arxiv.org/html/2603.18102 : HWE-Bench, whole-board results and error types.
- https://www.alphaxiv.org/abs/2605.30345.md : SchGen, representation ablation.
- https://github.com/microsoft/SchGen : code and licence (MIT), KiCad 8.
- https://arxiv.org/html/2606.01188v1 : pcbGPT.
- https://claude.com/resources/articles/making-claude-a-better-electrical-engineer : Anthropic and Diode on Claude writing Zener.
- https://www.gend.co/blog/enhancing-claude-pcb-design-skills : third-party retelling of the same; adds nothing verified.
- https://github.com/diodeinc/pcb and https://raw.githubusercontent.com/diodeinc/pcb/main/README.md : `pcb` CLI, MIT, KiCad 10, Windows experimental.
- https://docs.pcb.new/pages/spec and https://docs.pcb.new/pages/quickstart : Zener language, checks, commands, authentication.
- https://docsearch.algolia.com/mcp/docs/repo/diodeinc/pcb : crate list (layout sync, symbol positions stored with source).
- https://github.com/tscircuit/tscircuit and https://docs.tscircuit.com/ : features, MIT, KiCad export.
- https://circuit-synth.readthedocs.io/en/latest/ : circuit-synth features.
- https://github.com/BerkeleyHCI/PolymorphicBlocks : edg features and stated limits.
- https://jitx.com/ : JITX positioning; no price or KiCad statement.
- https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/ : IPC API covers PCB editor only in 9 and 10; schematic and headless in 11.
- https://forum.kicad.info/t/kipilot-mcp-server-new-version-is-available-for-kicad-11-sch-pcb-workflows/71677 : schematic API needs a KiCad 11 nightly.
- https://kicad.org/blog/2025/02/Version-9.0.0-Released : component classes, rule areas, design blocks, multi-channel.
- https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ : variants, PCB design blocks, jumper pins.
- https://docs.kicad.org/master/en/eeschema/eeschema_schematic_creation_and_editing.html : net class directives and patterns.
- https://glama.ai/mcp/servers/@mixelpixx/KiCAD-MCP-Server/blob/8bc73ed408ece1f54c53d572a6710f2b80af3c98/README.md : older README of the MCP server (kicad-skip for schematics).
- https://github.com/rjwalters/kicad-tools : agent-oriented KiCad tools and MCP (newcomer, MIT, 56 stars).
- https://pypi.org/project/circuit-weaver/ : YAML-spec generator with validation groups (newcomer, alpha).
- https://github.com/uPesy/easyeda2kicad.py : importer, AGPL-3, correctness disclaimer.
- https://cdn.jsdelivr.net/npm/@jlcpcb/mcp@0.4.0/README.md : `jlc-mcp` part search and library install.
- https://jlcpcb.com/blog/gpt-6-astra-pcb-design-in-kicad : computer-use KiCad anecdote.
- https://kevinlynagh.com/newsletter/2026_07_kevins_kicad_helpers/ : netlist-into-database checks and a single build command around KiCad.

Seen in search results but not opened: Boardsmith (PyPI), KiCad's EasyEDA import docs, JLC2KiCadLib.
