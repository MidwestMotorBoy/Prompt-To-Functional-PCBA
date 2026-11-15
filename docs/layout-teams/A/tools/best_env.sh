# source this: copper recipe of the team A best board (planner P = portcu G5 rules on planner A; PACK_P second copy on In4; soft GND fill on B.Cu; no In2 straps)
A=/home/claude/repo/docs/layout-teams/A
export PLANNER=$A/portcu/tools/plan_copper_p.py
export BUS4="--mode=strip+copy --w=3 --box=96,100,122,140"
export BUS4B="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1"
unset STRAPS
BEST_PLAN="--sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1 --pinesc=1 --pinesc_refs=U501 --pinesc_near=1 --gndpair=1"
