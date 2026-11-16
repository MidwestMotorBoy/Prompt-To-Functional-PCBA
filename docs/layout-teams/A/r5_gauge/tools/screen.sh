#!/bin/bash
# screen.sh <rundir> <placement.json> [SUB=1] [extra planner options...]
#   r5_gauge screen: scorecard (r4_port1/tools/score_r4.sh = split copper, team best recipe + r4 v5p options
#   + planner r5_gauge/tools/plan_copper_g.py + extra options, --route=0 --no-hot) into <rundir>/sc, then (if SUB=1)
#   the gauge/MCU/lower-board sub-route (tools/route_sub.sh, box 88,113,101.5,127;104,115,121.6,134 (gauge + J302/MCU/R115), 60 min) into <rundir>/sub.
#   One at a time (lock).
H=$(cd "$(dirname "$0")/.." && pwd); A=$(cd $H/.. && pwd); D=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); SUB=$3; shift 3
exec 8>/tmp/r5_gauge_screen.lock; flock 8
BOX="88,113,101.5,127;104,115,121.6,134"
export PLANNER_Q=$H/tools/plan_copper_g.py
$A/r4_port1/tools/score_r4.sh $D/sc $PL --route=0 --no-hot -- $(cat $A/r4_port1/tools/best_plan_opts.txt) "$@" > $D/sc.out 2>&1
grep SCORE $D/sc.out > $D/score_line.txt
[ "$SUB" = 1 ] && KEEP=1 $H/tools/route_sub.sh $D/sc $D/sub "$BOX" 60 > $D/sub.out 2>&1
rm -f $D/sc/*.png.tmp
date > $D/DONE
