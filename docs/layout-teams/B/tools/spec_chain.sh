#!/bin/bash
# spec_chain.sh <screened run dir> <out spec.json> --straps="..." --filters="..."   (team B phase 2, worker A)
#   The plan steps 1 and 1b of final_route.sh only (straps.py runs, then the copper-plan filters), python only, no
#   KiCad: a spec.json to look at with pinlib.py look or to feed quick_dc.sh / spec_ghost.sh. Logs beside the out spec.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$1" && pwd); OUTS=$(readlink -f "$2"); shift 2; SOPT=""; FILT=""
for a in "$@"; do case $a in --straps=*) SOPT=${a#*=};; --filters=*) FILT=${a#*=};; esac; done
W=$(dirname $OUTS); B=$(basename $OUTS .json); cp $SRC/spec.json $W/$B.0.json; cur=$W/$B.0.json
IFS=';' read -ra SL <<< "$SOPT"; n=0
for o in "${SL[@]}"; do [ -z "$o" ] && continue; n=$((n+1)); python3 $TOOLS/straps.py $cur $SRC/cu.json $W/$B.s$n.json $o > $W/$B.s$n.log 2>&1; cur=$W/$B.s$n.json; echo "straps $n: $(tail -1 $W/$B.s$n.log)"; done
IFS=';' read -ra FL <<< "$FILT"; n=0
for o in "${FL[@]}"; do [ -z "$o" ] && continue; n=$((n+1)); set -- $o; f=$1; shift; [[ $f == */* ]] || f=$TOOLS/$f
  python3 $f $cur $SRC/cu.json $W/$B.f$n.json "$@" > $W/$B.f$n.log 2>&1 || { echo "filter $n ($o) FAILED:"; tail -8 $W/$B.f$n.log; exit 1; }
  cur=$W/$B.f$n.json; echo "filter $n: $(tail -1 $W/$B.f$n.log)"; done
cp $cur $OUTS
