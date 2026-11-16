cd /home/claude/repo/docs/layout-teams/B
ST="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
date -u +%T; time bash tools/final_route.sh runs/r4chg-hot runs/p2b-full2aor --straps="$ST" --filters="pins.py" --route=80 --resume${1:+ --post="$1"}; date -u +%T
