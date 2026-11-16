#!/bin/bash
# sequential scorecards (one heavy job at a time)
cd /home/claude/repo/docs/layout-teams/A/r4_general
bash copper_rules/score_rules.sh runs/sc_pkg ../best_placement.json --rules=monolith.rules.json --route=0 > runs/sc_pkg.log 2>&1
bash copper_rules/score_rules.sh runs/sc_gen ../best_placement.json --rules=general.rules.json --route=0 > runs/sc_gen.log 2>&1
bash copper_rules/score_rules.sh runs/sc_all ../best_placement.json --rules=runs/all.rules.json --route=0 > runs/sc_all.log 2>&1
bash copper_rules/score_rules.sh runs/sc_hand --rules=general.rules.json --route=0 --no-hot > runs/sc_hand.log 2>&1
echo CHAIN1 DONE > runs/chain1.done
