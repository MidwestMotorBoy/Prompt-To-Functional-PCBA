#!/bin/bash
# quickplace.sh <out_dir> <override.json> : fast placement variant on top of the team best (no re-run of the placer):
#   best_placement_gu.json + override -> placelib check (courtyards/edge/peg) -> scorecard placement.json in <out_dir>.
#   Needs runs/build0/b (one build_r4.sh run) for base.json / placelib.
set -e
H=$(cd "$(dirname "$0")/.." && pwd); A=$(cd "$H/.." && pwd); B=$H/runs/build0/b
O=$(mkdir -p "$1" && cd "$1" && pwd); OV=$(readlink -f "$2")
python3 $A/onecmd/apply_overrides.py $A/final/deliver/best_placement_gu.json $O/placement_gu.json $OV
python3 $A/onecmd/check.py $B $O/placement_gu.json
(cd $B && python3 gu_to_score.py $O/placement_gu.json $O/placement.json base.json)
