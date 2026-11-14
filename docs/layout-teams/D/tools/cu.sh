#!/bin/bash
# cu.sh <run-name> <x0,y0,x1,y1> [layer=F.Cu] [px/mm=30]  -> /home/claude/runs/<run>/crop_<layer>.png : the generated power copper in a window
R=$(cd "$(dirname "$0")/../../../.." && pwd); O=/home/claude/runs/$1; L=${3:-F.Cu}
python3 $R/tools/copper/render.py $O/cu.kicad_pcb $O/cu.json $O/crop_${L%%.*}.png $L $2 ${4:-30} && echo $O/crop_${L%%.*}.png
