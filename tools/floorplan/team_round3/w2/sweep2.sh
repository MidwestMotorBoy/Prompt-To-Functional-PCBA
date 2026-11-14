cd /home/claude/work/hp; S=/home/claude/work/team/w2/fz.sh
W2_ERODE=0.3 W2_THIN=1 $S e3t 0
W2_ERODE=0.3 W2_THIN=1 W2_RASTER=center $S e3tc 0
W2_ERODE=0.5 W2_THIN=1 W2_RASTER=center $S e5tc 0
W2_MINA=5 $S a5 0
W2_MINA=10 W2_ADD=VBUS,PPHV,PP5V $S a10pd 0
W2_MINA=10 W2_ADD=VBUS,PPHV,PP5V $S a10pd15 0.15
