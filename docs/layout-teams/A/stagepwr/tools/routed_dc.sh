#!/bin/bash
# routed_dc.sh <scorecard outdir with routed.kicad_pcb> : power_open and loss on the ROUTED board (zones as the router refilled them)
OUT=$(cd "$1" && pwd); T=/home/claude/repo/tools; C=$T/floorplan/example/monolith/constraints.json; cd $OUT
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "python3 cu_dump.py routed.kicad_pcb routed.json 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o drc_routed.json routed.kicad_pcb >/dev/null 2>&1"
python3 $T/copper/dc_score.py routed.kicad_pcb routed.json $C dc_routed.json > dc_routed.log 2>&1
python3 - <<'P'
import json
for f in ('dc.json', 'dc_routed.json'):
    d = json.load(open(f)); n = d.get('nets', d)
    print(f, 'loss_W', round(sum(v.get('loss_W', 0) for v in n.values() if isinstance(v, dict)), 3), 'power_open', {k: v.get('open') for k, v in n.items() if isinstance(v, dict) and v.get('open')})
d = json.load(open('drc_routed.json')); print('routed DRC errors', sum(1 for v in d['violations'] if v['severity'] == 'error'), 'unconnected', len(d.get('unconnected_items', [])))
P
