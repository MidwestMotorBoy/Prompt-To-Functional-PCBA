#!/bin/bash
# finish.sh <board under new/> [--errors]: full-rule DRC in fin/ (project name Monolith, so the custom rules apply), drop the
# router copper the report flags (dangling ends; with --errors also clearance / hole / edge / keep-out offenders), repeat
# until quiet -> new/<name>_c.kicad_pcb
b=${1%.kicad_pcb}; e=$2
cp new/$b.kicad_pcb fin/Monolith.kicad_pcb
for k in 1 2 3 4 5 6 7 8; do
  ./drc.sh fin > fin/sum.txt
  ./kc python3 /w/cleanup.py /w/fin/Monolith.kicad_pcb /w/fin/Monolith.kicad_pcb /w/fin/drc.json /w/new/Monolith.kicad_pcb $e > fin/cleanup.log 2>&1
  r=$(cat fin/Monolith.kicad_pcb.cleanup.txt)
  echo "round $k: $r"
  case "$r" in "removed 0 "*) break;; esac
done
./drc.sh fin
cp fin/Monolith.kicad_pcb new/${b}_c.kicad_pcb; cp base/Monolith.kicad_pro new/${b}_c.kicad_pro
