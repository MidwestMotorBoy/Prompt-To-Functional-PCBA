#!/bin/bash
# run.sh <out placement.json> [input dir]: cplace.py on the generated inputs. Knobs and HOOKS come from the environment,
#   e.g.  SEED=3 HOOKS=cpower,cside,ccorr ./run.sh /home/claude/work/C/x/p.json        (about 1-3 min, one core)
H=$(cd "$(dirname "$0")" && pwd); I=${2:-/home/claude/work/C/in}
[ -f $I/bodies.json ] || $H/gen_inputs.sh $I >/dev/null
export PYTHONHASHSEED=${PYTHONHASHSEED:-0}   # [merge] eviction order follows string hashing; fixed for reproducible runs
CONSTRAINTS=$I/constraints.json BOXW=${BOXW:-0} python3 $H/cplace.py $I/dump.json $I/clusters.json $I/intent.json $I/floorplan.json $I/bodies.json "$1"
