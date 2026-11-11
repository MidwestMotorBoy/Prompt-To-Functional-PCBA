#!/bin/bash
# routej.sh <in board under new/> <out board under new/> <edges json under new/> [router options]: route the listed connections
set -e
i=$1; o=$2; j=$3; shift 3
args=""; for a in "$@"; do args="$args $(printf '%q' "$a")"; done
cp base/Monolith.kicad_pro new/${i%.kicad_pcb}.kicad_pro   # net classes come from the project file beside the board
./kc sh -c "PYTHONPATH=/w/pylib python3 -u /w/router.py /w/new/$i /w/new/$j /w/new/$o $args" 2>&1 | grep --line-buffered -v "^$"
cp base/Monolith.kicad_pro new/Monolith.kicad_pro
