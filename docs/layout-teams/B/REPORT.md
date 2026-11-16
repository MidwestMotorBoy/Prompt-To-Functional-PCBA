# Team B report (Monolith board)

Numbers come from named run dirs under `runs/` (their `final.json`, `score.json`, logs); `LOG.md` has every entry in
full. A number without a run dir is not in this file.

## Phase 1: placement (2026-11-14 to 2026-11-15, short)

Placement built from Logan's block floorplan by three section workers (Port 1, Port 2, pack side: `tools/secplace.py`
recipes, `fragments/`), stitched (`tools/stitch.py`) and fixed in four lead rounds (r1 to r4). Result r4
(`candidates/r4.json`; `score_r4.json`, `F_r4.png`, `B_r4.png`), shared scorecard:

| Board | Blocked edges | Full route | Hot loops | Loss before routing | Run |
|---|---|---|---|---|---|
| hand placement | 56 of 452 | 391 of 448 | sum 8.15 nH | 1.36 W | `runs/hand_screen` |
| **r4** | **19 of 437** | **411 of 437**, about 17 min, not timed out | **7 of 7, 5.54 nH** | **1.125 W** | `runs/r4chg-hot`, `runs/r4-route` |

What worked: power stages placed first from explicit coordinates with the hot-loop caps against the FETs; partial
screens per section (`screen.sh --partial`); a nudge of at most 0.5 mm per blocked pin, checked by a partial screen.
What did not: a skeleton of frozen power copper before the signal parts (round 3 of the earlier teams), and reading
the routed count of one route as exact (two routes of one board differ by about 4 edges).
Phase 1 left the routed board itself open: 2.854 W loss on `runs/r4-final` because signal tracks on In2 cut the
PACK_P sheet, 3 router DRC errors, 15 edges blocked at pins.

## Phase 2: from placement r4 to a routed board (2026-11-15 15:05 to 2026-11-16)

Gates (`PLAN2.md` section 2, all on the routed board, `final.json` of `tools/final_route.sh`): 0 unconnected items,
power paths joined and one piece, 0 DRC errors, 7 of 7 hot loops tier 1, ringing within 0.05 nH of 5.54 and no loop
more than 0.02 up, loss 1.25 W or less with PACK_P to J113 and R427 3.0 mohm or less, renders looked at.

### What was tried, in order, with numbers

| Run | What | Route | Unconnected | DRC routed | Loss routed | J113 / R427 mohm | Hot loops routed | Hot-pour items |
|---|---|---|---|---|---|---|---|---|
| `runs/r4-final` | r4, PACK_P straps only (phase 1 end) | 391 of 416 | 37 | 3 | 2.854 W | 15.6 / 15.4 | 7 of 7, 5.56 nH | - |
| `runs/p2a-base` | + 3V3 In3 straps | 399 of 421, 38 min | - | 3 | 2.206 W | 10.4 / 10.2 | not run | - |
| `runs/p2a-n1` | + bottom 2 oz PACK_P trunk 3 mm (worker A) | 387 of 422, 60 min | - | 3 | 1.198 W | 2.27 / 2.36 | 7 of 7, 5.55 nH | - |
| `runs/p2r1_w3n20` | trunk 3 mm, 2 mm neck at U403 | 394 of 422, 41 min | 39 | 3 | 1.306 W | 3.05 / 3.11 | 7 of 7, 5.54 nH | - |
| `runs/p2b-full2` | r4, pin escape table (worker B), no trunk | 362 of 367, 27 min | 18 | 0 after stub trim | 2.903 W | 11.6 / 11.4 | 7 of 7, 5.56 nH | - |
| `runs/p2-m1` | merge round 1: trunk 5 mm + pins + continuation pass | 356 of 368, 66 min | 26 | 0 | 1.186 W | 2.11 / 2.23 | 7 of 7, 5.56 nH | 14 tracks, 7 vias |
| `runs/p2b-m1fin` | p2-m1 + accept-or-revert pass (worker B) | same | 16 | 0 | 1.183 W | 2.11 / 2.22 | 7 of 7, 5.56 nH | 3 tracks, 3 vias |
| `runs/p2a-r5f` | placement r5, plan FR5 (worker A) | 346 of 353, 39 min | 15 | 0 | 1.257 W | 2.65 / 2.71 | 7 of 7, 5.56 nH | 1 track, 8 vias |
| `runs/p2-m3` | p2a-r5f + accept-or-revert pass | same | 7 | 0 | 1.254 W | 2.65 / 2.71 | 7 of 7, 5.56 nH | 1 track, 2 vias |
| `runs/p2-m4` | r5, plan FR6 (trunk back on the p2-m1 path) + pass | 341 of 342, 40 min | 4 | 0 | 1.250 W | 2.61 / 2.68 | 7 of 7, 5.56 nH | 1 track, 3 vias |
| `runs/p2b-r3dev` (k1) | p2-m4 finished board + loss pass only (round 3) | same | 4 | 0 | 1.181 W | 2.20 / 2.27 | not run | 1 track, 3 vias |
| `runs/p2b-r3fin` | p2-m4 routed board: passes aor, aork, loss (`--long=30`), hand tracks, hot loops (round 3) | same | **1** (EN_5V1) | **0** | **1.168 W** | **2.12 / 2.18** (R527 1.72) | **7 of 7, 5.56 nH** (every loop as p2-m4) | 1 track, 3 vias |
| `runs/p2b-r3en` | p2b-r3fin finished board + aork (`--long=30 --longptol=0.02`) + a second loss pass | same | **1** (EN_5V1) | **0** | **1.161 W** | **2.08 / 2.15** (R527 1.64) | **7 of 7, 5.56 nH** | 1 track, 3 vias |

No route and no pass in this table timed out. Logan's PC (counts only, stock router) gave the spread of plan
variants: p2-base 399 of 421, p2a-w3n20 396 of 422, p2a-w5n20 394 of 422, p2-m1 355 of 368, p2a-r5f 347 of 354,
p2a-r5fw4 345 of 354.

### What worked

1. **PACK_P on the 2 oz bottom.** A hard B.Cu trunk from Q102 to J113 and R427 (`tools/trunk.py`, worker A) took the
   routed loss from 2.2 to 2.9 W down to about 1.2 W: J113 15.6 to 2.1 mohm. The width under U403 is the trade: 3 mm
   everywhere costs U403's south pin escapes, a 2 mm neck costs mohm; 5 mm with the 2 mm neck
   (`--w=5 --narrow=U403:0.8:2.0`) was kept.
2. **3V3 straps on In3 and ties on F.Cu** (`straps.py`, `plan/p2-pins-r6.json` `"to": "zone"`, a hard In3 link):
   power_open empty and the 3V3 bus one piece on the routed board (first on `runs/p2-m4`).
3. **Copper before routing for every connection no router makes.** Pin escapes as a table (`tools/pins.py`,
   `plan/p2-pins*.json`: GND QFN pins into their exposed pad, gate pads cut out of their stage's pour, explicit vias
   for the CC pins under the protection chips): blocked edges 15 to 0 (`runs/p2b-pins2`, `runs/p2-m4s`).
4. **Vias the pins need anyway, laid before the trunk**, close the path the trunk must not take
   (`plan/p2-pins-u403b.json`): the trunk went back under U403's south row instead of the diagonal that cost five
   connections and 0.5 mohm at J113.
5. **Stub trim** (`tools/fin_trim.py`): the router's 3 to 5 DRC errors (0.4 mm pitch stubs at U101 against the 0.25 mm
   HighCurrent rule) cured on every board.
6. **Accept-or-revert finishing pass** (`router_b.py --aor`, round 2): one open connection or one hot-pour piece per
   task, KiCad's own unconnected count and a refilled power check per task, everything put back on refusal. 26 to 16
   (`p2b-m1fin`), 15 to 7 (`p2-m3`), 9 to 4 (`p2-m4`), never a worse board.
7. **Loss pass** (round 3, `finish.sh --modes=...,loss`): rank the In2 pieces by what each costs the PACK_P sheet
   (piece off, refill, solve), lay the worst again with the sheet closed, accept by loss. On the p2-m4 finished board:
   1.2499 to 1.1811 W, J113 2.61 to 2.20, R427 2.68 to 2.27, R527 2.20 to 1.77 mohm, unconnected 4 = 4, DRC 0 = 0,
   hot-pour items 4 = 4 (`runs/p2b-r3dev/fin/k1.log`: 7 of 47 tasks accepted: CELL3 -23.7 mW, EN_5V2 -32.0 mW, SCL,
   Port 2 BTST1, Port 1 C_CC1, IRQ_N, P1_LDO_3V3, in the power check's PACK_P + 3V3 + GND sum).
8. **Via-in-pad vias kept as anchors** (`router_b.py --split`, round 3): lifting a piece no longer loses the via that is
   the only way into a boxed pad; Port 2 LDO_3V3 closed in the aor pass of `runs/p2b-r3fin` (3 pulls) and Port 1 TS
   could be laid again by the loss pass (-9.1 mW).
9. **Hand tracks by coordinates with an exact check** (`tools/handroute.py`, `runs/p2b-r3hand/hand.json`): SRP_F
   through the 1.03 mm gap between the SRN_F and SW2 vias, Net-(C313-Pad2) over the north side of C313.1.

### What did not work

- A continuation route that lifts whole nets (`--cont`, round 1): pulled 810 routes for 24 open connections and ended
  with as many open; the pass rule dropped it. Per-connection accept-or-revert replaced it.
- No-via rule areas over every hot-loop return pour: cost 2 edges on the PC and were not needed on the route.
- A pass without a power check closes connections by cutting the PACK_P sheet (R527 1.57 to 3.38 mohm); closing all
  PACK_P fills to new channels is too strict. The per-task check with a small budget is the middle.
- Tying a 3V3 pad through a via into a soft inner pour: later tracks cut it off again; tie in the plan.
- More nodes for EN_5V1: the 50 mm edge is not a node-cap problem (see below).
- Re-laying a piece where its neighbours must move too: SDA, Port 1 REGN, SBU_FLT are refused in every sweep (the pulled
  neighbours do not all go back within 12 pulls). Port 1 TS was refused on the dev board k1 (its new path cost 3V3 /
  GND more, 0.6770 to 0.6880 W) and accepted on `runs/p2b-r3fin` (-9.1 mW): the result depends on what was laid first.
- Closing only the piece's own box (`box:3`) after the whole outline failed won no task in three runs.

### Still open after round 3

On `runs/p2b-r3en` (best board of round 3): unconnected 1, DRC 0, power open / loose / power pieces none, 7 of 7 hot
loops at 5.56 nH, loss 1.161 W, J113 2.08 and R427 2.15 mohm. Left:
- **EN_5V1** (R432.1 to U301.12, 50 mm). The edge lays (with `--long=30` the search finds it in 0.2 to 1.4 M nodes once
  the far end is free), but every way it finds runs north-south on In2 between the PACK_P sheet and J113 / R427
  (x 113 to 118, y 76 to 121), the feed of the 10 A path: the power check refused it at +4.7, +16, +37.8 mW and, with the
  In2 sheet made dear (`--longclose`), at J113 2.08 to 2.41 mohm (+42 mW). F.Cu and B.Cu are closed there (parts, the
  trunk), In3 holds the 3V3 bus. Picture: `runs/p2b-r3en2/look/en5v1_In2.png` (red = the router's path). On the
  p2-m4 board before the passes, U301.12 itself was boxed in (3V3 F.Cu pour west, escape vias of pins 11, 13, 14:
  `runs/p2b-r3dev/look/en5v1_u301.png`). Needs plan copper: a lane for EN_5V1 that crosses the PACK_P flow where it is
  thin (west of Q102 or south of the sheet), or a layer-change point on F.Cu south of U403, laid before routing.
- **Hot-pour items** (gate 7): Net-(U404-FB) F.Cu track 117.99,68.15 to 119.14,66.7 and the Port 2 I2CC_SCL / SDA vias
  at 83.93,90.27 / 84.28,92.52 / 83.28,90.82: every lift task fails or costs power (I2CC_SCL: PACK_P to U504 11.25 to
  11.60 mohm); they need a hot-pour trim under U404 or a plan lane west of C439 (lead's decision).
- The largest cut of the PACK_P sheet left is SDA (about 11 to 13 mW ranked): its re-lay pulls neighbours that do not
  go back within 12 pulls.
- Logan's PC route of the p2-m4 copper board: 333 of 342, 9 failed, 78.9 min, done (stock router; local route 341 of
  342): the spread of one plan is larger than on earlier boards.

### Round 3, the lead's merge: the first board with 0 unconnected (`runs/p2-m6` = `best_routed/`)

| Run | What | Unconnected | DRC routed | Loss routed | J113 / R427 mohm | Hot loops routed | Hot-pour items |
|---|---|---|---|---|---|---|---|
| `runs/p2a-m5` (worker A) | plan p2-m5 (everything in the plan), new route 338 of 341, 55 min + pass | 6 | 0 | 1.252 W | 2.57 / 2.64 | 7 of 7, 5.56 nH | 0, 0 |
| `runs/p2-m5h1` | the same + round 3 router + two hand tracks | 4 | 0 | 1.253 W | 2.59 / 2.67 | not run | 0, 0 |
| `runs/p2-m6` | worker B's routed copper (`runs/p2b-r3en`) carried onto plan p2-m6 (= p2-m4 + U404-FB path) + aor pass | **0** | **0** | **1.199 W** | **2.38 / 2.44** | **7 of 7, 5.56 nH** | **0 tracks**, 3 vias |

No route or pass here timed out; the copper of `runs/p2-m6` is the route of `runs/p2-m4` (341 of 342, 40 min).

What worked:
- **Carrying routed copper onto a changed plan** (`tools/transplant.py`) instead of routing the changed plan again.
  Plans p2-m4 and p2-m5 differ in 32 tracks and 5 vias, yet their two routes failed different connections (EN_5V1
  alone on p2-m4; TS, I2CC_SCL, SCL, TS1, ACUV and a PACK_P piece on p2-m5), and the finishing pass could close
  neither set fully. With the plan change cut down to the one item not yet on the board (the U404-FB path), the
  transplant had 0 DRC errors and only the two expected open connections.
- **Setting the pass tolerances from the gates for the last connection.** EN_5V1 lays at the first search; it was
  refused four times by per-task limits (2 mW, 0.1 mohm) that are no gate. With `--longptol=0.05` and `--prtol=1.0`
  it was accepted at +38 mW: 1.199 W against the 1.25 W limit.

What did not work:
- Worker A's full plan on worker B's copper: about 20 real conflicts (EN_5V2 waypoints against CELL3 / SDA, the
  SRN_F via against DRV_SUP, the C313-Pad2 path against RFIO, the LDO_3V3 via against CHG_INT).
- No-via areas over the hot pours on a board that already has vias there: the pass lifts the pieces and cannot lay
  them all again (5 unconnected on `runs/p2-m6t1`).
- The loss pass on EN_5V1: laid again with the sheet closed it cost 3.5 mW more. The router's layer costs put a long
  north-south run on In2 although In3 has room east of x 117.
- A transplant with plain vias: +29 mW from wider plane antipads (see tools/README.md).

Still open after the lead's merge:
- Three signal vias in the Port 2 input GND return pour (I2CC_SCL 83.925,90.2745 / 84.275,92.5245, SDA
  83.275,90.8245). Ringing unchanged (Port 2 HL_IN 0.80 nH before and after routing).
- EN_5V1's 54 mm on In2 across the J113 / R427 feed: 38 mW, J113 2.08 to 2.38 mohm.
