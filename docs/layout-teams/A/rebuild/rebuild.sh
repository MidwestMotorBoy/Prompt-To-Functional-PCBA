#!/bin/bash
# rebuild.sh <workdir> [--score[=ARGS]] [--no-keepv] [--gu=<dir of place scripts>]
#   One command from the bare scorecard template to the groundup placement (and optionally its scorecard).
#   1. dumps tools/score/template/board.kicad_pcb with gu/dump.py in the KiCad container -> <workdir>/base.json
#   2. runs the groundup placer (run.py, two passes) with GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3
#      -> <workdir>/placement_gu.json  (groundup format: absolute x, y, KiCad orientation)
#   3. converts to the scorecard format (quarter turns relative to the template) -> <workdir>/placement.json
#   4. --score : runs tools/score/score_board.sh <workdir>/score <workdir>/placement.json --route=0 --no-hot
#      --score="--route=0" : passes those args instead
#   --no-keepv : drop keep_vias.json (hand-copper via spots that the greedy placer avoids)
#   --exact    : apply gu/post_edits.json after the placer (hand edits made after the placer run that the committed
#                groundup placement.json carries: C549 at (80.2, 86.0), outside the placer's lip limit)
#   --gu=DIR   : take the place scripts from DIR instead of gu/ (variants; files in DIR replace the gu/ copies)
#   Examples:  ./rebuild.sh runs/base --exact --score          the committed groundup placement (65 of 441 blocked)
#              ./rebuild.sh runs/best --gu=variants/v5 --score  the best variant of this worker (55 of 436 blocked)
#   Do NOT combine --exact with a variant that places C549 itself (v5, v6): the post-edit would move it back.
set -e
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../../../.." && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd); shift
GU=$H/gu; SCORE=""; KEEPV=1; EXACT=0
for a in "$@"; do case $a in --score) SCORE="--route=0 --no-hot";; --score=*) SCORE=${a#*=};; --no-keepv) KEEPV=0;; --exact) EXACT=1;; --gu=*) GU=$(cd "${a#*=}" && pwd);; esac; done
cd $W; mkdir -p img
cp $H/gu/*.py $H/gu/keep_vias.json .            # base scripts
[ "$GU" != "$H/gu" ] && cp $GU/*.py . 2>/dev/null; [ -f $GU/keep_vias.json ] && cp $GU/keep_vias.json .
[ $KEEPV = 0 ] && rm -f keep_vias.json
cp $R/tools/score/template/board.kicad_pcb template.kicad_pcb
cp $R/tools/score/template/board.kicad_pro template.kicad_pro 2>/dev/null || true
docker run --rm -u 0 -v $W:/w -w /w kicad/kicad:10.0 python3 dump.py template.kicad_pcb base.json 2>&1 | grep -v -i swig
export GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3
python3 run.py place_keep.py,place_p1top.py,place_centre.py,place_p1stage.py,place_p2top.py,place_bot.py > place.log 2>&1 || { tail -20 place.log; exit 1; }
grep -v '  auto ' place.log | tail -5
mv placement.json placement_gu.json
[ $EXACT = 1 ] && python3 -c "import json; P=json.load(open('placement_gu.json')); P.update(json.load(open('$H/gu/post_edits.json'))); json.dump(P,open('placement_gu.json','w'),indent=0)" && echo "post edits applied"
python3 $H/gu/gu_to_score.py placement_gu.json placement.json base.json
rm -f template.kicad_pcb template.kicad_pro
[ -n "$SCORE" ] && $R/tools/score/score_board.sh $W/score $W/placement.json $SCORE
exit 0
