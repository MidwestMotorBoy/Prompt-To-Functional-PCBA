#!/bin/bash
# sequential heavy jobs (one at a time)
cd /home/claude/repo/docs/layout-teams/A/r5_general
until [ -f runs/regress/run2.log ] && grep -q REGRESS_DONE runs/regress/run2.log; do sleep 10; done
bash copper_rules/score_rules.sh runs/all_nh runs/build/placement.json --rules=monolith_r5.rules.json --route=0 --no-hot > runs/all_nh.log 2>&1
python3 tools/spec_diff.py ../r5_merge/runs/m1/spec.json runs/all_nh/spec.json > runs/all_nh_vs_m1.txt 2>&1
echo ALL_NH_DONE >> runs/chain.log
bash copper_rules/score_rules.sh runs/all_hot runs/build/placement.json --rules=monolith_r5.rules.json --route=0 > runs/all_hot.log 2>&1
echo ALL_HOT_DONE >> runs/chain.log
bash copper_rules/score_rules.sh runs/hand_all --rules=general_r5.rules.json --route=0 --no-hot > runs/hand_all.log 2>&1
echo HAND_DONE >> runs/chain.log
