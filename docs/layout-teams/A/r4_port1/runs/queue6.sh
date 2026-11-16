#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until [ -f runs/v6p/HOTDONE ]; do sleep 20; done
exec 8>/tmp/r4_port1_screen.lock; flock 8
# fallback local full route (PC result for r4_port1-v5q not back 75 min after queueing)
../tools/route_local.sh runs/v6p/hot 150 > runs/v6p/route_local.out 2>&1
date > runs/v6p/LOCALDONE
