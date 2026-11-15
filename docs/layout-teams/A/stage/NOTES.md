# Worker `stage` (team A, round 1): charger power-stage template

## Why the groundup stage failed with generated copper (lead_baseline)

The SiZ240DT (PowerPAIR 3x3S) has D1 (pads 2,3,4 + big pad 2) on one long side, S2 (5,6,7) on the other, the SW pad 9
between them, gate pins 1 (HG, D1 side) and 8 (LG, S2 side) at the two corners of one short edge ("gate edge"), and
pads 4/5 at the corners of the other short edge ("cap edge"). On F.Cu:

* a cap can only join D1 and S2 across the **cap edge** (any F.Cu path between the sides passes over the SW pad's
  end), so the HF cap belongs centred on the cap edge;
* the SW node can then only leave through the **gate edge**, between the two gate pins.

Groundup had both FETs at rot 180 (S2 left, D1 right), so Q401's S2 faced the AC column, whose caps had their AC pads
facing the FET (0.64 mm from the S2 pads: no via room, "Q401.5/6/7 no room for a GND via" -> GND open at Q401/Q501,
hard fail). C430 sat between the FETs, bridging Q401.D1 to **Q402**.S2, so no cap closed HL_IN on its own switch
(7726 nH per cap). TH401 sat under Q401 and the gate resistors were packed at y 102.7 (LG1, HG2 blocked).

## The template (stage_template.json, apply_stage.py)

"Classic" bridge with the switches mirrored by rotation: AC caps | Q401 (rot 0: D1 left, S2 right, gates up) |
FET gap (S2 facing S2) | Q402 (rot 180: S2 left, D1 right, gates down) | BAT caps.

* Q401 hangs from the fixed inductor (anchor_from L401): SW pad 9 under L401 pad 1, courtyard 1.05 mm below L401's.
  SW1 goes straight up on F.Cu. Port 2 = same template on L501/Q501 (pure -23.026 mm translation; mirroring is not
  possible for SMD on the same side, and the translation keeps one description).
* C430 / C438: centred on each switch's cap edge, offset courtyard half + cap half (2.45 mm).
* Bulk caps sit with their supply pad against the switch's D1 side (vertical 1210s, because the port-2 copy must stay
  right of x 79.4: horizontal 1210 columns on both sides do not fit 18.5 mm per port). GND pads get return vias.
* R445 (LG1) inside the 1.4 mm FET gap, level with pin 8: gives LG1 an escape and stops SW2 from wrapping round Q402
  through the gap (B3 did that: SW2 pour ran between the FETs and walled LG2).
* Every pose is relative (dx, dy, drot) in the switch frame with the rule that produced it; apply_stage.py applies it
  to both ports and re-places the neighbours it covers with groundup's greedy placer (placelib.auto), keeping keep-boxes free.

## Variants (quick = scorecard steps 1-4 + blocked-edge screen, quick.sh; stock planner unless noted)

| Variant | What | closes (P1 IN / OUT) | power_open | DRC | blocked | loss W | P1 HL_IN nH (C430/C420/C423, all) | P1 HL_OUT nH (C438/C431/C434, all) |
|---|---|---|---|---|---|---|---|---|
| lead baseline (groundup) | | [] / [] | GND Q401, Q501 (FAIL) | 0 | 65 of 441 | 1.064 | open (7726) | 0.88 (vias only) |
| hand template, generated copper | reference | C430 / C438 | PP5V U401 (FAIL) | 0 | n/a | 1.359 | 0.374 / open / open, all 0.673 | - |
| V1, A1 | hand core relative to Q401 inside groundup | - | - | - | - | - | did not fit: 4-7 overlaps (port-2 5 V buck, U406, U506) | |
| B1 | rot 0/180, horizontal columns | - | - | - | - | - | port-2 column off the board edge | |
| B2 | vertical caps | - | - | - | - | - | C423 on U406; auto-placer dropped R416 into the FET gap (added keep boxes) | |
| B3 | C423 under C430, keep box | C430 / C438, C434 | clean | 0 | 47 of 432 | 1.143 | 0.514 / 0.783 / 1.08, all 0.565 | 0.466 / 0.835 / 0.948, all 0.546 |
| **B4 (best)** | B3 + R445 in the FET gap, TH401 under Q401 S2 corner | C430 / C438, C434 | clean | 0 | 47 of 433 | 1.108 | see scorecard below | |
| B5 | B4 with C420/C424 swapped (loop cap out of the column) | C430 / C438, C434 | clean | 0 | 54 of 439 | 1.057 | - | - |
| B6 | B4 + intent lane at HG1 (F.Cu), --plan intent | same | clean | 0 | 46 of 433 | 1.108 | - | - |
| B7 | B4 + lane on F.Cu and B.Cu | same | clean | 0 | 47 of 433 | 1.115 | - | - |

Stage edges still blocked in B4: HG1 (Q401.1/Q501.1 to R444/R544), C412/C512 (bootstrap) to the SW1 pour,
R429 PACK_P to plane, C410-R454 REGN, U406-R454; P2 TS (TH501) appears in some variants. Gone vs baseline: GND at
Q401/Q501/Q502 S2, LG1, LG2, HG2, R526 AC (most runs).

## What did not work / why HG1 stays walled

HG1 (pin 1) sits next to the top end of D1's big pad. The planner's HL_IN supply pour is the convex hull of every
supply pad (D1 + C430.1 + C420.1 + C423.1); any AC pad left of the switch puts HG1 inside that hull, and inside a hull
only the clearance (not the 0.4 mm escape room) is kept, so no via fits beside HG1. Lanes from intent.json are
honoured by the power-net step but **not by the hot-loop pours** (B6/B7: the sliver over HG1 stayed). Fixes left for
round 2: (a) planner: clip hot-loop pours by intent lanes / keep escape room at gate pins; (b) placement: only HF and
bulk caps on the far side of HG1 (needs U406/U506 moved to free room under the stage).

Bootstrap/driver diodes D404/D410 were displaced by C423 and re-placed far (near J113) by the greedy placer: sprawl
that must be fixed together with the U403 support parts (other worker).

## Scorecard and route results

Best = B4. Stock scorecard, `tools/score/score_board.sh runs/sc_B4 best_score.json --route=0` (hot loops on):

| | value |
|---|---|
| power_open | 3V3@L201, GND@J301/J302 only (allowed) |
| DRC errors | 0 |
| hot loops | 7 of 7 pass tier 1, tier-2 sum 6.17 nH |
| P1 HL_IN | C430 0.499, C420 0.783, C423 1.081 nH; all parallel 0.561; loop total 0.76 (ref 1.02) |
| P1 HL_OUT | C438 0.494, C431 0.916, C434 0.960; all parallel 0.584; total 0.78 (ref 1.03) |
| P2 HL_IN | C530 0.519, C520 0.816, C523 1.059; all parallel 0.577; total 0.78 (ref 0.99) |
| P2 HL_OUT | C538 0.466, C531 0.911, C534 0.942; all parallel 0.558; total 0.76 (ref 1.00) |
| loss | 1.108 W (baseline 1.064, hand 1.36) |
| blocked edges | 47 of 433 (baseline 65 of 441, hand 56 of 452) |
| full route, Logan's PC (stage-B4, sha acf4404d) | **379 of 433 routed, 53 failed, TIMED OUT at 60 min** |

All bulk caps now close too (per-cap 0.78-1.08 nH; baseline HL_IN was open, hand-gen bulk open at 17393 nH).
Renders runs/sc_B4/F.png, B.png checked: both stages compact under their inductors, port 2 a copy of port 1; SW1 straight
up on F.Cu; SW2 joins L401.2 by a short via blob on B.Cu under the inductor; an AC_SNS_N B.Cu corridor runs from
the input-sense area down to each stage. Not good: D404/D410 (bootstrap / DRV_SUP diodes) pushed out to x~119 near J113.
