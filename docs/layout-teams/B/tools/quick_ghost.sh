#!/bin/bash
# quick_ghost.sh <plan_only run dir> [only-regex]: the scorecard's ghost router (blocked-edge screen) on a
#   plan_only_p2.sh / plan_only.sh run (cu.kicad_pcb + drc.json there), optionally only for nets matching the regex.
#   A quick look between full screens; screen.sh gives the numbers. Prints the GHOSTFAIL lines and the total.
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
OUT=$(cd "$1" && pwd); cd $OUT
cp $S/router.py .; [ -d pylib ] || cp -r $S/pylib .
ON=""; [ -n "$2" ] && ON="'--only=$2'"
docker run --rm -u 0 -v $OUT:/w -w /w kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout 20m python3 -u router.py cu.kicad_pcb drc.json ghost.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly $ON" > ghost.log 2>&1
grep -E "GHOSTFAIL|GHOST noway" ghost.log | sed 's/\[[^]]*\]//g' | cut -c1-160
