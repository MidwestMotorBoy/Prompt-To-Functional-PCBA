# Team A lead notes (final step)

- Best board = placement FB (`best_placement.json`, identical to final/deliver/best_placement.json and
  portcu/base_score.json) + copper recipe `tools/best_env.sh` (planner portcu/tools/plan_copper_p.py stack G5,
  PACK_P bus on In4, soft GND fill on B.Cu, no In2 straps). This combination (portcu G5 x strapfix i4b) had not been
  scored by any worker; the lead scored it as `lead_final/sc_Z`.
- Scorecard (tools/score_board_best.sh, --route=0, hot loops on): 0.835 W, power_open 3V3@L201 + GND@J301/J302,
  DRC 0, 7 of 7 hot loops 6.24 nH, blocked 5 of 369.
- PC full route `lead-Z` (A/lead-Z-bd03cd0e.json), queued 07:04 UTC, result seen 08:38 UTC:
  352 routed / 17 failed of 369, 92.2 min, status done.
- Local full route (tools/route_local.sh lead_final/sc_Z 150, default router options): 351 routed / 18 failed of
  369, finished in about 70 min, not timed out. Routed board: power_open 3V3@L201 only, DRC errors 0, loss 1.127 W
  (PACK_P 0.313, GND 0.330, CELL_P 0.124). The routed .kicad_pcb (8 MB) was deleted after the check; rebuild it
  with `rebuild_best.sh <wd> --score="--route=150"`.
- All PC results of the team were re-read from origin/route-results on 2026-11-15 and match the tables in REPORT.md.
- rebuild_best.sh verified: 119 s, "0 of 245 entries differ from best_placement.json" (lead_final/rebuild_check).
- Cleanup: 25 routed/ghost board copies over 5 MB deleted from the outdirs. The team folder is still about 1.4 GB
  (cu/bare boards of about 100 outdirs at 1.5-5 MB each, route_queue 131 MB already committed). The thread owner
  should decide what to commit; the deliverables are the files at the top of docs/layout-teams/A/, tools/, and the
  worker tools/NOTES listed in REPORT.md.
- queue_route.sh puts a model name in its commit trailer; CHARTER.md says no model names in commits. Not changed
  here (shared team script, commits already pushed); the thread owner should drop that line.
