cd /home/claude/repo/docs/layout-teams/B
# runs/p2-m6 (lead, phase 2 round 3): plan p2-m6 = tools/rebuild_m6.sh --no-hotvia (plan p2-m4 + Net-(U404-FB) path with
# the HL_5V pour corner trimmed), screened in runs/p2-m6nvs (0 of 341 blocked, DRC 0, 1.012 W).
# routed.kicad_pcb = the routed copper of runs/p2b-r3en/finished.kicad_pcb (local route of plan p2-m4 in runs/p2-m4 +
# worker B's passes) carried onto the plan board of p2-m6, without the routed Net-(U404-FB) track:
#   python3 tools/transplant.py runs/p2b-r3en/finished.kicad_pcb runs/p2b-r3en/cu.kicad_pcb runs/p2-m6nvs/cu.kicad_pcb runs/p2-m6/routed.kicad_pcb --drop=runs/p2-m6/drop.json
# DRC 0, 2 unconnected at the start (Net-(U404-FB) R434.1 to R433.2, EN_5V1).
eval "$(sed -n '/^ST=/,/^\[ -z "\$NOHV" \]/p' tools/rebuild_m6.sh | sed '/^\[ -z "\$NOHV" \]/d')"
bash tools/final_route.sh runs/p2a-r5src runs/p2-m6 --straps="$ST" --filters="$F" --route=80 --resume --post="finish.sh --modes=aor --min=30 --tol=0.06 --long=30 --longx=--longptol=0.05 --aorx=--prtol=1.0"
