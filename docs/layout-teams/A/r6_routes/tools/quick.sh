#!/bin/bash
# quick.sh <base scorecard outdir> <new outdir> <fix.json[,fix2.json]> [--ghost] [--only=REGEX]
#   Copper-only screen: copies base bare board + planned spec.json (already split), applies r6 specfix, writes copper,
#   DRC, cu dump, DC loss/opens and pad-join check (same tools and arguments as score_board_r6.sh steps 2-3),
#   F/B renders. --ghost adds the blocked-edge screen (~4 min). --only=REGEX runs a quick router pass on those nets
#   only (route_only.log). Hot loops are not rerun (power copper of the loops is not touched by the cuts used here;
#   rerun score_board_r6.sh for a candidate).
set -o pipefail
R=/home/claude/repo; T=$R/tools; S=$T/score; C=$T/floorplan/example/monolith/constraints.json
B=$(cd "$1" && pwd); OUT=$(mkdir -p "$2" && cd "$2" && pwd); F=""; for f in ${3//,/ }; do F="$F,$(readlink -f $f)"; done; shift 3; GH=0; ONLY=""
for a in "$@"; do case $a in --ghost) GH=1;; --only=*) ONLY=${a#*=};; esac; done
cd $OUT
for e in kicad_pro kicad_dru; do cp $B/bare.$e bare.$e; cp $B/cu.$e cu.$e; done
cp $B/bare.kicad_pcb $B/bare.json $B/spec.json $B/placement.json . 2>/dev/null
cp $T/copper/cu_dump.py $T/copper/write_copper.py .; cp ${ROUTER:-$S/router.py} router.py
python3 $R/docs/layout-teams/A/r6_routes/tools/specfix.py spec.json ${F#,} > plan.log 2>&1; cat plan.log
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"
$K python3 write_copper.py bare.kicad_pcb spec.json cu.kicad_pcb > write.log 2>&1
$K sh -c "kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 $T/copper/dc_score.py cu.kicad_pcb cu.json $C dc.json > dc.log 2>&1
python3 $R/docs/layout-teams/A/r4_vbus/tools/pad_join_check.py cu.kicad_pcb cu.json $C pad_join.json --allow=$R/docs/layout-teams/A/r4_vbus/allow.json > pad_join.log 2>&1
for L in F.Cu B.Cu; do python3 $T/copper/render.py cu.kicad_pcb cu.json ${L%%.*}.png $L > /dev/null 2>&1; done
RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
[ $GH = 1 ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly" > ghost.log 2>&1
[ -n "$ONLY" ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json only.kicad_pcb --softnets=GND,PACK_P,3V3 '--only=$ONLY' $ROUTER_OPTS" > route_only.log 2>&1
python3 - <<'P'
import json, re, os
s = {}
dc = json.load(open('dc.json')); nets = dc.get('nets', dc)
s['loss_W'] = round(sum(v.get('loss_W', 0) for v in nets.values() if isinstance(v, dict)), 3)
s['power_open'] = {k: v.get('open') for k, v in nets.items() if isinstance(v, dict) and v.get('open')}
d = json.load(open('drc.json')); s['drc_errors'] = sum(1 for v in d['violations'] if v['severity'] == 'error')
s['drc_error_types'] = sorted({v['type'] for v in d['violations'] if v['severity'] == 'error'})
if os.path.exists('ghost.log'):
    g = open('ghost.log').read(); m = re.search(r'GHOST noway (\d+) of (\d+)', g)
    s['blocked_edges'] = f"{m.group(1)} of {m.group(2)}" if m else 'not finished'
    s['ghostfail'] = re.findall(r'^GHOSTFAIL (.*)$', g, re.M)
pj = json.load(open('pad_join.json')); s['pad_unjoined'] = pj['unjoined_not_allowed']
json.dump(s, open('quick.json', 'w'), indent=1); print('QUICK', json.dumps(s))
P
