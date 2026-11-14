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
