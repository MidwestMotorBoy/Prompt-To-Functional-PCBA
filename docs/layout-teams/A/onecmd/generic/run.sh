#!/bin/bash
# run.sh <workdir> [--score[=ARGS]] [place_generic.py options...]
#   One command: bare scorecard template -> gdump.py dump (KiCad container) -> place_generic.py -> scorecard format
#   (-> optional scorecard).  Outputs <workdir>/base.json, placement_gu.json (absolute poses), placement.json
#   (scorecard format: quarter turns relative to the template), report.json, place.log [, score/].
#   --score            runs tools/score/score_board.sh <workdir>/score placement.json --route=0 --no-hot
#   --score="--route=0" passes those args instead
#   ANCHORS=<file> picks another anchors file (best: anchors_p2t.json, port 2 derived from port 1)
set -e
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../../../.." && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd); shift
SCORE=""; OPTS=()
for a in "$@"; do case $a in --score) SCORE="--route=0 --no-hot";; --score=*) SCORE=${a#*=};; *) OPTS+=("$a");; esac; done
T=$R/tools/score/template; M=$R/tools/floorplan/example/monolith
if [ ! -f $W/base.json ]; then
  cp $T/board.kicad_pcb $W/template.kicad_pcb; cp $H/gdump.py $W/
  docker run --rm -u 0 -v $W:/w -w /w kicad/kicad:10.0 python3 gdump.py template.kicad_pcb base.json 2>&1 | grep -v -i swig
  rm -f $W/template.kicad_pcb $W/gdump.py
fi
python3 $H/place_generic.py --dump $W/base.json --pro $T/board.kicad_pro --dru $T/board.kicad_dru --constraints $M/constraints.json \
  --anchors ${ANCHORS:-$H/anchors.json} --fixed $H/fixed_parts.json --enclosure $H/enclosure.json --out $W "${OPTS[@]}"
python3 $R/docs/layout-teams/A/tools/gu_to_score.py $W/placement_gu.json $W/placement.json $W/base.json
[ -n "$SCORE" ] && $R/tools/score/score_board.sh $W/score $W/placement.json $SCORE
exit 0
