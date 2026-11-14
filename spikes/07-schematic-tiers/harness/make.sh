#!/bin/bash
# make.sh : build the Monolith sheets from code, prove they are electrically identical to the frozen netlist, render them.
# Output: out/sheets/*.kicad_sch, out/render/sheets.pdf, out/render/page-N.png (100 dpi). Exit code 1 if the netlist differs.
set -eo pipefail
cd "$(dirname "$0")"
W=$PWD; SH=${SHARED:?set SHARED to the folder with ksym/, lib/ and frozen_netlist.json}
export SYMBOL_DIRS=$SH/ksym:$SH/lib
rm -rf out; mkdir -p out/render
(cd design && python3 top.py $W/out > /dev/null)
python3 tools/compare.py $SH/frozen_netlist.json out/netlist.json | tail -2      # the code itself must not change the circuit
(cd design && python3 draw.py $W/out $W/out/sheets monolith_gen)
sudo docker run --rm -u 0 -v $W/out/sheets:/w -w /w kicad/kicad:10.0 sh -c \
  "kicad-cli sch export netlist --format kicadsexpr -o /w/monolith_gen.net monolith_gen.kicad_sch >/dev/null && kicad-cli sch export pdf -o /w/sheets.pdf monolith_gen.kicad_sch >/dev/null"
python3 tools/netlist_truth.py out/sheets/monolith_gen.net out/sheets/monolith_gen.kicad.json
python3 tools/compare.py $SH/frozen_netlist.json out/sheets/monolith_gen.kicad.json | tail -3   # the drawn sheets must equal the circuit
mv out/sheets/sheets.pdf out/render/sheets.pdf
pdftoppm -r 100 -png out/render/sheets.pdf out/render/page
echo "NETLIST OK. Renders: out/render/page-*.png (page 1 is the root sheet; 2 3V3 rail, 3 cells and gauge, 4 MCU, 5-6 USB ports)"
