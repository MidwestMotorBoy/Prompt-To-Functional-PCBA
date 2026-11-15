#!/bin/bash
# queue.sh tag=placement.json ...: screens one after another (--route=0 --no-hot), waits for load < 3 before each
C=/home/claude/repo/docs/layout-teams/C/cplace
for a in "$@"; do t=${a%%=*}; p=${a#*=}
  while [ $(awk '{print int($1)}' /proc/loadavg) -ge 3 ]; do sleep 20; done
  echo "start $t $(date +%T)"; $C/cscore.sh /home/claude/work/C/sides/$t $p --route=0 --no-hot > /home/claude/work/C/sides/$t.log 2>&1; echo "end $t $(date +%T) $(grep SCORE /home/claude/work/C/sides/$t.log)"
done; echo ALLDONE
