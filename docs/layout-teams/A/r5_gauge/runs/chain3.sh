#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
while pgrep -f "route_sub.sh ../r4_port1/runs/v5p/hot runs/base_sub2" >/dev/null; do sleep 10; done
G="--fkeep=105.9,128.6,111.4,130.7;109.9,126.0,111.4,128.6 --pinvia=U101.19:1.0"
tools/screen.sh runs/g1 placement.json 1 $G
tools/screen.sh runs/g0 placement.json 1
