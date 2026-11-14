#!/bin/bash
# skel.sh <tag> <floorplan json> <seed>: skeleton placement, skeleton copper, freeze, fill, full copper
set -e; cd /home/claude/work/hp; F=/home/claude/prompt-to-functional-pcba/tools/floorplan; E=$F/example/monolith; T=$1; FP=$2; SD=${3:-1}
R=$(python3 $F/skeleton.py refs $E/constraints.json $E/board_dump.json); echo "skeleton: $R"
python3 $F/skeleton.py cut $E/board_dump.json $E/clusters.json /home/claude/work/anch/intent_pc.json $R ${T}_sk
(cd $F && CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=$FP python3 place_pack.py /home/claude/work/hp/${T}_sk_clusters.json /home/claude/work/hp/${T}_sk_dump.json /home/claude/work/hp/${T}_skp.json 0 $SD 100000 /home/claude/work/hp/${T}_sk_intent.json | tail -1 | cut -c1-150)
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 sh -c "python3 apply_placement.py m3_bare.kicad_pcb ${T}_skb.kicad_pcb ${T}_skp.json --strip >/dev/null 2>&1; python3 cu_dump.py ${T}_skb.kicad_pcb ${T}_skb_full.json >/dev/null 2>&1"
python3 $F/skeleton.py strip ${T}_skb_full.json $R ${T}_skb.json
python3 $F/../copper/plan_copper.py ${T}_skb.json $E/constraints.json ${T}_sk_spec.json --grow=0 --mirror=0 | grep "left to router \['" | cut -c1-160 || true
python3 $F/skeleton.py freeze $E/board_dump.json $E/clusters.json ${T}_skp.json ${T}_sk_spec.json ${T}_fz ${ROOM:-0.3}
(cd $F && REG_MARGIN=${FILL_MARGIN:-1.0} CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=$FP python3 place_pack.py /home/claude/work/hp/${T}_fz_clusters.json /home/claude/work/hp/${T}_fz_dump.json /home/claude/work/hp/${T}_fill.json 0 $SD 150000 /home/claude/work/anch/intent_pc.json | tail -1 | cut -c1-150)
python3 - <<P
import json; a=json.load(open('${T}_skp.json')); b=json.load(open('${T}_fill.json'))
for r,v in a.items():
    if r.rstrip('0123456789') not in ('J','H','TP','SW'): b[r]=v
json.dump(b,open('${T}.json','w'))
P
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 python3 apply_placement.py m3_bare.kicad_pcb ${T}_bare.kicad_pcb ${T}.json --strip >/dev/null 2>&1
cp m3_bare.kicad_pro ${T}_bare.kicad_pro; cp m3_bare.kicad_dru ${T}_bare.kicad_dru
timeout 900 ./trial.sh $T $T > ${T}_trial.log 2>&1 || true
echo "RESULT $T: $(grep "open \['" ${T}_trial.log | awk '{print $1,$2,$3,$NF}' | tr '\n' ' ') | $(grep 'total loss' ${T}_trial.log) | DRC errors $(grep -c "', 'error')" ${T}_trial.log)"
