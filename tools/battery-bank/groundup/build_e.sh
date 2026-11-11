#!/bin/bash
# build_e.sh: fix-pass board before the router. c11 -> lift (d0) -> hand gate drives -> moved caps -> stage vias -> extra vias -> new/e1
set -e
cp new/keepu_c11.txt new/keepu.txt
./kc python3 /w/lift.py /w/new/d0.kicad_pcb /w/new/d0c.kicad_pcb /w/new/Monolith.kicad_pcb '/USB Port 1/PPHV$|Net-\(U403-ACOV\)' 2>&1 | tail -n 1
python3 hand2/gate.py 2 > hand2/g2.json; python3 hand2/gate.py 1 > hand2/g1.json; python3 hand2/stagev.py > hand2/stagev.json
./kc python3 /w/handadd.py /w/new/d0c.kicad_pcb /w/new/e1a.kicad_pcb /w/hand2/g2.json /w/new/keepu.txt 2>&1 | tail -n 1
./kc python3 /w/handadd.py /w/new/e1a.kicad_pcb /w/new/e1b.kicad_pcb /w/hand2/g1.json /w/new/keepu.txt 2>&1 | tail -n 1
./kc python3 /w/movefp.py /w/new/e1b.kicad_pcb /w/new/e1c.kicad_pcb C530 86.52 97.32 180 C538 91.02 97.32 180 C430 109.546 97.32 180 C438 114.046 97.32 180 2>&1 | grep -c "^C"
./kc python3 /w/handadd.py /w/new/e1c.kicad_pcb /w/new/e1d.kicad_pcb /w/hand2/stagev.json /w/new/keepu.txt 2>&1 | tail -n 1
./step.sh e1d e1 hand2/pv.json 2>&1 | grep -v UNCONN | tail -n 14
