#!/bin/bash
# build_r4.sh <workdir> [override.json ...]
#   team A best build (final/build.sh with final/overrides/*.json) plus extra override files applied last, in the
#   order given (default r4_port1/overrides/50_r4_port1.json). Writes <workdir>/placement.json (scorecard format).
set -e
H=$(cd "$(dirname "$0")/.." && pwd); A=$(cd "$H/.." && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd); shift
OVS=(); for f in "$@"; do OVS+=("$(readlink -f "$f")"); done; [ ${#OVS[@]} = 0 ] && OVS=("$H/overrides/50_r4_port1.json")
mkdir -p $W/ov; cd $W/ov && rm -f ./*.json
cp $A/final/overrides/*.json $W/ov/
i=0; for f in "${OVS[@]}"; do i=$((i+1)); cp "$f" "$W/ov/5${i}_$(basename "$f")"; done
ls $W/ov
"$A/final/build.sh" "$W/b" --overrides=$W/ov --ref=$A/final/deliver/best_placement_gu.json > $W/build.log 2>&1 || { tail -20 $W/build.log; exit 1; }
grep -E "CHECK|placed|errors|differ" $W/build.log | tail -5
cp $W/b/placement.json $W/placement.json; cp $W/b/placement_gu.json $W/placement_gu.json
python3 - "$W/placement.json" "$A/best_placement.json" <<'P'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
d = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
print("[build_r4] %d entries differ from best_placement.json:" % len(d), d)
P
