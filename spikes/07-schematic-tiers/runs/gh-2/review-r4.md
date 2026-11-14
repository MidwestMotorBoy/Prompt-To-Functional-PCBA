# Round 4 review (strict outside reviewer, before this round's changes)

`./make.sh` run first (NETLIST OK, lint 0). All six `out/render/page-*.png` opened and cropped with PIL.
Page sizes now: 3V3 210 x 190, Cells 475 x 265, MCU 305 x 205, USB 400 x 540 (mm).
Order: flow / grouping / wires vs labels / clutter / space / recognisable / annotation / reviewability.

| sheet | scores before round 4 | total /40 |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 5 / 3 / 4 / 4 / 4 | 32 |
| Cells and Gauge | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |
| MCU | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |
| USB Port 1 and 2 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |

(3V3 space is 3, not the 4 I gave before: the page is 190 mm tall for 100 mm of drawing.)

Why space is 3 everywhere
- 3V3: two frames stacked in the left half; the lower half and the right third of the page are empty. Cause: bulk bank under the buck, plus the rule that adds
  32 mm of height when any frame touches the title-block columns.
- MCU: module frame carries a wide three-line note at its bottom, which drags the page height (title-block rule) for no drawing.
- Cells: blank block bottom right under the protector.
- USB: 100 x 150 mm blank block right of the front group, blank right of the stage's middle, 5 V frame bottom drives page height.

## Five changes, in priority order
1. Page-size rule: size the page from the frames that really touch the title block, not from the whole drawing (fixes blank bottoms on 3V3, MCU, Cells).
2. 3V3: put the bulk bank beside the buck (one row), page becomes landscape and filled.
3. MCU: move the note into the empty lower-left of the module frame so the frame and page get shorter.
4. USB: fill the blank block right of the front group with a "sheet interface and power flow" box (nets that leave the sheet, what each does) and
   pull the 9 V / 5 V column up under the stage.
5. Cells: use the blank bottom right for the protector's note and shorten the path rail so the right column is not wider than needed.

## After round 4 (all six pages re-opened and cropped, make.sh NETLIST OK, lint 0 on all sheets)
Page sizes now: 3V3 330 x 150, Cells 460 x 235, MCU 295 x 180, USB 410 x 500 (mm).

| sheet | scores after round 4 | total /40 |
|---|---|---|
| 3V3 Rail | 4 / 4 / 4 / 5 / 4 / 4 / 4 / 4 | 33 |
| Cells and Gauge | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |
| MCU | 4 / 4 / 4 / 4 / 4 / 4 / 4 / 4 | 32 |
| USB Port 1 and 2 | 4 / 4 / 4 / 4 / 3 / 4 / 4 / 4 | 31 |

What was done (list items 1 to 5)
1. Done. Page height follows the frames that reach the title-block columns (18 mm margin otherwise, 43 mm for those).
2. Done. Bulk bank is its own group beside the buck, two rows of three caps, page is landscape and filled.
3. Done. MCU note moved to seven short lines in the lower-left of the module frame.
4. Done. New "Sheet interface" box in the blank top-right block of the USB sheets (nets that leave the sheet, power flow); stage, charger, 9 V and 5 V rows pulled up.
5. Partly. Cells path rail compressed (about 20 mm shorter); the protector note stays in its own frame, a blank block remains bottom right.

Bug found in the final check and fixed: C407 (PP5V decoupling) was drawn twice on each USB sheet (once at the PD controller, once at the 5 V buck output),
the same part in two places. It is now drawn once, at the controller; the buck keeps C441 to C443. Netlist unchanged.

Still imperfect: Cells blank bottom right; USB is a tall page (410 x 500); two NTC return pads keep CELL_1N labels; pin numbers crowd the small AO3400 FETs;
all layouts are hand coordinates.
