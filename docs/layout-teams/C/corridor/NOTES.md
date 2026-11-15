# Package corridor (ccorr.py): notes

Module: `../cplace/ccorr.py` (hook module, `HOOKS=...,ccorr`). Knobs and model are in its docstring.
Core patch in `cplace.py`: one line, `hook("after_big", r)  # [corridor]`, right after a large part is put down
(used only by `CORR_PRE`). With `HOOKS` empty, `SEED=2 ./run.sh` still gives `base_seed2_placement.json` byte for byte.

Tools in this folder:
- `corr_draw.py`: placement + corridor estimate picture; with a scorecard `spec.json` a second panel with the copper
  `plan_copper.py` really drew and per-net hit/coverage numbers.
- `zoom_cu.py`: zoomed F.Cu copper + labelled power pads of a scorecard run (to see why a terminal was "left to router").
- `xings.py`: corridor crossings in a `CORR_DEBUG` file. `ghost_parts.py`: blocked edges per part from `ghost.log`.
- `ctrace.py`: debug hook (`PYTHONPATH=../corridor HOOKS=ccorr,ctrace`) printing the placement order of the power parts.
- `screen_queue.sh tag=placement.json ...`: screens one after another, waits for load < 3.

Get the corridor picture of any run: add `CORR_DEBUG=<file.json>`. With `CORR_W=0 ESC_W=0 CMPW=0 CMP_TVS=0` the
module changes nothing (placement identical to the run without it) but still writes the estimate.

## What the scorecard said (screen = `--route=0 --no-hot`), see the worker report for the full table

- Soft corridors + escape bands + crossing cost, alone (`HOOKS=ccorr`, CROSSW=30 is now the default, SEED=2): 86 of 462 blocked,
  1.59 W, 0 DRC (base 98 of 465, 2.00 W). Same knobs SEED=3: 104 of 469, 1.49 W; base SEED=3: 74 of 473, 1.26 W
  (but 5 open power nets). Seed spread is larger than the effect on blocked edges; loss went down on SEED=2.
- With the power package (`HOOKS=cpower,ccorr CROSSW=30`), cpower as of 15:33: 60 of 441, 1.915 W, 0 DRC against
  cpower alone 62 of 440, 2.504 W. With cpower as of 15:39 (current): cpower alone 65 of 454, 2.893 W; + ccorr 78 of 457,
  2.757 W (CMP_TVS=0) and 74 of 459, 2.811 W (CMP_TVS=5). The gain does not carry over to the newer cpower: re-measure
  after every cpower change.
- `best_placement.json` here = `HOOKS=ccorr SEED=2 ./run.sh` with today's defaults (alone): 86 of 462, 1.59 W, 0 DRC,
  open P1 PP5V at U401, P2 PP5V at U501, P2 BAT_SNS_P at R527, GND at Q402/U504 (+ allowed 3V3 L201, J301/J302).
  Not good enough by Logan's rule: the two 5 V bucks sit low on the left, 25-35 mm from their PD chips.
- `ESC_HARD=1` gave the same placement as the soft band (nothing sat in a band at ESC_W=8).
- `CORR_PRE=2` (power chains and their caps placed right after each PD chip) cut blocked edges to 55-63 and loss to
  1.26-1.40 W alone, but opened VBUS at both PD chips and gave 2-4 DRC errors: it takes the room the four-switch
  stages and the hot-loop caps need. With cpower it ran out of room for U406/U506 (before cpower's no-SystemExit fix).

## Traps
- plan_copper.py draws nets one at a time (switch nodes, then by current, ties by NAME: Port 1 PPHV before Port 1
  VBUS). Two power paths that cross on F.Cu: the later one is walled off. Crossing, not body overlap, is what opens
  the PD-chip pins: a PD chip with VBUS pins on one edge and PPHV/PP5V pins next to them needs its PP5V/PPHV parts on
  the side away from the connector. The straight-line estimate misses crossings that the real path makes when it
  detours round pads (Port 2 VBUS ran down between U401 and C407 in x1).
- A shunt pulled to the "nearest terminal" lands at the wrong end: D401 (VBUS TVS) went to the PD chip's far VBUS pin
  and the VBUS copper wrapped round U401, enclosing PPHV and PP5V. Hence CMP_TVS (TVS to the connector).
- A hot-loop hull (`plan_copper` hot_loops_step) covers every pad of the loop: one far hot-loop cap (C544 placed at the
  other port) makes a 47 mm2 PACK_P pour across the top and walls in a VBUS connector. Without cpower, hot-loop caps
  other than the first have no near statement and land anywhere.
- Big parts placed with no corridor yet are not moved by the passes; most "overlap left" is big parts under a straight
  corridor estimate, not a real conflict.
- SW_5V is not a power net for plan_copper (no current_a): it is a router track. The corridor reserves 0.43 mm for it.
- The floorplan box is off in the base (BOXW=0): late power parts (5 V bucks, F102) drift to wherever room is left.
