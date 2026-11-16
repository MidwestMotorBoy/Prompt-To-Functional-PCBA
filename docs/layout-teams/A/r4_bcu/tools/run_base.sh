#!/bin/bash
A=/home/claude/repo/docs/layout-teams/A
source $A/tools/best_env.sh
$A/tools/score_board_best.sh $A/r4_bcu/runs/base $A/best_placement.json --route=0 --no-hot --plan="$BEST_PLAN"
