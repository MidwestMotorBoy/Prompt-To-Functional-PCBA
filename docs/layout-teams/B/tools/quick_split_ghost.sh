#!/bin/bash
# quick_split_ghost.sh <plan_only run dir> [only-regex]
#   The plan_only run's copper written with one zone per outline (write_copper_split.py, as split_screen.sh does),
#   DRC, then quick_ghost.sh on it in <run>/qsplit. A quick look at the fair (split) blocked-edge count between full
#   screens; screen.sh + split_screen.sh give the numbers.
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
SRC=$(cd "$1" && pwd); OUT=$SRC/qsplit; mkdir -p $OUT; cd $OUT
cp $SRC/bare.kicad_pcb bare.kicad_pcb; cp $SRC/spec.json spec.json; cp $TOOLS/write_copper_split.py .
for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
K="docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0"
$K python3 write_copper_split.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1 || { echo "write_copper_split failed"; exit 1; }
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1"
bash $TOOLS/quick_ghost.sh $OUT "$2"
