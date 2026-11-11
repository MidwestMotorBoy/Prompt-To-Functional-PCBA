#!/bin/bash
# build.sh [outdir] : code -> netlist.json -> KiCad sheets -> KiCad's netlist of the sheets must equal the code's
set -e
cd "$(dirname "$0")"
OUT=${1:-out}
export SYMBOL_DIRS=${SYMBOL_DIRS:?set SYMBOL_DIRS to the KiCad symbol folder and the project library folder}
python3 top.py $OUT
rm -rf $OUT/sheets && python3 draw.py $OUT $OUT/sheets monolith_gen
../tools/check.sh $OUT/sheets monolith_gen $OUT/netlist.json
