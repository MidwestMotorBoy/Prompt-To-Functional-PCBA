#!/bin/bash
# poll.sh <name>...: poll route_result.sh every 3 min until all results are in; writes runs/route_<name>.json
A=/home/claude/repo/docs/layout-teams/A
while true; do left=0
  for n in "$@"; do f=$A/portcu/runs/route_$n.json; [ -s $f ] && continue
    $A/route_result.sh $n > $f.tmp 2>&1 && mv $f.tmp $f || { rm -f $f.tmp; left=1; }; done
  [ $left = 0 ] && break; sleep 180; done
