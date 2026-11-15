#!/bin/bash
# final: screens of FB, one at a time. d/c/a with hot loops on (--route=0), b with --no-hot.
F=/home/claude/repo/docs/layout-teams/A/final; S=$F/tools/score_board_f.sh; P=$F/fb_score.json; PF=$F/tools/plan_copper_f.py
cd $F/runs
t=$(date +%s); PLANNER=$PF STRAPS="--net=PACK_P --layer=In2.Cu" $S sc_d $P --route=0 --plan="--sealed=1 --taps=1 --joinfix=1" > sc_d.log 2>&1; echo "sc_d $(( $(date +%s)-t )) s" >> chain1.times
t=$(date +%s); PLANNER=$PF $S sc_c $P --route=0 --plan="--sealed=1 --taps=1 --joinfix=1" > sc_c.log 2>&1; echo "sc_c $(( $(date +%s)-t )) s" >> chain1.times
t=$(date +%s); $S sc_a $P --route=0 > sc_a.log 2>&1; echo "sc_a $(( $(date +%s)-t )) s" >> chain1.times
t=$(date +%s); PLANNER=$PF $S sc_b $P --route=0 --no-hot --plan="--sealed=1 --taps=1" > sc_b.log 2>&1; echo "sc_b $(( $(date +%s)-t )) s" >> chain1.times
echo CHAIN1 DONE >> chain1.times
