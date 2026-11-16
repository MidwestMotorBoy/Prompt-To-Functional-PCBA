#!/bin/bash
# plan_only.sh <bare.json> <out_spec.json> "<plan options>"  : planner M + split_spec + BUS4 + BUS4B, exactly as the scorecard
# (spec.json in a scorecard outdir is the post-split/bus4 spec)
set -e
A=/home/claude/repo/docs/layout-teams/A; C=/home/claude/repo/tools/floorplan/example/monolith/constraints.json
source $A/tools/best_env.sh
P=${PLANNER_M:-$A/r5_merge/tools/plan_copper_m.py}
python3 $P "$1" $C "$2" $3 > "${2%.json}.log" 2>&1
python3 $A/tools/split_spec.py "$2" >> "${2%.json}.log" 2>&1
python3 $A/strapfix/tools/bus4.py "$2" "$1" $BUS4 >> "${2%.json}.log" 2>&1
python3 $A/strapfix/tools/bus4.py "$2" "$1" $BUS4B >> "${2%.json}.log" 2>&1
