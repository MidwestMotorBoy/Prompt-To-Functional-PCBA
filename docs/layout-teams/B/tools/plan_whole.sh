#!/bin/bash
# plan_whole.sh <out dir> <placement.json> [plan_copper options]     (team B phase 2, worker A)
#   Whole-board copper plan of a placement, no scorecard: apply_b.py (flips allowed) -> bare board (stripped) ->
#   cu_dump -> plan_copper.py -> spec.json, plus cu.json (= bare.json: pads, outline, keep-outs) so that the out dir
#   works as a source for spec_chain.sh, pinlib.py look and win_items.py. About 1 min. NOT a screen: run screen.sh
#   (shared scorecard) for numbers.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score; C=$T/floorplan/example/monolith/constraints.json
OUT=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); shift 2; cd $OUT
cp $S/template/board.kicad_pcb template.kicad_pcb; for e in kicad_pro kicad_dru; do cp $S/template/board.$e template.$e; cp $S/template/board.$e placed.$e; cp $S/template/board.$e bare.$e; done
cp $TOOLS/apply_b.py $T/floorplan/apply_placement.py $T/copper/cu_dump.py .
python3 -c "import json; json.dump({r: v for r, v in json.load(open('$PL')).items() if not r.startswith('_')}, open('placement.json', 'w'))"
python3 $TOOLS/blib.py pads placement.json > expect_pads.json || exit 1
K="docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0"
$K python3 apply_b.py template.kicad_pcb placed.kicad_pcb placement.json --expect=expect_pads.json > apply_b.log 2>&1 || { grep -v swig apply_b.log | tail -3; exit 1; }
grep -v swig apply_b.log | tail -1
cp placed.kicad_pcb in.kicad_pcb
$K sh -c "python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip >/dev/null 2>&1; python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig"
python3 $T/copper/plan_copper.py bare.json $C spec.json "$@" > plan.log 2>&1 || { tail -3 plan.log; exit 1; }
cp bare.json cu.json; echo "plan_whole: $OUT/spec.json"
