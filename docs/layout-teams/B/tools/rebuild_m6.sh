#!/bin/bash
# rebuild_m6.sh <out dir> [--src=<source run dir>] [--board=<routed board.kicad_pcb> | --transplant=<run dir A>]
#               [--route=MIN] [--fin=MIN] [--no-hot] [--chain=<spec out>] [--screen] [--step=2|3] [--hotvia]
#   Plan p2-m6 (phase 2 round 3, lead): the plan of rebuild_best.sh (p2-m4: plan/p2-pins-u403b.json before the trunk)
#   with plan/p2-pins-r8.json (= r6 + worker A's Net-(U404-FB) path with the HL_5V pour corner trimmed). Worker A's
#   other round 3 entries (rebuild_m5.sh: SRP_F / SRN_F, Net-(C313-Pad2), Port 2 LDO_3V3, EN waypoints) are NOT in it:
#   the routed copper of runs/p2-m4 and its passes already holds those connections.
#   THE ONE COMMAND for the board in best_routed/ (about 15 min, start it as a background job with a 2 h limit):
#     bash tools/rebuild_m6.sh runs/<new> --src=runs/p2a-r5src --board=best_routed/monolith_routed.kicad_pcb
#   = plan p2-m6 with its screen (blocked edges, copper DRC, loss before routing), the given board as routed.kicad_pcb,
#   then tools/final_route.sh --resume with the same straps and filters and the finishing pass ($POST below), the
#   routed-board check and the seven hot loops: <out dir>/final.json and finished.kicad_pcb.
#   --transplant=<run dir A>: routed.kicad_pcb is made by tools/transplant.py from A/finished.kicad_pcb (plan board
#     A/cu.kicad_pcb) with plan/p2-m6-drop.json, then the same. The board in best_routed/ was made this way from
#     runs/p2b-r3en (the local route of plan p2-m4 in runs/p2-m4 + worker B's passes): runs/p2-m6.
#   Without --board / --transplant it is rebuild_best.sh for this plan: a NEW full route (steps 2 and 3 below), which
#   differs from the kept board by a few connections.
#   --chain=<spec out>: only the plan (tools/spec_chain.sh, about 1 min, no KiCad);
#   --screen: final_route.sh --route=0 --no-hot (blocked edges, copper DRC, loss) into <out dir>, then stop.
#   --hotvia: adds worker A's no-via areas over the hot GND pours as the last filter (ruleareas.py --hot
#     --hot_mode=vias); NOT for --board / --transplant while the board holds the three crossover vias in the Port 2 pour.
#   --step=2 runs only the route step, --step=3 only the finishing step (two background jobs of 2 h each).
#   1. the source run: tools/screen.sh <src> best_placement.json --hot=all (skipped when <src> already holds
#      bare.kicad_pcb, spec.json and cu.json; default <src> = <out dir>-src);
#   2. tools/final_route.sh <src> <out dir> with the straps and copper-plan filters below, full route (default 80 min
#      cap), stub trim only (--post="finish.sh --no-route"), no hot loops yet;
#   3. tools/final_route.sh ... --resume --post="finish.sh --modes=aor,aork --min=<fin> --tol=0.01": the
#      accept-or-revert finishing pass, then the routed-board check with the seven hot loops.
#   The filter string lives here and nowhere else.
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); TEAM=$(dirname "$TOOLS")
[ $# -ge 1 ] || { sed -n 2,18p "$0"; exit 2; }
OUT=$1; shift; SRC=""; RMIN=80; FMIN=20; HOT=""; CHAIN=""; SCREEN=""; STEP=""; NOHV=1; BOARD=""; TPL=""
for a in "$@"; do case $a in --src=*) SRC=${a#*=};; --route=*) RMIN=${a#*=};; --fin=*) FMIN=${a#*=};; --no-hot) HOT="--no-hot";; --chain=*) CHAIN=${a#*=};; --screen) SCREEN=1;; --step=*) STEP=${a#*=};; --hotvia) NOHV="";; --no-hotvia) NOHV=1;; --board=*) BOARD=$(readlink -f ${a#*=});; --transplant=*) TPL=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
SRC=${SRC:-$OUT-src}
ST="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
F="links.py --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.3/95.7,103.8"
F="$F;ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu"
F="$F;pins.py --rules=table --table=plan/p2-pins-u403b.json"
F="$F;trunk.py --w=5 --narrow=U403:0.8:2.0 --g=0.05"
F="$F;straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15"
F="$F;links.py --clr=0.25 --via=/USB~Port~1/VBUS|103.95,70.1 --via=/USB~Port~1/VBUS|108.9,70.35 --via=/USB~Port~1/VBUS|108.9,71.0 --link=/USB~Port~1/VBUS|B.Cu|0.4|103.95,70.1/103.95,69.25 --link=/USB~Port~1/VBUS|B.Cu|0.6|103.95,69.25/108.9,69.25/108.9,71.0"
F="$F;pins.py --table=plan/p2-pins-r8.json"
F="$F;links.py --clr=0.25 --via=/USB~Port~2/VBUS|91.1,70.35 --via=/USB~Port~2/VBUS|91.1,71.0 --via=/USB~Port~2/VBUS|95.9,70.35 --via=/USB~Port~2/VBUS|95.9,71.0 --link=/USB~Port~2/VBUS|B.Cu|0.6|91.1,71.0/91.1,69.25/95.9,69.25/95.9,71.0 --link=3V3|In3.Cu|0.3|102.85,78.375/101.15,76.675/101.15,76.275 --link=3V3|In3.Cu|0.3|86.12,117.52/90.14,117.52"
[ -z "$NOHV" ] && F="$F;ruleareas.py --hot --hot_mode=vias"
log() { echo "[rebuild] $(date -u +%H:%M:%S) $*" >&2; }
if [ -n "$CHAIN" ]; then bash $TOOLS/spec_chain.sh $SRC $CHAIN --straps="$ST" --filters="$F"; exit $?; fi
if [ -n "$SCREEN" ]; then bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=0 --no-hot > $OUT.log 2>&1; r=$?; tail -1 $OUT.log; exit $r; fi
if [ -f $SRC/bare.kicad_pcb ] && [ -f $SRC/spec.json ] && [ -f $SRC/cu.json ]; then log "source run $SRC kept"
else log "1. source run $SRC from best_placement.json"; bash $TOOLS/screen.sh $SRC $TEAM/best_placement.json --hot=all > $SRC.log 2>&1 || { echo "screen.sh failed, see $SRC.log"; exit 1; }; fi
if [ -n "$BOARD$TPL" ]; then
  POST="finish.sh --modes=aor --min=30 --tol=0.06 --long=30 --longx=--longptol=0.05 --aorx=--prtol=1.0"
  log "2. plan and screen: bash tools/final_route.sh $SRC $OUT --straps=... --filters=... --route=0 --no-hot"
  bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=0 --no-hot > $OUT.screen.log 2>&1 || { echo "screen failed, see $OUT.screen.log"; exit 1; }
  cp $OUT/final.json $OUT/final_screen.json
  if [ -n "$TPL" ]; then
    log "3. python3 tools/transplant.py $TPL/finished.kicad_pcb $TPL/cu.kicad_pcb $OUT/cu.kicad_pcb $OUT/routed.kicad_pcb --drop=plan/p2-m6-drop.json"
    python3 $TOOLS/transplant.py $TPL/finished.kicad_pcb $TPL/cu.kicad_pcb $OUT/cu.kicad_pcb $OUT/routed.kicad_pcb --drop=$TEAM/plan/p2-m6-drop.json > $OUT.transplant.log 2>&1 || { echo "transplant failed, see $OUT.transplant.log"; exit 1; }
  else cp $BOARD $OUT/routed.kicad_pcb; fi
  for e in kicad_pro kicad_dru; do cp $OUT/cu.$e $OUT/routed.$e; done
  log "4. bash tools/final_route.sh $SRC $OUT (same straps and filters) --route=80 --resume $HOT --post=\"$POST\""
  bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=80 --resume $HOT --post="$POST" > $OUT.resume.log 2>&1 || { echo "finishing step failed, see $OUT.resume.log"; exit 1; }
  STEP=done
fi
if [ "$STEP" != 3 ] && [ "$STEP" != done ]; then
log "2. bash tools/final_route.sh $SRC $OUT --straps=\"$ST\" --filters=\"$F\" --route=$RMIN --no-hot --post=\"finish.sh --no-route\""
bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=$RMIN --no-hot --post="finish.sh --no-route" > $OUT.route.log 2>&1 || { echo "route step failed, see $OUT.route.log"; exit 1; }
[ -f $OUT/routed.kicad_pcb ] || { echo "no routed board, see $OUT.route.log"; exit 1; }
fi
[ "$STEP" = 2 ] && { tail -1 $OUT.route.log | cut -c1-300; exit 0; }
if [ "$STEP" != done ]; then
log "3. bash tools/final_route.sh $SRC $OUT (same straps and filters) --route=$RMIN --resume $HOT --post=\"finish.sh --modes=aor,aork --min=$FMIN --tol=0.01\""
bash $TOOLS/final_route.sh $SRC $OUT --straps="$ST" --filters="$F" --route=$RMIN --resume $HOT --post="finish.sh --modes=aor,aork --min=$FMIN --tol=0.01" > $OUT.resume.log 2>&1 || { echo "finishing step failed, see $OUT.resume.log"; exit 1; }
fi
python3 - $OUT/final.json <<'P'
import json, sys
J = json.load(open(sys.argv[1])); r = J["routed"]
J["route"] = J.get("route") or {"text": "no new route (board given)", "timed_out": False}
print("FINAL route %s (timed out: %s); unconnected %d; DRC %d; power open %s; loose %s; loss %.3f W; PACK_P mohm %s; hot-pour items %s; hot loops %s, %s nH" % (
    J["route"]["text"], J["route"]["timed_out"], r["unconnected_items"], r["drc_errors"], r["power_open"] or "none", r["loose"] or "none",
    r["loss_W"], r.get("pack_p_mohm"), r.get("hot_pour_items"), J.get("hot_routed", {}).get("pass_count"), J.get("hot_routed", {}).get("sum_nH")))
P
