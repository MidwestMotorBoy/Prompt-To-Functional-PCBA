#!/bin/bash
# dcq.sh <scorecard outdir (for bare.kicad_pcb/bare.json)> <plan spec.json> <work dir> [rules.json]
#   quick power check of one plan: split + bus layer + write_copper + DRC + dc_score (no ghost, no hot loops). ~2 min.
#   prints power_open, DRC errors and loss.
set -o pipefail
R=/home/claude/repo; T=$R/tools; P=$R/docs/layout-teams/A/r4_general/copper_rules
SRC=$(cd "$1" && pwd); SPEC=$(readlink -f "$2"); W=$(mkdir -p "$3" && cd "$3" && pwd); RULES=$(readlink -f "${4:-$R/docs/layout-teams/A/r4_general/general.rules.json}")
C=$R/$(python3 -c "import json;print(json.load(open('$RULES'))['board']['constraints'])")
cd $W; for e in kicad_pcb kicad_pro kicad_dru; do cp $SRC/bare.$e .; done; cp $SRC/bare.json .; cp $T/copper/cu_dump.py $T/copper/write_copper.py .; cp $T/score/router.py .
cp $SPEC spec.json; python3 $P/split_zones.py spec.json > q.log; python3 $P/bus_layer.py spec.json bare.json $C --rules=$RULES --router=router.py >> q.log 2>&1
cp bare.kicad_pro cu.kicad_pro; cp bare.kicad_dru cu.kicad_dru
K="docker run --rm -u 0 -v $W:/w -w /w kicad/kicad:10.0"
$K sh -c "python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1; kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig" > /dev/null
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json > dc.log 2>&1
python3 - <<'P'
import json
dc = json.load(open('dc.json')); n = dc.get('nets', dc); d = json.load(open('drc.json'))
print("DCQ", json.dumps(dict(loss_W=round(sum(v.get('loss_W', 0) for v in n.values() if isinstance(v, dict)), 3),
      power_open={k: v.get('open') for k, v in n.items() if isinstance(v, dict) and v.get('open')},
      drc_errors=sum(1 for v in d['violations'] if v['severity'] == 'error'))))
P
rm -f bare.kicad_pcb cu.kicad_pcb
