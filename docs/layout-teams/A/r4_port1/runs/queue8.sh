#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
exec 8>/tmp/r4_port1_screen.lock; flock 8
ROUTER_OPTS="--maxrip=8 --capx=3" tools/route_sub.sh runs/v5p/sc runs/v5p/sub_rip8cap3 99,66,121.6,116 40 > runs/v5p/sub_rip8cap3.out 2>&1
date > runs/v5p/RDONE
