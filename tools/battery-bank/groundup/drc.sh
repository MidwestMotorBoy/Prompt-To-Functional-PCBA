#!/bin/bash
# drc.sh <dir under w> : real KiCad DRC with schematic parity; restores the .kicad_pro afterwards
d=$1
cp base/Monolith.kicad_pro $d/Monolith.kicad_pro
./kc kicad-cli pcb drc --schematic-parity --all-track-errors --severity-all --format json -o /w/$d/drc.json /w/$d/Monolith.kicad_pcb > $d/drc.log 2>&1
cp base/Monolith.kicad_pro $d/Monolith.kicad_pro
python3 drcsum.py $d/drc.json
