cd /home/claude/repo/docs/layout-teams/B
ST="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
F1="links.py --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.3/95.7,103.8;ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu;trunk.py --w=5 --narrow=U403:0.8:2.0;straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15;pins.py"
date -u +%T; time bash tools/final_route.sh runs/r4chg-hot runs/p2b-m1fin --straps="$ST" --filters="$F1" --route=80 --resume --post="$1"; date -u +%T
