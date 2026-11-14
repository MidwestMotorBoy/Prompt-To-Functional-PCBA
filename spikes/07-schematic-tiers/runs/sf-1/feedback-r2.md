# Reviewer feedback, round 2

Pages 2-5 were studied in zoomed crops. Page 6 was compared with page 5 only at a glance (same layout). Page 1 (root) was not reviewed.

## 1. Scores (0-5)

| Criterion | 3V3 Rail | Cells and Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 5 | 3 | 3 | 3 |
| 2 Grouping | 4 | 4 | 3 | 3 |
| 3 Wires vs labels | 5 | 3 | 3 | 4 |
| 4 Clutter | 4 | 3 | 4 | 3 |
| 5 Space | 3 | 3 | 3 | 2 |
| 6 Recognisable | 5 | 4 | 4 | 4 |
| 7 Annotation | 4 | 4 | 4 | 4 |
| 8 Reviewability | 4 | 4 | 3 | 3 |
| Mean | 4.25 | 3.50 | 3.38 | 3.25 |

Overall mean 3.59 (round 1: 3.34). The gain is on Cells and Gauge and the USB sheets; the 3V3 and MCU sheets are unchanged.

## 2. Status of the round-1 items

| # | Item | Status |
|---|---|---|
| 1 | Pin-label stubs and collision check | Partly. Stubs are done and work. The check exists but under-reports badly (see change 1). |
| 2 | Inline versus lanes on tight pin rows | Done. U101 and U401 are now readable. |
| 3 | RC ladders | Done. U101, U102 and the ACP/ACN filter read as ladders. Text collisions remain inside them. |
| 4 | Pads and lone leftovers | Partly. The pad grid is compact and clear. Pads still do not end wires; R432, TP412, TP301, Q409/R455 are still free-standing. |
| 5 | USB front end | Mostly done. The sketch is good. U401's ground pins are still a stack; U402 is still an island. |
| 6 | Page size and packing | Partly. Pages are smaller, but reading order is now broken and the USB sheet still has large holes. |
| 7 | Charger FB divider and sense lanes | Not done. |
| 8 | MCU duplicate label and pull-up order | Not done. |

## 3. Changes now, in priority order

**1. Make the collision check tell the truth, then clear its list.**
It reports 0 on the USB sheets and 1 on Cells, but these overlaps are plainly visible:
- Page 3: R104/R103/R102 ref and value on top of C101/C102/C103 ref; R119/R120/R121 on C112/C113/C114; R113 value on pin number 10 of U101; R124 ref on the U102 body corner; C118 text on its own body in the pack path.
- Page 5: R425 on C409's "(VAC)"; C415 on C414; R426 on C416; R417 and R435 text on their own bodies; R415 on TH401; D410 text on the diode; C458 value on D411's value and the DRV_SUP label; the pin-number stacks under U401 and U405.
- Page 4: R302 value on C304 ref.

Use these as test cases: the check is not finished until it lists every one of them. Likely causes: text width is underestimated (use about 1.15 mm per character at 1.27 mm text, and scale with size), field boxes are anchored at the wrong corner for right-justified or rotated fields, and field-versus-field between different symbols is not compared. Then fix the causes at the source:
- In a ladder, put the series resistor's ref and value above its row and the rung capacitor's text to the right of the capacitor.
- A part standing upright between two lanes (D410, R425, C414) needs its lane pitch widened to fit its text, or its text moved to the free side.
- Parts hung close together (R415/TH401, C458/D411) need `width_of` to use the real text width of ref and value.

**2. Restore reading order in the packer (pages 3 and 5-6).**
Random section order has put "Gauge interrupt" first on page 3 with the gauge itself bottom left, and on page 5 the 9 V supply is first while the USB connector, the input of the whole sheet, sits in the middle right. Flow is lost for a few percent of fill. Drop the random orders. Give each section a flow rank from the order the block declares it, and pack in that order: inputs and connectors top left, controller next, power stage and outputs to the right or below. Allow reordering only between sections of equal rank.

**3. Finish attaching the lone parts (pages 3, 4, 5-6).**
- Q409/R455: wire V9_EN to U406's EN pin, next to R454. It is now about 200 mm away under its own title text.
- U402 EEPROM: place it on the I2CC_SCL / I2CC_SDA lanes of U401, wired, with the pull-ups R402/R403 on the same two lines. R403 is now drawn differently from R402, which hides that they are a pair.
- R432: at U404's EN pin. TP412 and TP301: on a wire of their net.
- C439 has regressed: in round 1 it was drawn on U404's SS pin; it is now a detached "for U404.SS" cell with a label. Put it back on the pin.
- Pads: end the ladder inputs with J109-J111 and J116 instead of labels where the pad's net has exactly one drawn wire end.

**4. Shorten the lane runs (U101 left, U403 both sides).**
The lanes leave the IC, travel 50-80 mm of bare wire, and only then reach the parts. BAT/VCC/PBI on U101 climb well above the IC; PPHV, ICHG, ILIM and TS on U403 do the same. Start the first part directly after the fan-out columns, and put the net name on the wire between the fan-out and the part instead of reserving empty wire for it. Centre each lane group on its own pins so the vertical runs are short.

**5. Charger feedback divider and CE divider (round-1 item 7).**
R418/R419 are still at the far right on long FB/FBG runs; place tapped chains at the first free x of the lanes they tap, not at the global `xfar`. R417/R435 on CE_N sit at the far left edge with text on their bodies: bring them to the same x as the other left-side parts.

**6. Ground pin stacks.**
U401 and U204 show several ground pins at one spot with overprinted pin numbers and symbols. Join the pins with one short wire and draw one ground symbol, as the USB front-end sketch already does for U405. Do it generally in `draw_anchor` for any set of bottom pins on the same net.

**7. MCU sheet (round-1 item 8).**
Remove the duplicate 3V3 label on the VDDS wire. Put the pull-ups in the same order as the pins they serve, or draw them at the SCL/SDA/IRQ_N pins. This sheet was not touched this round.

**8. Fill after the above.**
Page 5 has holes below the PD controller and around the 5 V buck leftovers. Changes 3 and 4 remove most of the cause. Re-check the printed fill ratio afterwards; do not tune the packer before then.

## 4. Beliefs in NOTES.md to correct

- "Current result: 3V3 0, Cells 1, MCU 1, USB 0 each." This is not the state of the sheets. At least fifteen visible overlaps exist. A check that reports 0 here gives false comfort; treat it as unvalidated until it finds the list in change 1.
- "The check cannot be a gate because make.sh has `set -e`." It does not need to exit non-zero. Print the count and the pairs in the build output and treat a non-zero count as unfinished work.
- "Fill below 1.0 is partly unavoidable" is true, but the conclusion drawn (random section order for a better ratio) cost more in Flow than it gained in Space. Fill is a secondary measure; reading order comes first.
- "Remaining sketches are exact textbook arrangements": agreed, and the USB front-end sketch is a good use. Do not add sketches for the charger; its problems are general lane behaviour (changes 4 and 5).

## 5. Process

- After every `make.sh`, open all of page-2 to page-6 and zoom on every IC and every ladder at 2x or more. Pages 2 and 4 were not improved this round and page 4 still carries a known item.
- Check for regressions against the previous render, not only for the thing you changed: C439 moved off its pin without being noticed.
- After each build confirm NETLIST OK, read the collision list, and compare it with what you can see in the crops. If you can see an overlap the list does not have, fix the check first.
