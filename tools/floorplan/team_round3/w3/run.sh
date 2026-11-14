#!/bin/bash
# run.sh <x> [seed] [moves] : fill only on q7s2 skeleton with the w3 copy; log to w3/<x>.log
cd /home/claude/work/team/w3; E=/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith
export PYTHONPATH=/home/claude/prompt-to-functional-pcba/tools/copper
S=$(date +%s); REG_MARGIN=${RM:-3} CONSTRAINTS=$E/constraints.json BLOCK_FLOORPLAN=/home/claude/work/bfp7/floorplan_2.json python3 place_pack.py /home/claude/work/hp/q7s2_fz_clusters.json /home/claude/work/hp/q7s2_fz_dump.json /home/claude/work/hp/w3_$1_fill.json ${3:-0} ${2:-2} ${REF:-150000} /home/claude/work/anch/intent_pc.json ${WXA:-3} ${ESC:-0.5} > $1.log 2>&1
echo "time $(( $(date +%s)-S )) s" >> $1.log; python3 measure.py /home/claude/work/hp/w3_$1_fill.json $1.log >> $1.log 2>&1
