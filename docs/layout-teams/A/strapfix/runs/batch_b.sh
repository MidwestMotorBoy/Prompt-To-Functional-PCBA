cd /home/claude/repo/docs/layout-teams/A
M="--mode=strip+copy --w=3 --box=96,100,122,140"
run() { n=$1; shift; echo "== $n | $1 | BUSB=$BUSB"; strapfix/tools/fastcu.sh stagepwr/runs/sc_v1A3 strapfix/runs/f_$n "$1" "" stagepwr/runs/full_v1A3 2>&1 | grep -v "json:\|^dc"; python3 strapfix/tools/summ.py strapfix/runs/f_$n; }
BUSB="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1" run sc3_bgnd "$M"
BUSB="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1" run copy_bgnd "--mode=copy"
BUSB="" run sc3b "--mode=strip+copy --w=3 --box=96,100,122,140;78,118,96,140"
