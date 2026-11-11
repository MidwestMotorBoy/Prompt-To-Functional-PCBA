#!/bin/bash
# step.sh <in> <out> <spec.json>: hand edit new/<in>.kicad_pcb -> new/<out>.kicad_pcb, then full-rule DRC, plane islands and copper dump
i=$1; o=$2; sp=$3
./kc python3 /w/handadd.py /w/new/$i.kicad_pcb /w/new/$o.kicad_pcb /w/$sp /w/new/keepu.txt 2>&1 | tail -n 3
cp base/Monolith.kicad_pro new/$o.kicad_pro
cp new/$o.kicad_pcb fin/Monolith.kicad_pcb
./drc.sh fin ${SHOW:-clearance shorting_items hole_clearance copper_edge_clearance tracks_crossing unconnected_items track_dangling via_dangling hole_to_hole annular_width}
python3 - <<PY
import json
d=json.load(open('fin/drc.json'))
for u in d.get('unconnected_items',[]): print('UNCONN',' ; '.join("%s @(%.2f,%.2f)"%(i['description'][:70],i['pos']['x'],i['pos']['y']) for i in u['items']))
PY
./kc python3 /w/isl.py /w/new/$o.kicad_pcb '^(GND|3V3|/PACK_P|/CELL_P)$' 2>&1 | grep -E "^==|island" | head -20
./kc python3 /w/dumpcu.py /w/new/$o.kicad_pcb /w/new/cu$o.json | tail -n 1
