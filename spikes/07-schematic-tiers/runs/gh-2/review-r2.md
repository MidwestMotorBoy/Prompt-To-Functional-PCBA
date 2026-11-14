# Round 2 review (strict outside reviewer, before this round's changes)

Method: `./make.sh` (NETLIST OK), every `out/render/page-*.png` opened, cropped and zoomed (1.0 to 1.7x) with PIL.
Page 1 (root sheet, six boxes) is not part of the rubric and unchanged.

Order: flow / grouping / wires vs labels / clutter / space / recognisable / annotation / reviewability.

| sheet | scores before round 2 | total /40 |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 4 / 3 / 4 / 3 / 4 | 30 |
| Cells and Gauge | 4 / 4 / 3 / 3 / 3 / 4 / 3 / 3 | 27 |
| MCU | 4 / 4 / 4 / 3 / 2 / 4 / 3 / 4 | 28 |
| USB Port 1 and 2 | 4 / 4 / 3 / 3 / 3 / 4 / 3 / 3 | 27 |

## Why these scores
- 3V3: textbook buck, nothing overlaps. The notes are 1.0 mm text and unreadable at normal zoom, the right third of the page is empty,
  and the buck frame is wide with a blank lower half.
- Cells: ladders, shunt between the sense lanes, back-to-back FETs read well. Costs: many CELL_1N labels where a short wire or a
  shared ground rail would do (J118, J120 returns, PTCEN/PTC, VSS, DISP), text touching symbols (C105 value against the PTCEN label,
  thermistor value against its symbol, R117/CELL_1N), a lot of white space under the gauge and to the right, no notes in any group.
- MCU: RF pi match text collides with its own wires (R321 value, C313 value), NC flags sit on pin numbers 17 and 18, the module frame is
  half empty at the bottom, the header frame is far to the right, notes unreadable.
- USB: the stage, charger, divider and filter ladders are good. Costs: 405 x 530 mm page with empty areas (right of the front group,
  stage frame middle), SiZ240DT pin names run together ("SWG2"), C_CC1/C_CC2 labels crowd the RPD_G labels, no notes on the front end,
  the 9 V and 5 V groups, tiny 1.0 mm notes, some pin numbers crowding on the small FETs.

## The five changes that raise the lowest scores most
1. Annotation on every sheet: notes at 1.27 mm (readable) and a note in every group that says what the block does and what to check
   (cell ladder, protector, power path, RF match, reset, front end, stage, charger, 9 V, 5 V, buck). Raises annotation and reviewability on all sheets.
2. MCU space and clutter: pull the header frame in, move the notes up, redraw the RF match so no text sits on a wire, give the NC pins room
   so the flags are clear of the pin numbers.
3. USB clutter: widen the SiZ240DT symbol body (drawing only) so the pin names stay apart; give the CC labels their own clean place;
   use the empty middle of the stage frame for the hot-loop note.
4. Cells wires vs labels and clutter: fix the text collisions (C105, thermistors), draw the NTC return and PTC ties as short wires to a
   shared CELL_1N rail instead of one label per pin where they sit together.
5. Space: tighten the 3V3 frame and the MCU frame to their content, balance the 3V3 page (bulk bank beside the buck instead of below, if it fits).

# After round 2 changes (same strict grading, all pages re-opened and cropped after the rebuild)

| sheet | before | after |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 4 / 3 / 4 / 3 / 4 = 30 | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 = 33 |
| Cells and Gauge | 4 / 4 / 3 / 3 / 3 / 4 / 3 / 3 = 27 | 4 / 4 / 3 / 4 / 3 / 4 / 4 / 4 = 30 |
| MCU | 4 / 4 / 4 / 3 / 2 / 4 / 3 / 4 = 28 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 |
| USB Port 1 and 2 | 4 / 4 / 3 / 3 / 3 / 4 / 3 / 3 = 27 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 = 31 |

What was done against the five items
1. Annotation: notes are now 1.27 mm (they were 1.0 and unreadable; a note line pitch bug that made lines overlap was fixed too) and every
   group has one: cell sense, power path, protector, 3V3 buck, bulk bank, MCU reset/RF/pull-ups, USB front end, EEPROM, four-switch stage,
   hot loops, charger programming (with the designed values), 9 V supply, 5 V buck.
2. MCU: supply rail shortened (5 columns, 15 mm pitch), module moved left, header frame pulled in (page 345 to about 305 mm wide),
   DIO20/DIO12 NC pins spread to 7.6 mm so the flags are clear of the pin numbers, RF match lanes widened, notes moved up.
3. USB: SiZ240DT redrawn wider (`symlib.widen`, drawing only) so pin names no longer run together; TPD6S300 NC pins spread; the FLT line is
   now one straight wire from U405 to GPIO3 of the PD controller (two overlapping SBU_FLT labels removed); cap pitch widened so values
   do not hit the next cap; stage middle used for the hot-loop note.
4. Cells: R117 value no longer touches its label, notes added, frames no longer collide.
5. 3V3: group moved up and tightened, bulk bank explained.

Not done (judged not worth the risk, or no good idea found)
- A tighter USB arrangement (splitting the front end into connector and PD groups to fit the 9 V group under the connector). It would only
  move the blank area, not remove it. USB space stays at 3.
- One shared CELL_1N bar for the NTC return pads on Cells (the TS2/TS3 pad rows alternate, so a bar would cross a lane). Wires vs labels stays 3 there.
