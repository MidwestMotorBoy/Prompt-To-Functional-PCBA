#!/bin/bash
# finish.sh <out dir> [--min=30] [--modes=keepre|aor] [--rips=900] [--riptime=900] [--maxrip=6] [--phases=4] [--capx=2]
#           [--hcx=0.16] [--viacost=4] [--hand=<tracks.json>] [--no-route] [--tol=0.001]
#           [--tasktime=90] [--taskrips=12] [--sweeps=3] [--no-lift] [--no-pieces] [--no-pcheck] [--kelvin] [--closefill=NET]
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
#   Round 2 (phase 2): --modes=aor, the accept-or-revert pass (router_b.py --cont --keepre --split --aor): the routed copper
#      is cut into pieces (pad to pad, never through a pad); one task at a time, shortest open connection first, then
#      (--lift, on unless --no-lift) every piece with copper in a hot-loop pour of the plan (tools/hot_tracks.py) is lifted
#      and laid again with the hot pours closed; a task may pull pieces (--taskrips=12, --tasktime=90 s) but must lay
#      every pulled piece again, KiCad's own unconnected count must drop (open task) or hold (lift task), and (--pcheck,
#      on unless --no-pcheck) the PACK_P + 3V3 + GND loss after a refill may rise by --ptol (2 mW) per task and --pbudget
#      (5 mW) in all, no
#      PACK_P terminal past 3.0 mohm, no power open; otherwise the board is put back as it was. Sweeps repeat
#      (--sweeps=3) while one accepts something. Power pieces come as isl.py edges (--pieces, off with --no-pieces): a
#      cut-off In2 / In3 island is routed to the main body, never to itself. --kelvin lets tasks pull Kelvin pieces,
#      --closefill=NET closes NET's fills to new channels; mode aork is an aor pass with --kelvin (a Kelvin piece laid
#      again may be at most 1.3 x + 1 mm as long as before). Dead power copper (fin_islands.py, no pad) is removed first
#      (fin_dead.py). The pass is kept when unconnected + DRC errors drop, or hold with fewer hot-pour items.
#   Last two lines: 'finish: routed unconnected N {net: n} ; DRC errors M {type: n} ; loss ..., power open ...' and the
#   same for the finished board ('finish: finished (<candidate>) ...').
set -o pipefail
TOOLS=$(cd "$(dirname "$0")" && pwd); R=$(cd "$TOOLS/../../../.." && pwd); S=$R/tools/score
C=$R/tools/floorplan/example/monolith/constraints.json
OUT=$(cd "$1" && pwd); shift
MIN=30; MODES="keepre"; RIPS=900; RIPTIME=900; MAXRIP=6; PHASES=4; CAPX=2; HCX=0.16; VIAC=4; HAND=""; ROUTE=1; TOL=0.001
TASKT=90; TASKR=12; SWEEPS=3; LIFT=1; PIECES=1; AOREX=""; CLOSE=none; KELV=""; PCHK=1; PTOL=0.002; PBUD=0.005
for a in "$@"; do case $a in --min=*) MIN=${a#*=};; --modes=*) MODES=${a#*=};; --rips=*) RIPS=${a#*=};; --riptime=*) RIPTIME=${a#*=};;
  --tasktime=*) TASKT=${a#*=};; --taskrips=*) TASKR=${a#*=};; --sweeps=*) SWEEPS=${a#*=};; --no-lift) LIFT=0;; --no-pieces) PIECES=0;; --aorx=*) AOREX="$AOREX ${a#*=}";;
  --closefill=*) CLOSE=${a#*=};; --kelvin) KELV="--aorkelvin";; --no-pcheck) PCHK=0;; --ptol=*) PTOL=${a#*=};; --pbudget=*) PBUD=${a#*=};;
  --maxrip=*) MAXRIP=${a#*=};; --phases=*) PHASES=${a#*=};; --capx=*) CAPX=${a#*=};; --hcx=*) HCX=${a#*=};; --viacost=*) VIAC=${a#*=};;
  --hand=*) HAND=$(readlink -f ${a#*=});; --no-route) ROUTE=0;; --tol=*) TOL=${a#*=};; *) echo "unknown option $a"; exit 2;; esac; done
[ -f $OUT/routed.kicad_pcb ] && [ -f $OUT/cu.kicad_pcb ] || { echo "finish: $OUT needs routed.kicad_pcb and cu.kicad_pcb"; exit 1; }
F=$OUT/fin; rm -rf $F; mkdir -p $F; cd $F
log() { echo "[finish] $(date +%T) $*"; }
K="docker run --rm -u 0 -v $F:/w -w /w kicad/kicad:10.0"
cp $OUT/routed.kicad_pcb r0.kicad_pcb; cp $OUT/cu.kicad_pcb keep.kicad_pcb
cp $R/tools/copper/cu_dump.py $TOOLS/fin_clean.py $TOOLS/fin_trim.py $TOOLS/fin_dead.py $TOOLS/router_b.py $R/tools/battery-bank/groundup/isl.py .; cp -r $S/pylib pylib
CUJ=$OUT/cu.json; [ -f $CUJ ] || CUJ=$OUT/routed/cu.json        # pads, outline, keep-outs (same placement)
# the per-task power check of the accept-or-revert pass runs dc_score.py inside KiCad's container: copy it, its helpers,
# the constraints, the pads, and the host's shapely (same Python ABI) next to the router
cp $R/tools/copper/dc_score.py $R/tools/copper/roles.py $R/tools/copper/sx.py . ; cp $C cons.json; cp $CUJ pc_cu.json
SHP=$(python3 -c "import shapely, os; print(os.path.dirname(shapely.__file__))" 2>/dev/null)
[ -n "$SHP" ] && cp -r $SHP pylib/ && { [ -d $SHP.libs ] && cp -r $SHP.libs pylib/; true; } || PCHK=0
# hot <board>: router copper of other nets in hot-loop pours (tools/hot_tracks.py against the plan), count only
hot() { python3 $TOOLS/hot_tracks.py keep.kicad_pcb $CUJ $1.kicad_pcb $1.hot.json > $1.hot.log 2>&1
  python3 -c "import json; d=json.load(open('$1.hot.json')); print(d['tracks'] + d['vias'])"; }
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
# 1c. dead power copper (pieces of PACK_P / 3V3 / GND that hold no pad): removed (tools/fin_islands.py + fin_dead.py)
python3 $TOOLS/fin_islands.py $BEST.kicad_pcb $CUJ --out=$BEST.pieces.json | sed 's/^/    /'
if grep -q '"kind": "dead"' $BEST.pieces.json; then
  log "dead power copper on $BEST: removed (fin_dead.py)"
  $K sh -c "python3 fin_dead.py $BEST.kicad_pcb $BEST.pieces.json d0.kicad_pcb 2>&1 | grep -v -e swig -e Debug:" | sed 's/^/    /'
  if [ -f d0.kicad_pcb ]; then drc d0; log "dead copper removed: $(summ d0)"
    if [ "$(score d0)" -le "$(score $BEST)" ]; then BEST=d0; CANDS="d0 $CANDS"; else log "removal opened something, dropped"; fi; fi
fi
# 2. continuation passes
p=0
for MODE in ${MODES//,/ }; do
  [ $ROUTE = 1 ] || break
  HB=$(hot $BEST)
  [ "$(score $BEST)" != 0 ] || [ ${MODE:0:3} = aor -a $LIFT = 1 -a "$HB" != 0 ] || break
  p=$((p+1)); N=r$p; KR=""; [ $MODE = keepre ] && KR="--keepre"
  KP="$KELV"; [ $MODE = aork ] && { KP="--aorkelvin"; MODE=aor; }     # aork: an aor pass that may pull Kelvin pieces
  if [ $MODE = aor ]; then
    # accept-or-revert (router_b.py --aor): one open connection (shortest first) or one hot-pour piece at a time, the
    # board put back as it was unless the task lays everything it pulled; the power pieces as isl.py edges (--pieces)
    RPT=$BEST.drc.json; PX=""; LX=""
    if [ $PIECES = 1 ]; then
      $K sh -c "python3 isl.py $BEST.kicad_pcb '^(PACK_P|3V3)\$' isl$p.json 2>&1 | grep '^=='" | sed 's/^/    /'
      python3 $TOOLS/fin_report.py $BEST.drc.json isl${p}_edges.json a$p.drc.json | sed 's/^/    /'; RPT=a$p.drc.json; PX="--pieces=isl${p}_pieces.json"
    fi
    [ $LIFT = 1 ] && [ "$HB" != 0 ] && { cp $BEST.hot.json lift$p.json; LX="--lift=lift$p.json"; }
    log "2. accept-or-revert pass $p from $BEST (deadline ${MIN} min; task ${TASKT} s / ${TASKR} pulls, sweeps $SWEEPS; hot-pour items $HB)"
    $K sh -c "PYTHONPATH=/w/pylib timeout $((MIN+5))m python3 -u router_b.py $BEST.kicad_pcb $RPT $N.kicad_pcb --cont --keep=keep.kicad_pcb --orig=keep.drc.json --softnets=GND,PACK_P,3V3 --hcx=$HCX --viacost=$VIAC --hotko=$HOT --deadline=$((MIN*60-120)) --capx=$CAPX --keepre --split --aor --tasktime=$TASKT --taskrips=$TASKR --sweeps=$SWEEPS $PX $LX $KP $([ "$CLOSE" != none ] && echo --closefill=$CLOSE) $([ $PCHK = 1 ] && echo --pcheck=pc_cu.json:cons.json:$PTOL:$PBUD) $AOREX" > $N.log 2>&1
    rc=$?; [ $rc = 124 ] && log "pass $p timed out after $((MIN+5)) min (no board written)"
    [ -f $N.kicad_pcb ] || { log "pass $p wrote no board (exit $rc)"; break; }
    grep -E "^ *(aor|unconnected after fill)" $N.log | sed 's/^/    /'
    drc $N; HN=$(hot $N); log "pass $p: $(summ $N) ; hot-pour items $HN"
    trim $N t$p && { N=t$p; HN=$(hot $N); }
    if [ "$(score $N)" -lt "$(score $BEST)" ] || { [ "$(score $N)" = "$(score $BEST)" ] && [ "$HN" -lt "$HB" ]; }; then BEST=$N; CANDS="$N $CANDS"
    else log "pass $p not better (score $(score $N) vs $(score $BEST), hot $HN vs $HB), dropped"; fi
    continue
  fi
  [ "$(score $BEST)" != 0 ] || break
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
  pro h; python3 $TOOLS/handroute.py $BEST.kicad_pcb h.kicad_pcb $HAND --no-drc --keep=keep.kicad_pcb > h.log 2>&1
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
