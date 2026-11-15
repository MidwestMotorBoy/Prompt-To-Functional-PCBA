#!/bin/bash
# route_result.sh <name> : print the PC route result for route_queue/<name> if it is ready (exit 1 if not yet)
D=$(cd "$(dirname "$0")/.." && pwd); R=$(cd "$D/../../.." && pwd); cd "$R"
SHA=$(git hash-object docs/layout-teams/F/route_queue/$1.kicad_pcb | cut -c1-8)
git fetch -q origin route-results 2>/dev/null
git show origin/route-results:F/$1-$SHA.json 2>/dev/null || { echo "not ready: F/$1-$SHA.json"; exit 1; }
