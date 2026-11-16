#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until [ -f runs/v6r/DONE ]; do sleep 20; done
exec 8>/tmp/r4_port1_screen.lock; flock 8
tools/score_r4.sh runs/v6p/hot runs/v6/placement.json --route=0 -- --padjoin=4 --gatevia=1 --pinesc_refs=U401,U501 --gndtie=1 > runs/v6p/hot.out 2>&1
date > runs/v6p/HOTDONE
