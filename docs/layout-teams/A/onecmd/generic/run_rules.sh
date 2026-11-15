#!/bin/bash
# run_rules.sh <workdir> [--score[=ARGS]] [place_rules.py options...]
#   One command for the rule-based generic flow: bare template -> gdump.py dump (KiCad container) -> place_rules.py
#   (anchors_rules.json by default, stage template from ../stage/stage_template.json) -> scorecard format -> check.
#   --score  docs/layout-teams/A/tools/score_board_split.sh <workdir>/score placement.json --route=0 --no-hot
#   ANCHORS=<file> STAGE=<file> select other inputs.
set -e
H=$(cd "$(dirname "$0")" && pwd); A=$(cd "$H/../.." && pwd); R=$(cd "$H/../../../../.." && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd); shift
SCORE=""; OPTS=()
for a in "$@"; do case $a in --score) SCORE="--route=0 --no-hot";; --score=*) SCORE=${a#*=};; *) OPTS+=("$a");; esac; done
T=$R/tools/score/template; M=$R/tools/floorplan/example/monolith
if [ ! -f $W/base.json ]; then
  cp $T/board.kicad_pcb $W/template.kicad_pcb; cp $H/gdump.py $W/
  docker run --rm -u 0 -v $W:/w -w /w kicad/kicad:10.0 python3 gdump.py template.kicad_pcb base.json 2>&1 | grep -v -i swig
  rm -f $W/template.kicad_pcb $W/gdump.py
fi
python3 $H/place_rules.py --dump $W/base.json --pro $T/board.kicad_pro --dru $T/board.kicad_dru --constraints $M/constraints.json \
  --anchors ${ANCHORS:-$H/anchors_rules.json} --stage ${STAGE:-$H/../stage/stage_template_u403.json} --fixed $H/fixed_parts.json --enclosure $H/enclosure.json --out $W "${OPTS[@]}"
python3 $H/../gu/gu_to_score.py $W/placement_gu.json $W/placement.json $W/base.json
[ -n "$SCORE" ] && $A/tools/score_board_split.sh $W/score $W/placement.json $SCORE
exit 0
