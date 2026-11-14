#!/bin/bash
# route_result.sh <name>  : print the PC route result for route_queue/<name> if it is ready (exit 1 if not yet)
A=$(cd "$(dirname "$0")" && pwd); R=$(cd "$A/../../.." && pwd); cd "$R"
SHA=$(git hash-object docs/layout-teams/A/route_queue/$1.kicad_pcb | cut -c1-8)
( exec 9>/tmp/teamA_git.lock; flock 9; git fetch -q origin route-results 2>/dev/null )
git show origin/route-results:A/$1-$SHA.json 2>/dev/null || { echo "not ready: A/$1-$SHA.json"; exit 1; }
