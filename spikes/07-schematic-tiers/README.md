# Spike 7: which agent tier makes generated schematics readable

Run 2026-11-14 in the cloud container (KiCad 10.0.8 `kicad-cli` in Docker). Asked by Logan: compare Fable, Opus
and Sonnet agents, and a Sonnet worker steered by a Fable grader, on making the generated Monolith sheets readable
to a person. Cost, time and blind-graded quality.

## Setup

- **Task (identical for every agent):** `harness/BRIEF.md`. Starting point is spike 1's drawer
  (`spikes/01-blocks-as-code/design`). Change `draw.py` and drawing hints in the blocks so the five sheets read
  like a careful engineer drew them. `make.sh` rebuilds the sheets, and KiCad's netlist of them must equal a
  frozen netlist (285 parts, 168 nets). No hand-edited `.kicad_sch`.
- **Setups, two runs each:**
  - Fable 5.2 alone.
  - Opus 5.5 alone.
  - Sonnet 5.5 alone.
  - Sonnet 5.5 worker with a Fable 5.2 grader. The grader reviews the renders and writes prioritised feedback
    against the same rubric, for three feedback rounds, so four work rounds in all.
- **Gate:** every final design (and the intermediate Sonnet+grader rounds) was rebuilt with pristine
  `make.sh`/`tools` by `harness/verify.sh`. All passed with 0 netlist differences.
- **Quality:** renders at 150 dpi were anonymised as E01-E14 (`results/blind_key.json`). That covers the 8 finals,
  5 intermediate grader-loop rounds and the unchanged baseline. Two passes, each done by both Opus 5.5 and Fable 5.2:
  - (a) absolute scores, 8 criteria x 4 sheets, 0-5 (`harness/RUBRIC.md`, `harness/GRADER.md`);
  - (b) a forced ranking of all 14 versions of each sheet (`harness/RANKER.md`).
- **Cost:** from each agent's transcript usage (deduplicated per message). Prices per MTok: Fable $8 in, $40 out,
  $0.20 cache read; Opus $4 / $20 / $0.20; Sonnet $2 / $10 / $0.10. Cache writes are charged at 1.25x input
  (5-minute cache).

## Results

Rubric is the mean of 32 criterion scores, averaged over both graders (0-5). Rank is the mean place over 8 rankings
(4 sheets x 2 graders, 1 = best of 14).

| Setup | Run | Cost | Output tokens | Agent time | Rubric | Rank | What it built |
|---|---|---|---|---|---|---|---|
| Fable | 2 | $17.16 | 209 k | 47 min | **4.20** | **1.2** | net-aware drawing kit (`scene.py`, lints overlaps) + hand-placed view per block |
| Opus | 1 | $15.25 | 273 k | 58 min | 3.92 | 2.6 | drawing kit (`sheetkit.py`) + hand-placed layout per sheet |
| Fable | 1 | $13.30 | 155 k | 33 min | 3.86 | 3.0 | rewrote the general drawer (no per-part coordinates) |
| Opus | 2 | $11.98 | 207 k | 43 min | 3.80 | 3.5 | rewrote the general drawer + power-path templates |
| Sonnet + Fable grader | 1 | $9.76 ($5.81 + $3.95) | 189 k | 41 min | 3.50 | 5.1 | lanes, ladders, `sketches.py`, PDF text-overlap check |
| Sonnet + Fable grader | 2 | $6.23 ($2.63 + $3.60) | 96 k | 21 min | 3.47 | 10.5 | lane/inline fixes, `path` and `kelvin` templates |
| Sonnet | 2 | $0.48 | 7.5 k | 2 min | 2.81 | 11.0 | page packing only |
| Sonnet | 1 | $0.42 | 5.5 k | 2 min | 2.70 | 12.8 | page packing only |
| baseline (spike 1) | | | | | 2.81 | 12.6 | |

The two graders agree. Spearman rank correlation between the Opus and Fable rankings is 0.97-1.0 per sheet.
Fable scores run about 0.4 higher on the absolute scale.

Sonnet+grader rounds (rubric / rank):
- run 1: after round 1 (no feedback yet) 3.48 / 7.8; round 2 3.56 / 7.0; round 3 3.64 / 6.1; final 3.50 / 5.1.
- run 2: round 2 3.34 / 11.1; round 3 3.41 / 10.6; final 3.47 / 10.5.

## Findings

1. **Fable and Opus both make clearly readable sheets; Sonnet alone does not.** Every Fable and Opus run landed in
   the top four and reached "acceptable to review from" (rubric 3.8-4.2). Plain Sonnet stopped after about 2 minutes
   having only changed page packing, and the graders put it level with the unchanged baseline.
2. **Fable vs Opus is close at n=2.** Fable won both comparisons on rank (1.2 and 3.0 against 2.6 and 3.5). Its cost
   was similar ($13-17 against $12-15) and it finished faster (33-47 min against 43-58 min). Opus made 2-3x more
   tool calls.
3. **The top two hand-place each block.** Fable 2 and Opus 1 wrote a drawing kit plus fixed coordinates per block
   (about 100 part references in the layout code). A new block falls back to the old drawer. The best *general*
   drawers are Fable 1 and Opus 2 (3.86 / 3.80), which carry over to a new board. This matches spike 1 finding 6:
   a library block should carry its reviewed drawing, and templates cover new blocks.
4. **Sonnet's gap is mostly stopping too early, not skill.** Four Sonnet sessions started from the identical
   prompt. Three quit within 3 minutes. One (run 1, round 1) worked 12 minutes for $1.74 and alone reached 3.48 /
   rank 7.8, most of the way to Opus/Fable at about an eighth of the cost. The Fable grader's main effect was keeping
   Sonnet working. Each feedback round after that added only about +0.1, and Sonnet often did part of the list and
   stopped again.
5. **Sonnet held wrong beliefs that the brief didn't rule out.** "Renaming `Net-(U101-VC3)` would change the
   netlist" was false: the gate compares pin groupings, not names. "Dropping labels changes connectivity" was also
   false. It checked one page instead of all. The grader corrected these each time.
6. **The grader costs about as much as the worker.** The Fable grader cost $3.6-4.0 against a Sonnet worker cost of
   $2.6-5.8. Given 0.97+ rank agreement between Opus and Fable graders, an Opus grader would likely steer as well at
   about half the price. That is not tested here.

## What would let Sonnet close the gap

- **Ship the kit, not the task.** Give Sonnet Fable 2's `scene.py` (net-aware placement, auto-finish of open
  pins, built-in connectivity check, overlap and off-page lint) and Opus 1's `layouts.py` patterns. Its job then
  narrows to writing one view per block with a kit that refuses bad drawings.
- **A readability lint in `make.sh`** that gives a number: text overlaps measured from the PDF (sf-1's
  `pdfcheck.py` approach with `pdftotext -bbox`), parts tied only by labels, fill ratio, long wires and crossings.
  That turns "done" into a threshold instead of a feeling, which is Sonnet's main failure.
- **Fix the brief:** net names are display-only, open every page after every change, stop only when the lint
  passes.
- **Keep a grader, but cheaper and earlier.** Use one structured review after the first round, then lint-driven
  rounds.

## Not done / caveats

- Two runs per setup. The Sonnet+grader spread (rank 5.1 against 10.5) shows the variance is large.
- Quality is model-judged. Logan's own read of the PDFs (in project files `schematic-tiers/`) is the real test.
- Three runs changed non-drawing details that the gate allows:
  - display net names in code (sf-1, fable-2);
  - one `serves` list in `usb_port.py` (fable-1), so C457/C557 are drawn at the LDO input they decouple. This
    changes `constraints.json`.
- The first round of Opus blind grades was discarded and redone, because graders wrote crops to a shared folder
  and could have read another entry's images. The Fable grades all used private folders.
- Blind grading cost about $33 on top of the runs.

## Run it

`harness/make.sh` needs `SHARED` set to a folder holding `ksym/` (KiCad 10 symbols), `lib/MonolithDev.kicad_sym`
and `frozen_netlist.json`. `MonolithDev.kicad_sym` was rebuilt from the `lib_symbols` embedded in the spike 1
sheets, because the library is not in this repo. Copy a run's `design/` next to `make.sh` and `tools/` (from spike 1),
then run `./make.sh`.
