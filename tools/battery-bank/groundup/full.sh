#!/bin/bash
# full.sh: placement -> hand copper -> DRC -> Kelvin routes -> first signal pass
export GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3
./build0.sh > new/build0.log 2>&1
./build1.sh > new/build1.log 2>&1
./drc.sh new > new/drc_stage1.txt 2>&1
./route1.sh Monolith.kicad_pcb rk.kicad_pcb "--only=ACP_F|ACN_F|SRP_F|SRN_F|/Cells and Gauge/SR[PN]\$" > new/rk.log 2>&1
: > new/prio.txt
./route1.sh rk.kicad_pcb it1.kicad_pcb --prio=/w/new/prio.txt > new/it1.log 2>&1
python3 updprio.py new/it1.log new/prio.txt >> new/iter.log
