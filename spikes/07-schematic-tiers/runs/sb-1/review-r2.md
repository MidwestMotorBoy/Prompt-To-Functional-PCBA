# Self-review, round 2 (strict reviewer, state at the start of round 2)

Criteria: 1 Flow, 2 Grouping, 3 Wires vs labels, 4 Clutter, 5 Space, 6 Recognisable circuits, 7 Annotation, 8 Reviewability.

| Sheet | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 1 (content in a strip, page empty) | 4 | 3 | 4 |
| Cells and Gauge | 2 | 2 | 2 (long fan-out lanes, labels only on FETs) | 3 | 2 (tall, empty areas, F102/Q104 far down) | 2 (back-to-back FETs not drawn as a pair, fuse circuit scattered) | 3 | 2 |
| MCU | 3 | 2 (VDDS caps off on a bus, pi network split in two cells) | 3 | 4 | 2 | 2 (no pi filter) | 3 | 3 |
| USB Port 1/2 | 3 | 3 (loose "for U405.VBIAS" decoupling cells, EN pull-down, SS cap) | 3 | 3 | 3 | 4 (buck, four-switch stage good) | 3 | 3 |

## Five changes, in priority order
1. Pi/RC filter drawn in line (new `ladder()` hint). Done for the MCU antenna match.
2. Pull-ups and decoupling attach to the most specific pin net (fewest pins), so pull-ups sit on their signal pin and VDDS caps on VDDS. Done.
3. Small blocks centred on the sheet (3V3 Rail). Done.
4. Loose decoupling cells for top/bottom pins (U405 VBIAS, U401 LDO, U404 SS): draw them at the pin. Not done: needs top/bottom pin lanes.
5. Protection FET pair and fuse-ignition circuit as templates (ladder-like path with FET symbols). Not done.
