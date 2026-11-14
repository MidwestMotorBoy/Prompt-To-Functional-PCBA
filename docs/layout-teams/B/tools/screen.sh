#!/bin/bash
# screen.sh <outdir> <placement.json> [--partial] [--hot="loop,loop" | --hot=all] [--route=MIN] [--plan="..."]
#   Team B screen of a placement ({ref: [x, y, turn] or [x, y, turn, side]}, a stitched placement or one fragment).
#   whole board: apply_b.py (flips allowed) -> placed.kicad_pcb -> the shared tools/score/score_board.sh on that board
#                (--no-hot unless --hot=all). With no flips and 3-element entries this equals the shared scorecard
#                run on the placement json.
#   --partial:   apply_b.py --partial (only fixed parts + the placement's parts on the board), constraints filtered
#                to those parts (constraints_part.json), then score_part.sh (copy of the scorecard steps) with only
#                the hot loops named. score.json gets "partial": true and the refs present.
#   Default --route=0 (blocked-edge screen only). Put outdir under docs/layout-teams/B/runs/<unique-name>/.
#   One router or hot-loop job at a time per worker.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
[ $# -ge 2 ] || { sed -n 2,12p "$0"; exit 2; }
OUT=$(mkdir -p "$1" && cd "$1" && pwd); PL=$(readlink -f "$2"); shift 2
PART=0; HOT=""; RMIN=0; PLAN=""
for a in "$@"; do case $a in --partial) PART=1;; --hot=*) HOT=${a#*=};; --route=*) RMIN=${a#*=};; --plan=*) PLAN=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
cd $OUT
docker images >/dev/null 2>&1 || { echo "docker is not running"; exit 1; }
cp $S/template/board.kicad_pcb template.kicad_pcb; cp $S/template/board.kicad_pro template.kicad_pro; cp $S/template/board.kicad_dru template.kicad_dru
cp $S/template/board.kicad_pro placed.kicad_pro; cp $S/template/board.kicad_dru placed.kicad_dru
cp $TOOLS/apply_b.py .; cp $PL placement_in.json
python3 - placement_in.json <<'P'
import json, sys      # a fragment or placement: keep only ref entries
P = {r: v for r, v in json.load(open(sys.argv[1])).items() if not r.startswith("_")}
json.dump(P, open("placement.json", "w"))
P
PA=""; [ $PART = 1 ] && PA="--partial"
python3 $TOOLS/blib.py pads placement.json $PA > expect_pads.json || { echo "blib pads failed"; exit 1; }
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 python3 apply_b.py template.kicad_pcb placed.kicad_pcb placement.json $PA --expect=expect_pads.json > apply_b.log 2>&1
if [ $? != 0 ]; then echo "[screen] apply_b failed:"; grep -v swig apply_b.log | tail -5; exit 1; fi
grep -v swig apply_b.log | tail -1
if [ $PART = 0 ]; then
  H="--no-hot"; [ "$HOT" = all ] && H=""
  [ -n "$HOT" ] && [ "$HOT" != all ] && echo "[screen] whole board: only --hot=all is supported (running without hot loops)"
  if [ -n "$PLAN" ]; then bash $S/score_board.sh $OUT $OUT/placed.kicad_pcb --route=$RMIN $H "--plan=$PLAN"
  else bash $S/score_board.sh $OUT $OUT/placed.kicad_pcb --route=$RMIN $H; fi
else
  python3 $TOOLS/partcons.py $R/tools/floorplan/example/monolith/constraints.json placement.json constraints_part.json refs_present.json || exit 1
  if [ -n "$PLAN" ]; then bash $TOOLS/score_part.sh $OUT $OUT/placed.kicad_pcb $OUT/constraints_part.json --route=$RMIN "--hot=$HOT" "--plan=$PLAN"
  else bash $TOOLS/score_part.sh $OUT $OUT/placed.kicad_pcb $OUT/constraints_part.json --route=$RMIN "--hot=$HOT"; fi
fi
