#!/bin/bash
# build.sh [outdir] : code -> netlist.json -> intent gate -> KiCad sheets -> KiCad's netlist of the sheets must equal the code's
set -e
cd "$(dirname "$0")"
OUT=${1:-out}
export SYMBOL_DIRS=${SYMBOL_DIRS:?set SYMBOL_DIRS to the KiCad symbol folder and the project library folder}
python3 top.py $OUT
# intent gate (spike 2): ratings, limits, expected values, pin rules. A failing design draws no sheets.
if [ -n "$LIMITS_DIR" ]; then
  python3 ${INTENT_CHECK:-../../02-seeded-faults/intent_check.py} check $OUT $LIMITS_DIR ${LIMITS_MAP:?set LIMITS_MAP} .
else
  echo "LIMITS_DIR not set: intent gate skipped"
fi
rm -rf $OUT/sheets && python3 draw.py $OUT $OUT/sheets monolith_gen
../tools/check.sh $OUT/sheets monolith_gen $OUT/netlist.json
