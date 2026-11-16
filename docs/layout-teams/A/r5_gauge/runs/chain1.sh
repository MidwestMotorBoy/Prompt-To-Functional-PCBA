#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
until [ -s runs/base_sub.out ]; do sleep 10; done
G="--fkeep=105.9,128.6,111.4,130.7;109.9,126.0,111.4,128.6 --viasite=106.68,129.95 --pinvia=U101.19:1.0 --epnets=U101"
tools/screen.sh runs/g1 placement.json 1 $G
tools/screen.sh runs/g0 placement.json 1
