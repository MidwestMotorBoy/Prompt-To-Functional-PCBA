#!/bin/bash
# snap.sh <run> <round>
cd "$(dirname "$0")"; d=snaps/$1-r$2; mkdir -p $d; cp -r runs/$1/design $d/; find $d -name __pycache__ -prune -exec rm -rf {} +; echo "$1 r$2 $(date -u +%H:%M)" >> snaps/log.txt
