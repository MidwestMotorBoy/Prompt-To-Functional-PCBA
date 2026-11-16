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

# Lead round 5 (2026-11-16)
- Stack S = round-3 build + overrides 50 r4_port1, 60 r4_bcu, 70 r5_north, 80 r5_gauge (copies in best_overrides/,
  byte-identical to the workers' files), planner M with $BEST_PLAN_R5. Build: placed 289/289, CHECK clean.
  rebuild_best.sh re-run 2026-11-16: 121 s, "0 of 245 entries differ from best_placement.json".
- Scorecard lead_r5/sc_S (score_board_r5.sh, --route=0, hot on): 0.801 W, power_open 3V3@L201 + GND@J301/J302,
  DRC 0, 7 of 7 at 6.27 nH, blocked 4 of 364 (SCL J302.6, CHG_INH R535->J302.2, GAUGE_FUSE U101.25->R126,
  P2 DRV9_OFF), pad_unjoined C409.1, C509.1.
- Package check: r5_general plan_only.sh with monolith_r5.rules.json on sc_S/bare.json -> spec IDENTICAL to
  sc_S/spec.json (78 zones / 356 tracks / 288 vias).
- PC routes queued 13:01 UTC: lead5-S 356 / 8 of 364, 95.1 min, done; lead5-S-rep (same sha) 356 / 8, 95.3 min,
  done, identical FAILED list. Results seen 14:39-14:41 UTC (past the 75-min mark).
- Local route (route_local_r5.sh lead_r5/sc_S 150, started 13:07 at queue time for the routed checks, finished
  13:44, not timed out): 357 / 7 of 364; routed power_open 3V3@L201 only, routed DRC 0, routed loss 1.070 W;
  routed_pad_unjoined 3V3 C207.1/C403.1/C503.1, PACK_P C213.1, PPHV C409.1/C509.1. routed.kicad_pcb deleted (6 MB).
- Cleanup: 16 cu/routed boards over 5 MB deleted from old outdirs (none tracked by git).
