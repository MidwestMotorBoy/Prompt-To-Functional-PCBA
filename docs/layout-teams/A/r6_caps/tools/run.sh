#!/bin/bash
# run.sh <name> <CAPFIX var name|none> [scorecard args...]: r6 scorecard of the team best placement into runs/<name>
. /home/claude/repo/docs/layout-teams/A/r6_caps/tools/env_r6.sh
N=$1; V=$2; shift 2; [ "$V" = none ] && unset CAPFIX || export CAPFIX="${!V}"
echo "CAPFIX=$CAPFIX" > /home/claude/repo/docs/layout-teams/A/r6_caps/runs/$N.opts
/home/claude/repo/docs/layout-teams/A/r6_caps/tools/score_board_r6.sh /home/claude/repo/docs/layout-teams/A/r6_caps/runs/$N $R6_PLACEMENT --plan="$BEST_PLAN_R5" "$@"
