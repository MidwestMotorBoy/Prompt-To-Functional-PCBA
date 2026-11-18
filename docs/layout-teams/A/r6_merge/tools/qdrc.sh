#!/bin/bash
# qdrc.sh <base outdir> <new outdir> <fix.json> : quick.sh + list of DRC errors and unconnected items (team A r6_merge)
A=/home/claude/repo/docs/layout-teams/A
$A/r6_routes/tools/quick.sh "$1" "$2" "$3" 2>&1 | grep QUICK | cut -c1-400
python3 - "$2" <<'P'
import json,sys
d=json.load(open(sys.argv[1]+'/drc.json'))
print('unconnected',len(d['unconnected_items']))
for u in d['unconnected_items']: print(' UNC',' | '.join(i['description']+' @%.2f,%.2f'%(i['pos']['x'],i['pos']['y']) for i in u['items']))
for v in d['violations']:
    if v['severity']=='error': print(' ERR',v['description'][:110],[(i['description'][:60],i['pos']['x'],i['pos']['y']) for i in v['items']])
P
