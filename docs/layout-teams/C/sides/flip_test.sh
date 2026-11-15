#!/bin/bash
# flip_test.sh [workdir]: proves the flip in cplace/c_apply.py. 32 parts (8 per template rotation 0/90/180/-90, 2-pad
# passives, diodes, SOT-23, multi-pad ICs) are flipped to B in 4 placements so each part sees all 4 quarter turns.
# flip_check.py then checks in the SAVED board: footprint on B.Cu, every pad within 0.01 mm of origin + rotv(-lx, ly, q)
# (computed from the dump without KiCad), SMD copper on B.Cu only, no courtyard/fab/silk/field on an F layer, pad nets
# as in the template, whole-board pad-net list unchanged. About 20 s.
H=$(cd "$(dirname "$0")" && pwd); R=$(cd $H/../../../.. && pwd); W=${1:-/home/claude/work/C/sides/fliptest}; I=/home/claude/work/C/in
mkdir -p $W; [ -f $I/dump.json ] || $H/../cplace/gen_inputs.sh $I >/dev/null
cp $R/tools/score/template/board.kicad_pcb $W/tpl.kicad_pcb; cp $H/../cplace/c_apply.py $H/flip_check.py $W/
python3 $H/flip_test_gen.py $I/dump.json $I/clusters.json $W
for q in 0 1 2 3; do
  cp $R/tools/score/template/board.kicad_pro $W/fq$q.kicad_pro
  docker run --rm -u 0 -e FLIPLOG=1 -v $W:/w -w /w kicad/kicad:10.0 sh -c "python3 c_apply.py tpl.kicad_pcb fq$q.kicad_pcb flip_q$q.json --strip > apply_q$q.log 2>&1; python3 flip_check.py fq$q.kicad_pcb want_q$q.json tpl.kicad_pcb > check_q$q.log 2>&1"
  grep "^wrote" $W/apply_q$q.log | cut -c1-90; grep -E "^FAIL|^SUMMARY" $W/check_q$q.log
done
echo "turn used after the flip, by (template rotation after flip, q): count"; grep -h "^flip" $W/apply_q*.log | awk '{print $4, $6, $8}' | sort | uniq -c
