#!/bin/bash
# stage 0: stripped + placed board -> new/placed.kicad_pcb
set -e
GAP=${GAP:-0.25} RING=${RING:-0.4} python3 run.py place_keep.py,place_p1top.py,place_centre.py,place_p1stage.py,place_p2top.py,place_bot.py | grep -v auto
python3 strip.py base/Monolith.kicad_pcb new/placed.kicad_pcb
./kc python3 apply_place.py /w/new/placed.kicad_pcb /w/placement.json /w/new/placed.kicad_pcb | tail -1
