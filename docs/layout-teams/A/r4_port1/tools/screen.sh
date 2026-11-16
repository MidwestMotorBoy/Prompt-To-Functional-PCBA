#!/bin/bash
# screen.sh <rundir> <placement.json> [extra planner options...]
#   r4_port1 standard screen of one variant: scorecard (split copper, best recipe + planner q options, --route=0 --no-hot)
#   into <rundir>/sc, then the port-1 sub-route (tools/route_sub.sh, 40 min cap) into <rundir>/sub. Waits for any other
#   r4_port1 screen to finish first (lock), so only one CPU-heavy job runs at a time. Writes <rundir>/DONE at the end.
H=$(cd "$(dirname "$0")/.." && pwd); D=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); shift 2
exec 8>/tmp/r4_port1_screen.lock; flock 8
cd $H
tools/score_r4.sh $D/sc $PL --route=0 --no-hot -- "$@" > $D/sc.out 2>&1
grep SCORE $D/sc.out > $D/score_line.txt
KEEP=1 tools/route_sub.sh $D/sc $D/sub 99,66,121.6,116 40 > $D/sub.out 2>&1
rm -f $D/sc/*.png.tmp
date > $D/DONE
