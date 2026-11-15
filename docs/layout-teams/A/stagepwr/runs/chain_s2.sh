#!/bin/bash
W=/home/claude/repo/docs/layout-teams/A/stagepwr; cd $W
STRAPS="--net=PACK_P --layer=In2.Cu" PLANNER=$W/tools/plan_copper_a.py tools/score_board_split_a.sh runs/sc_v1A3S2 runs/v1_score.json --route=0 --plan="--sealed=1 --taps=1" > runs/sc_v1A3S2.log 2>&1
tail -1 runs/sc_v1A3S2.log; grep straps runs/sc_v1A3S2/plan.log
/home/claude/repo/docs/layout-teams/A/queue_route.sh runs/sc_v1A3S2 stagepwr-v1A3S2 2>&1 | tail -1; date
cd runs/sc_v1A3S2; S=/home/claude/repo/tools/score
docker run --rm -u 0 -v $PWD:/w -w /w -v $S/pylib:/w/pylib kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout 80m python3 -u router.py cu.kicad_pcb drc.json routed.kicad_pcb --softnets=GND,PACK_P,3V3 --riptime=600" > route_rt600.log 2>&1
grep -E "^routed|unconnected after|edges to route" route_rt600.log; $W/tools/routed_dc.sh .
echo CHAIN DONE
