#!/bin/bash
# fastcu.sh <base scorecard outdir (no straps)> <new outdir> "<bus4 opts or ->" ["<straps opts>"] [routed base outdir]
#   Team A strapfix quick copper check (~1-2 min, NOT the scorecard): reuses the base's bare board and split spec,
#   adds In2 straps and/or bus4 zones, writes copper, DRC, DC loss, renders In2/In4. With a routed base outdir
#   (holding routed.kicad_pcb); env BUSB = a second bus4.py option set
#   (holding routed.kicad_pcb), also injects the bus4 zones into that ROUTED board and reports routed DRC + DC.
B=$(cd "$1" && pwd); OUT=$(mkdir -p "$2" && cd "$2" && pwd); BUS="$3"; ST="$4"; RB=""; [ -n "$5" ] && RB=$(cd "$5" && pwd)
T=/home/claude/repo/tools; C=$T/floorplan/example/monolith/constraints.json; F=/home/claude/repo/docs/layout-teams/A/strapfix/tools
cd $OUT; for f in bare.kicad_pcb bare.kicad_pro bare.kicad_dru bare.json spec.json cu_dump.py write_copper.py; do cp $B/$f .; done
cp $B/cu.kicad_pro cu.kicad_pro; cp $B/cu.kicad_dru cu.kicad_dru; : > plan.log
[ -n "$ST" ] && python3 /home/claude/repo/docs/layout-teams/A/stagepwr/tools/straps.py spec.json bare.json $ST >> plan.log 2>&1
[ "$BUS" != "-" ] && [ -n "$BUS" ] && python3 $F/bus4.py spec.json bare.json $BUS >> plan.log 2>&1
[ -n "$BUSB" ] && python3 $F/bus4.py spec.json bare.json $BUSB >> plan.log 2>&1
K="docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0"
$K sh -c "python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1; kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json > dc.log 2>&1
for L in In2.Cu In4.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done
if [ -n "$RB" ]; then cp $RB/routed.kicad_pcb routed_base.kicad_pcb; cp $F/inject_zones.py .; cp cu.kicad_pro routed.kicad_pro
  $K sh -c "python3 inject_zones.py routed_base.kicad_pcb spec.json all routed.kicad_pcb; python3 cu_dump.py routed.kicad_pcb routed.json 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o drc_routed.json routed.kicad_pcb >/dev/null 2>&1"
  python3 $T/copper/dc_score.py routed.kicad_pcb routed.json $C dc_routed.json > dc_routed.log 2>&1; fi
grep -h "straps\|bus4" plan.log
python3 - <<'P'
import json, os
for f, dr in (('dc.json', 'drc.json'), ('dc_routed.json', 'drc_routed.json')):
    if not os.path.exists(f): continue
    n = json.load(open(f)); d = json.load(open(dr))
    print(f, 'loss_W', round(sum(v.get('loss_W', 0) for v in n.values() if isinstance(v, dict)), 3), 'PACK_P', round(n['PACK_P']['loss_W'], 3), 'GND', round(n['GND']['loss_W'], 3),
          'open', {k: v.get('open') for k, v in n.items() if isinstance(v, dict) and v.get('open')}, 'DRC', sum(1 for v in d['violations'] if v['severity'] == 'error'), 'unconn', len(d.get('unconnected_items', [])))
P
