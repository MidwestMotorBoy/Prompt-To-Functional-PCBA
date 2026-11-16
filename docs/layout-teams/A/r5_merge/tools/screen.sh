#!/bin/bash
# screen.sh <name> "<extra plan opts>" [scorecard opts, default --route=0 --no-hot]  -> r5_merge/runs/<name>
A=/home/claude/repo/docs/layout-teams/A; source $A/r5_merge/tools/best_env_r5.sh
n=$1; x=$2; shift 2; [ $# = 0 ] && set -- --route=0 --no-hot
PL=${PL:-$R5_PLACEMENT}
cd /home/claude/repo && $A/r5_merge/tools/score_board_r5.sh $A/r5_merge/runs/$n $PL "$@" --plan="$BEST_PLAN $x" > $A/r5_merge/runs/$n.log 2>&1
tail -1 $A/r5_merge/runs/$n.log
