#!/bin/bash
# screen.sh <name> <placement.json> "<extra planner opts>" [hot]
#   team A best copper recipe (tools/best_env.sh: BUS4, BUS4B, BEST_PLAN) with PLANNER = r4_bcu plan_copper_b.py,
#   split scorecard tools/score_board_best.sh --route=0 (--no-hot unless 4th arg = hot) into runs/<name>,
#   then bcu_area.py and the GHOSTFAIL diff against runs/base. One line appended to runs/log.txt.
A=/home/claude/repo/docs/layout-teams/A; B=$A/r4_bcu
N=$1; PL=$(readlink -f "$2"); X="$3"; HOT=--no-hot; [ "$4" = hot ] && HOT=""
source $A/tools/best_env.sh
export PLANNER=$B/tools/plan_copper_b.py
O=$B/runs/$N
$A/tools/score_board_best.sh $O $PL --route=0 $HOT --plan="$BEST_PLAN $X" > $B/runs/$N.log 2>&1
python3 $B/tools/bcu_area.py $O > $O/bcu_area.txt
diff <(grep -o 'GHOSTFAIL.*' $B/runs/base/ghost.log | sed 's/ len.*//' | sort) <(grep -o 'GHOSTFAIL.*' $O/ghost.log | sed 's/ len.*//' | sort) > $O/ghost_diff.txt
S=$(cat $O/score.json | tr -d '\n ' ); BA=$(grep BCU_JSON $O/bcu_area.txt | sed 's/BCU_JSON //' | python3 -c "import json,sys;d=json.load(sys.stdin);print('swB',d['swnode_bcu'],'swF',d['swnode'].get('F.Cu'),'bcu',d['bcu_nongnd'])")
echo "$(date +%H:%M) $N [$X] $HOT $S $BA ghostdiff=$(grep -c '^[<>]' $O/ghost_diff.txt)" >> $B/runs/log.txt
tail -1 $B/runs/log.txt
