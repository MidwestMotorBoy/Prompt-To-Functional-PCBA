#!/bin/bash
# runfix.sh <board.kicad_pcb> [tag=fix]: every comparison tool on one more board. The big solvers run one at a time (memory).
# Afterwards: python gmerge.py <tag>; (cd thermal; NTAG=<tag> python lossload.py); figures; NTAG=<tag> python build_page.py
cd "$(dirname "$0")"; C=$PWD; PY=${PY:-python3}
export PCB=$(realpath "$1"); export TAG=${2:-fix}
( export OMP_NUM_THREADS=1
  $PY groute.py > groute_$TAG.log 2>&1; $PY senspair.py > senspair_$TAG.log 2>&1; $PY custats.py > custats_$TAG.log 2>&1
  cd k; $PY viacur.py > via_$TAG.log 2>&1; $PY lossmap.py > lossmap_$TAG.log 2>&1
  mkdir -p r05_$TAG; cd r05_$TAG; RES=0.05 $PY ../kelvin.py > log.txt 2>&1
  cd $C; $PY coup.py > coup_$TAG.log 2>&1; $PY coup_post.py > coup_post_$TAG.log 2>&1; echo light done ) &
export OMP_NUM_THREADS=3
$PY run_hot2.py > hot_$TAG.log 2>&1; echo hot done
$PY run_gate3.py > gate3_$TAG.log 2>&1; echo gate done
wait
BOTH=1 ONLY='P2 LS gate leg A (Q501)' SUF=b $PY run_gate3.py > gate3b_$TAG.log 2>&1; echo gateb done
echo alldone
