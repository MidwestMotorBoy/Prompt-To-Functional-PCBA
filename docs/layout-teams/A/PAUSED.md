# Team A: resume pointer (updated 2026-11-18, after round 6, the last round)

State: finished. The best board is m14: placement `best_placement.json` (stack S, unchanged since round 5) with the
round-6 copper recipe `r6_merge/tools/env_r6m.sh` (BEST_*_R6), which ends with `r6_merge/fixes/frozen_final.json`,
the complete route laid as fixed copper and finished by hand.

One command: `docs/layout-teams/A/rebuild_best.sh <workdir> --score` (about 6 min, hot loops on), then
`r6_merge/tools/route_local_r6m.sh <workdir>/score 150` for the routed-board checks (router reports 0 edges).

Numbers (`score.json`, REPORT.md "Round 6"): power_open none, DRC 0 (custom rules on), KiCad unconnected 0,
hot loops 7 of 7 at 6.41 nH (6.27 nH on the planned copper), 1.241 W with all copper (0.865 W planned),
no pad off its pour. Local route 0 of 0 edges; PC routes lead6-m14 / lead6-m14-rep: see score.json `full_route_pc`.

The final board is a FROZEN route: the router alone reaches 340 of 341 with 4 open items on the planned copper
(m13). If a part or net changes: set BEST_* to the M13 recipe, route (`route_local_r6m.sh`, router_esc), then
freeze and finish again (SKILL-NOTES.md section 11).

Left for later: lower loss (escape cuts and capfix cost 64 mW on the plan), `r5_general/upstream.diff` not applied,
the CHG_INT track at exactly 0.15 mm clearance. Log: `r6_merge/NOTES.md`.
