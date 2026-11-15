#!/bin/bash
# cscore.sh <outdir> <placement.json> [scorecard options, e.g. --route=0 --no-hot]
#   The scorecard for a team C placement. A placement with no side changes (every entry [x, y, angle]) goes to
#   tools/score/score_board.sh as it is. One with side changes (a 4th element "F"/"B") is first applied to the
#   template with c_apply.py (the shared apply_placement.py cannot flip), and the resulting BOARD is scored.
#   Also copies the placement to <outdir>/placement.json and runs the placer-side legality check (overlaps.py) when it can.
set -o pipefail
H=$(cd "$(dirname "$0")" && pwd); R=$(cd $H/../../../.. && pwd); S=$R/tools/score
OUT=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); shift 2
cp $PL $OUT/placement_in.json
if python3 -c "import json,sys; sys.exit(0 if any(len(v) > 3 for v in json.load(open('$PL')).values()) else 1)"; then
  cp $S/template/board.kicad_pcb $OUT/tpl.kicad_pcb; cp $S/template/board.kicad_pro $OUT/placed.kicad_pro; cp $S/template/board.kicad_dru $OUT/placed.kicad_dru
  cp $H/c_apply.py $OUT/; cp $PL $OUT/placement4.json
  docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 python3 c_apply.py tpl.kicad_pcb placed.kicad_pcb placement4.json --strip > $OUT/c_apply.log 2>&1 || { echo "[cscore] c_apply failed:"; tail -5 $OUT/c_apply.log; exit 1; }
  exec $S/score_board.sh $OUT $OUT/placed.kicad_pcb "$@"
else
  exec $S/score_board.sh $OUT $PL "$@"
fi
