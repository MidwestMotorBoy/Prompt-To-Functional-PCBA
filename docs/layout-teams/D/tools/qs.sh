#!/bin/bash
# qs.sh <run-name> [placement.json] [score_board options]   quick score of the assembled team D placement.
#   With no placement file it assembles rooms/master.json overlaid with every rooms/<room>.json (tools/assemble.py).
#   Default options: --route=0 (no full route). Add --no-hot to skip hot loops (saves 2 min).
#   Output in /home/claude/runs/<run-name>/ : score.json, F.png, B.png, blocked.txt (blocked edges grouped by part)
D=$(cd "$(dirname "$0")/.." && pwd); R=$(cd $D/../../.. && pwd); N=$1; shift
O=/home/claude/runs/$N; mkdir -p $O
if [[ "$1" == *.json ]]; then PL=$(readlink -f $1); shift; else python3 $D/tools/assemble.py $O/placement_in.json || exit 1; PL=$O/placement_in.json; fi
OPTS="$@"; [[ "$OPTS" == *--route=* ]] || OPTS="--route=0 $OPTS"
# at most 2 scorecard runs at a time on this 4-core machine: wait for one of two slots
while true; do
  for i in 1 2; do exec 9>/tmp/qs_slot$i.lock; if flock -n 9; then break 2; fi; done
  sleep 10
done
bash $R/tools/score/score_board.sh $O $PL $OPTS > $O/score.log 2>&1
flock -u 9
python3 $D/tools/blocked.py $O > $O/blocked.txt 2>&1
tail -1 $O/score.log; head -30 $O/blocked.txt
