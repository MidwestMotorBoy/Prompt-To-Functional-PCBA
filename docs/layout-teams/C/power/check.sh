#!/bin/bash
# check.sh <tag> [seed]: package power test. Places the whole board with HOOKS=cpower (stage log with CP_LOG=1),
# checks legality against the base (overlaps.py), the HOOKS-empty byte-identity rule, and draws a quick look.
#   Output: /home/claude/work/C/power/<tag>.json, .place.log, .png
#   Then the scorecard (heavy, one at a time): ../cplace/cscore.sh /home/claude/work/C/power/<tag> /home/claude/work/C/power/<tag>.json --route=0
set -e
H=$(cd "$(dirname "$0")" && pwd); CP=$H/../cplace; W=/home/claude/work/C/power; I=/home/claude/work/C/in; T=$1; S=${2:-2}
mkdir -p $W
(cd $CP && CP_LOG=1 HOOKS=cpower SEED=$S ./run.sh $W/$T.json > $W/$T.place.log 2>&1)
grep "^\[cpower\] .*gap\|stage parts\|no free spot\|NO SPOT\|placed .* of" $W/$T.place.log
python3 $H/../../../../tools/floorplan/overlaps.py $I/dump.json > $W/ov_dump.txt
python3 $H/../../../../tools/floorplan/overlaps.py $I/dump.json $CP/base_seed2_placement.json > $W/ov_base.txt
python3 $H/../../../../tools/floorplan/overlaps.py $I/dump.json $W/$T.json > $W/ov_$T.txt
diff -q $W/ov_base.txt $W/ov_$T.txt >/dev/null && echo "legality: same overlap list as the base (fixed parts only)" || { echo "legality: NEW OVERLAPS"; diff $W/ov_base.txt $W/ov_$T.txt; }
(cd $CP && SEED=2 HOOKS= ./run.sh $W/_empty_s2.json > /dev/null 2>&1) && cmp -s $W/_empty_s2.json $CP/base_seed2_placement.json && echo "HOOKS empty, SEED=2: byte-identical to base_seed2_placement.json" || echo "HOOKS empty: DIFFERS from base"
python3 $CP/metrics.py $I/dump.json $W/$T.json | head -1
python3 $H/plot_stage.py $I/dump.json $W/$T.json $W/$T.png && echo "look: $W/$T.png"
