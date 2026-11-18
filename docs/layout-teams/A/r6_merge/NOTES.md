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
