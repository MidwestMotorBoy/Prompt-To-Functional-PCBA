#!/bin/bash
# Part 1: split-copper comparison scores (one at a time), each queued for a PC route right after.
A=/home/claude/repo/docs/layout-teams/A; S=$A/tools/score_board_split.sh; W=$A/stagepwr/runs
$S $W/split_rebuild_base $A/rebuild/base_placement.json --route=0 --no-hot > $W/split_rebuild_base.log 2>&1
$A/queue_route.sh $W/split_rebuild_base stagepwr-split-rebuild-base >> $W/split_rebuild_base.log 2>&1
$S $W/split_generic $A/generic/best_placement.json --route=0 --no-hot > $W/split_generic.log 2>&1
$A/queue_route.sh $W/split_generic stagepwr-split-generic >> $W/split_generic.log 2>&1
$S $W/split_hand --route=0 --no-hot > $W/split_hand.log 2>&1
$A/queue_route.sh $W/split_hand stagepwr-split-hand >> $W/split_hand.log 2>&1
echo PART1 DONE
