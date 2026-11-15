#!/bin/bash
# final_route.sh <screened whole-board run dir> <out dir> [--route=MIN] [--no-straps] [--no-hot] [--straps="<straps.py options>;..."]
#                 [--filters="<script> <options>;..."] [--post="<script> <options>"]
#   The routed-board check for the final scorecard. Takes a run of the shared scorecard (it needs the run's
#   bare.kicad_pcb, spec.json and cu.json) and:
#   1. adds hard PACK_P strap tracks on In2.Cu to the copper plan (tools/straps.py), so the router cannot cut the
#      soft PACK_P bus into islands (--no-straps skips it; --straps="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H"
#      replaces the default list, several runs of straps.py separated by ';');
#   2. writes the copper with one zone per outline (tools/write_copper_split.py);
#   3. runs the shared scorecard on that board with --keep-copper --no-hot --route=MIN (default 45; 0 = screen only):
#      DRC of the copper board, DC loss and power open before routing, blocked edges, full trial route;
#   4. on the routed board (routed.kicad_pcb): cu_dump.py + dc_score.py (loss, power open), tools/loose.py, KiCad DRC
#      (errors and unconnected items of the power nets), and the seven hot loops with hot_score.py + power_gate.py the
#      way score_board.sh step 4 calls them (PCB=routed board); --no-hot skips the loops;
#   5. writes <out dir>/final.json and prints it.
#   Phase 2 hooks (both optional, nothing changes without them):
#   --filters="trunk.py --w=3;pins.py"  copper-plan filters, run in this order after the straps, each as
#        python3 tools/<script> <spec.json in> <source run's cu.json> <spec.json out> <its options>
#      (the same call as straps.py). A filter that exits with a code other than 0 stops the run. Logs: split/filter_<n>.log.
#   --post="finish.sh --rips=900"       finishing pass on the routed board, run after the full route as
#        bash|python3 tools/<script> <out dir> <its options>
#      It reads <out dir>/routed.kicad_pcb (also there: cu.kicad_pcb = the board before routing, drc.json, route.log) and
#      writes <out dir>/finished.kicad_pcb. When that file exists, step 4 scores it instead of routed.kicad_pcb and
#      final.json says so ("scored_board"). Log: post.log.
#   Works unchanged on the hand board (runs/hand_screen). ONE router or hot-loop job at a time: this script runs a
#   full route and seven loop solves in a row (about 25 + 10 min on a loaded 4-core box).
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith; C=$E/constraints.json
[ $# -ge 2 ] || { sed -n 2,27p "$0"; exit 2; }
SRC=$(cd "$1" && pwd); OUT=$(mkdir -p "$2" && cd "$2" && pwd); shift 2
RMIN=45; STRAPS=1; HOT=1; SOPT="--net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V"; FILT=""; POST=""
for a in "$@"; do case $a in --route=*) RMIN=${a#*=};; --no-straps) STRAPS=0;; --no-hot) HOT=0;; --straps=*) SOPT=${a#*=};; --filters=*) FILT=${a#*=};; --post=*) POST=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
rm -f $OUT/finished.kicad_pcb $OUT/post.log
for f in bare.kicad_pcb spec.json cu.json; do [ -f $SRC/$f ] || { echo "$SRC has no $f (run the shared scorecard on it first)"; exit 1; }; done
log() { echo "[final] $(date -u +%H:%M:%S) $*" >&2; }
K="docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0"

# 1. plan + straps
mkdir -p $OUT/split; cd $OUT/split
cp $SRC/bare.kicad_pcb bare.kicad_pcb; cp $SRC/spec.json spec_plain.json; cp $TOOLS/write_copper_split.py .
cp spec_plain.json spec.json; : > straps.log
if [ $STRAPS = 1 ]; then
  IFS=';' read -ra SL <<< "$SOPT"
  for o in "${SL[@]}"; do
    nm=$(echo "$o" | sed -n 's/.*--net=\([^ ]*\).*/\1/p'); nm=${nm:-PACK_P}
    python3 $TOOLS/straps.py spec.json $SRC/cu.json spec_next.json $o --png=straps_$nm.png > straps_$nm.log 2>&1; rc=$?
    cat straps_$nm.log >> straps.log; mv spec_next.json spec.json; grep -v "^  tied" straps_$nm.log >&2
    [ $rc = 0 ] || log "straps for $nm: an untied group or a clearance fault (see split/straps.log)"
  done
fi
# 1b. copper-plan filters
if [ -n "$FILT" ]; then
  IFS=';' read -ra FL <<< "$FILT"; n=0
  for o in "${FL[@]}"; do
    n=$((n+1)); set -- $o; f=$1; shift; [[ $f == */* ]] || f=$TOOLS/$f
    python3 $f spec.json $SRC/cu.json spec_next.json "$@" > filter_$n.log 2>&1 || { log "filter $n ($o) failed:"; tail -5 filter_$n.log >&2; exit 1; }
    [ -f spec_next.json ] || { log "filter $n ($o) wrote no spec"; exit 1; }
    mv spec_next.json spec.json; log "filter $n: $o: $(tail -1 filter_$n.log)"
  done
fi
# 2. copper, one zone per outline
for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu_split.$e; done
docker run --rm -u 0 -v $OUT/split:/w -w /w kicad/kicad:10.0 python3 write_copper_split.py bare.kicad_pcb spec.json cu_split.kicad_pcb > write.log 2>&1 || { echo "write_copper_split failed"; grep -v swig write.log | tail -3; exit 1; }
log "$(grep -v swig write.log | tail -1)"
# 3. shared scorecard on that board
log "scorecard (--keep-copper --no-hot --route=$RMIN)"
bash $S/score_board.sh $OUT $OUT/split/cu_split.kicad_pcb --keep-copper --route=$RMIN --no-hot | tail -1
grep -E "^ *(FAILED|routed |unconnected after fill|edges to route)" $OUT/route.log | sed "s/^ *//" > $OUT/route_failed.txt 2>/dev/null
# 3b. finishing pass on the routed board
BOARD=$OUT/routed.kicad_pcb
if [ -n "$POST" ] && [ "$RMIN" != 0 ] && [ -f $OUT/routed.kicad_pcb ]; then
  set -- $POST; f=$1; shift; [[ $f == */* ]] || f=$TOOLS/$f
  case $f in *.py) run=python3;; *) run=bash;; esac
  log "finishing pass: $POST"
  $run $f $OUT "$@" > $OUT/post.log 2>&1 || log "finishing pass ended with an error (see post.log); scoring what it left"
  [ -f $OUT/finished.kicad_pcb ] && BOARD=$OUT/finished.kicad_pcb
fi
# 4. the routed board
mkdir -p $OUT/routed
if [ "$RMIN" != 0 ] && [ -f $OUT/routed.kicad_pcb ]; then
  cd $OUT/routed; cp $BOARD cu.kicad_pcb; cp $T/copper/cu_dump.py .
  for e in kicad_pro kicad_dru; do cp $S/template/board.$e cu.$e; done
  log "routed board: dump, DRC, DC"
  docker run --rm -u 0 -v $OUT/routed:/w -w /w kicad/kicad:10.0 sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
  python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json > dc.log 2>&1
  python3 $TOOLS/loose.py $OUT/routed > loose.log 2>&1
  if [ $HOT = 1 ]; then
    log "routed board: seven hot loops"
    rm -f hot_parts.log
    for L in HL_3V3 "Port 1/HL_5V" "Port 1/HL_IN" "Port 1/HL_OUT" "Port 2/HL_5V" "Port 2/HL_IN" "Port 2/HL_OUT"; do
      PCB=$OUT/routed/cu.kicad_pcb python3 $T/floorplan/hot_score.py $C "$L" 2>&1 | grep "HL_" | tail -1 >> hot_parts.log
    done
    python3 - <<'P'
import json; out={}
for l in open('hot_parts.log'):
    k,v=l.split(' {',1); out[k]=json.loads('{'+v)
json.dump(out,open('hot.json','w'),indent=1)
P
    (cd $R && python3 tools/floorplan/power_gate.py $E/constraints.json $E/netlist.json spikes/02-seeded-faults/limits spikes/02-seeded-faults/limitsmap.json $OUT/routed/hot.json $S/template/hand_hot.json) > hot_gate.log 2>&1
  fi
fi
# 5. final.json
cd $OUT; python3 $TOOLS/final_json.py $SRC $OUT $RMIN $STRAPS
