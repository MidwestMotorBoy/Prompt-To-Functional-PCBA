cd /home/claude/repo/docs/layout-teams/B
# runs/p2-m6a: routed.kicad_pcb = runs/p2-m5h1/finished.kicad_pcb (plan p2-m5, local route of runs/p2a-m5, stage 1 pass,
# hand tracks runs/p2-m5hand/h1.json: PACK_P at R112.2, via-in-pad at TH401.1). 4 unconnected at the start.
# aor with one PACK_P terminal allowed +0.25 mohm (Port 1 TS was refused at R527 +0.20), then the loss pass, then aork.
bash tools/finish.sh runs/p2-m6a --modes=aor,loss,aork --min=30 --tol=0.01 --long=20 --aorx=--prtol=0.25
