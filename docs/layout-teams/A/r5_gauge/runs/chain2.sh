#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
BOX="88,113,101.5,127;104,115,121.6,134"
while pgrep -f "score_r4.sh .*runs/g1/sc" >/dev/null; do sleep 10; done
grep SCORE runs/g1/sc.out > runs/g1/score_line.txt
KEEP=1 tools/route_sub.sh ../r4_port1/runs/v5p/hot runs/base_sub2 "$BOX" 60 > runs/base_sub2.out 2>&1
KEEP=1 tools/route_sub.sh runs/g1/sc runs/g1/sub "$BOX" 60 > runs/g1/sub.out 2>&1
tools/screen.sh runs/g0 placement.json 1
