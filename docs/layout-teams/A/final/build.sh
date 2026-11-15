#!/bin/bash
# build.sh <workdir> [--score[=ARGS]] [--plan="planner options"] [--overrides=DIR] [--ref=GU.json]
#   deliverable: PLANNER=$PWD/final/tools/plan_copper_f.py STRAPS="--net=PACK_P --layer=In2.Cu" final/build.sh <wd> --score="--route=150" --plan="--sealed=1 --taps=1 --joinfix=1"
#   final copy of onecmd/build.sh: scripts from onecmd/, overrides from final/overrides (10,20 = merged3; 30_ports_b1, 40_stagepwr_v1); --score uses final/tools/score_board_f.sh (env PLANNER/STRAPS honoured)
#   One command from the bare scorecard template to team A final board FB (merged3 + ports b1 + stagepwr v1; diff vs stagepwr/best_gu.json).
#   1. dump   tools/score/template/board.kicad_pcb in the KiCad container (gu/dump.py)       -> base.json
#   2. place  groundup placer (gu/run.py, two passes, GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3) with the rebuild v5
#             port scripts (gu/place_p1top.py, gu/place_p2top.py)                             -> v5_gu.json
#   3. stage  stage/apply_stage.py with stage/stage_template.json (B4: Q401 hung from the fixed L401, every stage
#             part relative to it, port 2 = same template on L501; evicted neighbours re-placed by placelib.auto)
#                                                                                              -> stage_gu.json
#   4. overrides  every overrides/*.json (or --overrides=DIR) in name order, later files win    -> placement_gu.json
#   5. convert to the scorecard format (gu_to_score.py)                                       -> placement.json
#   6. check  placelib courtyard / edge / lip / peg check (exit 1 on errors); diff against --ref (default merged3)
#   --score          final/tools/score_board_f.sh <workdir>/score placement.json --route=0 --no-hot
#   --score="ARGS"   the split scorecard with those ARGS instead (e.g. --score="--route=0" for hot loops on)
#   To add a worker's result: drop its {ref:[x,y,abs rot]} file into overrides/ with a name that sorts after the
#   others (e.g. 30_ports_b1.json, 40_stagepwr_v1.json). No code change needed.
set -e
H=$(cd "$(dirname "$0")" && pwd); A=$(cd "$H/.." && pwd); R=$(cd "$H/../../../.." && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd); shift
SCORE=""; PLANARG=""; OV=$H/overrides; REF=$A/stagepwr/best_gu.json; O=$A/onecmd
for a in "$@"; do case $a in --score) SCORE="--route=0 --no-hot";; --score=*) SCORE=${a#*=};; --overrides=*) OV=$(cd "${a#*=}" && pwd);; --ref=*) REF=$(readlink -f "${a#*=}");; --plan=*) PLANARG=$a;; *) echo "unknown option $a"; exit 2;; esac; done
t0=$(date +%s)
cd $W; mkdir -p img
cp $O/gu/*.py $O/gu/keep_vias.json .
cp $R/tools/score/template/board.kicad_pcb template.kicad_pcb
echo "[build] 1 dump template"
docker run --rm -u 0 -v $W:/w -w /w kicad/kicad:10.0 python3 dump.py template.kicad_pcb base.json 2>&1 | grep -v -i swig
rm -f template.kicad_pcb
echo "[build] 2 groundup placer + v5 port scripts"
export GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3
python3 run.py place_keep.py,place_p1top.py,place_centre.py,place_p1stage.py,place_p2top.py,place_bot.py > place.log 2>&1 || { tail -20 place.log; exit 1; }
grep -v '  auto ' place.log | tail -2
mv placement.json v5_gu.json
echo "[build] 3 stage template on both ports (GAP/RING unset: the stage worker re-placed evicted parts with gap 0)"
env -u GAP -u RING -u GAPB -u RINGB STAGE_WD=$W python3 $O/stage/apply_stage.py $W/v5_gu.json $O/stage/stage_template.json $W/stage_gu.json > stage.log 2>&1 || { tail -20 stage.log; exit 1; }
grep -E 'evict|placement errors' stage.log | tr '\n' ';' | sed 's/;/; /g'; echo
echo "[build] 4 overrides from $OV"
python3 $O/apply_overrides.py stage_gu.json placement_gu.json $(ls $OV/*.json 2>/dev/null | sort)
echo "[build] 5 scorecard format"
python3 gu_to_score.py placement_gu.json placement.json base.json
echo "[build] 6 check"
python3 $O/check.py $W $W/placement_gu.json
if [ -f "$REF" ]; then echo "[build] diff against $REF"; python3 cmp_place.py "$REF" placement_gu.json | tee cmp_ref.txt; fi
echo "[build] placement done in $(( $(date +%s) - t0 )) s: $W/placement_gu.json, $W/placement.json"
[ -n "$SCORE" ] && $H/tools/score_board_f.sh $W/score $W/placement.json $SCORE ${PLANARG:+"$PLANARG"}
exit 0
