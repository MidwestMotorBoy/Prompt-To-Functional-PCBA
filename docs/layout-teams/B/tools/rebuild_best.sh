#!/bin/bash
# rebuild_best.sh <out dir> [--src=<source run dir>] [--route=MIN] [--fin=MIN] [--no-hot]
#   ONE command from the placement to the routed, finished and scored board of team B (phase 2).
#   1. the source run: tools/screen.sh <src> best_placement.json --hot=all (skipped when <src> already holds
#      bare.kicad_pcb, spec.json and cu.json; default <src> = <out dir>-src);
#   2. tools/final_route.sh <src> <out dir> with the straps and copper-plan filters below, full route (default 80 min
#      cap), stub trim only (--post="finish.sh --no-route"), no hot loops yet;
#   3. tools/final_route.sh ... --resume --post="finish.sh --modes=aor,aork --min=<fin> --tol=0.01": the
#      accept-or-revert finishing pass (two passes of <fin> minutes, default 20), then the routed-board check with the
#      seven hot loops. Result: <out dir>/final.json, finished.kicad_pcb, routed/ (the scored board and its numbers).
#   Steps 2 and 3 are two calls so that each stays under the 2 h limit of a background job; start this script with a
#   4 h limit, or run the steps by hand (the two commands are printed).
#   The filter string is the lead's merge of phase 2 round 2 (LOG.md, 2026-11-16): plan/p2-pins-u403b.json before the
#   trunk, plan/p2-pins-r6.json after it. Change it here and nowhere else.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); TEAM=$(dirname "$TOOLS")
[ $# -ge 1 ] || { sed -n 2,14p "$0"; exit 2; }
OUT=$1; shift; SRC=""; RMIN=80; FMIN=20; HOT=""
for a in "$@"; do case $a in --src=*) SRC=${a#*=};; --route=*) RMIN=${a#*=};; --fin=*) FMIN=${a#*=};; --no-hot) HOT="--no-hot";; *) echo "unknown option $a"; exit 2;; esac; done
SRC=${SRC:-$OUT-src}
ST="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
F="links.py --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.3/95.7,103.8"
F="$F;ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu"
F="$F;pins.py --rules=table --table=plan/p2-pins-u403b.json"
F="$F;trunk.py --w=5 --narrow=U403:0.8:2.0 --g=0.05"
F="$F;straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15"
F="$F;links.py --clr=0.25 --via=/USB~Port~1/VBUS|103.95,70.1 --via=/USB~Port~1/VBUS|108.9,70.35 --via=/USB~Port~1/VBUS|108.9,71.0 --link=/USB~Port~1/VBUS|B.Cu|0.4|103.95,70.1/103.95,69.25 --link=/USB~Port~1/VBUS|B.Cu|0.6|103.95,69.25/108.9,69.25/108.9,71.0"
F="$F;pins.py --table=plan/p2-pins-r6.json"
F="$F;links.py --clr=0.25 --via=/USB~Port~2/VBUS|91.1,70.35 --via=/USB~Port~2/VBUS|91.1,71.0 --via=/USB~Port~2/VBUS|95.9,70.35 --via=/USB~Port~2/VBUS|95.9,71.0 --link=/USB~Port~2/VBUS|B.Cu|0.6|91.1,71.0/91.1,69.25/95.9,69.25/95.9,71.0 --link=3V3|In3.Cu|0.3|102.85,78.375/101.15,76.675/101.15,76.275 --link=3V3|In3.Cu|0.3|86.12,117.52/90.14,117.52"
log() { echo "[rebuild] $(date -u +%H:%M:%S) $*" >&2; }
if [ -f $SRC/bare.kicad_pcb ] && [ -f $SRC/spec.json ] && [ -f $SRC/cu.json ]; then log "source run $SRC kept"
else log "1. source run $SRC from best_placement.json"; bash $TOOLS/screen.sh $SRC $TEAM/best_placement.json --hot=all > $SRC.log 2>&1 || { echo "screen.sh failed, see $SRC.log"; exit 1; }; fi
log "2. bash tools/final_route.sh $SRC $OUT --straps=\"$ST\" --filters=\"$F\" --route=$RMIN --no-hot --post=\"finish.sh --no-route\""
bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=$RMIN --no-hot --post="finish.sh --no-route" > $OUT.route.log 2>&1 || { echo "route step failed, see $OUT.route.log"; exit 1; }
[ -f $OUT/routed.kicad_pcb ] || { echo "no routed board, see $OUT.route.log"; exit 1; }
log "3. bash tools/final_route.sh $SRC $OUT (same straps and filters) --route=$RMIN --resume $HOT --post=\"finish.sh --modes=aor,aork --min=$FMIN --tol=0.01\""
bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=$RMIN --resume $HOT --post="finish.sh --modes=aor,aork --min=$FMIN --tol=0.01" > $OUT.resume.log 2>&1 || { echo "finishing step failed, see $OUT.resume.log"; exit 1; }
python3 - $OUT/final.json <<'P'
import json, sys
J = json.load(open(sys.argv[1])); r = J["routed"]
print("FINAL route %s (timed out: %s); unconnected %d; DRC %d; power open %s; loose %s; loss %.3f W; PACK_P mohm %s; hot-pour items %s; hot loops %s, %s nH" % (
    J["route"]["text"], J["route"]["timed_out"], r["unconnected_items"], r["drc_errors"], r["power_open"] or "none", r["loose"] or "none",
    r["loss_W"], r.get("pack_p_mohm"), r.get("hot_pour_items"), J.get("hot_routed", {}).get("pass_count"), J.get("hot_routed", {}).get("sum_nH")))
P
