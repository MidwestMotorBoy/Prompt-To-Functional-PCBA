#!/bin/bash
# subs.sh <outdir> <tag> [p1|p2|both] [MIN]: r4_port1 route_sub.sh on the charger north-row/stage box of port 1 and/or
#   port 2 (port 2 box = port 1 box shifted -23.026 mm), one after the other; one line per run in runs/sub_log.txt
#   with the failed-edge list (port-relevant nets abbreviated).
A=/home/claude/repo/docs/layout-teams/A; H=$A/r5_north
O=$(readlink -f "$1"); T=$2; W=${3:-both}; M=${4:-40}
B1=103.5,96.5,118.5,109.3; B2=80.474,96.5,95.474,109.3
for p in p1 p2; do
  [ "$W" != both ] && [ "$W" != $p ] && continue
  B=$B1; [ $p = p2 ] && B=$B2
  r=$($A/r4_port1/tools/route_sub.sh $O $H/runs/sub_${T}_$p $B $M | tail -1)
  f=$(sed -E 's/^\/USB Port ([12])\//P\1 /; s/ \(Pad ([0-9]+) +of ([A-Z0-9]+) \)/ \2.\1/g; s/ [0-9.]+,[0-9.]+//g; s/ starts.*\| / | /' $H/runs/sub_${T}_$p/sub_fail.txt | tr '\n' ';')
  echo "$(date +%H:%M) $T $p $r FAILS: $f" | sed 's/(\/home[^)]*)//' >> $H/runs/sub_log.txt
  tail -1 $H/runs/sub_log.txt
done
