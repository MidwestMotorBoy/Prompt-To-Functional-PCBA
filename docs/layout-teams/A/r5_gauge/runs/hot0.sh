#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
exec 8>/tmp/r5_gauge_screen.lock; flock 8
export PLANNER_Q=$PWD/tools/plan_copper_g.py
../r4_port1/tools/score_r4.sh $PWD/runs/g0/hot $PWD/placement.json --route=0 -- $(cat ../r4_port1/tools/best_plan_opts.txt) > runs/g0/hot.out 2>&1
