#!/bin/bash
# q.sh "NAME:ENV1=a ENV2=b" ... : run fills one after another
cd /home/claude/work/team/w3
for spec in "$@"; do n=${spec%%:*}; e=${spec#*:}; env $e ./run.sh $n ${SEED:-2}; done
