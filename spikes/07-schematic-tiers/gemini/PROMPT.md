# Prompt to paste into Antigravity

Open the `schematic-benchmark` folder as the Antigravity workspace, then paste everything between the lines
below as the first and only message. Do not add hints or answer follow-up questions with task advice; if the
agent asks something, reply only: "Use your own judgement and keep going."

---

You are being benchmarked on a software and electronics drawing task. Several other AI agents have done the
exact same task from the exact same starting files, and every result will be graded blind by the same
reviewers. Do the task fully and autonomously: there is no one to answer questions, so make your own
decisions and keep going until you judge the result is as good as you can make it.

## Your workspace

Your working folder is the open workspace folder, `schematic-benchmark`. Work only inside it. Do not read,
create or change files outside it, and do not look at any other copies of this task on this computer.

What is in it:
- `BRIEF.md`: the task. Read it first, in full.
- `RUBRIC.md`: exactly how the result will be judged. Read it second, in full.
- `design/`: the circuit as Python code and the sheet generator (`design/draw.py`) you will improve.
- `make.py`: the build and check script. Run it with `python make.py` from the workspace folder.
- `tools/`, `shared/`: the checker, the frozen reference netlist and the symbol libraries. Read-only.
- `ref/hand_drawn_vs_generated.pdf`: a style reference.
- `PROMPT.md`, `HOW-TO-RUN.md`: instructions for the person running the benchmark. Ignore them.

## Environment

- This is a Windows PC. Use the terminal available to you (PowerShell is fine). Python 3 is installed; use
  `python` (or `py -3` if `python` is not found). Install only these packages if missing:
  `python -m pip install pymupdf pillow`.
- KiCad 10 is installed. `make.py` finds its `kicad-cli` on its own (it checks the `KICAD_CLI` environment
  variable, then PATH, then `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`). Do not install anything else.
- One `python make.py` run takes well under a minute. It builds the sheets from `design/`, checks that the
  drawn sheets are electrically identical to the frozen netlist (285 parts, 168 nets), writes
  `out/render/sheets.pdf` and renders every sheet to `out/render/page-N.png` at 100 dpi. It prints
  "NETLIST OK" on success and exits with code 1 and a list of differences on failure.
- Page 1 is the root sheet; page 2 is the 3V3 rail, 3 cells and gauge, 4 MCU, 5 and 6 the two USB ports
  (same circuit drawn twice).
- You can look at the rendered PNGs directly, and you can crop and zoom them with Python and Pillow to read
  small text.
- The internet is not needed for this task. Do not search the web or download anything other than the two
  Python packages above.

## How to work

1. Run `python make.py` once before changing anything, confirm it prints "NETLIST OK", and look at every
   rendered page so you know the starting point.
2. Read `BRIEF.md` and `RUBRIC.md` there and do the task the brief describes.
3. Run `python make.py` after every change and look at the pages it renders. It must still end with
   "NETLIST OK".

## Rules (from the brief, repeated so they are not missed)

- Change only files under `design/`. Do not edit `make.py`, `tools/`, `shared/`, `ref/`, `BRIEF.md` or
  `RUBRIC.md`.
- Do not change the circuit. The final `python make.py` must end with "NETLIST OK".
- The sheets must stay generated from code. Do not hand-edit `.kicad_sch` files or the PDF.
- Keep everything in the workspace folder.

## When you finish

1. Leave the final state in place, with `python make.py` passing and `out/render/sheets.pdf` from your final
   run present.
2. Write `NOTES.md` in the workspace folder: what you changed, what you would do next, and anything that
   blocked you.
3. Reply with a short summary.

---
