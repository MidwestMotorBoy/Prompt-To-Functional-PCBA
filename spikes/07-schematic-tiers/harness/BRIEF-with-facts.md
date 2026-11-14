# Task: make the generated Monolith schematic sheets readable to a person

The Monolith battery bank (285 parts, 5 blocks) is described as Python code. Its KiCad schematic sheets are
**generated** from that code, and they are electrically correct but hard for a person to read. Your job is to
change the drawing so the generated sheets read like a careful engineer drew them.

## Your folder
Everything is in this folder (your working directory). Work only here.
- `design/kernel.py`, `design/blocks/*.py`, `design/top.py`: the circuit as code (the truth). `design/draw.py`:
  the sheet generator (about 870 lines; templates `draw_as("buck"|"bridge4", ...)` and "lanes" already exist).
  `design/symlib.py`, `design/sx.py`: symbol library and s-expression helpers.
- `make.sh`: builds the sheets, **proves the drawn sheets are electrically identical to a frozen netlist** (exit
  code 1 and a list of differences otherwise), and renders `out/render/page-N.png` (100 dpi) and `sheets.pdf`.
  Run it after every change and look at the PNGs (you can crop/zoom them with Python PIL).
- `RUBRIC.md`: how the result will be judged. Read it first.
- `ref/hand_drawn_vs_generated.pdf`: earlier hand-drawn Monolith sheets next to an older generated version, as a
  style reference for what a person drew.

## Rules
- You may change anything under `design/` that affects how sheets are drawn: `draw.py`, and drawing hints in the
  block files or kernel (for example placement hints, template choices, section names). You must **not** change
  the circuit: `make.sh` must end with "NETLIST OK". Do not edit `make.sh`, `tools/` or anything outside your folder.
- The output must stay generated from code: the sheets are rebuilt from `design/` by `make.sh`. Do not hand-edit
  `.kicad_sch` files.
- Prefer general drawing improvements that would carry over to a new board, but per-block hints are allowed.
- Earlier feedback from the owner on generated sheets: "too much floating off in space" (labels on every pin with
  parts scattered around), "placements are super odd", "way too much down wire". Templates and lanes were judged
  "good enough to review from"; the goal now is clearly better than that.

## When you finish
Leave the final state in place (`make.sh` passing) and write `NOTES.md` in this folder: what you changed, what
you would do next, and anything that blocked you. Then reply with a short summary.

## Facts that earlier attempts got wrong
- The netlist check compares which pins are joined together, **not net names**. Renaming a net, or giving an
  auto-named net like `Net-(U101-VC3)` a readable name, does not fail the check.
- Replacing a label with a wire (or a wire with a label) on the same net does not change connectivity. Labels are
  a drawing choice.
- There are several pages. After every change, open **every** page PNG, not just the one you edited.
- Do not stop after a quick fix. Earlier attempts that stopped within a few minutes scored the same as the
  unchanged baseline. Expect to spend a substantial session iterating: change, rebuild, look at every page, repeat.
