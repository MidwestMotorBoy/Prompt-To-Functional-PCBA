# Reviewer feedback, round 3

Pages 2-5 were studied in zoomed crops. Page 6 was checked only by a text-overlap script (same result as page 5). Page 1 (root) was not reviewed.

## 1. Scores (0-5)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 5 | 4 | 3 | 4 |
| 2 Grouping | 4 | 4 | 3 | 3 |
| 3 Wires vs labels | 5 | 3 | 3 | 4 |
| 4 Clutter | 4 | 4 | 4 | 3 |
| 5 Space | 3 | 3 | 3 | 2 |
| 6 Recognisable | 5 | 4 | 4 | 4 |
| 7 Annotation | 4 | 4 | 4 | 4 |
| 8 Reviewability | 4 | 4 | 3 | 3 |
| Mean | 4.25 | 3.75 | 3.38 | 3.38 |

Overall mean 3.69 (round 2: 3.59, round 1: 3.34). This round's gain is small: reading order is back and the ladder text is clean, but most of the round-2 list is still open.

## 2. Status of the round-2 items

| # | Item | Status |
|---|---|---|
| 1 | Collision check that tells the truth | Not done. It reports 0 on every sheet while overlaps are visible. The ladder text and the C409/R425, C415/C414 cases were fixed by hand. |
| 2 | Reading order in the packer | Done. Connector first on the USB sheet, gauge first on Cells. |
| 3 | Attach lone parts (Q409/R455, U402, R432, C439, TP412, TP301, pads) | Not done. |
| 4 | Shorten lane runs | Not done. |
| 5 | Charger FB divider and CE divider | Not done. |
| 6 | Ground pin stacks (U401, U204) | Not done. |
| 7 | MCU sheet | Partly. The duplicate 3V3 label is gone. Pull-up order and TP301 are unchanged. |
| 8 | Fill | Worse, as expected after restoring order: 0.45 / 0.46 / 0.52 / 0.54. Page 5 has grown taller. |

## 3. Changes now, in priority order

**1. Replace the estimated collision check with a measured one.**
The estimate in `Sheet.collisions` models where you meant the text to go, not where KiCad draws it. Example: R417 and R435 on page 5 are drawn right-justified over their own bodies, while `_record_symbol` records them left-justified beside the body. KiCad flips field justification for rotated symbols; your model does not.

The rendered PDF contains real text with positions, so measure instead of estimating. This works today:

```
pdftotext -f 5 -l 5 -bbox out/render/sheets.pdf -
```

It returns every word with `xMin yMin xMax yMax` in points (1 pt = 0.3528 mm; the page origin is top left, same as the sheet). Write a small script under `design/` (not in `make.sh` or `tools/`) and run it after `make.sh`:
- Text against text: shrink each box by about 2.5 pt top and bottom (the line box is taller than the glyphs) and report overlapping pairs. My quick version of this found, on page 5: C410's value under D410's value, and two pin-number stacks (U401 bottom pins, U405 bottom pins). Page 3: R113 on the SRN label, and F102's pin number on FUSE_HTR. Page 4: RESET on VCC inside J301. Page 2: the U204 bottom pin names run into each other.
- Merged words: two texts that touch are returned as one word, for example "25VLRB520S-40T1G" (C458 value and D411 value). Report any word that is not a string you placed.
- Text against symbol body and against wires: keep your own body and wire boxes, but take the text boxes from the PDF.

Still visible and to be found by the new check before you call it working: R417/R435 on their bodies, R415 on TH401, D410 and D411 text on the diode, C458/D411/DRV_SUP, R302 value on C304 ref (page 4), R124 on the U102 corner, C118 on its own body.

Then fix causes, not instances:
- Set field justification explicitly in `symbol()` for every rotation so the drawn side is the side you asked for, and verify with the PDF boxes.
- An upright part between two lanes needs clear space on one side; put its text there and reserve the width in the lane layout.
- `width_of` must reserve the real width of the longest of ref and value for hung parts.

**2. Attach the lone parts.** Unchanged from round 2 and now the main Grouping loss.
- Q409/R455 onto U406's EN pin beside R454. The net V9_EN already has a wire end there.
- U402 on the I2CC_SCL / I2CC_SDA lanes of U401, with R402/R403 drawn the same way as each other.
- R432 at U404's EN pin; C439 back on the SS pin (it was there in round 1).
- TP412, TP301 and the cell pads at the end of a drawn wire of their net.
General rule to implement once: after the anchors are drawn, for each leftover cell find a drawn wire end or label position on one of its nets in the same section, and draw the cell there instead of in its own slot.

**3. Shorten lane runs and bring chains in.**
- U101 left and U403 both sides still have 50-80 mm of bare wire between fan-out and parts. Start parts right after the fan-out columns and put the net name on that short wire.
- R418/R419 belong directly after the SRP/SRN filter x, not at the far right.
- R417/R435 on CE_N belong at the x of the ACUV/ACOV divider, not at the sheet edge.

**4. Ground pin stacks.** U401 and U204 (and the pin-number stacks the PDF check reports under U405). Join same-net bottom pins with one wire and one ground symbol in `draw_anchor`. If several pins sit at one point in the symbol, draw one stub for the group.

**5. MCU pull-ups.** Order R304/R305/R314 as the pins they serve, or draw them at the pins. Small change, and this sheet has been static for three rounds.

**6. Fill, last.** Items 2 and 3 shrink the charger and remove the leftover slots under the PD controller and the 5 V buck. Re-measure after them. Then consider letting a short section share a row with a tall one (the 9 V supply and 5 V buck beside the power stage already do this well).

## 4. Beliefs in NOTES.md to correct

- "Current counts: 3V3 0, Cells 0, MCU 0, USB 0/0." You already note this is not proof. Go further: the estimate has now been tuned twice and still misses most cases, so stop tuning constants. The PDF gives exact boxes.
- "Lone parts need attaching; no code for this yet." This was item 3 last round and item 4 the round before. It is not blocked by anything; it is the next thing to build after the check.
- "MCU duplicate 3V3 label is gone": confirmed correct.
- Round-2 notes sections ("Not done / next") are now stale next to the round-3 section. Rewrite NOTES.md as one current state so the final reader is not misled.

## 5. Process

- After every `make.sh`, open all of page-2 to page-6 and zoom on each IC at 2x or more.
- Run the PDF text check on all pages each time and paste its count into NOTES.md next to what you see in the crops. If the two disagree, the check is wrong.
- Compare with the previous render for regressions before moving on.
- Work the list in order. This round fixed two instances by hand and left the general items; one general item finished is worth more than several instances.
