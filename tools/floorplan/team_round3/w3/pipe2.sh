#!/bin/bash
# pipe2.sh x1 x2 ... : board + 2-min screen for each fill; the router runs under a lock so only one runs at a time
for x in "$@"; do cd /home/claude/work/team/w3; ./board.sh $x > board_$x.out 2>&1
  if grep -q "DRC errors 0" board_$x.out; then
    cd /home/claude/work/team; flock /home/claude/work/team/w3/router.lock ./route_trial.sh w3_$x 2 > /home/claude/work/team/w3/scr_$x.out 2>&1
    echo "$x: $(grep RESULT /home/claude/work/team/w3/board_$x.out) || $(grep 'step 120' r_w3_$x/route.log)" >> /home/claude/work/team/w3/screen.txt
  else echo "$x: $(grep RESULT /home/claude/work/team/w3/board_$x.out) || no screen" >> /home/claude/work/team/w3/screen.txt; fi
done
