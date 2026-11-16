# Team A: resume pointer (updated 2026-11-16, after round 5)

State: five worker rounds and the lead's round-5 merge are done. The best placement is `best_placement.json`
(stack S = round-3 build + `best_overrides/` 50, 60, 70, 80), rebuilt with `rebuild_best.sh <workdir>` and scored
with `rebuild_best.sh <workdir> --score` (scorer `r5_merge/tools/score_board_r5.sh`, copper recipe
`r5_merge/tools/best_env_r5.sh` = planner M). Numbers: `score.json` and REPORT.md "Rounds 4-5"; method:
SKILL-NOTES.md. The round-3 board is `lead_final/best_placement_r3.json` (`tools/rebuild_best_r3.sh`).

Stack S: hard limits met (power_open allowed only, DRC 0, 7 of 7 hot loops at 6.27 nH), 4 of 364 blocked,
PC full route 356 / 8 failed of 364 (twice, 95 min), local 357 / 7, 0.801 W (routed 1.070 W).

Where to resume:
- **Before fab:** routing cuts the soft In3 3V3 pour: on the routed board C207.1, C403.1, C503.1 (3V3) and C213.1
  (PACK_P) are off their net's main copper (`routed_pad_unjoined` in score.json). Add a 3V3 copy on a non-routed
  layer (like the In4 PACK_P bus) or take 3V3 out of the router's soft nets, then re-check with route_local_r5.sh.
- C409.1 / C509.1 (charger VAC 1 uF caps) are joined only by router tracks.
- The remaining failed edges: port-1 PD cluster and the two long port-1 I2C runs to U403 (I2CC_SDA/SCL, P1_LDO_3V3
  at R441/R404), SMBC U101.19 -> R115, SCL J302.6 -> U301.9 (needs CELL_P re-planned; the r5_gauge lane costs
  +59-83 mW).
- Upstream: `r5_general/upstream.diff` (write_copper one zone per outline, planner hooks) is written, not applied.

Scorecard caveat: all numbers from round 2 on use split-zone copper. The old 391/448 hand reference used the
vanishing-pour copper; on split copper the hand board routes 363 of 422.
