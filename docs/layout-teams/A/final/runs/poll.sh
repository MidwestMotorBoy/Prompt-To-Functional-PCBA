#!/bin/bash
# poll.sh name1 name2 ... : every 2 min, write PC route results to pc_poll.txt; exit when all are in
A=/home/claude/repo/docs/layout-teams/A; O=$A/final/runs/pc_poll.txt
while true; do
  left=0
  for n in "$@"; do
    grep -q "^$n " $O 2>/dev/null && continue
    r=$($A/route_result.sh $n 2>/dev/null) && echo "$n $(date -u +%H:%M) $(echo $r | tr -d '\n')" >> $O || left=1
  done
  [ $left = 0 ] && break; sleep 120
done
