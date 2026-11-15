#!/bin/bash
# split_screen.sh <screened run dir> <new out dir> [--route=MIN] [--hot]
#   The same planned copper as <screened run dir> (its bare.kicad_pcb + spec.json), written with ONE ZONE PER OUTLINE
#   (tools/write_copper_split.py), then the shared scorecard on that board with --keep-copper: DRC, DC loss, renders,
#   blocked edges, and the full trial route when --route=MIN is given (default 0). Why: the shared writer's
#   multi-outline zones lose all but their first outline when KiCad loads and refills the board (LOG, 22:45 note), so
#   pads on the lost pieces show up as extra blocked edges and the routed board's refill drops pours.
#   Works for the hand board too (runs/hand_screen). One router job at a time.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
[ $# -ge 2 ] || { sed -n 2,9p "$0"; exit 2; }
SRC=$(cd "$1" && pwd); OUT=$(mkdir -p "$2" && cd "$2" && pwd); shift 2
RMIN=0; H="--no-hot"
for a in "$@"; do case $a in --route=*) RMIN=${a#*=};; --hot) H="";; *) echo "unknown option $a"; exit 2;; esac; done
[ -f $SRC/bare.kicad_pcb ] && [ -f $SRC/spec.json ] || { echo "$SRC has no bare.kicad_pcb + spec.json"; exit 1; }
mkdir -p $OUT/split; cd $OUT/split
cp $SRC/bare.kicad_pcb bare.kicad_pcb; cp $SRC/spec.json spec.json; cp $TOOLS/write_copper_split.py .
for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu_split.$e; done
docker run --rm -u 0 -v $OUT/split:/w -w /w kicad/kicad:10.0 python3 write_copper_split.py bare.kicad_pcb spec.json cu_split.kicad_pcb > write.log 2>&1 || { echo "write_copper_split failed"; grep -v swig write.log | tail -3; exit 1; }
grep -v swig write.log | tail -1
bash $S/score_board.sh $OUT $OUT/split/cu_split.kicad_pcb --keep-copper --route=$RMIN $H
