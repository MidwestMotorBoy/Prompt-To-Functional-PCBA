#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_general; A=..; O=runs/regress
run() { n=$1; d=$2; r=$3; shift 3; tools/plan_only.sh $d/bare.json $O/$n.json $r "$@" || echo "$n FAILED"; echo "== $n vs $d"; python3 tools/spec_diff.py $d/spec.json $O/$n.json --quiet | tail -4; }
for t in "$@"; do case $t in
 V) run V $A/r4_vbus/runs/v2sh $O/reg_v.rules.json;;
 Q) run Q $A/r4_port1/runs/v5p/hot $O/reg_q.rules.json;;
 B) run B $A/r4_bcu/runs/k1 $O/reg_b.rules.json;;
 Z) run Z $A/lead_final/sc_Z monolith.rules.json;;
esac; done
echo REGRESS_DONE
