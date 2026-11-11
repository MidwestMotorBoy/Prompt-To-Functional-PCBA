# Electrical design skills for AI agents

These are the electrical design, schematic and board-review techniques used to build the Monolith pack, written as general skills that any AI agent can follow on another hardware project. Each folder holds one `SKILL.md`, with `name` / `description` frontmatter and then the method. The examples point to files in this repo.

**Using them.** Claude Code finds skills in `.claude/skills/` by itself when it works in this repo. To use them elsewhere, copy the folders into that project's `.claude/skills/` (or `~/.claude/skills/` for all projects). Other agents can just read the `SKILL.md` that fits the task. These are files in the repo; they don't install into a claude.ai account.

| Skill | Use it when |
|---|---|
| [pcb-proto-flow](pcb-proto-flow/SKILL.md) | Planning an agent-driven flow from schematic to fab files: which skill covers each step, what the schematic must declare, what is proven and what is missing. **Start here for an auto-placer or auto-router project** |
| [pcb-scripted-placement](pcb-scripted-placement/SKILL.md) | Placing parts by program: footprint database, fixed parts, power stages from coordinates, greedy placer with pin targets, repeated blocks, enclosure checks |
| [pcb-scripted-routing](pcb-scripted-routing/SKILL.md) | Routing by program: a grid router that stays legal against real DRC, pad escapes, pours, the cleanup pass, the tidiness measure, accept-or-revert |
| [pcb-loop-and-coupling-solvers](pcb-loop-and-coupling-solvers/SKILL.md) | Hot-loop and gate-loop inductance and switch-node coupling into signals, solved on the real copper; comparing layouts; finding the via that picks up noise |
| [pcb-layout](pcb-layout/SKILL.md) | Laying out a board: stack-up, placement, hot loops, return paths, routing discipline, DFM, and the solver check loop for scripted layouts (with reference files and scripts) |
| [schematic-design-review](schematic-design-review/SKILL.md) | Reviewing a schematic or netlist: pin-by-pin, net-by-net, ratings, derating, state and fault tables, config defaults, challenge round |
| [kicad-schematic-scripting](kicad-schematic-scripting/SKILL.md) | Editing `.kicad_sch` / `.kicad_sym` by script, with a netlist diff to prove the change |
| [pcb-layout-review](pcb-layout-review/SKILL.md) | Reviewing a placed or routed board read-only, with fix coordinates for the layout owner |
| [pcb-copper-resistance](pcb-copper-resistance/SKILL.md) | Solving copper resistance, loss, via current and Kelvin sense error from the `.kicad_pcb` |
| [component-sourcing](component-sourcing/SKILL.md) | Choosing parts, checking stock, judging drop-ins, clones and new silicon revisions |
| [power-stage-design](power-stage-design/SKILL.md) | Charger / USB-PD / DC-DC stages: loss budget, gate drive, cap banks, sensing, port protection, fail-safe defaults |
| [battery-protection-config](battery-protection-config/SKILL.md) | Li-ion protection layers, short-circuit FET stress, gauge data-flash pitfalls, tap order, NTCs |
| [thermal-derating](thermal-derating/SKILL.md) | Charge and discharge derating policy, sensor placement that never reads low, thermal model inputs |
| [bringup-planning](bringup-planning/SKILL.md) | First power-up plans worked out from the netlist with blank firmware and factory configs |
| [jlc-fab-files](jlc-fab-files/SKILL.md) | Fab-rule DRC, gerbers, BOM/CPL from the board, top-only assembly, rotation fixes |
| [kicad-tools-and-mcp](kicad-tools-and-mcp/SKILL.md) | kicad-cli, a local KiCad MCP server, and working with no KiCad at all |

## Rules that apply to all of them

- **The datasheet is the source of truth** for part and cell figures. Cite the document and section, and keep the PDF in `datasheets/`. A number from memory, a search snippet or a forum post is a lead, not a fact.
- **One spec.** Decisions go into the project's single spec (`docs/spec.md` here), with the date and the reason. Superseded notes move to an archive and don't get edited to look current.
- **Design values aren't measurements.** Until hardware exists, label results as modelled and list what the first build must measure.
- **The layout belongs to its owner.** Agents change schematics and write reviews. The board file changes only when the owner explicitly asks for that edit.
- **Back up before every write** to someone's working files, and never write under an editor that has the file open.
- **Ask before anything irreversible** (an order, a blown fuse, a permanent-fail setting, a history rewrite). Do reversible work, then say what you did.
- **Put reviews in the repo** as markdown + PNG (`docs/reviews/<date>-<topic>/`), so outside reviewers can read them.
- **Say what you didn't check** (a graph you couldn't read, a DRC you couldn't run) and turn it into an open item.
