# Self-review, round 4 (state at the start of round 4, strict reviewer)

Criteria: 1 Flow, 2 Grouping, 3 Wires vs labels, 4 Clutter, 5 Space, 6 Recognisable circuits, 7 Annotation, 8 Reviewability.

| Sheet | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| Cells and Gauge | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 |
| MCU | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 |
| USB ports | 3 | 3 | 3 | 3 | 2 (sparse left column, gaps between rows) | 4 | 3 | 3 |

## Five changes, in priority order
1. Pack sections with a skyline packer (each section goes to the lowest free spot) so small sections fill the gaps beside tall ones (USB, Cells space).
2. Loose decoupling cells below ICs: pull the leftover cells of an IC to sit directly beside/below it with less gap.
3. F102/Q104 as one circuit.
4. Long gauge lanes: shorter fan-out.
5. Annotation: short block notes under section titles.
