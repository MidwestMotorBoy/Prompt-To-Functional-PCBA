#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_general/runs
until [ -f chain1.done ]; do sleep 20; done
cp sc_gen/score.json sc_gen/score_route0.json
date -u +%H:%M > route_gen_local.start
bash /home/claude/repo/docs/layout-teams/A/tools/route_local.sh sc_gen 150 > route_gen_local.log 2>&1
date -u +%H:%M > route_gen_local.done
