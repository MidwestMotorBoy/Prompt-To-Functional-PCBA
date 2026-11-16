#!/bin/bash
# score_rules.sh <outdir> [placement.json | board.kicad_pcb] --rules=<rules.json> [--route=MIN] [--no-hot] [--keep-copper]
#                [--plan="<plan_rules.py options>"] [--check=<script>]...
# Scorecard copy (docs/layout-teams/A/tools/score_board_best.sh) driven by one rules file instead of env variables:
#   copper = copper_rules/plan_rules.py --rules=<file> (+ --plan overrides) -> split_zones.py -> bus_layer.py (the
#   rules file's "bus_layer" steps) -> write_copper.py. Everything else is the scorecard unchanged: DRC, dc_score,
#   thermal, renders, hot loops (the list now comes from constraints.json hot_loops), blocked edges (ghost), full
#   route, routed-board DRC / power_open / loss when the route saved a board, score.json.
# rules.json keys used here (see the example rules files one folder up):
#   board.constraints, board.template, board.netlist, board.power_gate (power_gate.py limit args), board.hand_hot
#   router.softnets (default: the return net + the plan's bus nets, from spec.json), router.opts (default env ROUTER_OPTS)
#   checks: [script, ...]  extra checks, run like --check
# --check=<script>: run after scoring as `<script> <outdir>` (python if it ends in .py, else bash). Every stdout line
#   "CHECK {json}" is merged into score.json["checks"]. Every script in copper_rules/checks/*.sh|*.py runs too.
#   Use it for checks other workers add (e.g. a per-pad join check) without editing this script.
# No input = the hand placement (the template as it is), as in the stock scorecard.
set -o pipefail
R=/home/claude/repo; T=$R/tools; S=$T/score; P=$(cd "$(dirname "$0")" && pwd)
OUT=$(mkdir -p "$1" && cd "$1" && pwd); shift; IN=""; KEEP=0; RMIN=45; HOT=1; PLAN=""; RULES=""; CHECKS=()
for a in "$@"; do case $a in --keep-copper) KEEP=1;; --route=*) RMIN=${a#*=};; --no-hot) HOT=0;; --plan=*) PLAN=${a#*=};;
  --rules=*) RULES=$(readlink -f "${a#*=}");; --check=*) CHECKS+=("$(readlink -f "${a#*=}")");; *) IN=$(readlink -f "$a");; esac; done
[ -n "$RULES" ] || { echo "score_rules: --rules=<file.json> is required" >&2; exit 2; }
jget() { python3 -c "import json,sys; d=json.load(open('$RULES')); v=d
for k in '$1'.split('.'): v=v.get(k, {}) if isinstance(v, dict) else {}
print(v if isinstance(v, str) else ' '.join(map(str, v)) if isinstance(v, list) else '')"; }
C=$R/$(jget board.constraints); [ -f "$C" ] || { echo "score_rules: board.constraints missing in the rules file" >&2; exit 2; }
TPL=$R/$(jget board.template); [ -f "$TPL" ] || TPL=$S/template/board.kicad_pcb; TPLD=$(dirname $TPL); TPLS=$(basename $TPL .kicad_pcb)
NL=$R/$(jget board.netlist); [ -f "$NL" ] || NL=$(dirname $C)/netlist.json
cd $OUT; cp "$RULES" rules.json; for e in kicad_pro kicad_dru; do cp $TPLD/$TPLS.$e bare.$e; cp $TPLD/$TPLS.$e cu.$e; done
cp $T/floorplan/apply_placement.py $T/copper/cu_dump.py $T/copper/write_copper.py $S/router.py .
pylib() { [ -d $S/pylib/scipy ] || python3 -m pip install -q --target $S/pylib --python-version 3.13 --only-binary=:all: --platform manylinux2014_x86_64 numpy scipy pillow 2>&1 | grep -v WARNING | tail -1; }
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"
log() { echo "[score] $*" >&2; }
docker images >/dev/null 2>&1 || { log "docker daemon not reachable (never start or stop it from here)"; exit 3; }

# 1. the board to score
if [ -z "$IN" ]; then cp $TPL in.kicad_pcb; $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip >/dev/null 2>&1
elif [[ $IN == *.json ]]; then cp $TPL in.kicad_pcb; cp $IN placement.json; $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb placement.json --strip > apply.log 2>&1 || { log "apply failed"; tail -3 apply.log; }
else cp $IN in.kicad_pcb; if [ $KEEP = 1 ]; then cp in.kicad_pcb cu.kicad_pcb; else $K python3 apply_placement.py in.kicad_pcb bare.kicad_pcb --strip >/dev/null 2>&1; fi; fi
rm -f in_bare.kicad_pcb

# 2. power copper: rules planner, split, protected bus layer, write
if [ $KEEP = 0 ]; then
  $K python3 cu_dump.py bare.kicad_pcb bare.json 2>&1 | grep -v swig
  python3 $P/plan_rules.py bare.json $C spec.json --rules=rules.json $PLAN > plan.log 2>&1 || { log "planner failed"; tail -5 plan.log; }
  python3 $P/split_zones.py spec.json >> plan.log 2>&1
  python3 $P/bus_layer.py spec.json bare.json $C --rules=rules.json --router=router.py >> plan.log 2>&1 || { log "bus_layer failed"; tail -3 plan.log; }
  $K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1
fi
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
SOFT=$(jget router.softnets | tr ' ' ',')
[ -z "$SOFT" ] && SOFT=$(python3 - $C <<'P'
import json, sys
C = json.load(open(sys.argv[1])); S = json.load(open('spec.json'))
ret = []
for hl in C.get('hot_loops', {}).values():
    if hl['ret'] not in ret: ret.append(hl['ret'])
print(','.join(ret + [b for b in S.get('report', {}).get('buses', []) if b not in ret]))
P
)
RO=$(jget router.opts); RO=${RO:-$ROUTER_OPTS}; echo "$SOFT" > softnets.txt

# 3. DC loss and power opens, thermal
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json --lossmap=loss.npz > dc.log 2>&1
python3 $T/copper/thermal.py cu.kicad_pcb cu.json $C loss.npz thermal.json > thermal.log 2>&1
for L in F.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done

# 4. hot loops, one by one (the list comes from constraints.json)
if [ $HOT = 1 ]; then
  rm -f hot_parts.log
  python3 -c "import json; [print(k) for k in json.load(open('$C')).get('hot_loops', {})]" > hot_list.txt
  while IFS= read -r L; do
    PCB=cu.kicad_pcb python3 $T/floorplan/hot_score.py $C "$L" 2>&1 | grep -F ' {"' | tail -1 >> hot_parts.log
  done < hot_list.txt
  python3 - <<'P'
import json; out={}
for l in open('hot_parts.log'):
    if ' {' not in l: continue
    k,v=l.split(' {',1); out[k]=json.loads('{'+v)
json.dump(out,open('hot.json','w'),indent=1)
P
  PG=$(jget board.power_gate); HH=$R/$(jget board.hand_hot); [ -f "$HH" ] || HH=""
  [ -n "$PG" ] && (cd $R && python3 tools/floorplan/power_gate.py $C $NL $PG $OUT/hot.json $HH) > hot_gate.log 2>&1
fi

# 5. routing: blocked count (no path even with no other signal routed), then the full trial route
pylib
RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
$RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=$SOFT --ghostonly" > ghost.log 2>&1
[ "$RMIN" != 0 ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout ${RMIN}m python3 -u router.py cu.kicad_pcb drc.json routed.kicad_pcb --softnets=$SOFT $RO" > route.log 2>&1
if [ "$RMIN" != 0 ] && [ -f routed.kicad_pcb ]; then
  $K sh -c "python3 cu_dump.py routed.kicad_pcb routed.json 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o drc_routed.json routed.kicad_pcb >/dev/null 2>&1"
  python3 $T/copper/dc_score.py routed.kicad_pcb routed.json $C dc_routed.json > dc_routed.log 2>&1
  for L in F.Cu B.Cu; do python3 $T/copper/render.py routed.kicad_pcb routed.json routed_${L%%.*}.png $L > /dev/null 2>&1; done
fi

# 6. summary (as score_board_best.sh)
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
if os.path.exists('dc_routed.json'):
    dr = json.load(open('dc_routed.json')); nr = dr.get('nets', dr)
    s['routed_loss_W'] = round(sum(v.get('loss_W', 0) for v in nr.values() if isinstance(v, dict)), 3)
    s['routed_power_open'] = {k: v.get('open') for k, v in nr.items() if isinstance(v, dict) and v.get('open')}
if os.path.exists('drc_routed.json'):
    d2 = json.load(open('drc_routed.json')); s['routed_drc_errors'] = sum(1 for v in d2['violations'] if v['severity'] == 'error'); s['routed_unconnected'] = len(d2.get('unconnected_items', []))
json.dump(s, open('score.json', 'w'), indent=1)
P

# 7. extra checks (--check, rules.json "checks", copper_rules/checks/*)
for c in $(jget checks); do CHECKS+=("$R/$c"); done
for c in $P/checks/*.sh $P/checks/*.py; do [ -f "$c" ] && CHECKS+=("$c"); done
rm -f checks.log
for c in "${CHECKS[@]}"; do
  log "check $c"
  if [[ $c == *.py ]]; then python3 "$c" "$OUT"; else bash "$c" "$OUT"; fi >> checks.log 2>&1 || echo "CHECK {\"$(basename $c)\": \"failed to run\"}" >> checks.log
done
python3 - <<'P'
import json, os
s = json.load(open('score.json'))
if os.path.exists('checks.log'):
    ch = {}
    for l in open('checks.log'):
        if l.startswith('CHECK '):
            try: ch.update(json.loads(l[6:]))
            except ValueError: pass
    if ch: s['checks'] = ch
json.dump(s, open('score.json', 'w'), indent=1)
print('SCORE', json.dumps(s))
P
