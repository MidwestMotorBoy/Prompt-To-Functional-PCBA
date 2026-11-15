#!/bin/bash
# poll.sh name... : one line per PC route result (routed failed edges minutes status) or 'not ready'
A=/home/claude/repo/docs/layout-teams/A
for n in "$@"; do $A/route_result.sh $n 2>&1 | python3 -c "import sys,json
t=sys.stdin.read()
try: d=json.loads(t); print('$n',d['routed'],d['failed'],d['edges'],d['minutes'],d['status'])
except Exception: print('$n','not ready')"; done
