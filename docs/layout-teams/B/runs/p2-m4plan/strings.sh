FU3="links.py --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.3/95.7,103.8;ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu;pins.py --rules=table --table=plan/p2-pins-u403b.json;trunk.py --w=5 --narrow=U403:0.8:2.0 --g=0.05;straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15"
FR6="$FU3;$LP1;pins.py --table=plan/p2-pins-r6.json;$LP2"
LP3="$LP2 --link=3V3|In3.Cu|0.3|86.12,117.52/90.14,117.52"
FR6="$FU3;$LP1;pins.py --table=plan/p2-pins-r6.json;$LP3"
