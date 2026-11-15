# source this: team E copper recipe for sc.sh (planner P rules from team A, PACK_P second copy on In4, soft GND fill on B)
export BUS4="--mode=strip+copy --w=3 --box=96,100,122,140"
export BUS4B="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1"
export PLAN_OPTS="--sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1 --pinesc=1 --pinesc_refs=U501 --pinesc_near=1 --gndpair=1"
export PLAN_C=$(cd "$(dirname "${BASH_SOURCE[0]}")/../place" && pwd)/constraints_plan.json   # PPHV: only the PD pin, the shunt and its capacitor get pours (the charger's VAC pin 28 mm away is a sense branch)
export ECOPPER=$(cd "$(dirname "${BASH_SOURCE[0]}")/../place" && pwd)/copper.txt; export SPEC_STEPS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ecopper.py   # hand copper list
