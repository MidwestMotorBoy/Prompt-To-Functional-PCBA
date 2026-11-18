#!/bin/bash
# repair.sh <dir with in.kicad_pcb/.kicad_pro/.kicad_dru (a routed board) and cu.kicad_pcb (its planned board)> <windows> [MIN=30] [ripwin opts]
#   Regional rip-up and re-route with router_esc.py: rip.kicad_pcb -> drc_rip.json -> out.kicad_pcb -> drc_out.json
A=/home/claude/repo/docs/layout-teams/A; S=/home/claude/repo/tools/score
D=$(cd "$1" && pwd); W=$2; M=${3:-30}; shift 3; cd $D
cp $A/r6_merge/tools/ripwin.py $A/r6_merge/tools/router_esc.py .
for e in kicad_pro kicad_dru; do cp in.$e rip.$e; cp in.$e out.$e; done
docker run --rm -u 0 -v $D:/w -w /w -v $S/pylib:/w/pylib kicad/kicad:10.0 sh -c "python3 ripwin.py cu.kicad_pcb in.kicad_pcb rip.kicad_pcb '$W' $* 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o drc_rip.json rip.kicad_pcb >/dev/null 2>&1; PYTHONPATH=/w/pylib timeout ${M}m python3 -u router_esc.py rip.kicad_pcb drc_rip.json out.kicad_pcb --softnets=GND,PACK_P,3V3 $ROUTER_OPTS; kicad-cli pcb drc --severity-all --format json -o drc_out.json out.kicad_pcb >/dev/null 2>&1" > repair.log 2>&1
grep -v progress repair.log | tail -25
python3 - <<'P'
import json
d=json.load(open('drc_out.json'))
print('DRC errors',sum(1 for v in d['violations'] if v['severity']=='error'),'unconnected',len(d.get('unconnected_items',[])))
for v in d['violations']:
    if v['severity']=='error': print(' ERR',v['description'],[(i['description'],i['pos']['x'],i['pos']['y']) for i in v['items']])
for u in d.get('unconnected_items',[]):
    print(' UNC',[(i['description'],i['pos']['x'],i['pos']['y']) for i in u['items']])
P
