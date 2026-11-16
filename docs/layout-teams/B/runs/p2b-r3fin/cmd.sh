cd /home/claude/repo/docs/layout-teams/B
source runs/p2a-look/strings.sh; source runs/p2-m4plan/strings.sh
bash tools/final_route.sh runs/p2a-r5src runs/p2b-r3fin --straps="$ST" --filters="$FR6" --route=80 --resume --post="finish.sh --modes=aor,aork,loss --min=35 --tol=0.01 --long=30 --hand=/home/claude/repo/docs/layout-teams/B/runs/p2b-r3hand/hand.json"
