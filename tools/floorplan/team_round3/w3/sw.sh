#!/bin/bash
# sw.sh NAME "ENV..." : seeds 1-3, one line each
cd /home/claude/work/team/w3; n=$1; e=$2
for s in ${SEEDS:-1 2 3}; do env $e SEED=$s ./q.sh "${n}_s$s:$e" >/dev/null 2>&1
python3 - ${n}_s$s.log <<'P'
import json,sys,re
L=open(sys.argv[1]).read().splitlines(); r=[json.loads(l) for l in L if l.startswith('{"step": "refined"')][0]
nr=[l for l in L if l.startswith('NEAR')][0]; rp=[l for l in L if l.startswith('REPAIRED')]
d=eval(nr[5:]); print(f"{sys.argv[1][:-4]:14} hp {r['signal_half_perimeter_mm']} ov {r['overlap_mm2']} ie {r['intent_excess_mm']} x {r['crossings']} near {sum(d.values())} {list(d.values())} rep {rp[0].split()[1] if rp else 0}")
P
done
