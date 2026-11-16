#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until [ -f runs/v6p/DONE ]; do sleep 20; done
tools/screen.sh runs/v6r runs/v6/placement.json --padjoin=4 --gatevia=1 --pinesc_refs=U401,U501,U403,U503 --gndtie=1
