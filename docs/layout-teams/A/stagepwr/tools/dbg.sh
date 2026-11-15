#!/bin/bash
# dbg.sh <dir with cu.kicad_pcb drc.json> <net> <x0,y0,x1,y1> <out.png> [only-regex] : router free-cell maps (stagefix router_dbg2)
D=$(cd "$1" && pwd); cp /home/claude/repo/docs/layout-teams/A/stagepwr/tools/router_dbg3.py $D/router_dbg2.py
S=/home/claude/repo/tools/score
docker run --rm -u 0 -v $D:/w -w /w -v $S/pylib:/w/pylib kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout 10m python3 -u router_dbg2.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly --dbgnet='$2' --dbgbox=$3 --dbgout=$4 --only='${5:-$2}'"
