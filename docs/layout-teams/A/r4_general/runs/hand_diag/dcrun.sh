#!/bin/bash
cd /home/claude/repo/docs/layout-teams/A/r4_general/runs/hand_diag
for s in s0_stock s1_gate s3_ep s8_pair; do echo "$s $(bash ../../tools/dcq.sh ../sc_hand $s.json dcq_$s | grep DCQ)" >> dcq.txt; done
echo DONE >> dcq.txt
