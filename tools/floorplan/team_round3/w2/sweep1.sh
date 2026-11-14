cd /home/claude/work/hp; S=/home/claude/work/team/w2/fz.sh
W2_RASTER=center $S c15 0.15
$S r0 0
W2_ERODE=0.3 $S e3 0
W2_ERODE=0.6 $S e6 0
W2_ERODE=0.6 W2_HOTFULL=1 $S e6h 0
W2_ERODE=0.3 W2_RASTER=center $S e3c 0
W2_MINA=6 $S a6 0.15
W2_MINA=10 $S a10 0.15
W2_SKIP=/,GND,PACK_P,CELL_N $S none 0
