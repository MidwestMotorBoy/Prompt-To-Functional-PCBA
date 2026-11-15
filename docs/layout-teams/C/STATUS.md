# Team C status: paused after round 1 (2026-11-15)

Logan paused team C on 2026-11-15 at 03:07 UTC. Round 1 was finished. Its full scorecard re-run (official scorecard plus a copy with team D's zone-split fix) was stopped before it finished. No further rounds were started.

## What exists
- `cplace/`: one whole-board constructive placer, built from round 3's greedy_fill.py. Every feature is a hook you can switch off:
  - `cpd`: places the cell path first and locks it, then the PD chips with a pin-order cost, and moves the Port 1 5 V buck west of U401.
  - `cpower`: power stages with the hot-loop capacitors pad to pad.
  - `cpdl`: puts the R424/R524 sense resistors next to the PPHV pin.
  - `ccorr`: a copper-corridor cost.
  - `cside`: two-sided placement. It is off by default because it scored the same as one side, or 2 to 5 blocked edges worse.
  - Run it with `SEED=4 cplace/run_merged.sh`.
- `merge/`: the sweep driver (msweep.py) and the full sweep table (sweep_table.md). It holds 40 placements, 30 of them screened, and `candidates/` with placements and score.json files.
- `power/`, `corridor/`, `sides/` and `sweep/` hold each worker's piece. `score_fixed/` is the start of a scorecard copy with team D's zone split. It is untested.

## Round 1 results (official scorecard; the zone-outline flaw applies to every team)
| Board | Blocked edges | Full route | Hot loops | Loss | Power |
|---|---|---|---|---|---|
| r1_s4 (best) | 57 of 441 | 373 of 441, finished | 7 of 7, 5.36 nH | 1.189 W | all joined |
| m_s4 | 59 of 454 | 383 of 454 at the 45 min cap (timed out) | 7 of 7, 5.32 nH | 1.150 W | all joined |
| r1_s1 | 59 of 440 | 364 at the 45 min cap (timed out) | 7 of 7, 5.37 nH | 1.196 W | all joined |
| Hand placement | 56 of 452 | 391 of 448 | | 1.36 W | PP5V open at U401 |
| Round 3 w1_c | | 346 of 442 | 5.49 nH | 1.255 W | all joined |

Every board meets the hard limits: 0 DRC errors, every power path joined, and 7 of 7 hot loops. None reaches the routing target. The remaining blocked edges cluster at the PD chips, 15 to 17 each against 8 to 9 on the hand board, because PP5V, PPHV and VBUS copper wraps round the chips' signal pins. Port 2 AC_SNS_N still opens at R524 on several seeds.

## If resumed
The next step is to give the PD chips' signal sides room in the PD placement cost. After that, rescore with the zone-split fix.
