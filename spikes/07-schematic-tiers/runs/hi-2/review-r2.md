# Round 2: self-review (before changes)

Method: ran ./make.sh, opened every out/render/page-*.png and zoomed crops of each box. Page 1 is the root sheet
(five sheet symbols, not scored). Also wrote `design/lint.py` (text over text, text over wire, text over symbol)
and ran it on the generated sheets: 7 findings before round 2.

## Scores before (0-5)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4 | 3 | 3 | 3 |
| 2 Grouping | 3 | 4 | 3 | 3 |
| 3 Wires vs labels | 4 | 3 | 3 | 2 |
| 4 Clutter | 3 | 3 | 3 | 3 |
| 5 Space | 2 | 3 | 3 | 2 |
| 6 Recognisable circuits | 4 | 3 | 3 | 4 |
| 7 Annotation | 4 | 4 | 4 | 4 |
| 8 Reviewability | 4 | 3 | 3 | 3 |
| Mean | 3.5 | 3.3 | 3.1 | 3.0 |

Reasons, by sheet:
- 3V3: the bulk-cap row C208..C213 has each value running into the next cap; a tiny circuit sits in a huge A4 box
  with the bulk caps in a second box, so the page is mostly white; the bulk is not on the PACK_P path it serves.
- Cells: Q104 value clipped by the box edge; long detour wires from the gauge's BAT/VCC/PBI pins; the TS box and the
  right half of the power path are empty; PACK_P label touches the box edge.
- MCU: decoupling caps C301..C303 have values on top of their neighbours and sit far from VDDS on a long rail;
  the antenna pi network is tied to the chip only by the RFIO and ANT_IN labels; J301 value overlaps its body.
- USB: BQ25756 hub is a wall of 25 stub labels with its mini-circuits 40 mm away, so little is wired directly; A and
  B boxes are 60 percent empty; C406/C450, C420.., C431.. values collide with the next part; C414/C417 text on wires.

## Five changes ranked by expected gain

1. Remove every text/symbol/wire overlap (lint to zero): auto pitch for rows of hanging caps, move values that hit
   neighbours, fix Q104, J301, C406/C450, MCU caps. Lifts Clutter on all four sheets.
2. Fit each sheet to its content and rebalance boxes so no large white areas remain (custom page size, tighter
   boxes, USB A/B shortened, rows moved up). Lifts Space on 3V3 and USB, and a little on Cells and MCU.
3. 3V3 sheet: draw one left-to-right power path (PACK_P with the bulk and input caps, buck, inductor, output cap,
   3V3) with notes below, instead of two boxes with a lonely circuit. Lifts Flow, Grouping, Space.
4. MCU: stagger the decoupling caps right at the VDDS pin and wire the pi network between RFIO and ANT_IN with
   a direct chain. Lifts Grouping and Wires vs labels.
5. USB BQ25756 hub: bring the mini-circuits next to the pins they serve and wire the ones that can be wired
   (VAC bulk, REGN/DRV_SUP, TS network already done); shrink the PD controller pull-ups next to U401 pins.
   Lifts Wires vs labels and Reviewability.

# Round 2: what was done and scores after

Done: (1) overlaps removed, lint now 0 findings on all sheets (auto-pitch not added; pitches widened by hand in
3V3 bulk, MCU decoupling, USB bulk rows, C406/C450, C403; Q104, J301 and U402 text moved). (2) 3V3 page fitted
(297 x 138) and boxes tightened. (3) 3V3 is now one path: PACK_P, six bulk caps, C206, buck, L201, C207, 3V3.
(4) MCU decoupling caps moved next to the VDDS corner, TP301 and the reset parts spaced, pi network gap fixed.
Not done: direct wiring of the BQ25756 mini-circuits and of the MCU pi network (shapes need U-turns around
adjacent pins, judged worse than labels); shrinking USB A/B boxes (needs moving every later section).

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 5 | 3 | 3 | 3 |
| 2 Grouping | 4 | 4 | 4 | 3 |
| 3 Wires vs labels | 4 | 3 | 3 | 2 |
| 4 Clutter | 4 | 4 | 4 | 4 |
| 5 Space | 4 | 3 | 3 | 3 |
| 6 Recognisable circuits | 4 | 3 | 3 | 4 |
| 7 Annotation | 4 | 4 | 4 | 4 |
| 8 Reviewability | 4 | 3 | 3 | 3 |
| Mean | 4.1 | 3.4 | 3.4 | 3.3 |

Next biggest gains: USB hub wiring (Wires vs labels 2), Cells gauge input lanes, MCU antenna pi in line.
