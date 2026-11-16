#!/bin/bash
# faildiff.sh <queue name>: FAILED lines of a PC route and the gauge/MCU edges against both v5p logs
R=/home/claude/repo; A=$R/docs/layout-teams/A; cd $R
SHA=$(git hash-object docs/layout-teams/A/route_queue/$1.kicad_pcb | cut -c1-8)
git show origin/route-results:A/$1-$SHA.json 2>/dev/null | tr -d '\n' | cut -c1-300; echo
git show origin/route-results:A/$1-$SHA.log 2>/dev/null | grep "^  FAILED" | sed 's/ starts.*|/ |/' | cut -c1-150
echo "-- gauge/MCU (U101, J302/U301 SCL/SDA, CELL*, SMB*, VC*, GAUGE*, BTP*, U102):"
for f in $1-$SHA r4_port1-v5p-c11115b2 r4_port1-v5p-rep-c11115b2; do
  echo "$f: $(git show origin/route-results:A/$f.log 2>/dev/null | grep '^FAILKEY' | grep -v 'USB Port' | sed 's/FAILKEY //' | tr '\n' ';')"
done
