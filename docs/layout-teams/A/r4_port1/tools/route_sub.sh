#!/bin/bash
# route_sub.sh <scorecard outdir> <workdir> [box=99,66,121.6,116] [MIN=30] [extra router options]
#   r4_port1 fast congestion screen: runs tools/router_sub.py (copy of tools/score/router.py + --box) on the outdir's
#   cu.kicad_pcb / drc.json, routing ONLY the edges with an end in the box or crossing it (the rest of the board is
#   left unrouted). Same router, same options as the scorecard (--softnets=GND,PACK_P,3V3) plus env ROUTER_OPTS.
#   Writes <workdir>/sub.log and <workdir>/sub_fail.txt (one line per failed edge), prints "SUB routed R failed F of N".
#   Default box = port 1 column (PD chip, cluster, stage, the I2C/CHG_INT runs to the charger); 99,66,121.6,125 adds the MCU.
#   The routed board is not kept (only the log) unless env KEEP=1 (then <workdir>/sub.kicad_pcb, ~5 MB).
set -o pipefail
H=$(cd "$(dirname "$0")" && pwd); R=/home/claude/repo; S=$R/tools/score
SRC=$(cd "$1" && pwd); W=$(mkdir -p "$2" && cd "$2" && pwd); BOX=${3:-99,66,121.6,116}; MIN=${4:-30}; shift 4 2>/dev/null; EXTRA="$*"
for e in kicad_pcb kicad_pro kicad_dru; do cp $SRC/cu.$e $W/cu.$e; done; cp $SRC/drc.json $W/drc.json; cp $H/router_sub.py $W/router_sub.py
t0=$(date +%s)
docker run --rm -u 0 -v $W:/w -v $S/pylib:/w/pylib -w /w kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout ${MIN}m python3 -u router_sub.py cu.kicad_pcb drc.json $( [ -n "$KEEP" ] && echo sub.kicad_pcb || echo /tmp/sub.kicad_pcb) --softnets=GND,PACK_P,3V3 --box='$BOX' $ROUTER_OPTS $EXTRA" > $W/sub.log 2>&1
grep "^  FAILED" $W/sub.log | sed 's/^  FAILED //' > $W/sub_fail.txt
N=$(grep -o 'sub-route: [0-9]*' $W/sub.log | grep -o '[0-9]*$')
m=$(grep -E '^routed [0-9]+ edges' $W/sub.log)
if [ -n "$m" ]; then echo "SUB $(echo $m | awk '{print "routed",$2,"failed",$4}') of $N in $(( ($(date +%s)-t0)/60 )) min  box=$BOX  ($W)"
else echo "SUB TIMED OUT at $MIN min: $(grep progress $W/sub.log | tail -1)  of $N  ($W)"; fi
cd $W && rm -f cu.kicad_pcb router_sub.py
