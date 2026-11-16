cd /home/claude/repo/docs/layout-teams/B
# runs/p2-m5 = copy of runs/p2a-m5 (plan p2-m5, local route 338 of 341, routed.kicad_pcb as the route left it)
# stage 1: accept-or-revert passes with worker B's round 3 router (via-in-pad anchors, long edges)
eval "$(sed -n '/^ST=/,/^\[ -z "\$NOHV" \]/p' tools/rebuild_m5.sh | sed 's/^\[ -z "\$NOHV" \] && //')"
bash tools/final_route.sh runs/p2a-r5src runs/p2-m5 --straps="$ST" --filters="$F" --route=80 --resume --no-hot --post="finish.sh --modes=aor,aork --min=40 --tol=0.01 --long=20"
