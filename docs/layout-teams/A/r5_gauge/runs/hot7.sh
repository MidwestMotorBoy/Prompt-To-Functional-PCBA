#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
exec 8>/tmp/r5_gauge_screen.lock; flock 8
export PLANNER_Q=$PWD/tools/plan_copper_g.py
../r4_port1/tools/score_r4.sh $PWD/runs/g7/hot $PWD/placement.json --route=0 -- $(cat ../r4_port1/tools/best_plan_opts.txt) '--fcut_path=109.22,130.9/109.78,129.55/110.75,128.3/110.75,126.4' --fcut_w=1.1 --fcut_vias=10 --pinvia=U101.19:1.0 '--bfill=CELL_P@104.8,128.8,109.7,131.75' > runs/g7/hot.out 2>&1
