cd /home/claude/repo/docs/layout-teams/A
run() { n=$1; shift; echo "== $n | $1 | BUSB=$BUSB"; strapfix/tools/fastcu.sh stagepwr/runs/sc_v1A3 strapfix/runs/f_$n "$1" "" stagepwr/runs/full_v1A3 2>&1 | grep -v "json:\|^dc"; python3 strapfix/tools/summ.py strapfix/runs/f_$n; }
BUSB="--net=GND --layer=B.Cu --mode=fill --prio=0 --soft=1" run bgnd_only "-"
