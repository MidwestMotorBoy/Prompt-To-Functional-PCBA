# Team B report: Monolith board, placement (phase 1) and routed board (phase 2)

Every number here comes from a named run directory under `runs/` (its `score.json`, `final.json`, `dc.json` or log)
or from the charter. `LOG.md` has each work session in full. Rows marked "charter" were not rerun by team B.

## 1. Result

The kept board is `best_routed/monolith_routed.kicad_pcb` (= `runs/p2-m7/finished.kicad_pcb`), on placement
`best_placement.json` (= `candidates/r5.json`). Numbers from `best_routed/final.json`:

| Line | Kept routed board | Limit |
|---|---|---|
| Unconnected items (signal and power, KiCad) | 0 | 0 |
| DRC errors, routed board / copper board before routing | 0 / 0 | 0 |
| Power paths | `power_open` empty, no loose pad, PACK_P, 3V3 and GND one piece each | all joined |
| Hot loops, tier 1 | 7 of 7 | 7 of 7 |
| Ringing, sum of the seven loops | 5.56 nH routed (5.54 before routing; largest rise 0.01) | within 0.05 of 5.54 |
| Copper loss | 1.167 W routed (1.012 W before routing on this copper plan) | 1.25 W |
| PACK_P from Q102 to J113 / R427 / R527 | 2.14 / 2.21 / 1.64 mohm | 3.0 mohm |
| Signal tracks / vias inside hot-loop pours | 0 / 0 | 0 |

Every hard limit is met on the routed board. The four layer pictures (`best_routed/routed_{F,B,In2,In3}.Cu.png`) were
looked at again for this report: the two charger stages are compact twins, the PACK_P trunk is one strip on the
bottom, the In2 PACK_P sheet and the In3 3V3 bus are one piece each.

What this result is not:

- **Not one automatic run from the placement.** The copper is one local route (`runs/p2-m4`, 341 of 342, about 40 min,
  not timed out), then finishing passes, a carry-over onto a slightly changed plan, and two hand files (section 4).
  The one command (`tools/rebuild_m6.sh ... --board=...`) rebuilds the plan and checks the kept board; it gives the
  same board byte for byte (`runs/p2-m7v`). A new route from the placement (`tools/rebuild_best.sh`) was never run end
  to end and would differ: the same copper board routed 341 of 342 here and 333 of 342 on Logan's PC.
- **Loss is above the value before routing.** 1.167 W against 1.012 W before routing on this plan, and against the
  1.125 W of placement r4 at the end of phase 1. The rise is PACK_P +125 mW (signal tracks and via holes in the In2
  sheet) and GND +32 mW.
- **Not a fab release.** No fab-rule check and no fab files were made. The placement puts 18 movable parts on the
  bottom side (the two 9 V gate-drive supplies, Port 2's two gate-drive diodes and C451); the hand board has those
  parts on top.

## 2. Comparison with the earlier boards

### Placement and trial route (shared scorecard, before any team B routing work)

| Board | Blocked edges | Full trial route | Routed share | Loss before routing | Hot loops | Power paths before routing | Source |
|---|---|---|---|---|---|---|---|
| Hand placement, charter bar | 56 of 452 | 391 of 448, 18 min | 87.3 % | 1.36 W | 7 of 7 | PP5V open at U401 | charter; `runs/hand_screen` |
| Hand placement, scorecard re-run | 56 of 452 | 394 of 452 | 87.2 % | 1.36 W | 7 of 7, 6.75 nH | PP5V open at U401 | charter table |
| Skeleton q7s2 | not given | 299 of 442 | 67.6 % | 1.20 W | not given | all joined | charter table |
| Round 3 w1_c | not given | 346 of 442 | 78.3 % | 1.255 W | not given | all joined | charter table |
| Team B r1 | 58 of 451 | not run | | 1.142 W | 7 of 7, 5.78 nH | joined | `runs/r1-hot` |
| Team B r2 | 39 of 446 | 401 of 446, 27 min | 89.9 % | 1.133 W | 7 of 7, 5.54 nH | joined, but U401 pad 23 loose | `runs/r2-hot`, `runs/r2-route` |
| Team B r3 | 31 of 443 | not run | | 1.125 W | 7 of 7, 5.54 nH | joined | `runs/r3b-hot` |
| **Team B r4** (phase 1 result) | **19 of 437** | **411 of 437**, 17 min | **94.1 %** | **1.125 W** | **7 of 7, 5.54 nH** | joined | `runs/r4chg-hot`, `runs/r4-route` |
| Team B r5 (kept placement) | 21 of 436 | not run with the plain scorecard | | 1.124 W | 7 of 7, 5.54 nH | joined | `runs/p2a-r5src` |

No route in this table timed out. "Joined" means `power_open` holds only GND at J301 and J302, which the charter
allows. The hand board's hot-loop sum has two figures: 6.75 nH on the scorecard (also the sum of team B's partial
screens of the hand board) and 8.15 nH in the reference file `tools/score/template/hand_hot.json`. r5 is r4 with three
parts moved for the copper plan (U405 0.4 mm south, C451 0.5 mm south, R432 to 113.8, 71.4).

The plain scorecard flatters every board. The shared copper writer makes zones with several outlines and KiCad keeps
only the first, so power pours vanish when the router refills and the router runs where they were. With one zone per
outline (`tools/split_screen.sh`) the comparison is fair, and team B's lead over the hand board grows:

| Board | Blocked edges, zones split | Full route, zones split | With PACK_P straps (`final_route.sh`) |
|---|---|---|---|
| Hand | 58 of 422 | 363 of 422 (86.0 %), 13 min | 365 of 423 |
| Team B r3a | 30 of 421 | 385 of 421 (91.4 %), 22 min | r3: 387 of 422 |
| Team B r4 | 15 of 415 | 393 of 415 (94.7 %), 19 min | 391 of 416 |

### Routed board (the same routed-board check, `tools/final_route.sh`)

| Board | Route | Unconnected items | DRC routed | Power open routed | Loss before / routed | Hot loops routed | Run |
|---|---|---|---|---|---|---|---|
| Hand, PACK_P straps | 365 of 423 | 73 | 3 | PP5V at U401 | 1.359 / 2.413 W | 7 of 7, 6.76 nH | `runs/hand-final` |
| Team B r4, PACK_P straps (phase 1 end) | 391 of 416 | 37 | 3 | 3V3 at L201 | 1.124 / 2.854 W | 7 of 7, 5.56 nH | `runs/r4-final` |
| **Team B r5, full copper plan and finishing (kept)** | 341 of 342, then finished | **0** | **0** | **none** | 1.012 / **1.167 W** | **7 of 7, 5.56 nH** | `runs/p2-m7` |

The edge totals differ between rows because the phase 2 copper plan lays many connections itself before the router
starts (416 edges on r4 with straps only, 342 with the full plan on r5). So compare the unconnected items of the
routed boards, not the routed counts. The skeleton and round 3 boards have no routed-board numbers in the charter.

## 3. Phase 1: placement (2026-11-14 to 2026-11-15)

### Method

Chip by chip inside Logan's r2d boxes, in three groups worked side by side (Port 1, Port 2, pack side: 88, 88 and
69 movable parts). Each group is a list of short recipe files run by a greedy placer (`tools/secplace.py`), checked
(`tools/check.py`), screened alone on a partial board (`tools/screen.sh --partial`) and then stitched
(`tools/stitch.py`) into one placement that the shared scorecard screens. Port 2's stage and charger are Port 1's,
shifted by the L401 to L501 offset (-23.026, +0.006 mm). `PLAN.md` has the plan; `SKILL-NOTES.md` has the method as
steps.

Deviations from r2d, with the reason (`plan/boxes_B1.json`): r2d fixed only the J, H, TP and SW parts. With the
cup-fixed parts also held (U301, L401, L501, four NTCs, ten bottom capacitors), five r2d boxes hold a fixed part of
another section or miss their own anchor (`plan/r2d_vs_fixed.png`). Port 2's stage went to its inductor, both
chargers' programming parts to their chips, the MCU parts to the rim of U301, and both 9 V supplies to the bottom
because their top boxes were 1.37 and 1.14 times full.

### Rounds

| Round | What changed | Blocked edges | Loss | Hot loops | Run |
|---|---|---|---|---|---|
| Hand | reference | 56 of 452 | 1.36 W | 6.75 nH | `runs/hand_screen` |
| r1 | first stitch of the three groups | 58 of 451 | 1.142 W | 7 of 7, 5.78 nH | `runs/r1-hot` |
| r2 | escape yards south of U401 and U501, U501 north row closed to VBUS, Port 1 bulk capacitors joined | 39 of 446 | 1.133 W | 7 of 7, 5.54 nH | `runs/r2-hot` |
| r3 | VBUS pads 23 and 32 of both PD chips on planned copper, CC lines free, TVS back at the connector | 31 of 443 | 1.125 W | 7 of 7, 5.54 nH | `runs/r3b-hot` |
| r4 | charger and EEPROM pin escapes on both ports (31 small parts moved, 2 mm at most) | 19 of 437 | 1.125 W | 7 of 7, 5.54 nH | `runs/r4chg-hot` |

Group results on partial boards, against the same partial screen of the hand placement:

| Group | Hand partial | Final partial | Hot loops, final (hand) |
|---|---|---|---|
| Port 1 | 27 of 180, 0.482 W | 9 of 169, 0.313 W (`runs/chg-p1v1`) | HL_5V 0.70 (0.92), HL_IN 0.78 (0.87), HL_OUT 0.74 (0.77) nH |
| Port 2 | 42 of 173, 0.407 W | 9 of 169, 0.349 W (`runs/chg-p2v3`) | HL_5V 0.76 (1.17), HL_IN 0.80 (0.84), HL_OUT 0.74 (0.85) nH |
| Pack side | 7 of 156, 0.613 W | 1 of 153, 0.591 W (`runs/pack-H5`) | HL_3V3 1.02 (1.33) nH |

One route in phase 1 timed out: the Port 2 partial route `runs/p2v-i/scr` hit its 25 min cap (153 routed, 21 still
failing); run again with a 50 min cap as `runs/p2v-route50` it finished at 153 of 174.

### What worked

1. **Power parts first, pad to pad.** FETs at the fixed inductor's pads, the first hot-loop capacitor across the FET's
   supply and return pads, then the other capacitors, before any signal part. Every loop came out below the hand
   board's and stayed there, because no later round moved a stage part.
2. **A screen after every section.** The partial screen (about 5 min plus 1.5 min per loop) caught what the placer's
   cost could not: a capacitor 0.27 mm off its spot opened both the loop and GND at U404.
3. **Escape yards at the big chips.** A strip below a chip's pin row kept free of parts and walled by small parts so
   no power copper can leak in (`tools/yard_check.py`). U501: 16 blocked edges to 5; U401: 16 to 7.
4. **Standing capacitors over a pin row.** A CC or VBUS capacitor standing 0.3 to 0.5 mm over the pads it serves
   leaves no channel for VBUS copper along the row (north rows of U501 and U401).
5. **Naming the cause of each blocked edge, then moving one small part.** Round 4 cleared HIDRV1, FB, ACUV, ACOV,
   I2CC_SCL and four Kelvin taps on both ports with moves of 0.3 to 2 mm, each found with a quick single-net look
   (`tools/quick_ghost.sh`, `tools/zoom.py`): 31 to 19 blocked.
6. **Twins by explicit coordinates.** `tools/twin_recipe.py` writes Port 2's stage and charger as explicit spots; one
   fix in Port 1's charger then fixes Port 2's. The twin sets differ in four parts in the end, each for a named cause.
7. **Screening the hand board through every new tool.** Partial screens, the split run and the routed-board check of
   the hand placement gave a pass mark for each step.

### What did not work

- **The placer's hot-loop cost as a stand-in for the copper planner.** It passes spots where the planner's return pour
  has no room for vias. Only the screen tells.
- **More escape room in the planner** (`--plan="--escape=0.8"`): 58 to 40 blocked on r1, but PP5V opens at U401, a
  hard-limit miss. Dropped.
- **Bottom-side variants.** U502 and its pull-ups on the bottom sat in the planner's B.Cu VBUS pour: U501 had 18
  blocked edges. The second-level protector on the bottom walled the TS1 path. Both went back on top.
- **The TVS at the PD chip.** It joined U501 pad 23 but stood 11 mm from the connector. The lead put it back and
  joined pad 23 with the 4.7 uF capacitor, as on Port 1.
- **Reading one routed count as exact.** Two routes of one copper board differ by about 4 connections.
- **Trusting `power_open` alone.** A terminal counts as joined when any one of its pads is. Port 1's 5 A VBUS pad 23
  was off the copper on r1 and r2 while the scorecard showed nothing; `tools/loose.py` now prints such pads.
- **Left blocked at the end of phase 1** (15 with zones split): the CC pins under the protection chips, the QFN GND
  pins of U401 and U501, DRV9_OFF, 3V3 at U501.38, two gate pads wrapped by their stage's pour, C304.2. No part move
  cures these; phase 2 cured them with copper laid before routing.

Phase 1 also left the routed board open: `runs/r4-final` had 37 unconnected items, 3 DRC errors from the router and
2.854 W, because north-south signal tracks on In2 cut the half-ounce PACK_P sheet (J113 at 15.6 mohm against 2.24
before routing). The hand board fails the same way (2.413 W).

## 4. Phase 2: from placement to a finished routed board (2026-11-15 to 2026-11-16)

Definition of done (`PLAN2.md`), all on the routed board: 0 unconnected items; power paths joined and in one piece;
0 DRC errors; 7 of 7 hot loops; ringing within 0.05 nH of 5.54 with no loop more than 0.02 up; loss at most 1.25 W
with PACK_P to J113 and R427 at most 3.0 mohm; renders looked at with nothing in a hot-loop pour; one command.

### What was tried, in order

| Run | What | Route | Unconnected | DRC routed | Loss routed | J113 / R427 mohm | Hot loops routed | Hot-pour tracks, vias |
|---|---|---|---|---|---|---|---|---|
| `runs/r4-final` | r4, PACK_P straps only | 391 of 416, 31 min | 37 | 3 | 2.854 W | 15.6 / 15.4 | 7 of 7, 5.56 nH | not counted |
| `runs/p2a-base` | + 3V3 straps on In3 | 399 of 421, 38 min | 36 | 3 | 2.206 W | 10.4 / 10.2 | not run | not counted |
| `runs/p2a-n1` | + PACK_P trunk on the 2 oz bottom, 3 mm | 387 of 422, 60 min | 44 | 3 | 1.198 W | 2.27 / 2.36 | 7 of 7, 5.55 nH | not counted |
| `runs/p2r1_w3n20` | trunk 3 mm with a 2 mm neck at U403 | 394 of 422, 41 min | 39 | 3 | 1.306 W | 3.05 / 3.11 | 7 of 7, 5.54 nH | not counted |
| `runs/p2b-full2` | pin escape table, no trunk | 362 of 367, 27 min | 18 | 0 | 2.903 W | 15.9 / 15.6 | 7 of 7, 5.56 nH | not counted |
| `runs/p2-m1` | round 1 merge: trunk 5 mm + pins | 356 of 368, 66 min | 26 | 0 | 1.186 W | 2.11 / 2.23 | 7 of 7, 5.56 nH | 14, 7 |
| `runs/p2b-m1fin` | + accept-or-revert pass | same copper | 16 | 0 | 1.183 W | 2.11 / 2.22 | 7 of 7, 5.56 nH | 3, 3 |
| `runs/p2a-r5f` | placement r5, more plan copper | 346 of 353, 39 min | 15 | 0 | 1.257 W | 2.65 / 2.71 | 7 of 7, 5.56 nH | 1, 8 |
| `runs/p2-m3` | + accept-or-revert pass | same copper | 7 | 0 | 1.254 W | 2.65 / 2.71 | 7 of 7, 5.56 nH | 1, 2 |
| `runs/p2-m4` | round 2 merge: trunk back on its path + pass | 341 of 342, 40 min | 4 | 0 | 1.250 W | 2.61 / 2.68 | 7 of 7, 5.56 nH | 1, 3 |
| `runs/p2b-r3fin` | + passes with a loss pass, two hand tracks | same copper | 1 | 0 | 1.168 W | 2.12 / 2.18 | 7 of 7, 5.56 nH | 1, 3 |
| `runs/p2b-r3en` | + a second loss pass | same copper | 1 | 0 | 1.161 W | 2.08 / 2.15 | 7 of 7, 5.56 nH | 1, 3 |
| `runs/p2a-m5` | everything in the plan, new route + pass | 338 of 341, 55 min | 6 | 0 | 1.252 W | 2.57 / 2.64 | 7 of 7, 5.56 nH | 0, 0 |
| `runs/p2-m6` | round 3 merge: `p2b-r3en` copper carried onto a plan with one more path + pass | no new route | 0 | 0 | 1.199 W | 2.38 / 2.44 | 7 of 7, 5.56 nH | 0, 3 |
| `runs/p2r4b-1` | Port 2 SDA / I2CC_SCL crossover laid again by hand | no new route | 0 | 0 | 1.198 W | 2.38 / 2.44 | 7 of 7, 5.56 nH | 0, 0 |
| `runs/p2r4a-1` | EN_5V1 laid again by a pour-aware search | no new route | 0 | 0 | 1.169 W | 2.14 / 2.21 | 7 of 7, 5.56 nH | 0, 3 |
| **`runs/p2-m7`** | round 4 merge: both hand files in one | no new route | **0** | **0** | **1.167 W** | **2.14 / 2.21** | **7 of 7, 5.56 nH** | **0, 0** |
| `runs/p2-m7v` | the one command on the kept board | no new route | 0 | 0 | 1.167 W | 2.14 / 2.21 | 7 of 7, 5.56 nH | 0, 0 |

No route and no pass in this table timed out. Two worker runs were cut by a pause of the session, not by the route
cap (`runs/p2a-w3n15` and the first `runs/p2a-w3n20`); their numbers are not used.

Logan's PC (stock router, routed counts only) compared plan variants: p2-base 399 of 421; trunk variants p2a-t15
395 of 421, then p2a-w3n20 396, p2a-w5n20 394, p2a-n1 391 and p2a-t3 390 of 422; p2-m1 355 of 368; p2a-r5f 347 and
p2a-r5fw4 345 of 354; p2a-m5 340 and p2a-m5nv 337 of 341; p2-m4 333 of 342 (78.9 min). All finished, none timed out.

### What worked

1. **The 10 A path on the 2 oz bottom.** A hard B.Cu trunk from Q102 to J113 and R427 (`tools/trunk.py`) took the
   routed loss from between 2.2 and 2.9 W down to about 1.2 W, and J113 from 15.6 to 2.1 mohm. Straps on In2 keep
   the path joined but not low in resistance: In2 is half-ounce copper and every route cuts it differently. Kept
   width: 5 mm with a 2 mm neck under U403 (3 mm everywhere costs U403's south pin escapes; narrow costs mohm).
2. **3V3 as straps on In3 plus ties in the plan** (`tools/straps.py`, `"to": "zone"` rows, one hard In3 link). The 3V3
   bus stayed one piece on the routed board from `runs/p2-m4` on.
3. **Copper before routing for every connection no router makes.** A table of pin escapes (`tools/pins.py`,
   `plan/p2-pins*.json`): QFN GND pins tied into their exposed pad, gate pads cut out of their stage's pour, explicit
   vias for the CC pins under the protection chips, both VBUS pin pairs of each receptacle linked on B.Cu. Blocked
   edges 15 to 0.
4. **Vias the pins need anyway, laid before the trunk.** The via row south of U403 closes the diagonal the trunk
   would otherwise take under the chip. Without it the trunk cost five connections and 0.5 mohm at J113.
5. **Stub trim** (`tools/fin_trim.py`). The router's 3 to 5 clearance errors on every board were fan-out stubs of
   0.4 mm pitch pins at U101; moving each stub end to its pad edge gave DRC 0 every time.
6. **Accept-or-revert finishing pass** (`tools/router_b.py --aor`): one open connection per task, kept only when
   KiCad's own unconnected count drops and a refilled power check passes, everything put back otherwise. 26 to 16,
   15 to 7 and 9 to 4 unconnected, never a worse board.
7. **A loss pass** inside it: rank the In2 pieces by what each costs the PACK_P sheet, lay the worst again with the
   sheet closed, keep it only when the loss drops. 1.250 to 1.181 W in one pass on the round 2 board
   (`runs/p2b-r3dev`: CELL3 -24 mW, EN_5V2 -32 mW), 1.161 W after a second pass (`runs/p2b-r3en`).
8. **Carrying routed copper onto a changed plan** (`tools/transplant.py`) instead of routing again. Two plans that
   differ in 32 tracks and 5 vias gave routes that failed different connections, and the pass could close neither
   set. The carry-over had 0 DRC errors and only the two expected open connections.
9. **Pass tolerances from the gates for the last connection.** EN_5V1 was refused four times by per-task limits (2 mW,
   0.1 mohm) that are no gate. With the limits set from the gates it was laid at the first search: 0 unconnected.
10. **Measuring parts of one net, then looking at the current.** EN_5V1 cost 38 mW. Lifting it and putting back only
    its south end showed that 26 mW were the last 10 mm, where the PACK_P current is squeezed into J113 and R427
    (`tools/sheet_flow.py`), not the 40 mm run through the sheet. A search that knows the pours
    (`tools/lane_search.py`) then put it down the east edge on In3: 1.199 to 1.169 W.
11. **Finding which pours are hot before moving a via.** In the Port 2 corner only GND and AC_SNS_N on F.Cu are
    hot-loop pours. The two layer changes went into the PPHV pour (DC), and the three vias in the hot GND pour were
    gone with no new In2 copper.

### What did not work

- **A continuation route that lifts whole nets** (round 1): it pulled 810 routes for 24 open connections and ended
  with as many open. Replaced by accept-or-revert per connection.
- **A finishing pass with no power check.** It closes connections by cutting the PACK_P sheet (R527 1.57 to
  3.38 mohm). Closing every PACK_P fill instead is too strict. A per-task check with a small budget is the middle.
- **Everything in the plan, then a new route** (`runs/p2a-m5`): 6 unconnected against 4, on different nets. Laying that
  full plan under the other board's copper would have cost about 20 real conflicts.
- **No-via areas over the hot-loop pours.** On new routes their effect was inside the route-to-route noise (PC: 396
  without, 393 and 394 with; later 337 without, 340 with). On a board that already has vias there, the pass lifts
  the pieces and cannot lay them all again (5 unconnected, `runs/p2-m6t1`).
- **The loss pass on EN_5V1.** Laid again with the sheet closed it cost 3.5 mW more: the router's layer costs put the
  long north-south run on In2 although In3 has room.
- **More search nodes for EN_5V1.** The far end, U301.12, was boxed in by the escapes of pins 11, 13 and 14.
- **Tying a power pad through a via into a soft inner pour.** Later tracks cut it off again; the tie belongs in the
  plan.
- **Plain vias in the carry-over.** Wider plane antipads cost 29 mW until `transplant.py` copied the router's via
  pad options.
- **`tools/handroute.py` on this board.** It removes no inner-layer item (KiCad user layer names) and its writer fails
  in KiCad 10. Both round 4 workers found it; `tools/handroute2.py` is the fixed tool.

### What is left

- Loss: routed against before routing is PACK_P +125 mW and GND +32 mW; every other net under 1 mW
  (`runs/p2-m7/dc.json` against `runs/p2-m7/routed/dc.json`). In2 still carries several north-south signal tracks
  through the PACK_P sheet (`best_routed/routed_In2.Cu.png`). Which of them costs how much was not measured.
- EN_5V1 still costs 7 mW: every path to U301.12 east of x 108.2 passes the sheet's south edge on In2
  (`runs/p2r4_en/h12_east.png`).
- The route itself is not repeatable to the connection (section 1).

## 5. Files

- Placement: `best_placement.json` (r5), `score.json`, `F.png`, `B.png`; phase 1's r4 as `candidates/r4.json`,
  `score_r4.json`, `F_r4.png`, `B_r4.png`. Recipes in `recipes/`, group fragments in `fragments/`.
- Routed board: `best_routed/` (board, project and rule files, `final.json`, `summary.json`, four layer pictures).
- Copper plan: `tools/rebuild_m6.sh` holds the strap and filter strings; pin tables `plan/p2-pins-u403b.json` and
  `plan/p2-pins-r8.json`; hand copper `runs/p2-m7hand/hand_m7.json`.
- Tools: `tools/` with `tools/README.md`; the method as steps in `SKILL-NOTES.md`; plans in `PLAN.md`, `PLAN2.md`.
- The one command:
  `bash tools/rebuild_m6.sh runs/<new> --src=runs/p2a-r5src --board=best_routed/monolith_routed.kicad_pcb`
  (about 7 min; run as `runs/p2-m7v`).
