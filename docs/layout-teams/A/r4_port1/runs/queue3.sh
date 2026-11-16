#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until [ -f runs/v5q/DONE ]; do sleep 20; done
Q="--padjoin=4 --gatevia=1 --pinesc_refs=U401,U501 --gndtie=1"
tools/screen.sh runs/v5p runs/v5/placement.json $Q
tools/screen.sh runs/v6p runs/v6/placement.json $Q
