#!/bin/bash
# q.sh <name> [planner opts...]: quick screen of portcu base (or $PL placement) -> portcu/runs/q_<name>, one-line summary into portcu/runs/log.txt
W=/home/claude/repo/docs/layout-teams/A/portcu; N=$1; shift; P=${PL:-$W/base_score.json}
$W/tools/quick.sh $W/runs/q_$N $P --plan="$*" > $W/runs/q_$N.log 2>&1
cd $W/runs/q_$N; B=$(head -1 blocked.txt | sed 's#.*: ##')
L="$(date -u +%H:%M) q_$N [$*] pl=$(basename $P) blocked=$B drc=$(python3 -c "import json;q=json.load(open('quick.json'));print(q['drc_errors'],'loss',q['loss_W'],'open',q['power_open'])")"
echo "$L" | tee -a $W/runs/log.txt
