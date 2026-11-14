# Team B plan: chip by chip inside the boxes

Lead's plan of 2026-11-14. Read `../CHARTER.md`, `BRIEF.md` and `LOG.md` first. Everything here is a starting point
that the screens may overrule; when a screen overrules it, write the change and the number in `LOG.md`.

## 1. What we must reach

| Gate | Limit | Hand placement, same scorecard |
|---|---|---|
| Power paths joined | `power_open` empty except 3V3 at L201 and GND at J301, J302 | fails: Port 1 PP5V open at U401 |
| DRC errors | 0 | 0 |
| Hot loops | 7 of 7 pass tier 1 | 7 of 7 (charter) |
| Blocked edges (quick screen) | 56 of 452 or fewer; our target 40 or fewer | 56 of 452 |
| Full trial route | 391 of 448 or better | 391 of 448 in 18 min |
| Tier-2 loop inductance | each loop at or under `tools/score/template/hand_hot.json` | reference |
| Copper loss | 1.36 W or less | 1.36 W |
| Renders | power parts in compact groups round their chips; no power strip over 10 mm on the bottom | |

Order of priority when two of these pull apart: hard limits, then routability, then tier-2 nH, then loss.

## 2. What is fixed, and what that does to the r2d boxes

Not placed by us (they stay where `tools/score/template/board.kicad_pcb` has them):

- prefixes J, H, TP, SW: J108 to J120, J301, J302, J401, J501, H101 to H104, TP106, TP109, TP113, TP301, TP412, TP512;
- cup-fixed (groundup README): U301 with its antenna clearance, L401, L501, the NTCs TH101, TH104, TH401, TH501, and
  the back-side capacitors C208 to C213, C421, C456, C521, C556.

That leaves 245 movable parts (`plan/clusters_movable.json`, by section).

r2d was drawn with only J, H, TP, SW fixed, so some of its boxes cannot be used as they are (`plan/r2d_vs_fixed.png`).
We keep every r2d box that the fixed parts allow and amend the rest. The amended set is `plan/boxes_B1.json`
(picture `plan/boxes_B1.png`); the reason for each change is in its `why`. All Port 1 boxes are r2d's except the 9 V supply.

| Section | r2d box (x0..x1, y0..y1) | B1 box | Why |
|---|---|---|---|
| Port 2 four-switch stage | 78.5..91.4, 99.9..125.7 | 78.9..99.8, 88.2..102.8 | L501, TH501, C521, C556 are fixed at y 88 to 100. The stage goes where its inductor is: Port 1's stage shifted by -23.03 mm |
| Port 2 charger U503 | 85.8..98.8, 91.2..99.9 | 80.5..96.5, 102.8..113.6 | r2d's box is under L501. Below the stage, like Port 1, over the west gap-filler pad |
| Charger programming, both ports | P1 109.7..115.2, 79.7..88.0; P2 80.2..85.8, 91.5..99.8 | the charger's own box | These are U403's and U503's own resistors and capacitors. They go at the pins they serve (method step 4), not 15 mm away across the stage |
| Port 1 9 V supply | 87.8..99.2, 83.8..91.2 | 109.7..115.2, 79.7..88.0 on top, or the bottom side (section 6) | r2d's box is in Port 2's half and L501 covers its lower part |
| Port 2 5 V buck | 78.5..86.2, 75.5..91.2 | 78.9..86.2, 75.5..88.2 | cut where L501 and the stage start |
| 3V3 buck | 91.5..99.7, 115.0..123.2 | 78.9..91.0, 114.0..124.6 | the protection FETs need r2d's spot (next row); the buck draws 0.1 A and can sit in the free west area |
| Protection FETs | 99.7..121.6, 117.2..124.5 | 93.3..110.5, 115.4..122.8 (may use y from 113.6 for x 103.6..107.2, between the bottom via field and TP113) | east half of r2d's box is under U301 and J301 |
| Second-level protector and fuse | 109.3..121.6, 124.5..132.7 | 111.6..121.1, 126.9..134.2 for F102 and Q104; U102 and its filters beside the gauge or on the bottom | upper part is under U301 |
| MCU module, pull-ups, antenna match | 91.5..105.7, 103.4..112.9 and two small boxes | the rim round U301: 109.0..121.1, 116.2..128.8 | U301 is fixed; its parts go to its pins |
| Bottom boxes (stage capacitors, pack bulk, cell NTCs) | three boxes | the fixed parts' own places | they hold only cup-fixed parts |

The area r2d gave to the MCU module (91.5..105.7, 103.4..112.9) is left without a section. It is the middle of the
board, over the pack bulk capacitors' via fields, between the two chargers. Keep it for the north-south signals
(section 5) and for R527 and R427's PACK_P copper. Do not fill it with parts.

## 3. The method, per section

A section is placed by a short recipe file, run by the team placer (`tools/secplace.py`, section 8). The steps, in order:

1. **Main chip.** Explicit position and turn, chosen by looking at the picture: pins that carry power face their
   source or load, pins of nets that leave the section face the border they leave by. Try at most three variants
   and keep the one the screen likes.
2. **Escape ring.** Before any other part: a ring round every chip with 12 pads or more (U401, U501, U403, U503,
   U405, U505, U101, U102, U402, U502). No other part's courtyard within 0.8 mm of a pad row that has signal pins.
   The only parts allowed inside are capacitors declared in `constraints.json` `serves` for a pin of that row, at 0.3 mm,
   lying radially (far pad pointing away from the chip). Each chip side keeps one free gap of 0.6 mm per 2.5 mm of
   side between support parts, so tracks can leave. `tools/check.py` counts, for every signal pad of these chips,
   whether a 0.2 mm track can run 1.0 mm straight out; a pad that cannot is an escape fault.
3. **Hot-loop capacitors, pad to pad.** For each loop in `constraints.json` `hot_loops`, first capacitor first:
   its supply pad within 1.5 mm (pad edge to pad edge) of the switch's supply pads, its return pad within 1.5 mm
   of the switch's return pads, and no pad of another net between them. Then the other capacitors of the loop in the
   order listed. No signal part may take a spot before these.
4. **Switches, inductor, sense.** The parts in `constraints.json` `draw` and `kelvin` for that chip: FETs at the
   inductor pads, bootstrap parts, sense resistors in the current path with room for the two Kelvin taps to leave
   from the inner pad edges as a pair.
5. **Own resistors and capacitors at their pins.** Every remaining part of the section, most constrained first,
   each with a pad target ("pad 1 of C410 at U403 pad 24"). A part with no declared pin gets the pad of its two-pad
   net. Plane nets (GND, PACK_P, 3V3) are never a target.
6. **The section's power copper, then the screen.** Run `tools/screen.sh --partial` on the parts placed so far: the
   shared copper planner, DRC, DC loss, renders, blocked edges, and the hot loops of this section. Look at
   `F.png` and `B.png`. Fix by moving parts, then go on to the next section. Nothing placed earlier is frozen: a
   later section may ask an earlier one to move (same worker: just do it; other worker: section 5).

Reserved boxes come before parts: a strip the power copper needs (for example from L402 pad 2 to U401 pad 34 for
PP5V, which is open on the hand placement), a via field, a lane. A recipe step `reserve` blocks them for parts.

Port 2 is not designed twice. Port 1's stage and charger are placed first; Port 2's stage and charger are that
placement shifted by (-23.026, +0.006) mm, the offset from L401 to L501, then adjusted only where a fixed part differs.
The port front ends (protection, PD controller, 5 V buck, 9 V supply) are placed separately for each port: J501 sits
east of L501 while J401 sits west of L401, so a shift does not fit there. While Port 1's stage and charger are
placed, the placer also tests each spot's shifted copy against Port 2's fixed parts and the board edge, so no
Port 1 spot is taken whose copy cannot exist (stage and charger parts stay east of x 102.0; the copy's west limit is 78.9).
R424, R427 and R524, R527 are placed per port, not copied: their ends are U401, J113 and U501, which do not shift alike.

## 4. Sections, in order, with refs and pins

Port 1 refs; Port 2 is the same with 5xx for 4xx. Pad numbers from `constraints.json` `pin_pads` and the netlist.

**P-a. Stage** (anchor L401, fixed: pad 1 SW1 at 109.3, 92.6; pad 2 SW2 at 114.4, 92.6; TH401 fixed at 111.8, 97.3;
C456 and C421 on the bottom at x 102.2..107.0 and 116.1..121.0, y 91.6..100.5). Box 100.2..121.1, 88.0..102.8.
1. Q401 (port leg) and Q402 (battery leg), pad 9 (SW) toward the L401 pad of its net. Start south of L401, side by side.
2. C430 across Q401 pads 2 to 4 (AC_SNS_N) and 5 to 7 (GND); C438 across Q402 pads 2 to 4 (BAT_SNS_P) and 5 to 7.
3. C420, C423 (loop HL_IN), C431, C434 (loop HL_OUT), then C424, C427: supply pad toward the FET's supply pads,
   return pad where a via array to In1 fits. Leave the vias to C456 and C421 free on top.
4. Gate resistors R444 (pad 2 at Q401 pad 1), R445 (Q401 pad 8), R446 (Q402 pad 1), R447 (Q402 pad 8), on the
   charger side. Bootstrap C412 (BTST1 to SW1), C413, D404, D405 between the FETs and U403 pads 26, 28, 20, 18.
5. R424 (PPHV to AC_SNS_N) between U401 pad 20 and the input capacitors; R427 (BAT_SNS_P to PACK_P) between
   Q402's supply pads and J113. Both belong to the charger section in the netlist but are placed here, in the current path.
6. Screen with `--hot="USB Port 1/HL_IN,USB Port 1/HL_OUT"`. Reference: 0.82 and 0.83 nH (hand, all capacitors in parallel).

**P-b. Charger** U403. Box 103.5..117.3, 102.8..113.6, over the east gap-filler pad. Gate-drive side (pads 19 to 28)
faces the FETs. Ring first. Then by pad: C410 at 24 (REGN), C411 at 23 (DRV_SUP), C409 at 32 and 33 (VAC),
C414, C415, C416, R425, R426 at 29 and 30 (ACN, ACP), C417, C418, C419, R428, R429 at 13 and 14 (SRN, SRP),
R418, R419 at 11 and 12 (FBG, FB) and at least 2 mm from SW1, SW2 and SW_5V copper, R409, R410, R411 at 34 and 35,
R412 at 36, R413 at 9, R414 at 10, R415, R416 at 8 (TS), R417, R435 at 7 (CE_N).

**P-c. PD controller** U401 with U402. Box 101.4..109.7, 75.3..87.6. VBUS pads (32, 23) toward J401, PPHV pad 20
toward R424, PP5V pad 34 toward the 5 V buck. Ring first, and 1 mm free round pads 34, 32 and 23 for every part not
on that net (round 3 lesson). Then C449 at 20, C450 at 32, C407 at 34, C404 and C408 at 1 and 2, C405 at 4, C403 at 38,
U402 with R402, R403 at pads 16, 17, R404 at 18, R441 at 19. Pads 8, 9, 10 (SDA, SCL, IRQ_N) need a free way to the
port border lane.

**P-d. Port protection** U405, D401. Box 100.2..113.0, 69.9..75.3 (H104 is inside it). U405 between J401's CC pads
(A5, B5) and U401 pads 28, 29, turned so C_CC1 and C_CC2 (U405 pads 4 to 7) face the connector. Ring. D401 and
C406 on VBUS at J401's VBUS pads, in the path, not on a stub. C401, C402 at U401 pads 28, 29; C451 at U405 pad 3;
C452 at U405 pad 10.

**P-e. 5 V buck** U404. Box 115.2..121.1, 66.4..85.8 (Port 2: 78.9..86.2, 75.5..88.2, and up to y 63.8 if the 9 V
supply goes to the bottom). C446 then C444 across pads 3 (VIN) and 4 (GND), pad to pad. L402 pad 1 at pad 5 (SW),
C440 at 6 and 5, C439 at 7, R433, R434 at 8, R432 at 2. C441, C442, C443 at L402 pad 2, on the way to U401 pad 34.
Reserve the PP5V strip to U401 pad 34 before placing P-c's small parts. Screen with `--hot="USB Port 1/HL_5V"`
(reference 0.88 nH).

**P-f. 9 V gate-drive supply** U406, Q409, C457 at pad 8, C458 at pad 1, R452, R453 at pad 2, R454, R455, D410, D411.
D410 and D411 go with C411 at U403 pad 23, not with U406. The rest: bottom side first choice (section 6).

Pack side:

**K-a. Cell path.** F102 at J112 (CELL_P_RAW), Q101 and Q102 in the box 93.3..110.5, 115.4..122.8, RS101 between J108
and J114. Screen both orders of the FETs (Q102's PACK_P pads west as on the hand board, or east toward J113 and R427)
and keep the lower loss with all paths joined. Then C107, C108, C110, C111, D103, R109 to R112, R118 at the gate pads
(Q101 pad 4, Q102 pad 4).
**K-b. Gauge** U101 in 93.3..104.4, 123.0..132.4: ring, C105 and the supply parts, the cell-input filters R101 to R106
with C101 to C104 at the VC pads, R107, R108, C106 at the shunt taps (Kelvin pair from RS101's inner pad edges),
R113, R115, R116, D101.
**K-c. Second-level protector** U102 with R119 to R126, C112 to C118: beside the gauge or under it on the bottom. Q104 at F102 pad 3.
**K-d. 3V3 buck** U204 in 78.9..91.0, 114.0..124.6: C206 across pads 2, 3 (VIN) and 1 (PGND), L201 at pad 9, C207 at
L201 pad 2. Screen with `--hot=HL_3V3` (reference 1.75 nH).
**K-e. MCU parts** in the rim round U301: C301, C302, C303 at pads 6, 7; C304, R302 at pad 14; R304 at 9, R305 at 10,
R313 at 15, R314 at 21; C313, C314, C315, R321 at pads 3, 4. Q103, R117 in 83.6..89.4, 127.0..130.8.

## 5. Worker groups and borders

| Group | Sections | Region on top (x, y) | Movable parts |
|---|---|---|---|
| Port 1 | P-a to P-f for 4xx | 100.0..121.6, 63.8..113.6 | 88 |
| Pack side | K-a to K-e | 78.4..121.6, 113.6..137.2 | 69 |
| Port 2 | P-a to P-f for 5xx | 78.4..100.0, 63.8..113.6 | 88 |

The refs of each group are the sections of its sheets in `plan/clusters_movable.json` (Port 1: USB Port 1; Port 2:
USB Port 2; Pack side: Cells and Gauge, MCU, 3V3 Rail). `stitch.py` refuses a fragment that misses or adds a ref.

Order: Port 1 and Pack side run first, side by side. Port 2 starts when Port 1's stage and charger have passed
their screen, from the shifted copy. If Port 2 has to start earlier, it does its front end (P-c to P-f) first.

Border rules:

1. No courtyard crosses a region line. Each group stays 0.4 mm back from the line, so 0.8 mm is free between
   groups. That gap is the lane for tracks and vias that pass between groups.
2. Six signals cross between groups, plus two that pass through: SDA, SCL, IRQ_N (U401 and U501 pads 8, 9, 10 to
   U301 pads 10, 9, 21, the gauge and J302), CHG_INH (R435, R535 to U301 pad 11), EN_5V1 (U404 pad 2 to U301 pad 12),
   EN_5V2 (U504 pad 2 to U301 pad 13), CELL1 (J109 to the gauge), CELL3 (J111 to the gauge). They run north-south on
   the inner layers. Two via fields stay free of parts on both sides and are reserved in every recipe:
   top 98.6..101.4, 83.8..87.8 (between the PD controllers) and bottom 99.6..103.4, 113.0..115.2 (above the
   protection FETs, beside TP412). The centre area 96.5..103.5, 102.8..113.0 takes no parts except R527.
3. A part that must cross a line needs a claim in `fragments/claims.json` (ref, box, group, reason). First claim
   holds. The lead settles a clash at the stitch: a power or hot-loop part wins over a signal part; a part within
   2 mm of the pin it serves wins over one that has another spot; the loser is placed again with the winner as an obstacle.
4. Each worker's checks load the other groups' latest fragments from `fragments/` as obstacles. Where a group has no
   fragment yet, its B1 boxes for chips with 12 pads or more stand in.
5. Bottom-side areas belong to the group above them: Port 1 has x over 100, y under 113.6; Port 2 x under 100;
   Pack side y over 113.6.
6. PACK_P and GND are the planner's (In2 and the planes). Groups keep the top side free above the via arrays of
   C208 to C213 (95.9..105.8, 102.8..112.2) and of the four stage capacitors on the bottom.

After each group's fragment is accepted, the lead stitches all accepted fragments, runs the whole-board screen and
`tools/blame.py`, and sends each group its list: blocked edges, open power pins and DRC errors by ref.

## 6. Bottom side

The hand board has 12 parts on the bottom (the fixed ones), soldered by hand, so every part we add there is an
assembly cost. We report the count with every result. Rules:

- Whole small-signal sections only, never a stray part, never a hot-loop capacitor, a Kelvin part or a part that
  serves a pin within 2 mm on top.
- No parts in the cup's keep-outs: the gap-filler pads (84..93 and 107..116, y 88.5..114.5), the rails, the tails and
  the wire pads. Free areas: top-left 78.9..88.5, 70.2..86.3; top-centre 93.7..106.3, 70.2..86.3; top-right
  111.5..121.1, 70.2..86.3; pack 93.7..106.3, 112.6..134.6; and the strips x 78.9..83.8 and 116.2..121.1 below y 100.8.
- Not under a QFN's thermal-via field or a through-hole pad.

Planned, in order of need:

1. Both 9 V gate-drive supplies (U406, Q409, C457, C458, R452 to R455 and the 5xx set; D410, D411 stay on top at the
   charger): 16 parts. Reason: on top the Port 1 9 V box is 1.37 full and the Port 2 5 V box 1.14 full by courtyard area.
   Port 1's to the top-right area, Port 2's to the top-left area.
2. The second-level protector's chip and filters (U102, R119 to R126, C112 to C118): 16 parts, to the pack area under
   the gauge. Reason: its top box is 1.31 full once U301 is where the cup wants it.
3. Only if the whole-board screen still shows a boxed-in PD controller: U402 with R402, R403 (and 5xx) to the top-centre area.

Each move is tested: screen with the section on top (where it fits at all) and on the bottom, and keep the bottom
only if blocked edges drop or a hard limit needs it.

## 7. Screens and what passes

After every section (partial board, about 4 min, plus about 1.5 min per hot loop):
`tools/check.py` clean (no overlap, no ring fault, no part outside its region without a claim), DRC errors 0,
no open power pin on the section's nets, the section's hot loops pass tier 1 and read at or under the hand
reference, no new blocked edge at a chip that had none before. Look at both renders.

After every group (partial board with the group's parts only, compared with the same partial screen of the hand
placement, `runs/hand_<group>/`, which the framework worker makes):

| Group | Blocked edges, hand whole-board count for its parts | Pass | Target |
|---|---|---|---|
| Port 1 | 19 | at or under the hand partial screen | 12 or fewer |
| Port 2 | 25 | at or under the hand partial screen | 12 or fewer |
| Pack side | 6 | at or under the hand partial screen | 4 or fewer |

plus: its power pins all joined (Port 1 and Port 2: PP5V at U401, U501 joined, which the hand board misses), its hot
loops 3 of 3 (Pack side 1 of 1) at or under the hand's nH, signal half-perimeter of its nets at or under the hand's.

After every stitch (whole board, shared scorecard, `--route=0 --no-hot`): blocked 56 or fewer, DRC 0, power joined,
loss 1.36 W or less. When that passes: one run with hot loops, then one full route (45 min cap). Only one router or
hot-loop job per worker at a time. Report a timed-out route as timed out, with the last progress line.

## 8. Framework (built first, by the framework worker)

All in `docs/layout-teams/B/tools/`; shared tools are copied, not edited.

- `blib.py`: the board as data (`tools/floorplan/example/monolith/board_dump.json`: courtyards, pads, keep-outs; the
  real outline from a `cu_dump.py` run), the fixed list, the placement transform, legality, the cost terms.
- `secplace.py`: runs a recipe (steps `put`, `ring`, `reserve`, `hot`, `at_pin`, `auto`, `translate`, `side`) and
  writes a fragment. Legal from the first part, like `team_round3/w1/greedy_fill.py`, whose grid search it reuses.
- `check.py`: legality, rings, escape faults, pin distances against the limits, parts outside box or region, picture.
- `stitch.py`: fragments to one placement; refuses missing, double or foreign refs and overlaps.
- `apply_b.py` (KiCad python): placement to board, with side flips and a partial mode.
- `screen.sh`: partial or whole-board screen; the whole-board one calls the shared `tools/score/score_board.sh`.
- `blame.py`: blocked edges, open pins and DRC errors by ref, chip and group, with what stands next to the blocked pad.
- already there: `hpwl.py`, `draw_boxes.py`.

Formats: a fragment is `{ref: [x, y, turn, side]}` with turn 0, 90, 180 or 270 relative to the template (the shared
`apply_placement.py` convention) and side `"F"` or `"B"`. Fragments live in `fragments/<group>.json` with
`fragments/<group>.meta.json` (rings, reserved boxes, claims, bottom-side refs, deviations from B1 with reasons).
Recipes live in `recipes/<group>/<section>.json`. Runs go to `runs/<group>-<section>-<n>/`.

## 9. Housekeeping

- Append a dated entry to `LOG.md` at the end of every session: what was done, scorecard numbers, files.
- Commit on `layout-team-B`; no push, no branch switch, no model names in files or commits.
- Numbers come from the scorecard or a named team tool. Say which options were used (`--plan=...`, partial or whole).
- Never order PCBs or call any JLCPCB endpoint.
