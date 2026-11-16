# source this: copper recipe of the team A round-5 merged board (planner M = r4_bcu B + r4_vbus V + r4_port1 Q on portcu P;
# PACK_P second copy on In4; soft GND fill on B.Cu; no In2 straps). BEST_PLAN_R5 is set below (see ../best_plan_opts.txt).
A=/home/claude/repo/docs/layout-teams/A
source $A/tools/best_env.sh
export PLANNER=$A/r5_merge/tools/plan_copper_m.py
R5_V="--padpair=2 --padpair_live=1"
R5_Q="--padjoin=4 --gatevia=1 --pinesc_refs=U401,U501 --gndtie=1"
R5_B="--tap_max=16 --ret_band=1.6 --pw_nogrow=1 --mirror_skip_supply=1 --stub_nogrow=1 --mirror_maxa=10"
R5_M="--gatevia_chk=1 --capjoin=1"
BEST_PLAN_R5="$BEST_PLAN $R5_V $R5_Q $R5_B $R5_M"
R5_PLACEMENT=$A/r5_merge/placement.json
