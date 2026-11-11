# PCB flow hand-off: skills and tools from the Monolith project

Made 2026-11-11 from the Battery-Bank repository (branch `claude/project-thread-ploune`). Everything an agent
learned on that project about schematic work, part placement, routing, layout verification and fab output,
written as skills, plus the code those skills call. It is meant as the starting point of a separate project that
builds an automatic placer, an automatic router and the rest of a prototype PCB flow.

Nothing built from these boards had been powered when this was written. Every electrical number is modelled.
All of it comes from one design (a 4S Li-ion USB-PD pack, 430 parts, six layers, KiCad 10, JLCPCB rules).

## Start here

1. `skills/pcb-proto-flow/SKILL.md`: the whole flow, what each step looked like on this project, what the
   schematic has to declare for placement and routing to be automatic, and the list of missing pieces in order
   of value.
2. `skills/pcb-scripted-routing/SKILL.md` and `skills/pcb-scripted-placement/SKILL.md`: what worked, what went
   wrong and why, and what to build next.
3. `skills/pcb-layout/references/solver-verified-layout.md`: the check loop. It is what made a scripted board
   trustworthy, and it is the part to carry over first.

## Installing the skills

Copy the folders under `skills/` into the new project's `.claude/skills/` (or `~/.claude/skills/` for all
projects). Claude Code finds them by their `name` and `description`. Other agents can read the `SKILL.md` that
fits the task.

| Skill | Use it when |
|---|---|
| `pcb-proto-flow` | Planning the flow, deciding what to build next |
| `pcb-scripted-placement` | Writing or running a placer; a routing failure traces back to a part |
| `pcb-scripted-routing` | Writing or running a router or a cleanup pass; routed copper looks untidy |
| `pcb-loop-and-coupling-solvers` | Hot-loop and gate-loop inductance, switch-node coupling into signals |
| `pcb-copper-resistance` | DC resistance, loss, via current, Kelvin tap error from the board file |
| `pcb-layout` | Layout method and rules, with reference files (stack-up, return paths, placement, power stages, routing discipline, KiCad scripting pitfalls, the solver check loop) and scripts |
| `pcb-layout-review` | Reviewing a board read-only, with fix coordinates |
| `schematic-design-review` | Reviewing a schematic or netlist |
| `kicad-schematic-scripting` | Editing schematics and symbols by script with a netlist diff |
| `power-stage-design`, `battery-protection-config`, `thermal-derating` | Circuit design of chargers, PD ports, protection and derating |
| `component-sourcing` | Part choice, stock, drop-ins |
| `bringup-planning` | First power-up plans from the netlist |
| `jlc-fab-files` | Fab rules, gerbers, BOM and placement file |
| `kicad-tools-and-mcp` | Running KiCad from an agent: Docker in a cloud container, kicad-cli, a KiCad MCP on a PC |

## The tools, and the paths the skills use

The skills name files by their path in the Battery-Bank repository. In this zip:

| Path in the skills | Path here | What |
|---|---|---|
| `hardware/Production/groundup/` | `tools/groundup/` | Placement (`placelib.py`, `fpdb.py`, `place*.py`, `apply_place.py`, `mechcheck.py`), the maze router (`router.py`), spec-driven edits (`handadd.py`, `step.sh`, `finish.sh`), exact-clearance link search (`ml.py`, `vsite.py`), the cleanup pass (`tidynet.py`, `tidyall.py`, `runwidth.py`), dumps (`dump.py`, `dumpcu.py`, `dumpkeep.py`), pictures (`netpic.py`, `sigpic.py`, `piecepic.py`), Docker wrappers (`dk.sh`, `kc`, `drc.sh`). `README.md` is the record of every pass |
| `hardware/Production/groundup/compare/` | `tools/groundup/compare/` | Solvers: loop inductance (`peec.py`, `run_hot2.py`, `run_gate3.py`), coupling (`coup.py`), copper and Kelvin (`k/`), sense pairs, tidiness (`tidy.py`, `tidycmp.py`), `runfix.sh` for all of them. `README.md` lists every tool and the comparison of the board versions |
| `docs/reviews/2026-10-30-routed-board/tools/` | `tools/review-tools/` | S-expression parser (`sx.py`), board loader (`board.py`), DC copper solver (`solve.py`, `run2.py`). `tidy.py` and the solvers import these; keep the relative layout or set the path at the top of each script |
| `hardware/Production/tools/` | `tools/schematic-tools/` | Schematic helpers: `schlib.py` (S-expression editing, new uuids), symbol generators written from datasheet pin tables, `check_netlist.py`, JLC BOM and placement builders |
| `.claude/skills/pcb-layout/scripts/` | `skills/pcb-layout/scripts/` | Routing-rule checker, DRC summary, net extents, render |

The board files themselves are not in the zip. They are in the repository:
`hardware/Production/Monolith.kicad_pcb` (on this branch at commit `83de66a`: the script-built board after the
cleanup pass; at commit `dd34285`: the same board before the cleanup pass; at commit `8dd9eb6`: the hand-routed,
reviewed board), with `Monolith.kicad_pro`, `Monolith.kicad_dru` and the schematics.

## What is general and what is one board's

General: the methods in the skills, the dump formats, the spec-and-step loop, the solvers' physics, the tidiness
measure, the cleanup and width passes, the greedy placer.

Monolith's, and typed into the code: net names and the regular expressions built on them (switching nets, plane
nets, sense pairs), net classes and widths, the stack-up heights, the lists of hot loops, gate loops, power
paths and sense resistors, enclosure limits, the fixed-part list, every coordinate in the `place*.py` scripts
and the `hand*/` spec folders. `pcb-proto-flow` section 3 lists what should come from the schematic instead.
Check each solver against a known answer before trusting it on another board.

## Running things

- KiCad steps (dump, edit, refill, DRC) run inside the `kicad/kicad:10.0` Docker image through `kc` and `dk.sh`;
  the paths at the top of `kc` point at a scratch folder and need changing. See `kicad-tools-and-mcp`.
- Everything else is plain Python 3 with numpy, scipy, Pillow, matplotlib and pyamg.
- Memory: the loop solver needs about 8 bytes × branches²; about 27 000 branches is the ceiling in 14 GB.
Made from commit 83de66a45c98d3266d6462e2dddf99f0b2da228d (2026-11-11) of branch claude/project-thread-ploune.
