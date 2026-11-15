# Rooms p1_stage and p2_stage: the two four-switch power stages (one worker does both)

Do p1_stage first, get it right, then build p2_stage as the same arrangement moved 23.1 mm to the left (Port 2's fixed
parts sit exactly 23.1 mm left of Port 1's), adjusted where the room differs.

p1_stage area: x 101.1-121.5, y 87.8-102.4; x 107.6-121.5, y 102.4-104.5; x 116.5-121.5, y 104.5-107.2.
p2_stage area: x 78.5-99.3, y 87.8-102.5; x 78.5-94.0, y 102.5-104.5.
The strip x 99.3-101.1 between the two rooms is a reserved lane (a 1.5 A rail and signals run up it): keep out.

## Parts (Port 1 names; Port 2 has 5 instead of 4 as the first digit)
Fixed: L401 (pad 1 = SW1 at (109.3, 92.6), pad 2 = SW2 at (114.4, 92.6)), TH401, and on the BOTTOM side C456 (x 102.2-107.0,
y 91.6-100.5) and C421 (x 116.1-121.0), both from AC_SNS_N (pad at y 92.9) to GND (pad at y 99.2).
Yours: Q401 (input half-bridge: D1 = pads 2,3,4 on AC_SNS_N, S2 = pads 5,6,7 on GND, pad 9 = SW1, gates 1 = HG1, 8 = LG1),
Q402 (output half-bridge: D1 on BAT_SNS_P, S2 on GND, pad 9 = SW2, gates HG2, LG2), input capacitors C430 (0.1 uF, first),
C420, C423, C424, C427, output capacitors C438 (first), C431, C434, boot capacitors C412 (BTST1-SW1), C413 (BTST2-SW2),
boot diodes D404, D405 (from DRV_SUP), gate resistors R444 (HG1), R445 (LG1), R446 (HG2), R447 (LG2), and R427 (the
battery-side shunt, BAT_SNS_P -> PACK_P).

## Power flow
- AC_SNS_N, 5 A, enters from the room above through the top edge at about x 104-108, y 87.7 (Port 2: x 81-85). It must reach
  Q401 D1 by a short, wide top-layer path with the input capacitors on the way. On the hand board the capacitors sat on
  both sides of the inductor and Q401's D1 pads faced away from the entry; the path cost 9.2 milliohm (0.23 W). Target:
  under 2 milliohm. The lead's suggestion: all four big input capacitors in the left column(s) next to the entry, and Q401
  turned so that D1 faces that column and S2 (GND) faces Q402's S2, sharing one ground via field between the two FETs.
  You decide; measure it.
- BAT_SNS_P, 5 A: Q402 D1 -> C438, C431, C434 -> R427 pad 1; R427 pad 2 is PACK_P and must sit right at J113 (fixed PACK_P
  wire pad, x 117.6-121.3, y 107.3-110.6). Port 2: R527 pad 2 (PACK_P) should end near x 96-99, y 98-104 (the pack rail's
  bulk capacitors are under the board centre). R427/R527 are shunts with sense taps: via room at the inner pad edges.
- SW1: Q401 pad 9 -> L401 pad 1. SW2: Q402 pad 9 -> L401 pad 2. Short and wide; keep small-signal parts off them.
- GND: free space for return vias beside Q401/Q402 S2 pads and beside every capacitor's GND pad.

## Hot loops (the copper is generated from your placement and then solved; tier-1 limits are hard)
- "USB Port 1/HL_IN": capacitors C430 (first), C420, C423; supply AC_SNS_N; switch pins Q401 D1 and S2. Limit 1.3 nH; the
  hand board scored 0.87 total, 0.37 for the first capacitor. C430's pads must sit right at Q401's D1 and S2 pins.
- "USB Port 1/HL_OUT": C438 (first), C431, C434; supply BAT_SNS_P; Q402 D1 and S2. Limit 2.17 nH; hand 0.77 / 0.43.
- Same two loops on Port 2 (C530, C520, C523 / C538, C531, C534): hand 0.84 and 0.85.
Run `bash tools/qs.sh <name>` WITHOUT --no-hot and read /home/claude/runs/<name>/hot_gate.log. All four loops must pass;
then lower is better.

## Gate drive and boot
The charger chip sits below the stage. Its north-side pins are at about y 108, left to right from x 109.2 to 113.7:
SW1, HIDRV1, BTST1, LODRV1, REGN, DRV_SUP, GND, LODRV2, BTST2, HIDRV2; SW2 is the top pin of its east side (Port 2: the
same 23.0 mm to the left). Gate resistors and boot parts go between the FETs and that edge, each with a clear way to its
gate pad. On the hand board HG2 (R446 to Q402), LG1 (R445 to Q401) and HIDRV1 had no path on either port.

## Numbers to report
For each port: the four loop inductances, AC_SNS_N and BAT_SNS_P resistance and loss, SW1/SW2 loss (dc.log), which
capacitors the copper planner could not join (plan.log lines with "left to router"), blocked connections.
