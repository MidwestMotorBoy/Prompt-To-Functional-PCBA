# Round 3 review (strict outside reviewer, before this round's changes)

`./make.sh` run first (NETLIST OK); every `out/render/page-*.png` opened and cropped with PIL at 1.0 to 1.6x.
Order: flow / grouping / wires vs labels / clutter / space / recognisable / annotation / reviewability.

| sheet | scores before round 3 | total /40 |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 | 33 |
| Cells and Gauge | 4 / 4 / 3 / 3 / 3 / 4 / 4 / 4 | 29 |
| MCU | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |
| USB Port 1 and 2 | 4 / 4 / 4 / 3 / 3 / 4 / 4 / 4 | 30 |

(Cells clutter is 3 now, not the 4 I gave last round: the R117 CELL_1N label sits against the PRES/DISP label and the pin numbers.)

Findings
- USB: C_CC1/C_CC2 are carried by four labels that crowd each other and the RPD_G labels; page about 405 x 550 mm, blank block right
  of the front group, 43 mm gap between charger and the 9 V/5 V column, a programming note hanging far below the charger; small FET pin numbers.
- Cells: 11 CELL_1N labels where the nets sit next to each other (C105/PTCEN, TH104/PTC, PRES/DISP/VSS/R117).
- MCU: the 30 mm stubs to the labels on the right make the frame wider than it needs to be; header frame leaves blank space.
- 3V3: fine. Remaining: page larger than the content (bottom blank).

## Five changes, in priority order
1. USB: wire RPD_G1/RPD_G2 straight to the CC lines (reorder the TPD6S300 pins so they sit just outside the CC pair) and drop the four C_CC labels.
2. USB size: move the 9 V and 5 V groups left to the charger, narrow the cap pitch of the input bank, move the programming note beside the TS network.
3. Cells: one CELL_1N bus on the right (R117, PRES/DISP, VSS) with a single label; join C105/PTCEN and TH104/PTC with wires.
4. MCU: shorter label stubs, tighter module frame.
5. Cells/3V3 page sizes: shrink the blank margins (minimum page height) so the page matches its content.

# After round 3 changes (all pages re-opened and cropped after the final rebuild; NETLIST OK, lint 0)

| sheet | before | after |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 = 33 | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 = 33 |
| Cells and Gauge | 4 / 4 / 3 / 3 / 3 / 4 / 4 / 4 = 29 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 |
| MCU | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 |
| USB Port 1 and 2 | 4 / 4 / 4 / 3 / 3 / 4 / 4 / 4 = 30 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 |

Done
1. USB: TPD6S300 pins reordered (drawing only) so RPD_G1/RPD_G2 sit just outside the CC pair and join their CC lines by wire. The four C_CC labels are gone.
2. USB size: 9 V and 5 V groups moved 22 mm toward the charger, input/output cap pitch 15.24 to 13.97, programming note moved beside the TS network and shortened.
   Page about 405 x 550 mm to about 395 x 550 mm; the blank block right of the front group remains (an honest 3 for space).
3. Cells: CELL_1N labels 11 to 7. One bus on the right (R117, PRES/SHUTDN + DISP, VSS), C105/PTCEN and TH104/PTC joined by wire.
   The two NTC return pads keep their labels (a bus would cross the TS3 lane).
4. MCU: label stubs on the right 30 to 20 mm, header frame pulled in; page 345 to 305 mm wide at round 2, now about 295 mm.
5. Page-size minimums left alone: 3V3 and MCU pages show blank space at the bottom because of the 140 mm minimum height; not worth the risk.

Still imperfect: USB page size and the blank block right of the front group; two NTC return labels on Cells; pin numbers on the small AO3400 FETs; hand coordinates.
