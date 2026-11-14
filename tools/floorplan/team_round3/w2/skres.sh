#!/bin/bash
# skres.sh <sk> <seed>: skeleton with W2_RESERVE controllers (inflated by W2_RES_MM), copper planned round their rooms.
# writes /home/claude/work/hp/w2_<sk>_skp.json and _sk_spec.json for fz.sh (SK=w2_<sk>)
set -e; cd /home/claude/work/hp; F=/home/claude/prompt-to-functional-pcba/tools/floorplan; E=$F/example/monolith; T=w2_$1; SD=${2:-2}; FP=/home/claude/work/bfp7/floorplan_2.json
W=/home/claude/work/team/w2/skeleton.py
R=$(python3 $F/skeleton.py refs $E/constraints.json $E/board_dump.json)
python3 $W cut $E/board_dump.json $E/clusters.json /home/claude/work/anch/intent_pc.json $R ${T}_sk
(cd $F && REG_MARGIN=${SK_MARGIN:-1.0} CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=$FP python3 place_pack.py /home/claude/work/hp/${T}_sk_clusters.json /home/claude/work/hp/${T}_sk_dump.json /home/claude/work/hp/${T}_skp.json 0 $SD 100000 /home/claude/work/hp/${T}_sk_intent.json | tail -1 | cut -c1-150)
python3 - <<P
import json,os; P=json.load(open('${T}_skp.json'))
if os.path.exists('${T}_sk_resfix.json'): P.update(json.load(open('${T}_sk_resfix.json'))); json.dump(P,open('${T}_skp.json','w')); print({r:P[r] for r in ['U404','U403','U503','U101','U102','U301'] if r in P})
P
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 sh -c "python3 apply_placement.py m3_bare.kicad_pcb ${T}_skb.kicad_pcb ${T}_skp.json --strip >/dev/null 2>&1; python3 cu_dump.py ${T}_skb.kicad_pcb ${T}_skb_full.json >/dev/null 2>&1"
W2_SKP=${T}_skp.json python3 $W strip ${T}_skb_full.json $R ${T}_skb.json
python3 $F/../copper/plan_copper.py ${T}_skb.json $E/constraints.json ${T}_sk_spec.json --grow=0 --mirror=0 | grep "left to router \['" | cut -c1-200 || true
