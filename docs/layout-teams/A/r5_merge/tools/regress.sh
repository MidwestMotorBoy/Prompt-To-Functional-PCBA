#!/bin/bash
# regression: planner M with one worker's options on that worker's bare.json must equal that worker's spec.json
A=/home/claude/repo/docs/layout-teams/A; source $A/tools/best_env.sh; O=$A/r5_merge/runs/regress; mkdir -p $O
run() { n=$1; d=$2; shift 2; $A/r5_merge/tools/plan_only.sh $d/bare.json $O/$n.json "$BEST_PLAN $*"; echo "== $n"; python3 $A/r5_merge/tools/spec_diff.py $d/spec.json $O/$n.json --quiet | tail -3; }
run V $A/r4_vbus/runs/v2sh --padpair=2 --padpair_live=1
run Q $A/r4_port1/runs/v5p/hot --padjoin=4 --gatevia=1 --pinesc_refs=U401,U501 --gndtie=1
run B $A/r4_bcu/runs/k1 --tap_max=16 --ret_band=1.6 --pw_nogrow=1 --mirror_skip_supply=1 --stub_nogrow=1 --mirror_maxa=10
