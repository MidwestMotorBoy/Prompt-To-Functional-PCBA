#!/bin/bash
# gen_inputs.sh [outdir, default /home/claude/work/C/in]
#   Regenerates everything cplace.py reads, from files in the repo only (no KiCad needed, 2 s):
#     dump.json       the template board as the placer sees it (= tools/floorplan/example/monolith/board_dump.json; checked
#                     2026-11-14 against cu_dump of tools/score/template/board.kicad_pcb: 289 parts, same x, y, side, turn)
#     clusters.json   section -> parts TO PLACE (example clusters.json minus the cup-fixed parts). A part in no cluster is fixed.
#     fixed.json      the fixed parts and why
#     intent.json     near / keepapart statements incl. the power-path ones (= tools/score/template/intent.json)
#     floorplan.json  Logan's reviewed boxes, option r2-d (same section names as clusters.json)
#     bodies.json     per part: body box (courtyard + pads, + 0.5 mm escape room for movable parts of 12 pads or more, + 1.5 mm
#                     on the power-pin sides of movable power ICs), through-hole box, keep-outs, board box. From pp_bodies.py
#                     (copy of round 3 pp_w1.py, DUMP_BODIES). Offsets are in the board frame at the dump pose (turn 0).
set -e
H=$(cd "$(dirname "$0")" && pwd); R=$(cd $H/../../../.. && pwd); F=$R/tools/floorplan; E=$F/example/monolith
O=${1:-/home/claude/work/C/in}; mkdir -p $O
cp $E/board_dump.json $O/dump.json; cp $R/tools/score/template/intent.json $O/intent.json; cp $E/floorplan_r2d.json $O/floorplan.json
cp $E/constraints.json $E/netlist.json $O/
python3 - $E/clusters.json $O <<'P'
import json, sys
cl = json.load(open(sys.argv[1])); O = sys.argv[2]; d = json.load(open(O + "/dump.json"))
# fixed by the cup (tools/battery-bank/groundup/README.md: "antenna module, the back-side parts, NTCs and L401/L501 are unchanged")
CUP = {"U301": "antenna module", "L401": "tall inductor, cup pocket", "L501": "tall inductor, cup pocket"}
for f in d["fps"]:
    if f["side"] == "B.Cu": CUP.setdefault(f["ref"], "back-side part (cup pocket / thermistor)")
inc = {r for v in cl.values() for r in v}
fixed = {f["ref"]: "connector / hole / test pad / switch" for f in d["fps"] if f["ref"] not in inc}; fixed.update(CUP)
out = {k: {r: p for r, p in v.items() if r not in fixed} for k, v in cl.items()}; out = {k: v for k, v in out.items() if v}
json.dump(out, open(O + "/clusters.json", "w"), indent=0); json.dump(fixed, open(O + "/fixed.json", "w"), indent=0)
print(f"{sum(len(v) for v in out.values())} parts to place in {len(out)} sections, {len(fixed)} fixed")
P
cd $F && DUMP_BODIES=$O/bodies.json CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=$O/floorplan.json PYTHONPATH=$F python3 $H/pp_bodies.py $O/clusters.json $O/dump.json /dev/null 0 1 0 $O/intent.json
ls -la $O
