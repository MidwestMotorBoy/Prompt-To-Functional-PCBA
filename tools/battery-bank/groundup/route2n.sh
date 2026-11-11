#!/bin/bash
# route2.sh <in board under new/> <out board under new/> [router options]: continuation pass. Full-rule DRC of the input
# (in fin/, project name Monolith), then the router re-lays every net the report names and may pull the others.
set -e
i=$1; o=$2; shift 2
args=""; for a in "$@"; do args="$args $(printf '%q' "$a")"; done
cp new/$i fin/Monolith.kicad_pcb
./drc.sh fin > fin/sum_in.txt
cp fin/drc.json new/drc_cont_${i%.kicad_pcb}.json
./kc sh -c "PYTHONPATH=/w/pylib python3 -u /w/router.py /w/new/$i /w/new/drc_cont_${i%.kicad_pcb}.json /w/new/$o --cont --keep=/w/new/Monolith.kicad_pcb --orig=/w/new/drc_Monolith.json --keepu=/w/new/keepu.txt $args" 2>&1 | grep --line-buffered -v "^$"
cp base/Monolith.kicad_pro new/Monolith.kicad_pro
cp base/Monolith.kicad_pro new/${o%.kicad_pcb}.kicad_pro
