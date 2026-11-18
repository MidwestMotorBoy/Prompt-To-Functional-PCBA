# r6_merge NOTES (lead, round 6 merge of r6_caps + r6_routes onto stack S)

Recipes are in tools/env_r6m.sh (CAPFIX_* / SPECFIX_* per candidate). Scorer: tools/score_board_r6m.sh, local route: tools/route_local_r6m.sh.
All numbers split-zone. PC = stock router on Logan's PC, "unc" = "unconnected after fill" line of the PC log (KiCad open items on the routed board).

| cand | what | pre-route | PC route | local route |
|---|---|---|---|---|
| m1 | cp5 fixes + capfix E | 0.831 W, DRC 0, blocked 3/347 | - | - |
| m3 | + vbus32 tracks, NRST stub | DRC 4 (rejected) | - | - |
| m4 | m3 fixed | 0.858 W, DRC 0, hot 7/7 6.27, blocked 3/343 | 342/1 unc 9; rep 340/3 unc 13 | 338/5, routed unc 13 |
| m5q | + vac_pins, r314, p2self | blocked 6/330 | 330/2 unc 7 | - |
| m6 | m5 variant | blocked 3/331 | 320/10 | - |
| m7 | m5 without p2self | 0.859 W, DRC 0, hot 7/7 6.28, blocked 3/340 | 337/3 unc 9; rep 339/2 unc 9 | 340/0 failed, but KiCad unc 8 |
| m8q | m7 + p2scl.json (P2 I2CC_SCL laid first) | quick path | queued x2 (lead6-m8q, -rep) | - |

Findings
- Router "0 failed" is not "0 open". Stock router.py closes an edge when its escape stub touches ANY own-net copper, also the
  pad's own island; it skips Zone|Zone items; Zone|Pad of a non-plane net becomes a zero-length route. Even r6r-sccp5 (350/0) had
  "unconnected after fill: 15" in its PC log. Judge by KiCad unconnected items on the routed board.
- m7 local routed board: 8 open items: PACK_P R418.1-zone, ACUV U403.34, P1 REGN R415.1, 3V3 R304.1-C303.1, 3V3 F zone-In4 zone,
  P1 TS U403.8, P2 CC2 U501.29, VC4 U101.2.
- tools/router_esc.py = router.py + _esc_joined (stub must reach the far end). Full route with it (runs/m7p) was at failing 11 at
  step 1160 when the container restarted (killed, not finished).
- Finish pass with the STOCK router on a routed board (runs/fin, fin2) does not close the items and added DRC errors.

## Resume log
- 01:30 Nov 18: container restarted (3rd time). Resumed from commit c72209c. Next: finish pass with router_esc on runs/m7 routed board,
  then freeze the connected routes as fixed copper so the rebuild is deterministic; poll lead6-m8q / lead6-m8q-rep.
- 02:08: PC lead6-m8q 336/3, lead6-m8q-rep 337/3 (P2 CHG_INT, P2 I2CC_SDA, EN_5V1): pre-laying P2 I2CC_SCL moved the failures; m8 rejected.
- Finish pass with router_esc on the m7 routed board (runs/fin3): 3 power edges closed, 5 signal edges fail (VC4 U101.2, ACUV U403.34,
  P1 TS U403.8, P2 CC2 U501.29, P1 REGN R415.1) = the true open list of the m7 local route. Regional rip-up + re-route of 38 nets
  around them (tools/ripwin.py + tools/repair.sh, runs/rp1): 75 of 82, 7 failed, 2 DRC errors -> does not converge; rejected.
- Cause of ACUV/TS/REGN (port 1, also open on r6caps-ce, not on r6r-sccp5): capfix link3d put the VAC via at (107.30,111.42),
  0.59 mm from pin 34's only via site. m9 = m7 with fixes/p1vac.json (VAC via at 107.2,110.8, B.Cu link kept east of a fixed
  ACUV escape via at 107.05,111.99), link3d only for port 2, hard stub R418.1. Copper DRC 0. Queued lead6-m9 and lead6-m9-rep at 02:18.
- 02:23: m9 scorecard: 0.860 W, opens allowed only, DRC 0, hot 7/7 6.28 nH, blocked 3/340. Local routes started: runs/m9 (stock router) and runs/m9e (router_esc), 150 min cap.
- 02:55: m9 local routes finished (about 34 min each, not timed out, both run at once):
  runs/m9 (stock router): 339/340, 1 failed, routed DRC 0, KiCad unconnected 4, routed_power_open 3V3@L201 only, routed_pad_unjoined {},
  routed_allpad_off 3V3 R417.2, routed loss 1.136 W. runs/m9e (router_esc): 338/340, 2 failed, unconnected 4, otherwise the same.
- m9 open list (KiCad, same 4 on both local routes): (1,2) 3V3 J301.1 end of the MCU F.Cu pour cut off by SWDIO, (3) P2 CC2 U505.11 ->
  U501.29: the diagonal B.Cu VBUS pin-32 link (vbus32.json) takes the via sites north of pins 28-31, (4) EN_5V1 R432.1 -> U301.12:
  "no way": its only crossing of the port-1 east column was F.Cu at R418.1, where m9 put a hard PACK_P stub.
- m10 (EN_5V1 laid first from the m7 route: 121 tracks, 11 vias) shorted against m9 copper: dropped.
- m11 = m9 with r418.json (via in R418.1 pad instead of the stub), vbus32b.json (P2 VBUS link along the pin row), j301_3v3.json
  (J301.1 3V3 via into the In4 band). Copper DRC 0. Queued lead6-m11 and lead6-m11-rep at 03:09.
- 03:07: m12q = m11 + p2scl.json (P2 I2CC_SCL laid first; PC fails that edge 'pulled 1' on m4/m7/m9, local routes it), quick path, DRC 0, queued lead6-m12q. PC lead6-m9-rep: 339/1 (P2 I2CC_SCL), unc 7, 39.0 min.
- 03:13: m11 scorecard: 0.866 W, power_open GND J301/J302 only (3V3@L201 now joined), DRC 0, hot 7/7 6.28 nH, blocked 3/339. Local routes started: runs/m11 (stock), runs/m11e (router_esc).
- 03:48: PC lead6-m9 339/1 (P2 I2CC_SDA U502.5 -> U501.16), unc 7, 88.2 min; lead6-m9-rep 339/1 (P2 I2CC_SCL), unc 7, 39.0 min.
- 04:04: m11 local routes (about 55 min each, not timed out): runs/m11 (stock) 335/339, 4 failed (LODRV2, VC2, ACOV, GND J301.5), KiCad unc 8;
  runs/m11e (router_esc) 336/339, 3 failed (U102-V4, U403-FB, GND J301.5), unc 4. Worse than m9: the J301.1 3V3 via leaves J301.5 GND
  "goals 0" and the route needs about 600 rip-ups (m9: 127). EN_5V1 and CC2 routed on both, so r418.json and vbus32b.json work.
- m13 = m11 without j301_3v3.json. Building.
- 04:15: m13 scorecard done (see runs/m13/score.json), PC lead6-m13 and -rep queued 04:07, local routes started (runs/m13 stock, runs/m13e router_esc).
- 04:17: container restarted (4th time); m13 local routes (runs/m13, runs/m13e) were killed and must be re-run; PC lead6-m13/-rep still queued on the PC.
- 04:20: m13 local routes restarted (runs/m13 stock, runs/m13e router_esc).
- 04:45: m13 local routes done (about 25 min each, not timed out): runs/m13 (stock) 340/341, 1 failed (P2 CHG_INT R504.2 -> U501.18), routed DRC 0,
  KiCad unc 5 (PACK_P F zone island, P1 I2CC_SCL R403.2, 3V3 J301.1 island x2, P2 CHG_INT); runs/m13e (router_esc) 340/341, 1 failed (same),
  unc 4 (PACK_P F zone island, 3V3 J301.1 island x2, P2 CHG_INT), routed_pad_unjoined {}, routed_power_open 3V3@L201, routed loss 1.176 W.
  PC lead6-m11 337/2 (P2 I2CC_SDA, P1 TS), 85 min; lead6-m11-rep 338/1 (P2 I2CC_SDA), unc 4; lead6-m12q 335/3. PC lead6-m13/-rep pending.
- Plan: finish the m13e routed board (router_esc pass + regional rip-up at P2 CHG_INT), then FREEZE the finished route into a fix file
  (tools/prelay.py --net=. -> fixes/frozen_*.json, SPECFIX_POST) so the rebuild is deterministic and the PC/local routes have nothing left to do.
- 04:58: frozen_final.json (tools/freeze_fix.py) on the m13e route: quick build runs/fz3 = KiCad DRC 0 errors, 0 unconnected, power_open {}, pad_unjoined {}, no islands on 3V3/PACK_P/GND (tools/net_islands.py). TRAP found: routed-board DRC ran without routed.kicad_dru (custom rules missing): m13e routed had 4 clearance errors (CELL_1N 0.25 mm rule); route_local_r6m.sh / score_board_r6m.sh now copy cu.kicad_dru. m14 recipe in env; rebuild_best.sh runs/final --score started.
- 05:00: rebuild_best.sh r6_merge/runs/final --score (m14, from the bare template, about 6 min): 0 of 245 placement entries differ; loss 1.241 W
  (all copper), power_open {}, DRC 0, unrouted items 0, hot loops 7/7 6.41 nH, pad_unjoined {}.
- 05:02: local route on runs/final/score (stock router, about 1 min): 0 of 0 edges, 0 failed, routed DRC 0 (custom rules on), KiCad unconnected 0,
  routed_power_open {}, routed_pad_unjoined {}, routed_allpad_off {}. PC routes queued: lead6-m14 (05:01), lead6-m14-rep (05:02).
- FINAL = m14. Top-level score.json, renders, rebuild_best.sh, REPORT.md "Round 6", SKILL-NOTES.md section 11, PAUSED.md updated.
- 05:20: PC lead6-m14 and lead6-m14-rep: 0 edges, 0 failed, unconnected after fill 0 (0.2 min). PC lead6-m13-rep: 339/1 of 340 (P2 I2CC_SCL), unc 4, 54.6 min; lead6-m13 not returned yet. Done.
