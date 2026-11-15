#!/bin/bash
# dbg.sh <scorecard outdir> <net> x0,y0,x1,y1 <out.png> [pts 'x:y;x:y'] [only-regex]
# Router ghost debug for one net on a scorecard outdir (KiCad container, ~3 s):
#   <out.png>      router free-cell mask, 4 px per 0.05 mm cell: white = F+B+via free, yellow = F+B free (no via),
#                  red = F only, green = B only (F walled), dark = nothing; magenta = the net's end cells.
#   <out>_ov.png   the same mask blended over the F.Cu copper render (zoom.py, 80 px/mm) with pad numbers.
#   pts: prints which net owns the router cell at each point on F/In2/In3/B.
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../../../../.." && pwd)
D=$(cd "$1" && pwd); NET=$2; BOX=$3; OUT=$4; PTS=${5:-}; ONLY=${6:-$2}
cp $R/docs/layout-teams/A/rebuild/tools/router_dbg.py $D/router_dbg.py
docker run --rm -u 0 -v $D:/w -v $R/tools/score/pylib:/w/pylib -w /w kicad/kicad:10.0 sh -c "PYTHONPATH=/w/pylib timeout 10m python3 -u router_dbg.py cu.kicad_pcb drc.json /tmp/g.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly --only='^$ONLY\$' --dbgbox=$BOX --dbgnet='$NET' --dbgpts='$PTS' --dbgout=dbg.png" 2>&1 | grep -E "dbg at|GHOST"
mv $D/dbg.png $OUT
python3 $R/docs/layout-teams/A/rebuild/tools/zoom.py $D ${OUT%.png}_cu.png $BOX F.Cu 80 >/dev/null
python3 - $OUT ${OUT%.png}_cu.png ${OUT%.png}_ov.png <<'P'
import sys
from PIL import Image
m=Image.open(sys.argv[1]).convert('RGB'); c=Image.open(sys.argv[2]).convert('RGB').resize(m.size)
Image.blend(c,m,0.45).save(sys.argv[3])
P
rm -f ${OUT%.png}_cu.png
