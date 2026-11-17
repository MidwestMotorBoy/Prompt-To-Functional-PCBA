# source this: team A round-6 merged recipe = stack S copper (planner M, r5) + r6_routes escape fixes (SPECFIX) + r6_caps capfix (CAPFIX)
A=/home/claude/repo/docs/layout-teams/A
source $A/r5_merge/tools/best_env_r5.sh
RF=$A/r6_routes/fixes; MF=$A/r6_merge/fixes
fixlist() { local s=""; for f in "$@"; do s="$s,$f"; done; echo ${s#,}; }
CP5=$(fixlist $(for f in $(cat $RF/CP5_LIST.txt); do echo $RF/$f; done))
AVOID="--avoid=$A/r6_caps/runs/base/routed.kicad_pcb"
CAPFIX_E="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C409.1>U403.33;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID"
CAPFIX_G2="$CAPFIX_E --anchor=U501.20>U503.32"
# m2: + PD-chip VBUS pin 32 planned links (router.py skips Zone|Zone ratsnest items, so the pin was never joined),
#     + P2 PP5V ratsnest anchor for R533.1, + port-1 PPHV pour pull-back (pphv1), + BTST1 / NRST@J301 laid first
CAPFIX_M2="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C409.1>U403.33;C509.1>U503.33;U401.32>C406.1;U501.32>C506.1 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID --anchor=U501.20>U503.32;C542.1>R533.1"
SPECFIX_M2="$CP5,$MF/pphv1.json,$MF/btst1.json,$MF/nrst_j301.json"
# m3: VBUS pin-32 links as fixed F.Cu tracks (vbus32.json; capfix link3d found no path), NRST@J301.3 as an escape stub + via
CAPFIX_M3="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C409.1>U403.33;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID --anchor=U501.20>U503.32;C542.1>R533.1"
SPECFIX_M3="$CP5,$MF/pphv1.json,$MF/btst1.json,$MF/nrst_j301.json,$MF/vbus32.json"
# m5: + charger VAC pin 32-33 bridge, 3V3 via at R314.1 (the In4 band grows to it), port-2 PD cluster laid first (p2self)
SPECFIX_M5="$SPECFIX_M3,$MF/vac_pins.json,$MF/r314.json,$MF/p2self.json"
# m7: m5 without the port-2 cluster pre-lay (p2self boxed P2 SBU_FLT / CHG_INT on the PC route of m5q)
SPECFIX_M7="$SPECFIX_M3,$MF/vac_pins.json,$MF/r314.json"
