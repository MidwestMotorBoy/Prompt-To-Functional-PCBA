#!/bin/bash
# local full scorecard run of variant d (planner F sealed+taps+joinfix, PACK_P In2 straps), hot loops on, 150-min route cap
F=/home/claude/repo/docs/layout-teams/A/final; cd $F/runs
until grep -q DONE chain1.times; do sleep 15; done
t=$(date +%s); echo "full_d start $(date -u +%H:%M)" >> full_d.times
PLANNER=$F/tools/plan_copper_f.py STRAPS="--net=PACK_P --layer=In2.Cu" $F/tools/score_board_f.sh full_d $F/fb_score.json --route=150 --plan="--sealed=1 --taps=1 --joinfix=1" > full_d.log 2>&1
echo "full_d done $(( ($(date +%s)-t)/60 )) min $(date -u +%H:%M)" >> full_d.times
