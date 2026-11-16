#!/bin/bash
# poll the PC route result for r4_general-gen (max 150 min)
A=/home/claude/repo/docs/layout-teams/A
for i in $(seq 75); do
  if bash $A/route_result.sh r4_general-gen > route_gen.json 2>/dev/null; then echo "arrived $(date -u +%H:%M)" >> route_gen.json; exit 0; fi
  sleep 120
done
echo "not ready after 150 min $(date -u +%H:%M)" > route_gen.timeout
