#!/bin/bash
# widen.sh <in board under new/> <out board under new/>: widen GateDrive / Power class tracks as far as the full rule set
# allows (DRC in fin/ under the project name, so the custom rules apply). A flagged track drops one width step per round;
# from round 7 on it goes straight back to its routed width.
i=$1; o=$2
cp new/$i fin/Monolith.kicad_pcb
[ -f fin/plan.json ] && mv fin/plan.json fin/plan_prev.json
./kc python3 /w/widen.py /w/fin/Monolith.kicad_pcb /w/fin/Monolith.kicad_pcb /w/fin/plan.json 2>&1 | grep planned
for r in 1 2 3 4 5 6 7 8 9 10 11 12; do
  last=""; [ $r -gt 6 ] && last="WIDEN_LAST=1"
  ./drc.sh fin > fin/sum_w.txt
  ./kc sh -c "$last python3 /w/widen.py /w/fin/Monolith.kicad_pcb /w/fin/Monolith.kicad_pcb /w/fin/plan.json /w/fin/drc.json" 2>&1 | grep planned | tee fin/w.txt
  grep -q "lowered this round 0," fin/w.txt && break
done
./drc.sh fin
cp fin/Monolith.kicad_pcb new/$o
