#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until [ -f runs/v1p/DONE ]; do sleep 20; done
tools/screen.sh runs/v5q runs/v5/placement.json --padjoin=4 --gatevia=1
