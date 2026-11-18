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
# m9: port-1 VAC link by hand (p1vac.json: via moved north of pin 33 so ACUV pin 34 keeps its via site, + fixed ACUV escape via);
#     capfix link3d only for port 2; hard stubs for R418.1 (PACK_P) and R304.1 (3V3)
CAPFIX_M9="--band=3V3 --stubs=1 --stub_refs=R418.1,R304.1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID --anchor=U501.20>U503.32;C542.1>R533.1"
SPECFIX_M9="$SPECFIX_M3,$MF/vac_p2.json,$MF/p1vac.json,$MF/r314.json"
# m11 (m10 was dropped: an EN_5V1 pre-lay from the m7 route shorted against m9 copper): m9 with
#   - R418.1 joined by a via in the pad (r418.json) instead of a hard stub (the stub closed EN_5V1's F.Cu crossing),
#   - port-2 VBUS pin-32 link along the pin row (vbus32b.json; the diagonal took the CC2 via sites north of pins 28-31),
#   - J301.1 3V3 via into the In4 band (j301_3v3.json, applied after capfix)
CAPFIX_M11="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID --anchor=U501.20>U503.32;C542.1>R533.1"
SPECFIX_M11="$CP5,$MF/pphv1.json,$MF/btst1.json,$MF/nrst_j301.json,$MF/vbus32b.json,$MF/vac_p2.json,$MF/p1vac.json,$MF/r314.json,$MF/r418.json"
SPECFIX_POST_M11="$MF/j301_3v3.json"
# BEST (round 6 final) = m11
BEST_CAPFIX_R6="$CAPFIX_M11"; BEST_SPECFIX_R6="$SPECFIX_M11"; BEST_SPECFIX_POST_R6="$SPECFIX_POST_M11"
# m13 = m11 without the J301.1 3V3 via (j301_3v3.json): on m11 the via left J301.5 GND with no way to its plane and NRST / port-1
#   charger edges failed again (local 335/4 and 336/3). Keeps r418.json (EN_5V1 routed on both m11 routes) and vbus32b.json.
CAPFIX_M13="$CAPFIX_M11"; SPECFIX_M13="$SPECFIX_M11"; SPECFIX_POST_M13=""
