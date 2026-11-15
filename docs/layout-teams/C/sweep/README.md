# sweep: seed/knob sweep and screening harness for team C's placer

Runs many `cplace` placements, throws out bad ones with cheap proxies (seconds, no KiCad), predicts the power opens
with the copper planner on the host (about 70 s each, no KiCad), screens the rest with the scorecard's blocked-edge
count (about 5 min each, strictly one at a time), and runs the full scorecard (hot loops + 45 min route) on the best.
Everything is cached in the sweep folder; any command can be stopped and started again and skips what is done.

Files: `sweep.py` (all subcommands), `sweep.sh` (background start, bounded wait, status), `bare_xform.py` (moves the
template's cu_dump to a placement so the copper planner runs without KiCad), `grid_calib.json` (example grid).

## Commands, in order

All paths absolute. `S=/home/claude/repo/docs/layout-teams/C/sweep`, `O=/home/claude/work/C/sweep/<name>` (one folder
per sweep; for a new placer variant use a new `<name>`). Foreground shell calls stop at 10 min, so anything longer goes
through `sweep.sh bg` and `sweep.sh wait` (repeat `wait` until it prints `== finished`).

```bash
S=/home/claude/repo/docs/layout-teams/C/sweep; O=/home/claude/work/C/sweep/merged
$S/sweep.sh status                                   # 0. load average and running heavy jobs; wait if load > 3

# 1. place: seeds x configs, 2 placer processes at once (10-20 s per placement with no hooks; hooks are slower)
$S/sweep.sh bg $O/place.log place $O --seeds 1-12 --hooks cpower,cside,ccorr
#    or several knob settings:  --grid $S/grid_calib.json   or  --set p6:PASSES=6 --set n30:NOISE=0.3
#    (a config can also set HOOKS itself, e.g. --set pw:HOOKS=cpower,PWRW=1)
$S/sweep.sh wait $O/place.log                        # ends with the rank table (also $O/rank.md, $O/rank.csv)

# 2. plan: power opens predicted by the real copper planner, one placement at a time, about 70 s each
$S/sweep.sh bg $O/plan.log plan $O --top 6          # or --tags a_s1,a_s2 ; no --top = all non-duplicates
$S/sweep.sh wait $O/plan.log                         # writes plan_n_open into each proxies.json; rank re-sorts by it

python3 $S/sweep.py rank $O                          # gates, then predicted opens, then weighted score

# 3. screen: scorecard --route=0 --no-hot, ONE AT A TIME, about 5 min each (4.3-6.8 min measured)
$S/sweep.sh bg $O/screen.log screen $O --top 4       # best 4 that pass the gates; or --tags ...; or --spread 6
$S/sweep.sh wait $O/screen.log                       # repeat; 4 boards = about 22 min
#    -> $O/table.md, $O/table.csv, $O/contact.png. LOOK at contact.png with the Read tool (F then B per board).
#    hot loops in the screen too: add  --opts="--route=0"  (+5-10 min each)

# 4. full scorecard on the chosen placement (hot loops + route cap 45 min; 55-65 min wall)
python3 $S/sweep.py full $O --tag a_s3 --bg          # log $O/runs/a_s3/full.log, ends with DONE
$S/sweep.sh wait $O/runs/a_s3/full.log               # repeat about 7 times; then the table has a "full" row

python3 $S/sweep.py table $O                         # rebuild table + contact sheet at any time
python3 $S/sweep.py calib $O                         # proxy vs screen rank correlations -> $O/calib.md
```

Knobs: `--load-max 3.0` (env `SWEEP_LOAD_MAX`; every heavy step waits until the 1-minute load is at or below it),
`--jobs 2` (placer processes), `--hl-max 4.0` (gate, mm), `--pd-slack 3` / `--buck-slack 6` (gates, mm over the hand
board), `--weights power_IxL=2,hl_sum=2,sig_tree_mm=1,crossings=1,near_excess=0.5,pp_excess=1`, `--sprawl-x 2`.
`SWEEP_THREADS` (default 1: scorecard runs get NUMBA/OMP/OPENBLAS/MKL_NUM_THREADS=1; without it the hot-loop solve took
183 % CPU, i.e. two cores), `SWEEP_IN` (inputs, default `/home/claude/work/C/in`), `SWEEP_TPL_BARE` (template cu_dump for `plan`, default
`/home/claude/work/C/hand_screen/bare.json`; if it is missing run `tools/score/score_board.sh /home/claude/work/C/hand_screen --route=0 --no-hot` once).

## What lands where

`$O/runs/<config>_s<seed>/`: `p.json` (placement), `place.log`, `run.json` (env knobs, exact command, git rev, md5 of
every `cplace/*.py`, time, rc), `proxies.json`, `plan/plan.json` + `plan.log`, `screen/` and `full/` (full scorecard
outdirs: `score.json`, `F.png`, `B.png`, `hot.json`, `route.log`, ...; `sweep_meta.json` has options and wall time).
Reproduce a placement: run the `cmd` line from its `run.json` (base seed 2 reproduces `cplace/base_seed2_placement.json` byte for byte).
`$O/hand_proxies.json`: the same proxies on the hand board (reference row in every table).

## Proxies (proxies.json; side-aware: a 4th element "F"/"B" mirrors local x before the turn)

| key | what |
|---|---|
| `new_overlap_mm2`, `new_overlaps` | courtyard / far-side pad / keep-out / off-board items that the base placement does not have (overlaps.py logic, side-aware). Gate: > 0.05 |
| `sig_hp_mm`, `sig_tree_mm`, `crossings` | signal half-perimeter, sum of per-net shortest trees, tree-edge crossings (crossings.py logic); nets with < 12 pads |
| `hl_fail/hl_excess`, `pp_fail/pp_excess`, `near_fail/near_excess`, `keepapart_fail` | intent near statements over their limit (count, weight x mm over), split hot-loop / power-path / other |
| `power_IxL`, `power_tree_mm` | sum over power nets of current x pad tree length |
| `hl_mm`, `hl_max`, `hl_sum` | per hot loop: first cap's supply/return pads to the switch's supply/return pads, centre to centre (hand: max 3.37). Gate: `hl_max` > 4.0 |
| `d_U401_J401`, `d_U501_J501`, `d_U404_U401`, `d_U504_U501` | PD chip to connector, 5 V buck to PD chip (pad centroids). Gates: hand + 3 mm, hand + 6 mm |
| `sprawl`, `sprawl_worst`, `sprawl_flags` | per section bounding box / courtyard area, against the hand board |
| `crowd`, `crowd_sum` | parts within 2.5 mm of the big chips (metrics.py) |
| `pwr_pin_crowd` | power pads with another part's other-net pad within 0.5 mm (did not predict anything; kept for reference) |
| `plan_n_open`, `plan_open` | (after `plan`) power opens predicted from the copper planner: U/Q/J parts it leaves to the router on any net but PACK_P |

## Calibration on the base placer (HOOKS empty), 2026-11-14

16 placements (base seeds 1-10, NOISE=0.3 seeds 1-3, PASSES=6 seeds 1-3; NOISE=0.3 seed 2 gave the same file as
base seed 2), 8 screened (`/home/claude/work/C/sweep/base`, `calib.md`, `table.md`, `contact.png`).

- **Power opens: the planner prediction is exact.** `plan_open` matched the scorecard's non-GND power opens on 8 of 8
  screened boards and on the hand board; running the planner on a host-made cu_dump (`bare_xform.py`) gives a
  `plan.log` identical to the scorecard's (checked on base_s7, only the timing line differs). GND opens at U404/U504/Q502
  (return pads) are not predicted.
- **Blocked edges:** no single cheap proxy is reliable with 8 points. The weighted rank score had Spearman +0.83
  (p 0.01), `d_U404_U401` +0.71, `power_IxL` +0.67, signal tree length -0.07, crossings +0.38. With 16 proxies tested
  on 8 boards, one p of 0.01 can be luck; treat the rank as a weak filter and keep screening 4-6 boards.
- **Full scorecard on the best-screened base placement (base_s7, seed 7, HOOKS empty)**, `/home/claude/work/C/sweep/base/runs/base_s7/full`:
  route **366 of 457 routed, 91 failed** (finished, NOT timed out; 28.7 min wall for the whole scorecard), hot loops
  **6 of 7 pass, 7.26 nH** (USB Port 1/HL_OUT at Q402 fails: no closed loop through C438), blocked 81 of 457, 1.902 W,
  0 DRC, opens P1 PP5V@U401, P2 PP5V@U501, P2 SW2@Q502. Below the hand board (391 of 448) and fails the hard limits.
- **Loss** is not comparable between boards with different opens (an open net carries no current): base_s3 shows
  1.259 W with 6 extra opens.

## Traps

- One heavy job at a time. `screen`, `full` and `plan` share a lock file (`/home/claude/work/C/sweep/.score.lock`), so
  two sweeps queue instead of running two scorecards. Placer batches do not take the lock (they check the load only).
- Killing `sweep.py plan` with SIGTERM stops its planner; killing `sweep.py screen/full` does not stop the scorecard
  (its docker containers and host python steps keep running). Find them with `sweep.sh status` and check `readlink /proc/<pid>/cwd` before you kill anything:
  other workers run the same tools.
- `NOISE` only perturbs the pick order; two settings can give the same file (n30_s2 = base_s2). `rank` marks
  duplicates by md5 and `plan`/`--top` skip them.
- `power_open` always lists 3V3@L201 and GND@J301/J302; they are allowed. `hard_ok` in the table already ignores them.
- `blocked_edges` "X of Y": Y changes with the placement (456-473 here); compare X, but note the total.
- A route that hits the cap shows `TIMED OUT at 45 min; last ...` in the `route` column; it is not a final count.
- `metrics.py` and `tools/floorplan/overlaps.py` are not side-aware; the proxies here are. The scorecard needs
  `cscore.sh` (not `score_board.sh`) for placements with a 4th element; `sweep.py` always calls `cscore.sh`.
- After `plan` has run on some placements, `rank` puts placements without a plan result below the planned ones
  (before the fix a missing plan counted as 0 opens and floated unplanned boards to the top).
- The rank score is relative (each proxy divided by its median over the placements in that folder), so scores are
  comparable only inside one sweep folder.
