#!/bin/bash
# iter.sh <first> <last> [router options]: full signal passes from the Kelvin-routed board; failed nets go first next time
a=$1; b=$2; shift 2
for k in $(seq $a $b); do
  ./route1.sh rk.kicad_pcb it$k.kicad_pcb --prio=/w/new/prio.txt "$@" > new/it$k.log 2>&1
  python3 updprio.py new/it$k.log new/prio.txt >> new/iter.log
done
