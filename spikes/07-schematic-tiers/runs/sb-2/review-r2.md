# Round 2 self-review (scores BEFORE the round-2 changes, harsh reviewer)

| Sheet | flow | group | wires/labels | clutter | space | circuits | annot | overall |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 |
| Cells and Gauge | 3 | 3 | 3 | 3 | 2 | 4 | 4 | 3 |
| MCU | 4 | 4 | 4 | 3 | 3 | 3 | 4 | 3.5 |
| USB Port 1 | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 2.5 |
| USB Port 2 | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 2.5 |
| Root (page 1) | - | - | - | 5 | 2 | - | 2 | 2 (empty sheet boxes, no pins) |

## Prioritised changes
1. Text-justification bug: rotated (180) parts had their ref/value drawn over the body (R305, R314, TP113...). Fixed in page.py.
2. Charger section collisions (R409 vs C409 note, R412-414 stacked texts, sense filters vs TS ladder, bootstrap floating far right). Fixed by spacing.
3. PD / 9 V / 5 V collisions (C405 over LDO label, R401 text, EEPROM cap over SDA label, PACK_P label on frame, EN_5V1 over C446, sections touching). Fixed.
4. Explicit no-connects for all NC pins (tag_all) - U406/U506 pins 6,7. Fixed.
5. NOT DONE: four-switch stage still generic (sparse, wide); unused whitespace on Cells (NTC pad rows, lower left) and USB sheets (tall page, empty bands); R123/C116 text overlap on protector; root sheet has empty boxes.
