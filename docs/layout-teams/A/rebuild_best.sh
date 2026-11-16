#!/bin/bash
# rebuild_best.sh <workdir> [--score[=ARGS]]
#   ONE COMMAND from the bare scorecard template (tools/score/template/board.kicad_pcb) to team A's best placement
#   (round 5: the round-3 build + overrides 50 port-1 PD cluster, 60 stage move, 70 charger north row, 80 gauge caps).
#   1. final/build.sh --overrides=best_overrides: KiCad dump of the template -> groundup placer with the rebuild-v5
#      port scripts -> charger stage template B4 on both ports -> best_overrides/*.json in name order
#      (10 stagefix s3, 20 pdfix a3, 30 ports b1, 40 stagepwr v1, 50 r4_port1, 60 r4_bcu, 70 r5_north, 80 r5_gauge)
#      -> <workdir>/placement.json (scorecard format) + placement_gu.json; courtyard/edge/peg check; about 2 min.
#   2. compares <workdir>/placement.json with the committed best_placement.json (must be identical).
#   3. --score        : team scorecard r5_merge/tools/score_board_r5.sh (split zones, per-pad join check) with the
#                       best copper recipe r5_merge/tools/best_env_r5.sh (planner M, In4 PACK_P bus, soft B.Cu GND
#                       fill), --route=0, hot loops on (about 10 min)
#      --score="ARGS" : the same with your ARGS, e.g. --score="--route=150" for a local full route with routed checks
#   The round-3 version of this script is tools/rebuild_best_r3.sh (placement lead_final/best_placement_r3.json).
#   Needs docker image kicad/kicad:10.0 and python3 with numpy scipy shapely numba pillow.
set -e
A=$(cd "$(dirname "$0")" && pwd); W=$(mkdir -p "$1" && cd "$1" && pwd); shift
SCORE=""; for a in "$@"; do case $a in --score) SCORE="--route=0";; --score=*) SCORE=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
"$A/final/build.sh" "$W" --overrides="$A/best_overrides" --ref="$A/final/deliver/best_placement_gu.json"
python3 - "$W/placement.json" "$A/best_placement.json" <<'P'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
d = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
print(f"[rebuild_best] {len(d)} of {len(b)} entries differ from best_placement.json", d[:10]); sys.exit(1 if d else 0)
P
if [ -n "$SCORE" ]; then . "$A/r5_merge/tools/best_env_r5.sh"; "$A/r5_merge/tools/score_board_r5.sh" "$W/score" "$W/placement.json" $SCORE --plan="$BEST_PLAN_R5"; fi
