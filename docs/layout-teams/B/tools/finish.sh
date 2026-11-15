#!/bin/bash
# finish.sh <out dir> [--min=30] [--modes=keepre] [--rips=900] [--riptime=900] [--maxrip=6] [--phases=4] [--capx=2]
#           [--hcx=0.16] [--viacost=4] [--hand=<tracks.json>] [--no-route] [--tol=0.001]
#   Team B finishing pass (final_route.sh --post="finish.sh ..."): reads <out>/routed.kicad_pcb and <out>/cu.kicad_pcb
#   (the copper plan the router started from) and writes <out>/finished.kicad_pcb. Work files in <out>/fin/.
#   1. KiCad DRC of the routed board.
#   2. While connections are open or DRC errors are left, one continuation route per mode in --modes (tools/router_b.py,
#      copy of the shared router, --cont): keepre = the nets with open connections keep their copper and only the
#      open connections are routed (nets with DRC errors are lifted and routed afresh); lift = every net with an
#      open connection or a DRC error loses its routed copper and is routed afresh. More pulls, time and search than the
#      first route (--rips --riptime --maxrip --phases --capx, --min minutes each); HighCurrent copper keeps --hcx (0.16:
#      the 0.25 mm rule on the grid's diagonal steps too); hot-loop pours are closed to other nets (--hotko with the
#      hot loops' parts). A pass is kept only if it leaves fewer open connections + DRC errors; the next starts from
#      the best board so far.
#   1b/2b. Stub trim (tools/fin_trim.py): stub ends of neighbouring pins named in a clearance error are moved to the
#      pad edge (CELL_1N against TS1 / BTP_INT / SMBD at U101), before the continuation and after each pass.
#   3. --hand=<json>: tools/handroute.py lays explicit tracks / vias (exact clearance check first).
#   4. Dangling ends the router left are removed (tools/fin_clean.py), zones refilled, DRC again.
#   5. Power guard (tools/fin_guard.py): dc_score loss and power opens no worse than the routed board's (+ --tol W),
#      no new track or via of another net in a hot-loop pour. The best candidate that passes becomes finished.kicad_pcb
#      (the routed board itself when none does).
#      Each pass gets --deadline=<min*60-300> s: past it the router stops pulling and starting phases and writes its
#      board, so the outer timeout (--min) does not kill a pass that has a better board (r1 of runs/p2r1_full1fin did).
#   Last two lines: 'finish: routed unconnected N {net: n} ; DRC errors M {type: n} ; loss ..., power open ...' and the
#   same for the finished board ('finish: finished (<candidate>) ...').
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
C=$R/tools/floorplan/example/monolith/constraints.json
OUT=$(cd "$1" && pwd); shift
MIN=30; MODES="keepre"; RIPS=900; RIPTIME=900; MAXRIP=6; PHASES=4; CAPX=2; HCX=0.16; VIAC=4; HAND=""; ROUTE=1; TOL=0.001
for a in "$@"; do case $a in --min=*) MIN=${a#*=};; --modes=*) MODES=${a#*=};; --rips=*) RIPS=${a#*=};; --riptime=*) RIPTIME=${a#*=};;
  --maxrip=*) MAXRIP=${a#*=};; --phases=*) PHASES=${a#*=};; --capx=*) CAPX=${a#*=};; --hcx=*) HCX=${a#*=};; --viacost=*) VIAC=${a#*=};;
  --hand=*) HAND=$(readlink -f ${a#*=});; --no-route) ROUTE=0;; --tol=*) TOL=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
[ -f $OUT/routed.kicad_pcb ] && [ -f $OUT/cu.kicad_pcb ] || { echo "finish: $OUT needs routed.kicad_pcb and cu.kicad_pcb"; exit 1; }
F=$OUT/fin; rm -rf $F; mkdir -p $F; cd $F
log() { echo "[finish] $(date +%T) $*"; }
K="docker run --rm -u 0 -v $F:/w -w /w kicad/kicad:10.0"
cp $OUT/routed.kicad_pcb r0.kicad_pcb; cp $OUT/cu.kicad_pcb keep.kicad_pcb
cp $R/tools/copper/cu_dump.py $TOOLS/fin_clean.py $TOOLS/fin_trim.py $TOOLS/router_b.py .; cp -r $S/pylib pylib
pro() { for e in kicad_pro kicad_dru; do cp $S/template/board.$e $1.$e; done; }
drc() { pro $1; $K sh -c "kicad-cli pcb drc --severity-all --format json -o $1.drc.json $1.kicad_pcb >/dev/null 2>&1"; }
nerr() { python3 -c "import json; print(sum(v['severity'] == 'error' for v in json.load(open('$1.drc.json'))['violations']))"; }
# trim <board> <out>: stub ends of neighbouring pins in clearance errors moved to the pad edge (tools/fin_trim.py)
trim() { [ "$(nerr $1)" = 0 ] && return 1
  log "stub ends in the clearance errors of $1 (fin_trim.py)"
  $K sh -c "python3 fin_trim.py $1.kicad_pcb $1.drc.json $2.kicad_pcb 2>&1 | grep -v -e swig -e Debug:" | sed 's/^/    /'
  [ -f $2.kicad_pcb ] || return 1; drc $2; log "trimmed: $(summ $2)"
  [ "$(score $2)" -lt "$(score $1)" ] || { log "trim not better, dropped"; return 1; }; }
score() { python3 - $1.drc.json <<'P'
import json, sys; d = json.load(open(sys.argv[1]))
print(len(d.get("unconnected_items", [])) + sum(v["severity"] == "error" for v in d["violations"]))
P
}
summ() { python3 - $1.drc.json <<'P'
import json, sys, re; from collections import Counter; d = json.load(open(sys.argv[1]))
u = Counter((re.search(r"\[(.*?)\]", x["items"][0]["description"]) or [0, "?"])[1] for x in d.get("unconnected_items", []))
e = Counter(v["type"] for v in d["violations"] if v["severity"] == "error")
print("unconnected %d %s ; DRC errors %d %s" % (sum(u.values()), dict(u), sum(e.values()), dict(e)))
P
}
HOT=$(python3 -c "
import json; h = json.load(open('$C'))['hot_loops']
print(','.join(sorted({r for v in h.values() for r in v['caps']} | {s.split('.')[0] for v in h.values() for s in v['switch_pins']})))")

log "1. DRC of the routed board and of the plan"
drc r0; drc keep; log "routed: $(summ r0)"
BEST=r0; CANDS="r0"
# 1b. stub trim first, so that the continuation does not lift (and maybe lose) a net only for a stub clearance error
trim r0 t0 && { BEST=t0; CANDS="t0 $CANDS"; }
# 2. continuation passes
p=0
for MODE in ${MODES//,/ }; do
  [ $ROUTE = 1 ] && [ "$(score $BEST)" != 0 ] || break
  p=$((p+1)); N=r$p; KR=""; [ $MODE = keepre ] && KR="--keepre"
  log "2. continuation pass $p ($MODE) from $BEST (${MIN} min; rips $RIPS, riptime $RIPTIME, maxrip $MAXRIP, phases $PHASES, capx $CAPX, hcx $HCX)"
  $K sh -c "PYTHONPATH=/w/pylib timeout ${MIN}m python3 -u router_b.py $BEST.kicad_pcb $BEST.drc.json $N.kicad_pcb --cont --keep=keep.kicad_pcb --orig=keep.drc.json --softnets=GND,PACK_P,3V3 --hcx=$HCX --viacost=$VIAC --hotko=$HOT --deadline=$((MIN*60-300)) --rips=$RIPS --riptime=$RIPTIME --maxrip=$MAXRIP --phases=$PHASES --capx=$CAPX $KR" > $N.log 2>&1
  rc=$?; [ $rc = 124 ] && log "pass $p timed out after $MIN min (no board written)"
  [ -f $N.kicad_pcb ] || { log "pass $p wrote no board (exit $rc)"; break; }
  grep -E "^ *(routed |continuation|unconnected after fill)" $N.log | sed 's/^/    /'
  drc $N; log "pass $p: $(summ $N)"
  if [ "$(score $N)" -lt "$(score $BEST)" ]; then BEST=$N; CANDS="$N $CANDS"; else log "pass $p not better, dropped"; fi
  trim $BEST t$p && { BEST=t$p; CANDS="t$p $CANDS"; }
done
# 3. hand-laid tracks
if [ -n "$HAND" ]; then
  log "3. hand tracks $HAND on $BEST"
  pro h; python3 $TOOLS/handroute.py $BEST.kicad_pcb h.kicad_pcb $HAND --no-drc > h.log 2>&1
  cat h.log | sed 's/^/    /'
  if [ -f h.kicad_pcb ]; then drc h; log "hand: $(summ h)"
    if [ "$(score h)" -lt "$(score $BEST)" ]; then BEST=h; CANDS="h $CANDS"; else log "hand tracks not better, dropped"; fi
  fi
fi
# 4. dangling ends
log "4. dangling ends of $BEST"
$K sh -c "python3 fin_clean.py $BEST.kicad_pcb keep.kicad_pcb $BEST.drc.json c.kicad_pcb 2>&1 | grep -v -e swig -e Debug:" | sed 's/^/    /'
if [ -f c.kicad_pcb ]; then drc c; log "cleaned: $(summ c)"
  if [ "$(score c)" -le "$(score $BEST)" ]; then BEST=c; CANDS="c $CANDS"; else log "cleaning opened connections, dropped"; fi
fi
# 5. power guard, best candidate first
log "5. power guard"
$K sh -c "python3 cu_dump.py r0.kicad_pcb r0.cu.json 2>&1 | grep -v swig"
python3 $R/tools/copper/dc_score.py r0.kicad_pcb r0.cu.json $C r0.dc.json > r0.dc.log 2>&1
PICK=r0
for c in $CANDS; do
  [ $c = r0 ] && break
  python3 $R/tools/copper/dc_score.py $c.kicad_pcb r0.cu.json $C $c.dc.json > $c.dc.log 2>&1
  python3 $TOOLS/fin_guard.py r0.kicad_pcb r0.cu.json $c.kicad_pcb r0.dc.json $c.dc.json --tol=$TOL > $c.guard.log 2>&1; rc=$?
  log "$c: $(head -1 $c.guard.log)"
  [ $rc = 0 ] && { PICK=$c; break; }
done
cp $PICK.kicad_pcb $OUT/finished.kicad_pcb; for e in kicad_pro kicad_dru; do cp $S/template/board.$e $OUT/finished.$e; done
L0=$(python3 -c "import json; d=json.load(open('r0.dc.json')); d=d.get('nets',d); print('%.4f W, power open %d' % (sum(v.get('loss_W',0) for v in d.values()), sum(len(v.get('open',[])) for v in d.values())))")
L1=$L0; [ $PICK != r0 ] && L1=$(python3 -c "import json; d=json.load(open('$PICK.dc.json')); d=d.get('nets',d); print('%.4f W, power open %d' % (sum(v.get('loss_W',0) for v in d.values()), sum(len(v.get('open',[])) for v in d.values())))")
echo "finish: routed $(summ r0) ; loss $L0"
echo "finish: finished ($PICK) $(summ $PICK) ; loss $L1"
