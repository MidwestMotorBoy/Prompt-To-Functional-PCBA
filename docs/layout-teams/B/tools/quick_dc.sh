#!/bin/bash
# quick_dc.sh <spec.json> <out dir> [dc_score options, e.g. --net=PACK_P]
#   Fast copper check of a copper plan between screens (about 1 min, no blocked-edge screen, no route):
#   writes the plan into r4's bare board with one zone per outline (write_copper_split.py), KiCad DRC, cu_dump,
#   dc_score. Prints DRC errors and PACK_P J113/R427 resistance and total loss. Not a scorecard number: the screen
#   (final_route.sh --route=0) is.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score; C=$T/floorplan/example/monolith/constraints.json
SPEC=$(readlink -f "$1"); OUT=$(mkdir -p "$2" && cd "$2" && pwd); shift 2
BARE=${BARE:-$TOOLS/../runs/r4chg-hot/bare.kicad_pcb}
cd $OUT; cp $BARE bare.kicad_pcb; cp $SPEC spec.json; cp $TOOLS/write_copper_split.py $T/copper/cu_dump.py .
for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "python3 write_copper_split.py bare.kicad_pcb spec.json cu.kicad_pcb 2>&1 | grep -v swig | tail -1; kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig" > write.log 2>&1
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json "$@" > dc.log 2>&1
python3 - <<'P'
import json
d = json.load(open('drc.json')); errs = [v for v in d['violations'] if v['severity'] == 'error']
dc = json.load(open('dc.json')); nets = dc.get('nets', dc)
loss = sum(v.get('loss_W', 0) for v in nets.values() if isinstance(v, dict))
p = nets.get('PACK_P', {}); t = {x['ref']: x['R_mohm'] for x in p.get('terminals', [])}
op = {k: v.get('open') for k, v in nets.items() if isinstance(v, dict) and v.get('open')}
print(f"QUICK drc_errors {len(errs)} unconnected {len(d.get('unconnected_items', []))} loss_W {loss:.3f} PACK_P {p.get('loss_W')} W J113 {t.get('J113')} R427 {t.get('R427')} mohm open {op}")
for e in errs[:8]: print('  DRC', e['type'], e['description'][:60], [i['description'][:50] for i in e['items']], [i['pos'] for i in e['items']][:1])
P
