# Round 3: agent team on skeleton-first routability (2026-11-14)

A lead agent diagnosed why the skeleton-first board q7s2 routed badly (signal parts stranded away from their chips by the fill step) and gave four workers one strategy each. REPORT.md has the results; BRIEF.md is what every worker was given.

- w1/: greedy_fill.py, a constructive fill placer (winner: w1_c, 346 of 442 routed vs 299 for q7s2, power limits unchanged). pp_w1.py is a place_pack.py copy that exports part bodies for it.
- w2/: skeleton.py variant with thinner frozen keep-outs (W2_RASTER is the only change worth keeping).
- w3/: place_pack.py / fastcore.py with rigid-group fill moves and big-parts-first, plus ghost_router.py (counts connections with no path on an empty board, a better screen than a 2-minute route).
- w4/: repair.py, local moves driven by router failures (did not beat q7s2 on a full route).

Scripts still use the work paths they were written with (/home/claude/work/...). Not yet merged into the main flow.
