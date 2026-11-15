# merge: the team C whole-board placer, all pieces on, and its sweep

## The placer (`cplace/`)

`cplace/run_merged.sh <out.json>` = `cplace/run.sh` with
`HOOKS=cpd,cpower,cpdl,ccorr PD_BUCK1=97,74,105,88 PD_BOX1=106,75,118,90 PDW_B=20` (about 100-120 s, one core).
This is the round-2 config `r1` of the sweep (4 of 4 seeds with every power path joined on the screen).
Every piece stays a feature flag: leave a module out of `HOOKS` or set its knob.

| Order | Module | What it adds | Off switch |
|---|---|---|---|
| 1 | `cpd.py` (new, this merge) | cell-path chain F102 -> Q101 -> Q102 placed and locked first; PD chips U401/U501 placed and locked before the stages, with a pin-topology cost; port 1 5 V buck box moved west of its PD chip | drop `cpd`, or `CELL_FIRST=0`, `PD_FIRST=0`, `PD_BUCK1=` `PD_BOX1=` (empty) |
| 2 | `cpower.py` (package power) | the 7 power stages, hot-loop caps pad to pad, locked | drop `cpower` |
| 3 | `cpdl.py` (new, 4 lines) | moves the stage input sense resistor (R424/R524) next to the PD chip's PPHV pin | drop `cpdl`, or `PD_RIN=0` |
| (4) | `cside.py` (package sides) | parts to B.Cu; off by default, `MERGE_SIDES=1` adds it in POST mode with the via-site knobs | default off |
| 5 | `ccorr.py` (package corridor) | copper-corridor cost, PD escape bands, crossing cost | drop `ccorr` |

`run.sh` now exports `PYTHONHASHSEED=0` (tagged `# [merge]`): with a large part evicted, the eviction order followed
Python string hashing, so runs were not reproducible. With `HOOKS` empty, SEED=2 is still byte-identical to
`base_seed2_placement.json` (cmp, checked after every change). `cplace.py` itself has no change from this merge
(its only diffs are the `# [power]` fallback and the `# [corridor]` `after_big` hook).

### Why cpd (what the first sweep runs showed)

The copper planner (`tools/copper/plan_copper.py`, the scorecard's power-copper step) left PP5V/PPHV open at the PD
chips on every cpower run, and the hand board too. Three causes, each fixed by one part of cpd:

1. **Pin order.** Clockwise round the TPS25751 the power pins are PP5V (34), VBUS (32, 23), PPHV (20). One layer, nets
   drawn one after another: the destinations must lie round the chip in that order (buck -> connector -> charger).
   That order does not change with rotation. Logan's box for the port 1 5 V buck is EAST of U401, with the connector
   north and the charger south: the wrong side, so PP5V always crossed VBUS. `PD_BUCK1/PD_BOX1` swap the buck
   to the west and the chip east. The topology cost (crossings of the pin -> 1 mm out -> destination paths, of a path with
   the chip, and destinations behind a pin) picks the chip's turn and spot.
2. **The sense resistor.** cpower put R424/R524 (PPHV -> AC_SNS_N) at the stage, so PPHV had to run 15-20 mm through
   the stage's AC_SNS_N pour, which plan_copper draws first. Next to the PD pin (as on the hand board) PPHV is a few
   mm long and the long run is AC_SNS_N.
3. **Room.** With the stages placed first, the PD chips (and Q101) found no legal spot near their box on some seeds
   and went 30-40 mm away. cpd places the cell chain and the PD chips before cpower.

Planner predictions on seed 3 (no KiCad, `merge/plan_look.sh`): cpower+ccorr: PPHV open at both PD chips, PP5V at
U401; + topology cost only: PPHV both; + buck box moved: port 1 clear but U501 pushed 40 mm away; + PD chips first +
sense resistor moved + cell chain: no predicted power opens.

## The sweep driver (`merge/msweep.py`)

`msweep.py OUT GRID.json --seeds cfg=1-10,... [--screen N|all] [--lanes 2] [--jobs 2]`, built on `sweep/sweep.py`:
place (2 placers) -> legality gate (side-aware overlap proxy against the base: any new courtyard / keep-out /
off-board overlap over 0.05 mm2, or a byte-identical duplicate, is discarded before screening) -> host copper planner
on each legal placement (predicted non-GND power opens) -> scorecard screen `--route=0 --no-hot` through
`cplace/cscore.sh`, best predicted first, at most `lanes` at once (own lock file per lane) -> `OUT/table.md`,
`OUT/contact.png` and `OUT/msweep.md` (ranked: extra power opens, DRC errors, blocked edges, loss).
`msweep.py rank OUT` rebuilds the ranking. Grids: `grid_merged.json` (round 1), `grid_merged2.json` (round 2).

`plan_look.sh <placement.json> <dir>` runs the planner on one placement and draws the F.Cu power copper round the PD
chips (zoom.png): the quickest way to see why a power path opens.

## Results (all from score.json; screen = `--route=0 --no-hot`, full = hot loops + 45 min route cap)

40 placements (24 in `/home/claude/work/C/sweep/merged`, 16 in `.../merged2`), 0 failed the legality gate, 10 were
byte-identical duplicates, 30 screened. Full table: `sweep_table.md`. Hand: 56 of 452 blocked, 1.359 W,
P1 PP5V@U401 open; full route 391 of 448.

| Candidate | Config | Screen blocked | Loss | Extra power_open | DRC | Hot loops | Full route |
|---|---|---|---|---|---|---|---|
| r1_s4 (`candidates/r1_s4_placement.json`, = `SEED=4 run_merged.sh`, cmp checked) | r1 | 57 of 441 | 1.189 W | none | 0 | 7 of 7, 5.36 nH | 373 of 441 routed, 68 failed (finished) |
| m_s4 (`candidates/m_s4_placement.json`) | m (PDW_B=8) | 59 of 454 | 1.150 W | none | 0 | 7 of 7, 5.32 nH | TIMED OUT at 45 min; last 383 of 454 routed, 71 failing |
| r1_s1 (`candidates/r1_s1_placement.json`) | r1 | 59 of 440 | 1.196 W | none | 0 | 7 of 7, 5.37 nH | TIMED OUT at 45 min; last 364 of 439 routed, 64 failing |

Hard limits (power paths, DRC, hot loops) are met by all three; the routability target (391) is not: 373-383.
Seven of the 30 screened boards had no extra power opens (m_s4, mn_s4 = same as m_s4 within 1 loss mW, ms_s4,
m_s7, r1_s1..s4); before this merge no team C run had none.
Two-sided (cside POST, 9-18 parts on B) gave the same or 2-5 more blocked edges than the one-sided run of the same seed.
Remaining failures are at the PD chips (15-17 blocked edges each against 8-9 on the hand board): the power pours of
PP5V/PPHV/VBUS wrap the chips' signal sides. That is the next thing to fix (signal side room in the PD topology cost).
