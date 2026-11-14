#!/bin/bash
# plan_only.sh <outdir> <placement.json>
#   Quick partial check of a placement's power copper: the --partial screen steps up to the DC solve and the renders
#   (apply_b --partial, strip, copper plan, write copper, DRC, DC), with no hot-loop solve and no ghost router.
#   Prints the planner lines for the power nets and the open power pins. Not a scorecard: screen.sh gives the numbers.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score
OUT=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); cd $OUT
cp $S/template/board.kicad_pcb template.kicad_pcb; for e in kicad_pro kicad_dru; do cp $S/template/board.$e template.$e; cp $S/template/board.$e placed.$e; cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
cp $TOOLS/apply_b.py $T/floorplan/apply_placement.py $T/copper/cu_dump.py $T/copper/write_copper.py .
python3 -c "import json,sys; json.dump({r: v for r, v in json.load(open('$PL')).items() if not r.startswith('_')}, open('placement.json', 'w'))"
python3 $TOOLS/blib.py pads placement.json --partial > expect_pads.json || exit 1
K="docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0"
$K python3 apply_b.py template.kicad_pcb placed.kicad_pcb placement.json --partial --expect=expect_pads.json > apply_b.log 2>&1 || { grep -v swig apply_b.log | tail -3; exit 1; }
python3 $TOOLS/partcons.py $R/tools/floorplan/example/monolith/constraints.json placement.json constraints_part.json refs_present.json > /dev/null || exit 1
cp placed.kicad_pcb in.kicad_pcb
$K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip > strip.log 2>&1
$K python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig > /dev/null
python3 $T/copper/plan_copper.py bare.json constraints_part.json spec.json > plan.log 2>&1
$K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig > /dev/null"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json constraints_part.json dc.json > dc.log 2>&1
for L in F.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done
grep -E "Port 1|PACK_P" plan.log | grep -v "^hot\|Port 2"
python3 - <<'P'
import json
d = json.load(open('dc.json')); n = d.get('nets', d)
print('open:', {k: v.get('open') for k, v in n.items() if isinstance(v, dict) and v.get('open')})
v = json.load(open('drc.json')); print('drc errors:', sum(1 for x in v['violations'] if x['severity'] == 'error'))
P
