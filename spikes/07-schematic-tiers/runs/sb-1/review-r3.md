# Self-review, round 3 (state at the start of round 3, strict reviewer)

Criteria: 1 Flow, 2 Grouping, 3 Wires vs labels, 4 Clutter, 5 Space, 6 Recognisable circuits, 7 Annotation, 8 Reviewability.

| Sheet | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| Cells and Gauge | 3 | 3 | 3 | 3 | 2 | 2 | 2 (auto names Net-(U101-VC3) everywhere) | 3 |
| MCU | 4 | 3 | 4 | 4 | 3 | 4 | 3 | 3 |
| USB ports | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 |

Main faults seen: back-to-back FETs not a pair and F102/Q104 far apart (Cells); lone D101 and long fan-out lanes (Cells);
auto-generated net names (Net-(...)) in labels; loose decoupling cells for top/bottom pins (USB); large empty areas on the tall sheets.

## Five changes, in priority order
1. Back-to-back FET template (`fetpair`): Q101 | FET_MID | Q102, gate dividers beside each gate, rails out left and right.
2. Readable names for the auto-named nets (BAT_FEED, GAUGE_VC1.., PROT_V1.., FUSE_HTR ...). Names only.
3. Fuse and ignition FET in one section (F102 above Q104) so the heater net is a short connection.
4. Series chains on lanes (D101 + R105 in line) so no lone part, and tighter lane pitch to shorten gauge lanes.
5. Loose decoupling cells for top/bottom pins: draw them beside their IC rather than far below (if time).
