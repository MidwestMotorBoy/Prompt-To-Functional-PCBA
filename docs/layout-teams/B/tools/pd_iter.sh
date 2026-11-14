#!/bin/bash
# pd_iter.sh <name> <recipe 01> <02> <03> <04> <05> <06> [--screen | --hot | --esc]
#   Port 1 PD-pocket iteration: builds a port1 fragment from the given recipe files (border first) into
#   runs/<name>/frag.json (+ meta), check.py against port2/pack, then plan_only.sh (planner + DC, ~45 s) and zooms of
#   U401 (F, B) and the input bulk capacitors. --screen: partial screen without hot loops; --hot: with the three
#   Port 1 loops. Env PLANOPT="--escape=0.8" passes planner options to plan_only2.sh.
set -o pipefail
cd "$(dirname "$0")/.."
N=$1; shift; R=(); OPT=""
for a in "$@"; do case $a in --*) OPT="$OPT $a";; *) R+=("$a");; esac; done
O=runs/$N; mkdir -p $O
python3 tools/secplace.py recipes/common/border.json "${R[@]}" --group=port1 --out=$O/frag.json --others=fragments > $O/secplace.log 2>&1 || { echo "[pd_iter] secplace failed"; grep -i "fail" $O/secplace.log | head; exit 1; }
grep -iE "FAIL|warn" $O/secplace.log | head -5
python3 tools/check.py $O/frag.json fragments/port2.json fragments/pack.json --group=port1 --png=$O/check.png > $O/check.log 2>&1; grep -E "overlap|reserved|ring |region|pin |escape|hard" $O/check.log | cut -c1-400
if [[ $OPT == *--screen* || $OPT == *--hot* ]]; then
  H=""; [[ $OPT == *--hot* ]] && H='--hot=USB Port 1/HL_5V,USB Port 1/HL_IN,USB Port 1/HL_OUT'
  if [ -n "$H" ]; then bash tools/screen.sh $O $O/frag.json --partial "$H" > $O.out 2>&1; else bash tools/screen.sh $O $O/frag.json --partial > $O.out 2>&1; fi
  grep SCORE $O.out | cut -c1-600; python3 tools/blame.py $O > $O/blame.txt 2>&1; grep -E "^blocked|by chip" $O/blame.txt
else
  bash tools/plan_only2.sh $O/plan $O/frag.json "$PLANOPT" 2>&1 | grep -E "AC_SNS_N|PPHV|VBUS|PP5V|open|drc" | cut -c1-300
  O=$O/plan
fi
python3 tools/zoom.py $O $O/u401_F.png 100,72,113,90 F.Cu 40 > /dev/null; python3 tools/zoom.py $O $O/u401_B.png 100,72,113,90 B.Cu 40 > /dev/null
python3 tools/zoom.py $O $O/in_F.png 100,84,114,104 F.Cu 30 > /dev/null
echo "[pd_iter] pictures in $O"
