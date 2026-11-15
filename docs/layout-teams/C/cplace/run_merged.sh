#!/bin/bash
# run_merged.sh <out placement.json> [input dir]: the team C whole-board placer with every working piece switched on.
#   Each piece stays a feature flag: drop a module from HOOKS (or set its knob) to switch it off, e.g.
#     HOOKS=cpd,cpower,cpdl ./run_merged.sh x.json        (no corridor cost)      PD_RIN=0 / CELL_FIRST=0 / PD_FIRST=0
#   cside (both sides) is OFF by default (no gain on the screen, see sides/README.md); MERGE_SIDES=1 adds it in POST mode.
#   SEED picks the fill noise (and cpower's tie-break). About 100 s, one core.
H=$(cd "$(dirname "$0")" && pwd)
export HOOKS=${HOOKS:-cpd,cpower,cpdl,ccorr}
export PD_BUCK1=${PD_BUCK1-97,74,105,88} PD_BOX1=${PD_BOX1-106,75,118,90} PDW_B=${PDW_B:-20}
if [ "${MERGE_SIDES:-0}" = 1 ]; then
  export HOOKS=cpd,cpower,cpdl,cside,ccorr SIDE_POST=${SIDE_POST:-30} SIDE_VS_MM=${SIDE_VS_MM:-1} SIDE_GVS_MM=${SIDE_GVS_MM:-0.5} \
         SIDE_VS_PWR=${SIDE_VS_PWR:-1.0} SIDE_VS_HARD=${SIDE_VS_HARD:-1} SIDE_VRES=${SIDE_VRES:-1} SIDE_CU=${SIDE_CU:-$H/../sides/cu_prior_s4.json}
fi
exec $H/run.sh "$@"
