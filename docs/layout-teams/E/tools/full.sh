#!/bin/bash
# full.sh <run name> [last pass, default 3]    full route of /home/claude/runs/<run>/cu.kicad_pcb (made by go.sh):
#   pass 1: Kelvin taps and joins (place/routes.txt), power pieces with wide tracks, then every signal;
#   pass 2..: every net again, ground / pack / 3V3 included, with all pours as KiCad filled them after the pass before.
# Stops when KiCad reports nothing unconnected. Results r1, r2, ... (.kicad_pcb, .drc.json, .e.json, .routes.json),
# then rt: the last pass with the stubs that rip-up left trimmed (etidy.py). rt.kicad_pcb is the board to score.
# EROUTE_OPTS: extra router options for every pass. Default: signal tracks pay 1 per cell to run over the pack sheet
# on In2 (they cut it into strips: routed loss 1.27 W without the price, 1.14 W with it; at 2 per cell SDA stays open).
: ${EROUTE_OPTS=--softpen=PACK_P:2:1.0}
HERE=$(cd "$(dirname "$0")" && pwd); D=/home/claude/runs/$1; cd $D || exit 1
python3 $HERE/eroute.py . cu r1 --taps=$HERE/../place/routes.txt --power --skip='^(GND|PACK_P|3V3)$' $EROUTE_OPTS > route1.log 2>&1
grep -h "^taps\|^power pass\|^routed\|^DRC" route1.log
for i in $(seq 2 ${2:-3}); do
  grep -q "unconnected 0$" route$((i-1)).log && break
  python3 $HERE/eroute.py . cu r$i --routes=r$((i-1)).routes.json --fills=r$((i-1)).e.json $EROUTE_OPTS > route$i.log 2>&1
  grep -h "^routed\|^  open\|^DRC" route$i.log
done
L=$(ls r[0-9]*.routes.json | sort -V | tail -1); L=${L%.routes.json}
python3 $HERE/etidy.py cu.e.json $L.e.json $L.routes.json rt.routes.json && bash $HERE/eapply.sh . cu rt.routes.json rt | tail -1
