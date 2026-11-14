# Round 4 self-review (before any round-4 change)

All pages opened and zoomed. Order: flow, grouping, wires vs labels, clutter, space, recognisable circuits, annotation, reviewability.

| sheet | flow | group | wires/labels | clutter | space | circuits | annot | review | evidence |
|---|---|---|---|---|---|---|---|---|---|
| Root | 3 | 3 | n/a | 4 | 3 | n/a | 3 | 3 | five boxes in a 3x2 grid in creation order, not power-flow order; no hint of who talks to whom except one paragraph |
| 3V3 Rail 280x150 | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | lower-left of the page empty (title block eats the corner); buck frame wider than its circuit |
| Cells and Gauge 440x310 | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | TS rows spaced for the worst case, gauge frame blank lower right; CELL_x taps to the protector are labels |
| MCU 300x200 | 4 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | connector frame half empty |
| USB Port 480x390 | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | PD frame blank under connector; charger to power stage by labels |

Prioritised changes:
1. Compact the gauge pin gaps (TS2 to PTC) so the Cells frames shrink (Space, Cells). Done.
2. Shorten the 3V3 rail leads so the buck frame follows its circuit (Space, 3V3). Done.
3. Root sheet in power-flow order (USB ports left, pack path middle, 3V3 and MCU right) with the nets named between boxes
   (Flow, Grouping, Annotation, root). Done.
4. USB: compact stretched pitches of U401/U403 and wire charger to power stage (Space, Wires vs labels). Not done: the
   stretches are what give the CC capacitors and sense networks room, and wires would add about 250 mm of width.
5. Cells: wire the CELL_x taps to the protector rather than label them. Not done: they sit in separate frames 150 mm apart.

## After round 4

| sheet | flow | group | wires/labels | clutter | space | circuits | annot | review | paper |
|---|---|---|---|---|---|---|---|---|---|
| Root | 4 | 4 | n/a | 4 | 3 | n/a | 4 | 4 | A4 |
| 3V3 Rail | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 280x150 -> 270x150 |
| Cells and Gauge | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 440x310 -> 440x290 |
| MCU | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 300x200 |
| USB Port | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 480x390 |

Still imperfect: items 4 and 5 above; the root sheet has no sheet pins (cross-sheet nets are global labels, so arrows are plain text).
