#!/bin/bash
# dk.sh <command...>: run a command with a docker daemon that lives only as long as the command
D=""
if ! docker info >/dev/null 2>&1; then
  dockerd > /tmp/dockerd.log 2>&1 & D=$!
  for i in $(seq 120); do docker info >/dev/null 2>&1 && break; sleep 0.5; done
fi
"$@"; rc=$?
if [ -n "$D" ]; then kill $D; wait $D 2>/dev/null; fi
exit $rc
