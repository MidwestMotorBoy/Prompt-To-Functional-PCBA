# Self review, start of round 3

| criterion | 3V3 | Cells+Gauge | MCU | USB 1+2 |
|---|---|---|---|---|
| Flow | 4 | 3 | 3 | 3 |
| Grouping | 3 | 3 | 3 | 3 |
| Wires vs labels | 4 | 2 | 3 | 3 |
| Clutter | 3 | 2 | 3 | 2 |
| Space | 3 | 3 | 2 | 3 |
| Recognisable | 4 | 2 | 4 (pi) | 3 |
| Annotation | 3 | 3 | 3 | 3 |
| Reviewability | 3 | 2 | 3 | 3 |

## Five changes
1. Single-pin terminals (J, TP) leave the IC zones and form one row in their section (done this round), spacing counts text (done).
2. Overlapping pin labels at U101 left (VCC/PBI vs R105 text) and R-value text on wires.
3. Gauge cell-tap filters (R+C per VC pin) drawn as a tidy column with fewer crossings.
4. Pull-ups on MCU drawn as one bus under a 3V3 rail with the signal lines running to U301 (already partly), tighten column spacing.
5. Fuse ignition circuit as a series template (F102 - Q104 - gate divider) instead of side-by-side blocks.
