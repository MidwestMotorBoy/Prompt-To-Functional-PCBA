# Team A: paused (2026-11-15, at Logan's request after round 3)

State: three worker rounds and the lead's final step are done. The best placement is `best_placement.json`, rebuilt with `rebuild_best.sh <workdir>` and scored with `tools/score_board_best.sh` (copper recipe in `tools/best_env.sh`). Numbers and open points are in `REPORT.md`; the method is in `SKILL-NOTES.md`.

What was committed: scripts, notes, placements, score.json, hot-loop and DC results, and renders. Left out: board files, DRC and dump JSONs, and per-run pylib copies. Re-run the scorecard to regenerate them.

Where to resume:
- The 17-18 failed signal edges, mostly on port 1.
- The second VBUS pin pair on J401/J501 is not joined to the VBUS pour, and dc_score does not flag it.
- The SW2 switch-node pours on B.Cu under each inductor.
- Moving portcu's planner rules into the shared planner.

Scorecard caveat: all numbers from round 2 on use split-zone copper (`tools/split_spec.py`). The old 391/448 hand reference used the vanishing-pour copper. On split copper the hand board routes 363 of 422.
