#!/bin/bash
# queue_route.sh <scorecard_outdir> <name>
#   Queue a full trial route on Logan's PC (see CHARTER.md "Full routes on Logan's PC").
#   Copies cu.kicad_pcb/.kicad_pro/.kicad_dru to route_queue/<name>.*, commits ONLY those files, pushes layout-team-A.
#   Serialised with flock so parallel agents do not collide. Prints the result path to poll with route_result.sh.
set -e
A=$(cd "$(dirname "$0")" && pwd); R=$(cd "$A/../../.." && pwd); OUT=$(cd "$1" && pwd); N=$2
[ -n "$N" ] || { echo "usage: queue_route.sh <outdir> <name>"; exit 1; }
exec 9>/tmp/teamA_git.lock; flock 9
mkdir -p "$A/route_queue"
for e in kicad_pcb kicad_pro kicad_dru; do cp "$OUT/cu.$e" "$A/route_queue/$N.$e"; done
cd "$R"
git add docs/layout-teams/A/route_queue/$N.kicad_pcb docs/layout-teams/A/route_queue/$N.kicad_pro docs/layout-teams/A/route_queue/$N.kicad_dru
git commit -q -m "Team A: queue full route $N" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- docs/layout-teams/A/route_queue/$N.kicad_pcb docs/layout-teams/A/route_queue/$N.kicad_pro docs/layout-teams/A/route_queue/$N.kicad_dru
for i in 1 2 3 4; do git push -q -u origin layout-team-A && break; sleep $((2**i)); done
SHA=$(git hash-object docs/layout-teams/A/route_queue/$N.kicad_pcb | cut -c1-8)
echo "queued: A/$N-$SHA.json"
