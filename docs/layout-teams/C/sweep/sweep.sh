#!/bin/bash
# sweep.sh: background launcher and bounded wait for sweep.py (foreground shell calls are capped at 10 min).
#   sweep.sh bg <log> <sweep.py arguments...>   start "python3 sweep.py <args>" detached; the log ends with a line DONE
#   sweep.sh wait <log> [seconds=540]           wait until the log has DONE (or the time is up); prints the log tail
#   sweep.sh status                             load average, running scorecard/placer processes, scorecard lock holder
H=$(cd "$(dirname "$0")" && pwd)
case "$1" in
  bg)   L=$2; shift 2; mkdir -p "$(dirname "$L")"
        (nohup bash -c "cd $H && python3 sweep.py $(printf '%q ' "$@"); echo DONE" > "$L" 2>&1 &)
        echo "started; log $L";;
  wait) L=$2; T=${3:-540}
        timeout $T bash -c "until grep -q '^DONE' '$L' 2>/dev/null; do sleep 10; done"
        grep -q '^DONE' "$L" && echo "== finished" || echo "== still running (call wait again)"; tail -15 "$L";;
  status) uptime; ps aux --sort=-%cpu | grep -E 'router.py|cplace.py|dc_score|hot_score|plan_copper|thermal.py|kicad-cli' | grep -v grep | awk '{print $3"%", substr($0, index($0,$11), 110)}'
        fuser /home/claude/work/C/sweep/.score.lock 2>/dev/null && echo "(pids above hold the scorecard lock file open)";;
  *)    sed -n 2,6p "$0";;
esac
