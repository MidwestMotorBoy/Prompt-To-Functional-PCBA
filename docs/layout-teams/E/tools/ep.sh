#!/bin/bash
# ep.sh <run name> <moves.txt> [view window x0,y0,x1,y1] [px/mm]    quick look at a placement: moves -> placement.json ->
# bare board (no copper) -> dump -> picture /home/claude/v/<run>_bare.png. No scoring.
HERE=$(cd "$(dirname "$0")" && pwd); R=$(cd "$HERE/../../../.." && pwd); T=$R/tools; S=$T/score
OUT=/home/claude/runs/$1; mkdir -p $OUT /home/claude/v
python3 $HERE/eplace.py ${BASE:-/home/claude/runs/handP/cu.e.json} $2 $OUT/placement.json || exit 1
cp $2 $OUT/moves.txt; cp $S/template/board.kicad_pcb $OUT/in.kicad_pcb; cp $T/floorplan/apply_placement.py $HERE/edump.py $OUT/
for e in kicad_pro kicad_dru; do cp $S/template/board.$e $OUT/bare.$e; done
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "python3 apply_placement.py in.kicad_pcb bare.kicad_pcb placement.json --strip 2>&1 | grep -v swig | tail -2; python3 edump.py bare.kicad_pcb bare.e.json 2>&1 | grep -v swig"
python3 $HERE/eview.py $OUT/bare.e.json /home/claude/v/$1_bare.png ${3:--} ${4:-20} --layers=F,B
