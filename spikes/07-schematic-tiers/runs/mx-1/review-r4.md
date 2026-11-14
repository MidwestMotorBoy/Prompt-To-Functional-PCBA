# Round 4 (short): one item from the round-3 "next in line" list

No new full re-grade. State before: snap25 (scores of `review-r3.md`: 3V3 4.25, Cells and Gauge 4.06, MCU 4.31, USB 4.06).

## Done

* **F102 tied to Q104 with a wire (Cells and Gauge: Wires vs labels, Grouping).** The fuse and the FET that heats it were two separate
  items joined by two FUSE_HTR labels 50 mm apart. `draw_near` pairs are now merged into one item when the pair's only common net runs from a
  bottom pin of the first to a top pin of the second (`link_item` in `layout.py`): the first part stands above the second, its stub and the
  stub of the other part meet in one wire (about 12 mm from the heater pin to the drain), and no label is drawn at either end
  (`link_nets`, `stubs`, `end_v`). Nothing else in the design has such a pair, so only the gauge sheet changed; the other four sheets are
  byte-identical to the build I checked in round 3.
  The packer re-ordered the gauge page for the new item: protection FETs on top of the middle column, then the second-level protector with the fuse
  and its FET, then the wire pads; 411x242 (was 420x226), wire length 879 mm, 2 segments over 50 mm, unchanged.

## Not done (still the list for anyone continuing)

* Two frame widths per section for the packer (Space is still the weakest criterion, 3.5 on every sheet).
* A compact stair for the I2C pull-ups of the PD controller (the I2Cc_IRQ lane is 57 mm).

## Checks

`./make.sh`: NETLIST OK (285 parts, 168 nets, 0 differences); generator lint 0 on all sheets; tight lint 3 benign findings on the gauge and on each
USB page (as before); PDF lint no text on text; `PYTHONHASHSEED` 1 and 777 give byte-identical sheets; the gauge page was opened and
read after the final build. Expected effect on the scores: Cells and Gauge Wires vs labels 4 to 4.5 and Grouping 4 to 4.5 (mean about 4.2); the
rest unchanged.
