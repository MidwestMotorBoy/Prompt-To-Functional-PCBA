#!/bin/bash
# rescore.sh <screened run dir> <out dir> [--no-hot] [--route=45] [--no-straps]
#   Team B: steps 4 and 5 of tools/final_route.sh alone (the same commands): the routed-board check (DRC, cu_dump, DC,
#   loose, seven hot loops, power gate) of <out>/finished.kicad_pcb (or routed.kicad_pcb) into <out>/routed/, then
#   final.json. For a finishing pass run by hand (bash tools/finish.sh <out> ...) after final_route.sh. --route and
#   --no-straps only fill the same fields of final.json as the original run.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith; C=$E/constraints.json
SRC=$(cd "$1" && pwd); OUT=$(cd "$2" && pwd); shift 2; HOT=1; RMIN=45; STRAPS=1
for a in "$@"; do case $a in --no-hot) HOT=0;; --route=*) RMIN=${a#*=};; --no-straps) STRAPS=0;; *) echo "unknown option $a"; exit 2;; esac; done
log() { echo "[rescore] $(date -u +%H:%M:%S) $*" >&2; }
BOARD=$OUT/routed.kicad_pcb; [ -f $OUT/finished.kicad_pcb ] && BOARD=$OUT/finished.kicad_pcb
mkdir -p $OUT/routed; cd $OUT/routed; cp $BOARD cu.kicad_pcb; cp $T/copper/cu_dump.py .
for e in kicad_pro kicad_dru; do cp $S/template/board.$e cu.$e; done
log "$(basename $BOARD): dump, DRC, DC"
docker run --rm -u 0 -v $OUT/routed:/w -w /w kicad/kicad:10.0 sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json > dc.log 2>&1
python3 $TOOLS/loose.py $OUT/routed > loose.log 2>&1
if [ $HOT = 1 ]; then
  log "seven hot loops"
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
else rm -f hot.json hot_gate.json hot_parts.log
fi
cd $OUT; python3 $TOOLS/final_json.py $SRC $OUT $RMIN $STRAPS
