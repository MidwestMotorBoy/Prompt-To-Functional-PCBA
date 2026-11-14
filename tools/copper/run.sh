#!/bin/bash
# run.sh <work dir> <stem> <constraints.json> [plan_copper options, e.g. --mirror=3 --grow=1.5]
# In <work dir>: <stem>_bare.kicad_pcb (placed, no copper) with its .kicad_pro and .kicad_dru beside it.
# Dump, plan, write and fill, DRC, dump again, DC solve with loss map, thermal. Needs Docker with kicad/kicad:10.0.
set -eo pipefail
W=$(cd "$1" && pwd); S=$2; C=$(cd "$(dirname "$3")" && pwd)/$(basename "$3"); shift 3; T=$(cd "$(dirname "$0")" && pwd)
K="docker run --rm -u 0 -v $W:/w -v $T:/t -w /w kicad/kicad:10.0"
cd "$W"; for e in kicad_pro kicad_dru; do [ -f ${S}_bare.$e ] && cp ${S}_bare.$e ${S}_cu.$e; done
$K python3 /t/cu_dump.py ${S}_bare.kicad_pcb ${S}_bare.json 2>&1 | grep -v swig
python3 $T/plan_copper.py ${S}_bare.json $C ${S}_spec.json "$@" | grep -v "left to router \[\]"
$K sh -c "python3 /t/write_copper.py ${S}_bare.kicad_pcb ${S}_spec.json ${S}_cu.kicad_pcb 2>&1 | grep -v swig; kicad-cli pcb drc --severity-all --format json -o ${S}_cu_drc.json ${S}_cu.kicad_pcb >/dev/null 2>&1; python3 /t/cu_dump.py ${S}_cu.kicad_pcb ${S}_cu.json | grep -v swig"
python3 -c "
import json,collections
d=json.load(open('${S}_cu_drc.json')); e=[v for v in d['violations'] if v['severity']=='error']
print('DRC errors', len(e)); [print(' ', v['type'], v['description'][:70]) for v in e[:20]]"
python3 $T/dc_score.py ${S}_cu.kicad_pcb ${S}_cu.json $C ${S}_dc.json --lossmap=${S}_loss.npz > ${S}_dc.log
python3 $T/thermal.py ${S}_cu.kicad_pcb ${S}_cu.json $C ${S}_loss.npz ${S}_th.json --png=${S}_th.png > /dev/null
python3 - ${S}_dc.json ${S}_th.json <<'P'
import json,sys
r=json.load(open(sys.argv[1])); r=r.get('nets',r); th=json.load(open(sys.argv[2]))
for k,v in sorted(r.items()):
  if isinstance(v,dict): print(f"{k[-26:]:28}{v.get('worst_drop_mV')!s:>7} mV {v.get('loss_W')!s:>7} W  open {v.get('open')}")
print('copper loss W', round(sum(v.get('loss_W',0) for v in r.values() if isinstance(v,dict)),3), ' thermal: max rise', th['max_rise_K'], 'K, mean', th['mean_rise_K'], 'K')
P
