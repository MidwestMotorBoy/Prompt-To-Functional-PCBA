#!/bin/bash
# rest.sh <x>: apply w2_<x>.json, plan full copper (trial.sh), print RESULT
cd /home/claude/work/hp; T=w2_$1
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 python3 apply_placement.py m3_bare.kicad_pcb ${T}_bare.kicad_pcb ${T}.json --strip >/dev/null 2>&1
cp m3_bare.kicad_pro ${T}_bare.kicad_pro; cp m3_bare.kicad_dru ${T}_bare.kicad_dru
timeout 900 ./trial.sh $T $T > ${T}_trial.log 2>&1 || true
echo "RESULT $T: $(grep "open \['" ${T}_trial.log | awk '{print $1,$2,$3,$NF}' | tr '\n' ' ') | $(grep 'total loss' ${T}_trial.log) | DRC errors $(grep -c "', 'error')" ${T}_trial.log)"
