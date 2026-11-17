# source this: team A best copper recipe (round 5, planner M) + r6_caps CAPFIX
source /home/claude/repo/docs/layout-teams/A/r5_merge/tools/best_env_r5.sh
R6_PLACEMENT=/home/claude/repo/docs/layout-teams/A/best_placement.json
# 3V3 In4 band + cross, cap stubs, PPHV VAC links (pad->pin on F.Cu) and the PPHV north-south planned link
CAPFIX_BASE="--band=3V3 --stubs=1 --link_w=0.2 --link_pass=GND,PACK_P --links=C409.1>U403.33;C509.1>U503.33;R509.1>C509.1 --link3d=C409.1>U401.20;C509.1>U501.20"
export CAPFIX_IN2="$CAPFIX_BASE --l3_layers=F.Cu,In2.Cu,B.Cu --l3_cost=1.5,1.0,1.8"
export CAPFIX_IN3="$CAPFIX_BASE --l3_layers=F.Cu,In3.Cu,B.Cu --l3_cost=1.5,1.0,1.8"
export CAPFIX_BAND="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1"
export CAPFIX_C="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=U403.33>U401.20;C409.1>U403.33;U503.33>U501.20;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0"
# round 2: escape-room penalty on new vias, links steered into the gaps of the base full route (runs/base/routed.kicad_pcb)
AVOID="--avoid=/home/claude/repo/docs/layout-teams/A/r6_caps/runs/base/routed.kicad_pcb"
export CAPFIX_E="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=C409.1>U403.33;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID"
export CAPFIX_F="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=U403.33>U401.20;C409.1>U403.33;U503.33>U501.20;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID"
export CAPFIX_G="$CAPFIX_E --anchor=U401.20>U403.32;U501.20>U503.32"
export CAPFIX_H="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1 --link3d=U403.33>U401.20;C409.1>U403.33;U503.33>U501.20;C509.1>U503.33 --l3_layers=F.Cu,In3.Cu,B.Cu --l3_cost=3,1.0,1.5"
# round 3: ce + the two single 3V3 pads the router left on In3 islands in ce's local route (R417.2 F.Cu link to C301.1, R314.1 F/B link to U301.6)
export CAPFIX_J="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1;R417.2>C301.1 --link3d=C409.1>U403.33;C509.1>U503.33;R314.1>U301.6 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID"
export CAPFIX_K="--band=3V3 --stubs=1 --link_w=0.2 --links=R509.1>C509.1;R417.2>C301.1 --link3d=C409.1>U403.33;C509.1>U503.33 --l3_layers=F.Cu,B.Cu --l3_cost=3,1.0 $AVOID"
