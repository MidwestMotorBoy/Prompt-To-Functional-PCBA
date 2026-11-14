# Round 2 self-review (before this round's changes)

Scores 0-5 per rubric criterion, strict reviewer. Renders read at 220 dpi.

| Sheet | Flow | Grouping | Wires vs labels | Clutter | Space | Recognisable | Annotation | Reviewability | Mean |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 3.9 |
| Cells and Gauge | 3 | 3 | 3 | 2 | 3 | 4 | 3 | 3 | 3.0 |
| MCU | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 3.8 |
| USB Port (1 and 2) | 4 | 4 | 3 | 3 | 3 | 4 | 4 | 3 | 3.5 |

Main faults seen:
- Cells: text collisions the lint does not catch (pad texts over the CELL labels, R119-R122 values touching the next row's
  reference, Q102 reference on its gate wire, J113 text on TP106, ground label touching the thermistor value, J117/J118 texts);
  long staircase wires from the gauge's left pins; TP109/J114 floating alone; Q101/Q102 are tiny boxes.
- USB: the EEPROM floats alone at the far right tied only by labels; long PPHV/PP5V tails; A2 paper with 20 % margin;
  crowded text in the Kelvin blocks; D401 text touching the body.
- 3V3: notes block far from the circuit, big empty area right of the buck.
- MCU: fine; pull-up rows are long.

## Five changes ranked by expected gain
1. Cells: remove every text collision (pads drawn hanging with text beside, 'U' text on the protector ladder, Q102 text,
   J113/TP106 spacing, ground labels clear of values, J118/J120 beside their pads).
2. Cells: put TP109/J114 on the RS101 ground wire, tighten the TS tower.
3. USB: give the EEPROM its own titled group close to the pull-ups; shorten PPHV/PP5V tails.
4. USB: space the Kelvin-block texts and D401 so nothing touches; keep lint at 0 and add a text-width check to the lint.
5. 3V3: move the notes next to the circuit; MCU: shorten pull-up rows.

## After round 2 (self-estimate, same strict reading)
| Sheet | Mean before | Mean after |
|---|---|---|
| 3V3 Rail | 3.9 | 4.1 |
| Cells and Gauge | 3.0 | 3.6 |
| MCU | 3.8 | 3.9 |
| USB Port (1 and 2) | 3.5 | 3.9 |

All five changes done. Still weak: Cells has long staircase wires from the gauge's left pins and a large empty lower right;
USB is A2 with wide margins; Q101/Q102 are flat boxes.
