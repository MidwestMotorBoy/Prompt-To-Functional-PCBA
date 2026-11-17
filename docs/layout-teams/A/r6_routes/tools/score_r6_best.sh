#!/bin/bash
# score_r6_best.sh <outdir> [scorecard args, default --route=0]
#   Round-6 best board: stack S placement (A/best_placement.json, unchanged) + planner M copper + the r6 escape fixes
#   listed in r6_routes/fixes/CP5_LIST.txt (applied by specfix.py after split_spec), scored with score_board_r6.sh.
#   Local full route afterwards: A/r5_merge/tools/route_local_r5.sh <outdir> 150
set -e
A=/home/claude/repo/docs/layout-teams/A; F=$A/r6_routes/fixes; OUT=$1; shift
. $A/r5_merge/tools/best_env_r5.sh
SPECFIX=""; for f in $(cat $F/CP5_LIST.txt); do SPECFIX="$SPECFIX,$F/$f"; done; export SPECFIX=${SPECFIX#,}
$A/r6_routes/tools/score_board_r6.sh "$OUT" $A/best_placement.json ${@:---route=0} --plan="$BEST_PLAN_R5"
