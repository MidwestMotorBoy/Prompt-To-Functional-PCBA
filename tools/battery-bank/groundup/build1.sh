#!/bin/bash
# stage 1: placed board + copper.json -> new/Monolith.kicad_pcb (filled)
set -e
python3 copper.py
./kc python3 add_copper.py /w/new/placed.kicad_pcb /w/copper.json /w/new/Monolith.kicad_pcb 2>&1 | tail -3
cp base/Monolith.kicad_pro new/Monolith.kicad_pro
