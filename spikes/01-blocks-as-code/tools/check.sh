#!/bin/bash
# check.sh <sheet dir> <project> <netlist.json> : KiCad's own netlist of the drawn sheets must equal the code's netlist
set -e
D=$(realpath "$1"); P=$2; T=$(dirname "$0")
docker run --rm -u 0 -v "$D":/w -w /w kicad/kicad:10.0 kicad-cli sch export netlist --format kicadsexpr -o /w/$P.net $P.kicad_sch 2>&1 | grep -v "^$" | tail -5
python3 $T/netlist_truth.py "$D/$P.net" "$D/$P.kicad.json"
python3 $T/compare.py "$3" "$D/$P.kicad.json"
