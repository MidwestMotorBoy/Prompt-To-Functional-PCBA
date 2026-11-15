#!/bin/bash
# spec_ghost.sh <spec.json> <screened run dir> <out dir> [--only=<net regex>] [--no-ghost]
#   Quick look at a copper plan (team B, phase 2): writes the plan with one zone per outline on the screened run's
#   bare board (write_copper_split.py), KiCad DRC (drc.json; errors and unconnected count printed), cu_dump (cu.json),
#   then the shared router's ghost screen (ghost.log: blocked edges), optionally only for nets matching --only.
#   About 1 min + 2.5 min for the whole ghost screen. The out dir then works with zoom.py and pinlib.py look.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
SPEC=$(readlink -f "$1"); SRC=$(cd "$2" && pwd); OUT=$(mkdir -p "$3" && cd "$3" && pwd); shift 3; ONLY=""; GH=1
for a in "$@"; do case $a in --only=*) ONLY="$a";; --no-ghost) GH=0;; esac; done
cd $OUT; cp $SRC/bare.kicad_pcb bare.kicad_pcb; cp $SPEC spec.json; cp $TOOLS/write_copper_split.py . ; cp $R/tools/copper/cu_dump.py $S/router.py .
for e in kicad_pro kicad_dru; do cp $S/template/board.$e bare.$e; cp $S/template/board.$e cu.$e; done
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "python3 write_copper_split.py bare.kicad_pcb spec.json cu.kicad_pcb 2>&1 | grep -v swig | tail -1; kicad-cli pcb drc --severity-all --format json -o drc.json cu.kicad_pcb >/dev/null 2>&1; python3 cu_dump.py cu.kicad_pcb cu.json 2>&1 | grep -v swig"
python3 - <<'P'
import json; d = json.load(open('drc.json')); from collections import Counter
e = [v for v in d['violations'] if v['severity'] == 'error']
print('DRC errors %d %s; unconnected items %d' % (len(e), dict(Counter(v['type'] for v in e)), len(d.get('unconnected_items', []))))
for v in e[:8]: print('  ', v['type'], v['description'][:60], '|', ' / '.join(i['description'][:50] for i in v['items']))
P
[ $GH = 1 ] || exit 0
docker run --rm -u 0 -v $OUT:/w -w /w -v $S/pylib:/w/pylib kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly $ONLY" > ghost.log 2>&1
grep -E "^GHOST" ghost.log
