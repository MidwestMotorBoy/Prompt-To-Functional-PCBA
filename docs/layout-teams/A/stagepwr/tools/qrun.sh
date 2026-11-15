#!/bin/bash
# qrun.sh <name> <placement_score.json> [planner-opts]: quick screen (split copper, ghost) -> runs/q_<name>; planner copy if opts given
W=/home/claude/repo/docs/layout-teams/A/stagepwr; N=$1; P=$2; shift 2
if [ -n "$1" ]; then export PLANNER=$W/tools/plan_copper_a.py; $W/tools/quick.sh $W/runs/q_$N $P --plan="$*" --ghost > $W/runs/q_$N.log 2>&1
else $W/tools/quick.sh $W/runs/q_$N $P --ghost > $W/runs/q_$N.log 2>&1; fi
echo "== $N $(grep -o '"blocked": "[^"]*"' $W/runs/q_$N/quick.json) drc=$(grep -o '"drc_errors": [0-9]*' $W/runs/q_$N/quick.json) open=$(python3 -c "import json;print(json.load(open('$W/runs/q_$N/quick.json'))['power_open'])")"
grep GHOSTFAIL $W/runs/q_$N/ghost.log | grep -E "Q[45]0|R4[1-5][0-9]|R5[1-5][0-9]|C4[1-3][0-9]|C5[1-3][0-9]|D4|D5|U403|U503|U406|U506|SW|TH" | sed 's/GHOSTFAIL/  /' | cut -c1-150
