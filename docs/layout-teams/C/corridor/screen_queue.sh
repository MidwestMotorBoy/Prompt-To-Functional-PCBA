#!/bin/bash
# screen_queue.sh <tag>=<placement.json> ...: screen each placement in turn (cscore.sh --route=0 --no-hot) into
#   /home/claude/work/C/corridor/<tag>/, one at a time, waiting until the 1-min load is under 3 before each.
#   Prints "<tag> DONE" lines; run in the background with a log.
C=/home/claude/repo/docs/layout-teams/C/cplace; W=/home/claude/work/C/corridor
for a in "$@"; do
  tag=${a%%=*}; pl=${a#*=}
  until awk '{exit !($1 < 3.0)}' /proc/loadavg; do sleep 20; done
  echo "$tag start $(date +%T) load $(cut -d' ' -f1 /proc/loadavg)"
  $C/cscore.sh $W/$tag $pl --route=0 --no-hot > $W/$tag.log 2>&1
  echo "$tag DONE $(date +%T) $(python3 -c "import json;s=json.load(open('$W/$tag/score.json'));print(s.get('blocked_edges'), s.get('loss_W'), s.get('drc_errors'), json.dumps(s.get('power_open')))" 2>&1)"
done
echo ALLDONE
