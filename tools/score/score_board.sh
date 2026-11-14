#!/bin/bash
# score_board.sh <outdir> [placement.json | board.kicad_pcb] [options]
#   The one scorecard every Monolith layout is judged by. Writes <outdir>/score.json and prints a summary.
#   input:  placement.json  {ref: [x, y, angle, ...]} applied to the bare template (hand placement, no copper)
#           board.kicad_pcb a placed board; its copper is stripped unless --keep-copper
#           (none)          the hand placement itself (the reference)
#   options: --keep-copper   score the board's own copper (skip the copper planner)
#            --route=MIN     full trial-route cap in minutes (default 45; 0 = skip the full route)
#            --no-hot        skip the hot-loop solve (5-10 min)
#            --plan="..."    extra plan_copper.py options
#   Needs: docker with image kicad/kicad:10.0, python3 with numpy scipy shapely numba on the host.
#   Reference (hand placement, generated copper): 391 of 448 routed in 18 min, 1.36 W, Port 1 PP5V open at U401.
set -o pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith; C=$E/constraints.json
OUT=$(mkdir -p "$1" && cd "$1" && pwd); shift; IN=""; KEEP=0; RMIN=45; HOT=1; PLAN=""
for a in "$@"; do case $a in --keep-copper) KEEP=1;; --route=*) RMIN=${a#*=};; --no-hot) HOT=0;; --plan=*) PLAN=${a#*=};; *) IN=$(readlink -f "$a");; esac; done
cd $OUT; for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
cp $T/floorplan/apply_placement.py $T/copper/cu_dump.py $T/copper/write_copper.py $S/router.py .
pylib() { [ -d $S/pylib/scipy ] || python3 -m pip install -q --target $S/pylib --python-version 3.13 --only-binary=:all: --platform manylinux2014_x86_64 numpy scipy pillow 2>&1 | grep -v WARNING | tail -1; }
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"
log() { echo "[score] $*" >&2; }
docker images >/dev/null 2>&1 || { rm -f /var/run/docker.pid /var/run/docker.sock; (dockerd > /tmp/dockerd.log 2>&1 &); for i in $(seq 30); do sleep 2; docker images >/dev/null 2>&1 && break; done; }
docker image inspect kicad/kicad:10.0 >/dev/null 2>&1 || docker pull -q kicad/kicad:10.0

# 1. the board to score
if [ -z "$IN" ]; then cp $S/template/board.kicad_pcb in.kicad_pcb; $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip >/dev/null 2>&1
elif [[ $IN == *.json ]]; then cp $S/template/board.kicad_pcb in.kicad_pcb; cp $IN placement.json; $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb placement.json --strip > apply.log 2>&1 || { log "apply failed"; tail -3 apply.log; }
else cp $IN in.kicad_pcb; if [ $KEEP = 1 ]; then cp in.kicad_pcb cu.kicad_pcb; else $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip >/dev/null 2>&1; fi; fi
rm -f in_bare.kicad_pcb

# 2. power copper (planned on the bare board unless kept), DRC, dumps
if [ $KEEP = 0 ]; then
  $K python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig
  python3 $T/copper/plan_copper.py bare.json $C spec.json $PLAN > plan.log 2>&1
  $K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1
fi
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"

# 3. DC loss and power opens, thermal
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json --lossmap=loss.npz > dc.log 2>&1
python3 $T/copper/thermal.py cu.kicad_pcb cu.json $C loss.npz thermal.json > thermal.log 2>&1
for L in F.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done

# 4. hot loops
if [ $HOT = 1 ]; then
  rm -f hot_parts.log
  for L in HL_3V3 "Port 1/HL_5V" "Port 1/HL_IN" "Port 1/HL_OUT" "Port 2/HL_5V" "Port 2/HL_IN" "Port 2/HL_OUT"; do
    PCB=cu.kicad_pcb python3 $T/floorplan/hot_score.py $C "$L" 2>&1 | grep "HL_" | tail -1 >> hot_parts.log
  done
  python3 - <<'P'
import json; out={}
for l in open('hot_parts.log'):
    k,v=l.split(' {',1); out[k]=json.loads('{'+v)
json.dump(out,open('hot.json','w'),indent=1)
P
  (cd $R && python3 tools/floorplan/power_gate.py $E/constraints.json $E/netlist.json spikes/02-seeded-faults/limits spikes/02-seeded-faults/limitsmap.json $OUT/hot.json $S/template/hand_hot.json) > hot_gate.log 2>&1
fi

# 5. routing: blocked count (no path even with no other signal routed), then the full trial route
pylib
RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
$RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly" > ghost.log 2>&1
[ "$RMIN" != 0 ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout ${RMIN}m python3 -u router.py cu.kicad_pcb drc.json routed.kicad_pcb --softnets=GND,PACK_P,3V3" > route.log 2>&1

# 6. summary
python3 - $RMIN <<'P'
import json, re, sys, os
s = {}
dc = json.load(open('dc.json')); nets = dc.get('nets', dc)
s['loss_W'] = round(sum(v.get('loss_W', 0) for v in nets.values() if isinstance(v, dict)), 3)
s['power_open'] = {k: v.get('open') for k, v in nets.items() if isinstance(v, dict) and v.get('open')}
d = json.load(open('drc.json'))
s['drc_errors'] = sum(1 for v in d['violations'] if v['severity'] == 'error')
s['unrouted_signal_items'] = len(d.get('unconnected_items', []))
if os.path.exists('hot_gate.log'):
    g = open('hot_gate.log').read(); m = re.search(r'(\d+) of (\d+) hot loops pass.*?([\d.]+) nH', g)
    s['hot_loops'] = f"{m.group(1)} of {m.group(2)} pass, {m.group(3)} nH" if m else 'see hot_gate.log'
g = open('ghost.log').read(); m = re.search(r'GHOST noway (\d+) of (\d+)', g)
s['blocked_edges'] = f"{m.group(1)} of {m.group(2)}" if m else 'not finished'
if sys.argv[1] != '0':
    r = open('route.log').read(); m = re.search(r'^routed (\d+) edges, (\d+) failed', r, re.M); e = re.search(r'edges to route: (\d+)', r)
    if m: s['route'] = f"{m.group(1)} of {e.group(1) if e else '?'} routed, {m.group(2)} failed"
    else:
        p = re.findall(r'routed (\d+), failing (\d+)', r)
        s['route'] = f"TIMED OUT at {sys.argv[1]} min; last {p[-1][0]} routed, {p[-1][1]} failing of {e.group(1) if e else '?'}" if p else 'no result'
json.dump(s, open('score.json', 'w'), indent=1)
print('SCORE', json.dumps(s))
P
