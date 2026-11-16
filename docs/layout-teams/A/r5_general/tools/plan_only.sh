#!/bin/bash
# plan_only.sh <bare.json> <out spec.json> <rules.json> [extra plan_rules options...]
#   package planner + split_zones + bus_layer, exactly the copper steps of copper_rules/score_rules.sh (spec.json in a
#   scorecard outdir is this post-split, post-bus spec). Log next to the spec (.log).
set -e
P=/home/claude/repo/docs/layout-teams/A/r5_general/copper_rules; R=/home/claude/repo
B=$(readlink -f "$1"); O=$(readlink -f "$2"); RU=$(readlink -f "$3"); shift 3
C=$R/$(python3 -c "import json;print(json.load(open('$RU'))['board']['constraints'])")
python3 $P/plan_rules.py $B $C $O --rules=$RU "$@" > ${O%.json}.log 2>&1
python3 $P/split_zones.py $O >> ${O%.json}.log 2>&1
python3 $P/bus_layer.py $O $B $C --rules=$RU --router=$R/tools/score/router.py >> ${O%.json}.log 2>&1
