#!/bin/bash
# quick.sh <outdir> <placement.json (scorecard format)> [--plan="..."] [--noghost] [--hot]   (pdfix copy of stage/quick.sh: ghost ON by default, port zooms)
#   Scorecard steps 1-4 only (apply, plan copper, write, DRC, DC loss, renders); copied from tools/score/score_board.sh
#   for fast stage iteration (~1-2 min). --ghost adds the blocked-edge count, --hot the hot-loop solve (one at a time).
#   Not the scorecard: final numbers come from tools/score/score_board.sh.
R=/home/claude/repo; T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith; C=$E/constraints.json
OUT=$(mkdir -p "$1" && cd "$1" && pwd); IN=$(readlink -f "$2"); shift 2; PLAN=""; GH=1; HOT=0
for a in "$@"; do case $a in --plan=*) PLAN=${a#*=};; --noghost) GH=0;; --hot) HOT=1;; esac; done
cd $OUT; for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
cp $T/floorplan/apply_placement.py $T/copper/cu_dump.py $T/copper/write_copper.py $S/router.py .
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"
cp $S/template/board.kicad_pcb in.kicad_pcb; cp $IN placement.json
$K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb placement.json --strip > apply.log 2>&1 || { echo "apply failed"; tail -3 apply.log; }
$K python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig
python3 $T/copper/plan_copper.py bare.json $C spec.json $PLAN > plan.log 2>&1
$K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json --lossmap=loss.npz > dc.log 2>&1
if [ $GH = 1 ]; then RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
  $RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly" > ghost.log 2>&1; fi
if [ $HOT = 1 ]; then rm -f hot_parts.log
  for L in "Port 1/HL_IN" "Port 1/HL_OUT" "Port 2/HL_IN" "Port 2/HL_OUT"; do PCB=cu.kicad_pcb python3 $T/floorplan/hot_score.py $C "$L" 2>&1 | grep "HL_" | tail -1 >> hot_parts.log; done; fi
python3 - <<'P'
import json, re, os
dc = json.load(open('dc.json')); nets = dc.get('nets', dc)
s = {'loss_W': round(sum(v.get('loss_W', 0) for v in nets.values() if isinstance(v, dict)), 3)}
s['power_open'] = {k: v.get('open') for k, v in nets.items() if isinstance(v, dict) and v.get('open')}
d = json.load(open('drc.json')); s['drc_errors'] = sum(1 for v in d['violations'] if v['severity'] == 'error')
for l in open('plan.log'):
    if l.startswith('hot loops'):
        h = json.loads(l[len('hot loops '):]); s['closes'] = {k.replace('USB ', ''): v['shape'].split(', ')[2] if 'closes' in v['shape'] else v['shape'] for k, v in h.items() if 'Port' in k}
    if l.startswith('return pads'): s['ret_left'] = json.loads(l[len('return pads '):])['left_to_router']
if os.path.exists('ghost.log'):
    m = re.search(r'GHOST noway (\d+) of (\d+)', open('ghost.log').read()); s['blocked'] = f"{m.group(1)} of {m.group(2)}" if m else '?'
if os.path.exists('hot_parts.log'): s['hot'] = open('hot_parts.log').read()
json.dump(s, open('quick.json', 'w'), indent=1); print(json.dumps({k:v for k,v in s.items() if k!='closes'}))
P
Z=$R/docs/layout-teams/A/rebuild/tools
python3 $Z/zoom.py $OUT p1.png 99,68,113,89 F.Cu 40 >/dev/null; python3 $Z/zoom.py $OUT p2.png 78,68,99,89 F.Cu 40 >/dev/null
[ -f ghost.log ] && V=-v python3 $Z/blocked.py $OUT > blocked.txt && head -1 blocked.txt
