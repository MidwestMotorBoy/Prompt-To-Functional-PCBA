#!/bin/bash
# route_trial.sh <tag> [minutes=45]: trial-route /home/claude/work/hp/<tag>_cu.kicad_pcb with the groundup router.
# Writes /home/claude/work/team/r_<tag>/route.log and prints "ROUTE <tag>: routed N failed M (of E edges)".
# Reference: hand placement m3 with generated copper routes 391 of 448 in 18 min; skeleton board q7s2 routes 299 of 442.
T=$1; MIN=${2:-45}; H=/home/claude/work/hp; D=/home/claude/work/team/r_$T; mkdir -p $D
for e in kicad_pcb kicad_pro kicad_dru; do cp $H/${T}_cu.$e $D/b.$e; done
cp /home/claude/work/team/router.py $D/
docker run --rm -u 0 -v $D:/w -v /home/claude/work/team/pylib:/w/pylib -w /w kicad/kicad:10.0 sh -c "kicad-cli pcb drc --severity-all --format json -o /w/drc.json /w/b.kicad_pcb >/dev/null 2>&1; PYTHONPATH=/w/pylib timeout ${MIN}m python3 -u /w/router.py /w/b.kicad_pcb /w/drc.json /w/routed.kicad_pcb --softnets=GND,PACK_P,3V3" > $D/route.log 2>&1
E=$(grep -o "edges to route: [0-9]*" $D/route.log | awk '{print $4}')
F=$(grep "^routed" $D/route.log)
if [ -n "$F" ]; then echo "ROUTE $T: $F (of $E edges)"; else echo "ROUTE $T: TIMED OUT at ${MIN} min, last: $(grep progress $D/route.log | tail -1) (of $E edges)"; fi
