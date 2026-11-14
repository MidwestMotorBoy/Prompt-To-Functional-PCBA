#!/bin/bash
# board.sh <x>: merge q7s2 skeleton placement with w3_<x>_fill.json into hp/w3_<x>.json, apply, trial copper (tail of hp/skel.sh)
set -e; cd /home/claude/work/hp; T=w3_$1
python3 - <<P
import json; a=json.load(open('q7s2_skp.json')); b=json.load(open('${T}_fill.json'))
for r,v in a.items():
    if r.rstrip('0123456789') not in ('J','H','TP','SW'): b[r]=v
json.dump(b,open('${T}.json','w'))
P
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 python3 apply_placement.py m3_bare.kicad_pcb ${T}_bare.kicad_pcb ${T}.json --strip >/dev/null 2>&1
cp m3_bare.kicad_pro ${T}_bare.kicad_pro; cp m3_bare.kicad_dru ${T}_bare.kicad_dru
timeout 900 ./trial.sh $T $T > ${T}_trial.log 2>&1 || true
echo "RESULT $T: $(grep "open \['" ${T}_trial.log | awk '{print $1,$2,$3,$NF}' | tr '\n' ' ') | $(grep 'total loss' ${T}_trial.log) | DRC errors $(grep -c "', 'error')" ${T}_trial.log)"
