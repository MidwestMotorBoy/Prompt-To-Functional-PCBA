#!/bin/bash
# stage_route.sh <dir with cu.kicad_pcb/.kicad_pro/.kicad_dru> <pass name> <input board> <only-regex or -> [router options]
#   One tier of the lead's routing plan: route only the nets matching the regex on top of the input board (all copper
#   already there stays), write <pass>.kicad_pcb and <pass>.drc.json in the same dir. "-" routes everything left.
#   Later tiers cannot pull the copper of earlier tiers, so the important nets get the direct paths.
set -e
O=$(cd "$1" && pwd); P=$2; IN=$3; RX=$4; shift 4
S=$(cd "$(dirname "$0")/../../../../tools/score" && pwd)
cp $S/router.py $O/; for e in kicad_pro kicad_dru; do [ -f $O/$P.$e ] || cp $O/cu.$e $O/$P.$e; [ -f $O/${IN%.kicad_pcb}.$e ] || cp $O/cu.$e $O/${IN%.kicad_pcb}.$e; done
K="docker run --rm -u 0 -v $O:/w -w /w -v $S/pylib:/w/pylib kicad/kicad:10.0"
$K sh -c "kicad-cli pcb drc --severity-all --format json -o $P.in.drc.json $IN >/dev/null 2>&1"
ONLY=""; [ "$RX" != "-" ] && ONLY="--only=$RX"
$K sh -c "PYTHONPATH=/w/pylib python3 -u router.py $IN $P.in.drc.json $P.kicad_pcb --softnets=GND,PACK_P,3V3 '$ONLY' $*" > $O/$P.log 2>&1 || true
$K sh -c "kicad-cli pcb drc --severity-all --format json -o $P.drc.json $P.kicad_pcb >/dev/null 2>&1"
grep -v progress $O/$P.log | tail -n 12
python3 - $O/$P.drc.json <<'E'
import json,sys; d=json.load(open(sys.argv[1])); print("after pass: DRC errors", sum(v.get("severity")=="error" for v in d.get("violations",[])), "unconnected", len(d.get("unconnected_items",[])))
E
