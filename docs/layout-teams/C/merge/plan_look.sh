#!/bin/bash
# plan_look.sh <placement.json> <outdir> [x0 y0 x1 y1]: host copper planner on a placement (no KiCad, about 70 s),
# keeps cu.json/spec.json/plan.log and draws the F.Cu power copper round the PD chips (zoom.png).
H=$(cd "$(dirname "$0")" && pwd); R=$(cd $H/../../../.. && pwd); O=$2; mkdir -p $O
python3 - "$1" "$O/cu.json" <<'P'
import json, sys
sys.path.insert(0, "/home/claude/repo/docs/layout-teams/C/sweep"); import bare_xform
tpl = json.load(open("/home/claude/work/C/hand_screen/bare.json"))
json.dump(bare_xform.xform(tpl, json.load(open(sys.argv[1]))), open(sys.argv[2], "w"))
P
(cd $O && python3 $R/tools/copper/plan_copper.py cu.json $R/tools/floorplan/example/monolith/constraints.json spec.json > plan.log 2>&1)
grep "left to router \['" $O/plan.log | cut -c1-200
python3 $H/../corridor/zoom_cu.py $O $O/zoom.png ${3:-80} ${4:-66} ${5:-122} ${6:-104}
