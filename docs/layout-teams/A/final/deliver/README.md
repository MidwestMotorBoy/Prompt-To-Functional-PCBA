# Team A deliverable candidate (round 3, worker `final`)

Board **FB-d** = placement FB (merged3 + ports b1 + stagepwr v1) with copper from planner F
(`--sealed=1 --taps=1 --joinfix=1`) plus PACK_P In2 straps. Numbers: see `score.json` and `../NOTES.md`.

Files:
- `best_placement.json` - scorecard format (245 refs that differ from the template)
- `best_placement_gu.json` - groundup format, all 289 refs
- `score.json`, `F.png`, `B.png` - from the local full-route scorecard run (`final/runs/full_d`)

## Reproduce (from the repo root, /home/claude/repo)

1. Placement, one command from the bare template (~110 s):
   ```
   docs/layout-teams/A/final/build.sh <workdir>
   ```
   Writes `<workdir>/placement_gu.json` and `<workdir>/placement.json`; checks placelib (CHECK clean, 289/289) and
   diffs against stagepwr/best_gu.json (exactly 6 ports-b1 refs differ). Overrides applied in name order from
   `final/overrides/`: 10_stagefix_s3, 20_pdfix_a3 (= merged3), 30_ports_b1, 40_stagepwr_v1.
2. Scorecard (split-zone copper, planner F, straps, hot loops on, local full route):
   ```
   PLANNER=docs/layout-teams/A/final/tools/plan_copper_f.py STRAPS="--net=PACK_P --layer=In2.Cu" \
     docs/layout-teams/A/final/tools/score_board_f.sh <outdir> <workdir>/placement.json --route=150 \
     --plan="--sealed=1 --taps=1 --joinfix=1"
   ```
   Quick screen instead: `--route=0 --no-hot` (~5 min); hot loops on: `--route=0` (~12 min).
   score_board_f.sh also writes routed-board `routed_power_open`, `routed_loss_W`, `routed_drc_errors` into
   score.json when the route saves `routed.kicad_pcb`.
   Both steps as one command (the scorecard outdir is `<workdir>/score`):
   ```
   PLANNER=$PWD/docs/layout-teams/A/final/tools/plan_copper_f.py STRAPS="--net=PACK_P --layer=In2.Cu" \
     docs/layout-teams/A/final/build.sh <workdir> --score="--route=150" --plan="--sealed=1 --taps=1 --joinfix=1"
   ```
3. Full route on Logan's PC: `docs/layout-teams/A/queue_route.sh <outdir> <unique-name>`, poll with
   `docs/layout-teams/A/route_result.sh <unique-name>`.

## Numbers (split copper)
Pre-route: power_open 3V3@L201 + GND@J301/J302 (allowed), DRC 0, hot loops 7/7 tier 1 6.21 nH, blocked 20 of 401,
loss 1.035 W. Local full route (this score.json, --route=150, finished): 364 of 401 routed, 37 failed. PC full route
(final-d-FBA3JS): 363 / 38 / 401 in 88 min. Routed board: power_open 3V3@L201 only, DRC 0, loss 1.504 W.
`routed_F.png` / `routed_B.png` are the routed board.
