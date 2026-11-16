#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_port1
until grep -q CHAINDONE runs/v1q/sub.out 2>/dev/null; do sleep 20; done
tools/screen.sh runs/v1p runs/v1/placement.json --padjoin=4 --gatevia=1 --pinesc_refs=U401,U501
