#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r5_gauge
tools/screen.sh runs/g6 placement.json 0 --pinvia=U101.19:1.0
tools/screen.sh runs/g7 placement.json 0 '--fcut_path=109.22,130.9/109.78,129.55/110.75,128.3/110.75,126.4' --fcut_w=1.1 --fcut_vias=10 --pinvia=U101.19:1.0 '--bfill=CELL_P@104.8,128.8,109.7,131.75'
