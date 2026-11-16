#!/bin/bash
# screen.sh <name> <placement.json> "<extra planner opts>" [hot]
#   r5_north screen: team A best copper recipe (tools/best_env.sh: BUS4, BUS4B) with PLANNER = r5_north plan_copper_n.py
#   (= r4_bcu planner B + n options), r4_bcu k1 options (r4_bcu/tools/best_plan_opts.txt, first option line) + extra,
#   split scorecard tools/score_board_best.sh --route=0 (--no-hot unless 4th arg = hot) into runs/<name>,
#   GHOSTFAIL diff against r4_bcu/runs/k1. One line appended to runs/log.txt.
A=/home/claude/repo/docs/layout-teams/A; H=$A/r5_north
N=$1; PL=$(readlink -f "$2"); X="$3"; HOT=--no-hot; [ "$4" = hot ] && HOT=""
source $A/tools/best_env.sh
export PLANNER=$H/tools/plan_copper_n.py
K1=$(grep -v '^#' $A/r4_bcu/tools/best_plan_opts.txt | head -1)
O=$H/runs/$N
$A/tools/score_board_best.sh $O $PL --route=0 $HOT --plan="$K1 $X" > $H/runs/$N.log 2>&1
diff <(grep -o 'GHOSTFAIL.*' $A/r4_bcu/runs/k1/ghost.log | sed 's/ len.*//' | sort) <(grep -o 'GHOSTFAIL.*' $O/ghost.log | sed 's/ len.*//' | sort) > $O/ghost_diff.txt
S=$(cat $O/score.json | tr -d '\n ' )
echo "$(date +%H:%M) $N [$X] $HOT $S ghostdiff=$(grep -c '^[<>]' $O/ghost_diff.txt)" >> $H/runs/log.txt
tail -1 $H/runs/log.txt
