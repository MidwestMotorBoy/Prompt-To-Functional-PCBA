#!/bin/bash
# queue_route.sh <scorecard_outdir> <name>
#   Queue a full trial route on Logan's PC (route_server.py watches branch layout-team-D, folder D/route_queue).
#   Commits ONLY the three queued files on the current branch and pushes it to its own remote and to layout-team-D.
set -e
D=$(cd "$(dirname "$0")/.." && pwd); R=$(cd "$D/../../.." && pwd); OUT=$(cd "$1" && pwd); N=$2
[ -n "$N" ] || { echo "usage: queue_route.sh <outdir> <name>"; exit 1; }
exec 9>/tmp/teamD_git.lock; flock 9
mkdir -p "$D/route_queue"; F=""
for e in kicad_pcb kicad_pro kicad_dru; do cp "$OUT/cu.$e" "$D/route_queue/$N.$e"; F="$F docs/layout-teams/D/route_queue/$N.$e"; done
cd "$R"; BR=$(git rev-parse --abbrev-ref HEAD)
git add $F
git commit -q -m "Team D: queue full route $N" -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01LzE9v24TmVQ4GCxtaTstCR" -- $F
for i in 1 2 3 4; do git push -q -u origin "$BR" && git push -q origin "$BR:layout-team-D" && break; sleep $((2**i)); done
echo "queued: D/$N-$(git hash-object docs/layout-teams/D/route_queue/$N.kicad_pcb | cut -c1-8).json"
