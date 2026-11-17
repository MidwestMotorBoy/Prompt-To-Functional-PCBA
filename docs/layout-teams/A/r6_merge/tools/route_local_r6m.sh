#!/bin/bash
# r6_caps copy: + env CAPFIX="<capfix.py options>" (r6_caps/tools/capfix.py after BUS4B, before write_copper) and allpad_check.py
#   (every pad of every power net on the main piece; allpad.json / allpad_routed.json, score.json allpad_off / routed_allpad_off)
# r5_merge copy of A/tools/route_local.sh + pad_join_check on the routed board (pad_join_routed.json, routed_pad_unjoined)
# route_local.sh <scorecard outdir made with --route=0> [MIN=150]
#   Adds the local full route to an existing scorecard outdir without redoing copper/hot loops: runs the scorecard's
#   router line (same options), then routed-board DRC + dc_score + renders, and rewrites score.json with the
#   route and routed_* fields (the tail of tools/score_board_best.sh, unchanged). env ROUTER_OPTS as there.
set -o pipefail
R=/home/claude/repo; T=$R/tools; S=$T/score; E=$T/floorplan/example/monolith; C=$E/constraints.json
OUT=$(cd "$1" && pwd); RMIN=${2:-150}; cd $OUT
D="docker run --rm -u 0 -v $OUT:/w -w /w"; K="$D kicad/kicad:10.0"; RUN="$D -v $S/pylib:/w/pylib kicad/kicad:10.0"
[ "$RMIN" != 0 ] && $RUN sh -c "PYTHONPATH=/w/pylib timeout ${RMIN}m python3 -u router.py cu.kicad_pcb drc.json routed.kicad_pcb --softnets=GND,PACK_P,3V3 $ROUTER_OPTS" > route.log 2>&1
if [ "$RMIN" != 0 ] && [ -f routed.kicad_pcb ]; then
  $K sh -c "python3 cu_dump.py routed.kicad_pcb routed.json 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o drc_routed.json routed.kicad_pcb >/dev/null 2>&1"
  python3 $T/copper/dc_score.py routed.kicad_pcb routed.json $C dc_routed.json > dc_routed.log 2>&1
  python3 /home/claude/repo/docs/layout-teams/A/r4_vbus/tools/pad_join_check.py routed.kicad_pcb routed.json $C pad_join_routed.json --allow=/home/claude/repo/docs/layout-teams/A/r4_vbus/allow.json > pad_join_routed.log 2>&1
  python3 /home/claude/repo/docs/layout-teams/A/r6_caps/tools/allpad_check.py routed.kicad_pcb routed.json $C allpad_routed.json --allow=/home/claude/repo/docs/layout-teams/A/r4_vbus/allow.json > allpad_routed.log 2>&1
  for L in F.Cu B.Cu; do python3 $T/copper/render.py routed.kicad_pcb routed.json routed_${L%%.*}.png $L > /dev/null 2>&1; done
fi

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
if os.path.exists('dc_routed.json'):
    dr = json.load(open('dc_routed.json')); nr = dr.get('nets', dr)
    s['routed_loss_W'] = round(sum(v.get('loss_W', 0) for v in nr.values() if isinstance(v, dict)), 3)
    s['routed_power_open'] = {k: v.get('open') for k, v in nr.items() if isinstance(v, dict) and v.get('open')}
if os.path.exists('drc_routed.json'):
    d2 = json.load(open('drc_routed.json')); s['routed_drc_errors'] = sum(1 for v in d2['violations'] if v['severity'] == 'error'); s['routed_unconnected'] = len(d2.get('unconnected_items', []))
if os.path.exists('pad_join.json'):
    pj = json.load(open('pad_join.json')); s['pad_unjoined'] = pj['unjoined_not_allowed']; s['pad_unjoined_all'] = pj['unjoined']
if os.path.exists('pad_join_routed.json'):
    pj = json.load(open('pad_join_routed.json')); s['routed_pad_unjoined'] = pj['unjoined_not_allowed']
if os.path.exists('allpad_routed.json') and os.path.exists('pad_join_routed.json'):
    s['routed_allpad_off'] = json.load(open('allpad_routed.json'))['off_main_not_allowed']
if os.path.exists('drc_routed.json'):
    import collections; d2 = json.load(open('drc_routed.json')); cnt = collections.Counter()
    for u in d2.get('unconnected_items', []):
        for n in set(re.findall(r'\[(.*?)\]', ' '.join(i['description'] for i in u['items']))): cnt[n] += 1
    s['routed_unconnected_power'] = {k: v for k, v in cnt.items() if k in ('3V3', 'PACK_P', 'GND') or 'PPHV' in k or 'PP5V' in k or 'VBUS' in k}
json.dump(s, open('score.json', 'w'), indent=1)
print('SCORE', json.dumps(s))
P
