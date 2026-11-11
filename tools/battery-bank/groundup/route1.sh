#!/bin/bash
# route1.sh <in board under new/> <out board under new/> [router options]: DRC the input, route what is missing
set -e
i=$1; o=$2; shift 2
args=""; for a in "$@"; do args="$args $(printf '%q' "$a")"; done
j=new/drc_${i%.kicad_pcb}.json
if [ ! -s $j ] || [ new/$i -nt $j ]; then ./kc kicad-cli pcb drc --schematic-parity --severity-all --format json -o /w/$j /w/new/$i > new/drc.log 2>&1 || true; fi
cp $j new/drc_in.json
./kc sh -c "PYTHONPATH=/w/pylib python3 -u /w/router.py /w/new/$i /w/new/drc_in.json /w/new/$o $args" 2>&1 | grep --line-buffered -v "^$"
cp base/Monolith.kicad_pro new/Monolith.kicad_pro
