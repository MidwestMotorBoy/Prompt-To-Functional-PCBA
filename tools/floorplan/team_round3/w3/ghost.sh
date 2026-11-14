#!/bin/bash
# ghost.sh <tag> [minutes=15]: count edges of /home/claude/work/hp/<tag>_cu.kicad_pcb with no path even on a board without signal routes
T=$1; MIN=${2:-15}; H=/home/claude/work/hp; D=/home/claude/work/team/w3/g_$T; mkdir -p $D
for e in kicad_pcb kicad_pro kicad_dru; do cp $H/${T}_cu.$e $D/b.$e; done
cp /home/claude/work/team/w3/ghost_router.py $D/router.py
docker run --rm -u 0 -v $D:/w -v /home/claude/work/team/pylib:/w/pylib -w /w kicad/kicad:10.0 sh -c "kicad-cli pcb drc --severity-all --format json -o /w/drc.json /w/b.kicad_pcb >/dev/null 2>&1; PYTHONPATH=/w/pylib timeout ${MIN}m python3 -u /w/router.py /w/b.kicad_pcb /w/drc.json /w/routed.kicad_pcb --softnets=GND,PACK_P,3V3 --ghostonly" > $D/ghost.log 2>&1
echo "GHOST $T: $(grep '^GHOST ' $D/ghost.log)"
