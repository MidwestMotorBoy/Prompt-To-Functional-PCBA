#!/bin/bash
# score_part.sh <outdir> <placed board.kicad_pcb> <constraints_part.json> [--hot="loop,loop"] [--route=MIN] [--plan="..."]
#   Team copy of tools/score/score_board.sh for a PARTIAL board (made by apply_b.py --partial): the same steps
#   (strip, copper plan, write copper, DRC, dumps, DC loss, thermal, renders, blocked edges, optional route),
#   but with the given filtered constraints and only the hot loops named (default: none). Summary in score.json with
#   "partial": true. Called by screen.sh; not meant to be run by hand.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith
OUT=$(mkdir -p "$1" && cd "$1" && pwd); IN=$(readlink -f "$2"); C=$(readlink -f "$3"); shift 3; RMIN=0; HOT=""; PLAN=""
for a in "$@"; do case $a in --route=*) RMIN=${a#*=};; --hot=*) HOT=${a#*=};; --plan=*) PLAN=${a#*=};; esac; done
cd $OUT; for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
cp $T/floorplan/apply_placement.py $T/copper/cu_dump.py $T/copper/write_copper.py $S/router.py .
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"
log() { echo "[score_part] $*" >&2; }
[ "$IN" = "$OUT/in.kicad_pcb" ] || cp $IN in.kicad_pcb
$K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip > strip.log 2>&1 || { log "strip failed"; tail -3 strip.log; }
$K python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig
python3 $T/copper/plan_copper.py bare.json $C spec.json $PLAN > plan.log 2>&1 || log "plan_copper exit $? (see plan.log)"
$K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1 || log "write_copper failed (see write.log)"
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json --lossmap=loss.npz > dc.log 2>&1 || log "dc_score exit $?"
python3 $T/copper/thermal.py cu.kicad_pcb cu.json $C loss.npz thermal.json > thermal.log 2>&1
for L in F.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done
rm -f hot_parts.log hot.json hot_gate.log
if [ -n "$HOT" ]; then
  IFS=',' read -ra LOOPS <<< "$HOT"
  for L in "${LOOPS[@]}"; do
    PCB=cu.kicad_pcb python3 $T/floorplan/hot_score.py $C "$L" 2>&1 | grep "HL_" | tail -1 >> hot_parts.log
  done
  python3 - <<'P'
import json; out={}
for l in open('hot_parts.log'):
    if ' {' not in l: continue
    k,v=l.split(' {',1); out[k]=json.loads('{'+v)
json.dump(out,open('hot.json','w'),indent=1)
P
  (cd $R && python3 tools/floorplan/power_gate.py $C $E/netlist.json spikes/02-seeded-faults/limits spikes/02-seeded-faults/limitsmap.json $OUT/hot.json $S/template/hand_hot.json) > hot_gate.log 2>&1
fi
[ -d $S/pylib/scipy ] || log "no $S/pylib (run the shared scorecard once to install it)"
RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
$RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly" > ghost.log 2>&1
[ "$RMIN" != 0 ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout ${RMIN}m python3 -u router.py cu.kicad_pcb drc.json routed.kicad_pcb --softnets=GND,PACK_P,3V3" > route.log 2>&1
python3 - $RMIN <<'P'
import json, re, sys, os
s = {"partial": True}
dc = json.load(open('dc.json')); nets = dc.get('nets', dc)
s['loss_W'] = round(sum(v.get('loss_W', 0) for v in nets.values() if isinstance(v, dict)), 3)
s['power_open'] = {k: v.get('open') for k, v in nets.items() if isinstance(v, dict) and v.get('open')}
d = json.load(open('drc.json'))
s['drc_errors'] = sum(1 for v in d['violations'] if v['severity'] == 'error')
s['unrouted_signal_items'] = len(d.get('unconnected_items', []))
if os.path.exists('hot_gate.log'):
    g = open('hot_gate.log').read(); m = re.search(r'(\d+) of (\d+) hot loops pass.*?([\d.]+) nH', g)
    s['hot_loops'] = f"{m.group(1)} of {m.group(2)} pass, {m.group(3)} nH" if m else 'see hot_gate.log'
    try: s['hot_loop_nH'] = {r['loop']: r.get('loop_total_nH') for r in json.load(open('hot_gate.json'))}
    except Exception: pass
g = open('ghost.log').read(); m = re.search(r'GHOST noway (\d+) of (\d+)', g)
s['blocked_edges'] = f"{m.group(1)} of {m.group(2)}" if m else 'not finished'
if sys.argv[1] != '0':
    r = open('route.log').read(); m = re.search(r'^routed (\d+) edges, (\d+) failed', r, re.M); e = re.search(r'edges to route: (\d+)', r)
    if m: s['route'] = f"{m.group(1)} of {e.group(1) if e else '?'} routed, {m.group(2)} failed"
    else:
        p = re.findall(r'routed (\d+), failing (\d+)', r)
        s['route'] = f"TIMED OUT at {sys.argv[1]} min; last {p[-1][0]} routed, {p[-1][1]} failing of {e.group(1) if e else '?'}" if p else 'no result'
if os.path.exists('refs_present.json'): s['refs'] = json.load(open('refs_present.json'))
json.dump(s, open('score.json', 'w'), indent=1)
print('SCORE', json.dumps({k: v for k, v in s.items() if k != 'refs'}))
P
