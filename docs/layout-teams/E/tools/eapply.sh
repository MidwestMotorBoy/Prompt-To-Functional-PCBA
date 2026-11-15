#!/bin/bash
# eapply.sh <dir> <base board name> <routes.json> <out board name>   base + routes -> out.kicad_pcb, out.drc.json, out.e.json
set -e
HERE=$(cd "$(dirname "$0")" && pwd); O=$(cd "$1" && pwd); B=$2; RJ=$(readlink -f $3); N=$4
cp $HERE/eapply.py $HERE/edump.py $O/; [ "$RJ" = "$O/$N.routes.json" ] || cp $RJ $O/$N.routes.json
for e in kicad_pro kicad_dru; do cp $O/$B.$e $O/$N.$e; done
docker run --rm -u 0 -v $O:/w -w /w kicad/kicad:10.0 sh -c "python3 eapply.py $B.kicad_pcb $N.routes.json $N.kicad_pcb 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o $N.drc.json $N.kicad_pcb >/dev/null 2>&1; python3 edump.py $N.kicad_pcb $N.e.json 2>&1 | grep -v swig"
python3 - $O/$N.drc.json <<'P'
import json, sys, collections
d = json.load(open(sys.argv[1]))
e = [v for v in d["violations"] if v["severity"] == "error"]
print("DRC errors %d %s, unconnected %d" % (len(e), dict(collections.Counter(v["type"] for v in e)), len(d["unconnected_items"])))
P
