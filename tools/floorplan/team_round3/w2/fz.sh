#!/bin/bash
# fz.sh <x> <room> : freeze variant (env W2_*) on q7s2 skeleton + fill seed 2; prints area, hpwl, near counts
set -e; cd /home/claude/work/hp; F=/home/claude/prompt-to-functional-pcba/tools/floorplan; E=$F/example/monolith; T=w2_$1; SK=${SK:-q7s2}
python3 /home/claude/work/team/w2/skeleton.py freeze $E/board_dump.json $E/clusters.json ${SK}_skp.json ${SK}_sk_spec.json ${T}_fz $2 | tail -1
(cd $F && REG_MARGIN=3 CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=/home/claude/work/bfp7/floorplan_2.json python3 place_pack.py /home/claude/work/hp/${T}_fz_clusters.json /home/claude/work/hp/${T}_fz_dump.json /home/claude/work/hp/${T}_fill.json 0 ${SEED:-2} 150000 /home/claude/work/anch/intent_pc.json > /home/claude/work/hp/${T}_fill.log 2>&1)
python3 - <<P
import json; a=json.load(open('${SK}_skp.json')); b=json.load(open('${T}_fill.json'))
for r,v in a.items():
    if r.rstrip('0123456789') not in ('J','H','TP','SW'): b[r]=v
json.dump(b,open('${T}.json','w'))
P
echo "$T hpwl $(grep -o 'signal_half_perimeter_mm[^,]*' ${T}_fill.log | tail -1)  near $(python3 /home/claude/work/team/w2/near.py ${T}.json)"
