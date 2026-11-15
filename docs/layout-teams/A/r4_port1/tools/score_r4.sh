#!/bin/bash
# score_r4.sh <outdir> <placement.json> [scorecard args e.g. --route=0 --no-hot] [-- extra planner options]
#   Team A best copper recipe (tools/best_env.sh: planner P G5 stack, In4 PACK_P bus, B.Cu soft GND fill) through
#   tools/score_board_best.sh (split zones). PLANNER defaults to r4_port1/tools/plan_copper_q.py (= planner P when no
#   q option is given); extra planner options after "--" are appended to $BEST_PLAN.
A=/home/claude/repo/docs/layout-teams/A; . $A/tools/best_env.sh
export PLANNER=${PLANNER_Q:-$A/r4_port1/tools/plan_copper_q.py}
OUT=$1; PL=$2; shift 2; SC=(); EX=""
while [ $# -gt 0 ]; do if [ "$1" = "--" ]; then shift; EX="$*"; break; fi; SC+=("$1"); shift; done
echo "[score_r4] planner $PLANNER  plan: $BEST_PLAN $EX"
$A/tools/score_board_best.sh "$OUT" "$PL" "${SC[@]}" --plan="$BEST_PLAN $EX"
