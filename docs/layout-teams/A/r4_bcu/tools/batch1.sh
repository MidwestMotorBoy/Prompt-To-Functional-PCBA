#!/bin/bash
B=/home/claude/repo/docs/layout-teams/A/r4_bcu; cd $B
S0="--tap_max=16 --ret_band=1.6"
tools/screen.sh e1 runs/pl_v6/placement.json "$S0 --pw_nogrow=1"
tools/screen.sh d1 runs/pl_v6/placement.json "$S0 --mirror_skip_supply=1"
tools/screen.sh d2 runs/pl_v6/placement.json "$S0 --mirror_minw2=1.5"
echo BATCH1 DONE >> runs/log.txt
