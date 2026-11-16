#!/bin/bash
# rebuild_best.sh <workdir> [--score[=ARGS]]
#   ONE COMMAND from the bare scorecard template (tools/score/template/board.kicad_pcb) to team A's best placement.
#   1. final/build.sh: KiCad dump of the template -> groundup placer with the rebuild-v5 port scripts -> charger stage
#      template B4 on both ports -> overrides final/overrides/*.json (stagefix s3, pdfix a3, ports b1, stagepwr v1)
#      -> <workdir>/placement.json (scorecard format) + placement_gu.json; courtyard/edge/peg check; about 2 min.
#   2. compares <workdir>/placement.json with the committed best_placement.json (must be identical).
#   3. --score        : team scorecard with the best copper recipe (tools/best_env.sh), --route=0, hot loops on (~13 min)
#      --score="ARGS" : the same with your ARGS, e.g. --score="--route=150" for a local full route with routed-board checks
#   Needs docker image kicad/kicad:10.0 and python3 with numpy scipy shapely numba pillow.
set -e
A=$(cd "$(dirname "$0")" && pwd); W=$(mkdir -p "$1" && cd "$1" && pwd); shift
SCORE=""; for a in "$@"; do case $a in --score) SCORE="--route=0";; --score=*) SCORE=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
"$A/final/build.sh" "$W"
python3 - "$W/placement.json" "$A/best_placement.json" <<'P'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
d = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
print(f"[rebuild_best] {len(d)} of {len(b)} entries differ from best_placement.json", d[:10]); sys.exit(1 if d else 0)
P
if [ -n "$SCORE" ]; then . "$A/tools/best_env.sh"; "$A/tools/score_board_best.sh" "$W/score" "$W/placement.json" $SCORE --plan="$BEST_PLAN"; fi
