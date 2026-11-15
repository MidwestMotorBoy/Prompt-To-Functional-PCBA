#!/bin/bash
# screen.sh <name> "<extra plan options>" [scorecard options...]: r4_vbus screen on the team best placement with the
# best copper recipe + plan_copper_v.py; outdir r4_vbus/runs/<name>, log r4_vbus/runs/<name>.log (DONE at the end)
A=/home/claude/repo/docs/layout-teams/A; V=$A/r4_vbus
N=$1; X=$2; shift 2
source $A/tools/best_env.sh
export PLANNER=$V/tools/plan_copper_v.py
cd /home/claude/repo
$V/tools/score_board_r4v.sh $V/runs/$N $A/best_placement.json "$@" --plan="$BEST_PLAN $X" > $V/runs/$N.log 2>&1
echo DONE >> $V/runs/$N.log
