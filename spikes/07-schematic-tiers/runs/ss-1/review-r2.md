# Round 2 review (harsh outside reviewer)

Scores 0-5, criteria in RUBRIC.md order: Flow, Grouping, Wires vs labels, Clutter, Space, Recognisable, Annotation, Reviewability.
"Before" = state at the start of round 2; "After" = after this round's changes.

| Sheet | Flow | Group | Wires | Clutter | Space | Recog | Annot | Review | Total /40 |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail (before) | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 | 30 |
| Cells and Gauge (before) | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 24 |
| MCU (before) | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 3 | 25 |
| USB ports (before) | 3 | 3 | 2 | 2 | 3 | 3 | 2 | 2 | 20 |
| USB ports (after) | 3 | 3.5 | 2.5 | 3 | 3 | 3 | 3 | 3 | 24 |

Main faults seen when every page was opened at zoom:
- USB: the BQ25756 section is a long fan of labelled wires; the 9 V LDO enable parts (Q409, R454, R455) and the 5 V enable
  pull-down and test point floated alone; TVS D401/D501 text sat on the CC labels; pull-up bank net names were cut by wires.
- Gauge sheet: the BQ40Z50 cell-filter lanes are the old drawing (long parallel wires, ICs far from their pull-ups).
- MCU: pull-ups are a bank tied by labels, not on their pin lines.
- 3V3: the long single row of input capacitors; nothing says that FB is strapped to ground for the fixed-output part.

Prioritised list (done = this round):
1. USB 9 V enable: draw Q409/R454/R455 as one pull-up and kill-switch group (done).
2. USB 5 V enable pull-down and ground test point drawn as a small tidy group (done).
3. USB-C section overlaps: TVS before the caps with its text above the rail, supply label clear (done).
4. Pull-up bank labels: stub so names are not cut by the wire (done).
5. Next, not done: BQ25756 hand layout with the programming resistors on lanes beside their pins, and a hand ladder for the gauge cell filters.
