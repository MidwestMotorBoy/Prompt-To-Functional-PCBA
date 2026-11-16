#!/bin/bash
# poll.sh <name>...: wait for PC route results (route_result.sh) and save each to runs/route_<name>.json (gives up after 150 min)
A=/home/claude/repo/docs/layout-teams/A
for i in $(seq 1 75); do
  left=0
  for n in "$@"; do
    f=$A/r4_bcu/runs/route_$n.json
    [ -s $f ] && continue
    if $A/route_result.sh $n > $f.tmp 2>/dev/null; then mv $f.tmp $f; echo "$(date +%H:%M) $n arrived" >> $A/r4_bcu/runs/poll.log; else rm -f $f.tmp; left=1; fi
  done
  [ $left = 0 ] && break
  sleep 120
done
echo "$(date +%H:%M) poll done" >> $A/r4_bcu/runs/poll.log
