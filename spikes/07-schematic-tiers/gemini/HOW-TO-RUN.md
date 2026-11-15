# Running the Gemini benchmark (for Logan)

This is the same task every Claude run got: same brief, rubric, starting `design/` code, frozen netlist and
reference PDF. The only changes are portability ones. `make.sh` (Linux, Docker, cloud paths) is replaced by
`make.py`, which does the same steps with native KiCad 10 on Windows and PyMuPDF for the 100 dpi renders. The
brief's mentions of `make.sh` now say `make.py`. Only the KiCad symbol libraries the design uses are bundled
(`shared/symbols`), so the folder is about 20 MB instead of 220 MB.

The prompt adds environment and procedure details only. It gives no advice on how to draw schematics, so it
stays comparable with the Claude runs (Logan's rule: no task-specific help).

## Steps

1. Unzip to a fresh folder, for example `C:\bench\gemini-1\schematic-benchmark`. Use a fresh copy for each run.
2. Optional check before starting the agent: `python -m pip install pymupdf pillow`, then `python make.py` in
   that folder should end with "NETLIST OK". Delete the `out` folder it makes afterwards (or leave it; the agent
   rebuilds it).
3. In Antigravity, open that folder as the workspace. Pick the model and its thinking level and note them.
   Let the agent run commands without asking, if Antigravity offers that, so it does not stall on approvals.
4. Paste the prompt from `PROMPT.md` (between the lines). Note the start time.
5. If the agent asks a question, reply only "Use your own judgement and keep going."
6. When it stops, note the end time and any token or cost figure Antigravity shows.

## What to send back

Zip the whole workspace folder (`design/`, `NOTES.md` and `out/render/sheets.pdf` matter most) and drop it in the
thread, with: the model and thinking level, the start and end times, the token or cost figure if shown, and
how many times you had to nudge it.

I will then rebuild it with the original Linux harness, gate-check it, and grade it blind with the same Opus
grader and per-sheet ranking as the 13 finalists.

## Reference points (Opus blind rubric, 0-5)

fable-2 4.16 ($17), fh-1 Fable high 3.91 ($31), gh-2 Sonnet high + guide 4.28 ($10), mx-2 Sonnet max 4.25 ($38),
opus-1 3.75, baseline (the starting point you are giving it) 2.47.
