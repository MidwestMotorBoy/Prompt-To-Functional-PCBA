cd /home/claude/repo/docs/layout-teams/B
source runs/p2a-look/strings.sh; source runs/p2-m4plan/strings.sh
# routed.kicad_pcb here = runs/p2b-r3en/finished.kicad_pcb (p2-m4 route + aor, aork, loss, hand tracks, then aork + loss again)
bash tools/final_route.sh runs/p2a-r5src runs/p2b-r3en2 --straps="$ST" --filters="$FR6" --route=80 --resume --post="finish.sh --modes=aork,loss --min=30 --tol=0.01 --long=30 --longx=--longptol=0.02 --longx=--longclose --no-lift"
