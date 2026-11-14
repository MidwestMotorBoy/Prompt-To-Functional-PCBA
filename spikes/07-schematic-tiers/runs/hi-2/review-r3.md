# Round 3: self-review

Method: ./make.sh, then every out/render/page-*.png opened and cropped (3V3, Cells in three crops, MCU in two,
USB in six). Lint (design/lint.py) was at 0 findings at the start.

## Scores at the start of round 3 (0-5)

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

## Five changes ranked

1. USB hub: wire what can be wired instead of stub plus label (bootstraps, input Kelvin filter). DONE, see below.
2. Cells gauge input lanes (BAT, VCC, PBI run 45 to 60 mm up and across). Judged: lanes cannot be shortened without
   moving the cell RC rows, rows are already nested without crossings. NOT changed.
3. MCU antenna network: tied to RFIO and ANT_IN by labels. A direct chain needs a U-turn between two pins 2.54 mm
   apart and a ground symbol pointing up. NOT changed (labels are the cleaner drawing).
4. Cells right column: TS box half empty. NOT done (needs moving the protector box).
5. USB A/B boxes 20 percent empty. NOT done.

## Done in round 3
- BQ25756: VAC, ACP, ACN now rise on their own lanes (nearest lane first, so nothing crosses) to the PPHV rail and
  the filter: R425, C414, C415, C416, R426 are wired to the pins with only AC_SNS_N and PPHV as labels.
- Bootstraps: BTST1/SW1 and BTST2/SW2 rise on lanes to C412/C413 and D404/D405 above the hub. Only DRV_SUP and
  SW1/SW2 are labels (they go to other sections). 6 label stubs fewer on the hub.
- Scene.two() takes explicit text positions; USB battery-sense filter and feedback divider re-spaced.
- Lint 0 findings, NETLIST OK.

## Scores after round 3 (estimate)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 5 | 3 | 3 | 3 |
| 2 Grouping | 4 | 4 | 4 | 4 |
| 3 Wires vs labels | 4 | 3 | 3 | 3 |
| 4 Clutter | 4 | 4 | 4 | 4 |
| 5 Space | 4 | 3 | 3 | 3 |
| 6 Recognisable circuits | 4 | 3 | 3 | 4 |
| 7 Annotation | 4 | 4 | 4 | 4 |
| 8 Reviewability | 4 | 3 | 3 | 4 |
| Mean | 4.1 | 3.4 | 3.4 | 3.6 |
