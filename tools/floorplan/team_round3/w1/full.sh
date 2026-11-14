#!/bin/bash
# full.sh <tag> <fill placement json>: q7s2 skeleton + fill -> bare board -> trial.sh (power copper, DRC, DC). Tail of hp/skel.sh.
set -e; cd /home/claude/work/hp; T=$1; FILL=$2; SKP=${SKP:-q7s2_skp.json}
python3 - <<P
import json; a=json.load(open('$SKP')); b=json.load(open('q7s2.json')); f=json.load(open('$FILL'))
fill={r for v in json.load(open('q7s2_fz_clusters.json')).values() for r in v}
for r,v in f.items():
    if r in fill: b[r]=v
for r,v in a.items():
    if r.rstrip('0123456789') not in ('J','H','TP','SW'): b[r]=v
json.dump(b,open('${T}.json','w'))
P
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 python3 apply_placement.py m3_bare.kicad_pcb ${T}_bare.kicad_pcb ${T}.json --strip >/dev/null 2>&1
cp m3_bare.kicad_pro ${T}_bare.kicad_pro; cp m3_bare.kicad_dru ${T}_bare.kicad_dru
timeout 900 ./trial.sh $T $T > ${T}_trial.log 2>&1 || true
echo "RESULT $T: $(grep "open \['" ${T}_trial.log | awk '{print $1,$2,$3,$NF}' | tr '\n' ' ') | $(grep 'total loss' ${T}_trial.log) | DRC errors $(grep -c "', 'error')" ${T}_trial.log)"
