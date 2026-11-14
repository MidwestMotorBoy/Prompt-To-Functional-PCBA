# Review round 3 (pages 2-6 as rendered now)

## 1. Scores (0-5)

| Criterion | 3V3 Rail | Cells+Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4 | 3 | 3 | 3 |
| 2 Grouping | 4 | 3 | 3 | 2 |
| 3 Wires vs labels | 4 | 4 | 3 | 3 |
| 4 Clutter | 4 | 2 | 4 | 2 |
| 5 Space | 3 | 2 | 2 | 2 |
| 6 Recognisable | 4 | 4 | 4 | 3 |
| 7 Annotation | 3 | 3 | 3 | 3 |
| 8 Reviewability | 4 | 3 | 3 | 3 |

Average 3.1 (round 2: 3.0, round 1: 2.6). The ladder is a clear gain (both cell-tap filters now read like the
datasheet). The gain is small because the two things that cap every sheet, text collisions and floating parts, are
still there, and the USB sheet has not changed in three rounds.

## 2. Status of round-2 items

1. Collisions: checker written, but it under-reports and the collisions are not fixed (see below). Partly done.
2. Floating parts: not done (third round open). 3. Ladder: done. 4. Straight protection path: not done.
5. Sideways shunts on USB: not done. 6. Page balance: partly (packing changed, pages still half empty).
7. Unique aliases: done.

## 3. Remaining changes, in priority order

**1. The overlap checker is wrong; fix it, then fix what it finds.** NOTES says "2-5 collisions" on Cells and USB. I
count at least 12 on Cells U101 alone by eye, all text against text, which the checker claims to cover:
- `C105` ref on top of R105's value "100"; C105 value under the cap touching `CELL_1N` label of pin 24.
- `TH101` ref and "10k B3435" on top of the `PACK_P` global label and R113's value "10k"; TH104 ref on its own body.
- `R116` ref on top of the `SCL` global label; R116 value "100" under R115's row on the BTP_INT wire; R115 ref/value
  on `GAUGE_FUSE`.
- Protection: `R111` on Q102's value; R112 value on D103; C118 value on R125; `WAKE` label on TP113's text; Q104
  ref/value on its own symbol.
- Terminals: J120 "TS3 NTC return wire" runs through J116's `CELL_4P` label and text.
- USB U403: `R446` on the `LODRV1` label; `R445` on `HG2` and on R446's value; U401/U405 bottom pin numbers.
So debug the checker before anything else: print the box of each of the pairs above and see why they are not
reported. Likely causes: global labels not registered (they are wider: text + 2 x 1.5 mm frame); boxes built from the
anchor without the justification (right-justified text extends left of its anchor; rotated text extends in y);
height too small (use 2.0 mm for 1.27 mm text); ref and value registered only for some code paths (`small`, `horiz`,
template code calling `sheet.symbol` directly). Register boxes inside `Sheet.symbol`, `Sheet.label` and `Sheet.text`
themselves so no path can skip it. Also add symbol bodies (pin bounding box) and wires (as thin boxes) now: it is the
same list. Target: the checker reports every pair listed above, then goes to zero.

**2. Give inline parts room: one rule in `draw_anchor`.** The root cause on U101 and U403 is 2.54 mm pin pitch with a
part plus two text lines on adjacent rows. Rule: if the rows directly above and below an inline part are occupied (a
label, a wire or another inline part), do not draw it inline. Fan the pin out to a lane instead (the mechanism `lanes()`
already has, P_LANE spacing) and put the part there with normal text. For U101's left face that means BAT (D101 + R105),
PBI (C105), PACK (R113), TS1 (TH101), TS4 (TH104) become lanes below the ladder; for U101's right face SMBC/SMBD/
BTP_INT (R115, R116, R117); for U403 HIDRV1/LODRV1/HIDRV2/LODRV2 (R444-R447) and FSW/ICHG/ILIM (R412-R414, whose
ground symbols now sit on the neighbouring pin wires). This single rule also removes the sideways-shunt cases
(C401/C402, C405, C439), since a lane ends in a hung part with a downward ground.

**3. Floating parts: do the cheap half now.** You keep deferring this because "attach_plan must accept top/bottom
pins". Split it:
- (a) Series chains through an auto-named net need no new code path: `D101_K` exists only between D101 and R105, so
  D101 belongs in the BAT row as `CELL_4P -> D101 -> R105 -> BAT`. Generalise: when the far net of an inline or lane
  part has exactly one other two-pad part on it, draw that part in series and drop the label.
- (b) Single-pin parts (J1xx, TPxxx): in `attach_plan` you return them in `rest` at `npads == 1`. Instead keep a
  dict `net -> (x, y, direction)` of every label end point drawn (`end_label`, lane ends, template terminals), and
  after a section is drawn, place each single-pin part of that net at the recorded point in place of, or next to,
  the label. J109-J111 and J116 then sit at the ladder inputs, J117/J119 on TS2/TS3, TP301 on the 3V3 rail, J113/TP106
  on PACK_P at the right end of the protection path, J114/TP109 at RS101's ground end. The "Cell and load wires"
  section disappears.
- (c) Two-pad parts whose net is a top/bottom pin (C451, C452/C404/C408 at U405 VBIAS/VPWR, U402 VCC): draw the
  bank beside the IC at the height of its top edge with a wire to the pin stub. Only now touch top/bottom pins.
- (d) Per-block hints for the rest are fine: D401 on the VBUS wire at J401, R432 at U404 EN, Q409 at U406 EN (its
  drain net V9_EN is U406's EN row), U402 right of U401's I2Cc pins.

**4. Straight protection path.** No custom symbol is needed: `Sheet.symbol` already takes `angle` and `mirror`, and
`bridge4` uses them. Rotate Q101/Q102 by 90 so S and D lie on the path line and G points down (or up); compute pin
positions with the existing `rot()` helper from `symlib.pins`. Then F102, Q101, FET_MID, Q102, PACK_P share one y,
gate networks hang on the gate side, and C110/C111 and C107/C108 hang below the line. Label the `CELL_P` segment.
Also move the fuse-heater FET's text off its body (Q104).

**5. Page balance.** Cells: bottom-right third empty, and 60 mm of loose terminals under the gauge. USB: the whole
lower-left and lower-right are empty and the page is 300 x 175 mm for what fits in two thirds of it. MCU: lower half
empty. Items 2-3 change section sizes, so do this last: choose the page width that minimises empty area subject to
aspect between 1.2 and 1.6, and allow a short section to go under a short neighbour (column packing by height).
On MCU put the two Tag-Connect headers side by side under the antenna match.

**6. Annotation.** A one-line note under each template (from the hint: `note="..."`), for example "R101-R104/C101-C104:
cell-tap RC filters", "D101: BAT feed ahead of fuse", "R444-R447: gate tuning positions". Cheap, and moves
criterion 7 from 3 to 4 on three sheets.

## 4. Beliefs to correct

- "Now 0 (3V3, MCU), 2-5 (Cells, USB) text collisions": not true for Cells and USB; the checker misses most of them.
  Do not trust a checker until it reports collisions you can already see.
- "Straight fetpair needs rotated FET symbols or a custom symbol": rotation is already supported (`angle`, `mirror`,
  `rot()`); `bridge4` is the worked example.
- "Floating parts need attach_plan to accept top/bottom pins": only case (c) does. Cases (a), (b), (d) cover most of
  the islands and need no top/bottom pin support.
- Order of work: you did the ladder (my item 3) and skipped items 1-2 fixes. The scores move most with clutter and
  grouping now; the USB sheet counts as much as Cells and has had no work.

## 5. Process

After each `make.sh`, look at every page (2-6), each section zoomed 2x, and compare with the checker output: any
collision you can see that the checker does not print is a checker bug to fix first. Keep "NETLIST OK" at every step.
