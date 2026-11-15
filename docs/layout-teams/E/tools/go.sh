#!/bin/bash
# go.sh <run name> [moves.txt]    placement moves -> scorecard (copper plan, DRC, loss; no route) -> dump for the router
HERE=$(cd "$(dirname "$0")" && pwd); M=${2:-$HERE/../place/moves.txt}; OUT=/home/claude/runs/$1; mkdir -p $OUT
python3 $HERE/eplace.py ${BASE:-/home/claude/runs/handP/cu.e.json} $M $OUT/placement.json || exit 1
cp $M $OUT/moves.txt; source $HERE/recipe.sh
bash $HERE/sc.sh $1 $OUT/placement.json --no-ghost "${@:3}" > $OUT/sc.log 2>&1
cp $HERE/edump.py $OUT/; docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "python3 edump.py cu.kicad_pcb cu.e.json 2>&1 | grep -v swig"
python3 - $OUT $HERE <<'P'
import sys, json
sys.path.insert(0, sys.argv[2] + "/../../../../tools/copper")
from roles import Design
D = Design(sys.argv[1] + "/bare.json", sys.argv[2] + "/../../../../tools/floorplan/example/monolith/constraints.json")
T = {}
for net in list(D.power) + list(D.ret):
    T[net] = [dict(ref=g["ref"], pads=[p["num"] for p in g["pads"]], kind=g["kind"], current_a=(g["current_a"] if g["current_a"] != float("inf") else 10.0)) for g in D.terminals(net)]
json.dump(T, open(sys.argv[1] + "/terms.json", "w"), indent=0)
P
cat $OUT/score.json
