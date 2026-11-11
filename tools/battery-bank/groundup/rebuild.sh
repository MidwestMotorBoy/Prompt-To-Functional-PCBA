#!/bin/bash
# rebuild.sh: placement -> hand copper -> DRC -> Kelvin routes (new/rk.kicad_pcb)
export GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3
./build0.sh > new/build0.log 2>&1
./build1.sh > new/build1.log 2>&1
./drc.sh new > new/drc_stage1.txt 2>&1
./route1.sh Monolith.kicad_pcb rk.kicad_pcb "--only=ACP_F|ACN_F|SRP_F|SRN_F|/Cells and Gauge/SR[PN]\$" > new/rk.log 2>&1
echo done > new/rebuild.done
