#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until grep -qE "^SUB" runs/v3b/sub.out 2>/dev/null; do sleep 20; done
tools/score_r4.sh runs/v1q/sc runs/v1/placement.json --route=0 --no-hot -- --connesc_big=0.9 --padjoin=4 --gatevia=1 > runs/v1q/sc.out 2>&1
KEEP=1 tools/route_sub.sh runs/v1q/sc runs/v1q/sub 99,66,121.6,116 40 > runs/v1q/sub.out 2>&1
