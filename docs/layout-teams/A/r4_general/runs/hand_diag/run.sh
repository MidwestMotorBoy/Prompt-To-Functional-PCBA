#!/bin/bash
# planner-only ladder on the hand placement: which rule opens AC_SNS_N at R424/R524 and GND at U404
cd /home/claude/repo/docs/layout-teams/A/r4_general/runs/hand_diag
C=/home/claude/repo/tools/floorplan/example/monolith/constraints.json; PR=../../copper_rules/plan_rules.py; B=../sc_hand/bare.json
OFF="--gate_escape=0 --sealed=0 --taps=0 --joinfix=0 --epstrip=0 --directjoin=0 --nogrow_dead=0 --gndesc=0 --connesc=0 --gndpair=0 --pinesc=0"
step() { n=$1; shift; python3 $PR $B $C $n.json "$@" > $n.log 2>&1; echo "== $n: $(grep -o "AC_SNS_N: .*" $n.log | head -1 | cut -c1-200) | U404-ret: $(grep -o 'U404[.0-9]*' $n.log | sort -u | tr '\n' ' ')" >> ladder.txt; }
rm -f ladder.txt
step s0_stock --stock=1
step s1_gate --stock=1 --gate_escape=1 --sealed=1 --taps=1
step s2_join --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1
step s3_ep --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1
step s4_dj --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1
step s5_dead --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1
step s6_gesc --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1
step s7_conn --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1
step s8_pair --stock=1 --gate_escape=1 --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1 --gndpair=1
echo DONE >> ladder.txt
