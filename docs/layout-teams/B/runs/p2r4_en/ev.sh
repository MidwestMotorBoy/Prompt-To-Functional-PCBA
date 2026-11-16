#!/bin/bash
# ev.sh <name>: lay runs/p2r4_en/<name>.json on the kept board with handroute2.py, then dc_score (all nets) of it
cd /home/claude/repo/docs/layout-teams/B
N=$1; D=runs/p2r4_en
python3 tools/handroute2.py best_routed/monolith_routed.kicad_pcb $D/$N.kicad_pcb $D/$N.json --cu=runs/p2-m6/cu.json --keep=runs/p2-m6/cu.kicad_pcb > $D/$N.hr.log 2>&1
grep -E "FAULT|faults|wrote|WARNING" $D/$N.hr.log
[ -f $D/$N.kicad_pcb ] || exit 1
python3 /home/claude/repo/tools/copper/dc_score.py $D/$N.kicad_pcb runs/p2-m6/routed/cu.json /home/claude/repo/tools/floorplan/example/monolith/constraints.json $D/$N.dc.json > $D/$N.dc.log 2>&1
python3 - $D/$N.dc.json <<'P'
import json,sys
d=json.load(open(sys.argv[1])); tot=sum(v.get('loss_W',0) for v in d.values() if isinstance(v,dict))
pp=d['PACK_P']; print('loss %.4f W  PACK_P %.4f  3V3 %.4f  GND %.4f' % (tot, pp['loss_W'], d['3V3']['loss_W'], d['GND']['loss_W']), {t['ref']:t.get('R_mohm') for t in pp['terminals'] if t['ref'] in ('J113','R427','R527')}, 'open', {k:v.get('open') for k,v in d.items() if isinstance(v,dict) and v.get('open')})
P
