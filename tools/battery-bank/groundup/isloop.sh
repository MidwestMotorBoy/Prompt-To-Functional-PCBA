#!/bin/bash
# isloop.sh <in> <out> <netregex> <width> [PADSTART] [extra router options]: find cut-off groups of the nets, route each to its main body
i=$1; o=$2; rx=$3; w=$4; ps=$5; shift 5
./kc sh -c "$ps python3 isl.py /w/new/$i.kicad_pcb '$rx' /w/new/isl_$i.json" 2>&1 | grep "^=="
./routej.sh $i.kicad_pcb $o.kicad_pcb isl_${i}_edges.json --norip --nopre --phases=0 --w=$w --pad=25 --pieces=/w/new/isl_${i}_pieces.json "$@" > new/$o.log 2>&1
grep -v FAILKEY new/$o.log | tail -12
