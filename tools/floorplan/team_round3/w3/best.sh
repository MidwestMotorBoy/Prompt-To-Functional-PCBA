#!/bin/bash
# best.sh <x> [seed=11]: the w3 fill setting of the best board (w3_U6_s11), then board.sh <x> for the full board
cd /home/claude/work/team/w3
env FILL_CLUSTER=3000 REPAIR_C=2 PSWAP=0.05 CL_OFFW=600 BIGFIRST=1 BIGFIRST_AT=0.3 PLONG=0.1 LONG_LEGAL=20 LSPREAD=0.7 WNEAR=50 SHORT_K=4 SHORT_L=3 SATR=3 DETAIL=3000000 DETAIL_BIG=1 DLONG=0.2 DT0=1.0 ESC=0.5 ./run.sh $1 ${2:-11}
