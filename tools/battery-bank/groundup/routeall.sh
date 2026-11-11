#!/bin/bash
# signal routing after the Kelvin pass (rk): everything at 0.2 mm, then what is left at 0.15 mm
./route1.sh rk.kicad_pcb rs.kicad_pcb > new/rs.log 2>&1
./route1.sh rs.kicad_pcb rt.kicad_pcb --w=0.15 > new/rt.log 2>&1
grep -c FAILED new/rs.log new/rt.log; grep "routed\|unconnected\|edges" new/rs.log new/rt.log
