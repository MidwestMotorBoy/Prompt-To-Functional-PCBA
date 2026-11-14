# Round 3 self-review (before any round-3 change)

Scored as a harsh outside reviewer from the renders at the start of round 3 (pages 2 to 6 opened and zoomed).
Order: flow, grouping, wires vs labels, clutter, space, recognisable circuits, annotation, reviewability.

| sheet | flow | group | wires/labels | clutter | space | circuits | annot | review | evidence for the weak scores |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail (280x160) | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 | both frames forced to one bottom edge: the bulk-cap frame is half empty; page is 280 wide for 10 parts; notes are plain restatements |
| Cells and Gauge (460x310) | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | gauge frame runs the full page height with an empty lower-right half; right column frames have ragged widths and dead pockets; CELL_x and FET_MID are label-only links between frames |
| MCU (300x220) | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 4 | the connector frame is stretched to the module frame bottom and is mostly empty; 220 mm tall page for two frames |
| USB Port 1 / 2 (490x410) | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | EEPROM drags the PD frame 60 mm taller (blank lower-left); the group chain is hand placed so pockets are left beside the buck and under the title block; charger to power stage links are all labels (PPHV, SW1, HG1, LG1...) |

Prioritised changes (what moves the lowest scores most):

1. Automatic frame packer (Lay.pack): measure each group on a scratch sheet, search page width and layout, fill pockets, make
   stacked frames flush, keep the title block clear, set the paper from the result. Space on every sheet. (done in round 3)
2. Stop forcing equal frame heights (3V3, MCU) so a frame follows its content. Space. (done with 1)
3. Split the configuration EEPROM out of the PD frame into its own small frame the packer can drop in a pocket. Space and
   grouping on the USB sheets. (done)
4. Wire instead of label the charger to power stage hand-off. Wires vs labels on USB. Costs about 250 mm of page width, so
   it only pays if the packer can hide it; decide after 1 to 3.
5. Annotation on 3V3 and MCU: say what each frame does for the rest of the board and name the nets that leave the sheet.

## After round 3 (same order)

| sheet | flow | group | wires/labels | clutter | space | circuits | annot | review | paper before -> after |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 280x160 -> 280x150 |
| Cells and Gauge | 3 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 460x310 -> 440x310 |
| MCU | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 300x220 -> 300x200 |
| USB Port 1 / 2 | 3 | 4 | 3 | 4 | 4 | 4 | 4 | 4 | 490x410 -> 480x390 (20.1 -> 18.7 m2) |

Still imperfect: gauge frame has an empty lower-right half; PD frame has blank space under the connector; charger to
power stage hand-off is by labels only; the packer cannot beat about 14 m2 of frame area on the USB sheets, so only
shrinking the frames themselves would raise Space further.
