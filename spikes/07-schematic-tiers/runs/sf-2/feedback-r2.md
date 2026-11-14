# Review round 2 (pages 2-6 as rendered now)

## 1. Scores (0-5)

| Criterion | 3V3 Rail | Cells+Gauge | MCU | USB Port |
|---|---|---|---|---|
| 1 Flow | 4 | 3 | 3 | 3 |
| 2 Grouping | 4 | 3 | 3 | 2 |
| 3 Wires vs labels | 4 | 3 | 3 | 3 |
| 4 Clutter | 4 | 2 | 3 | 2 |
| 5 Space | 3 | 2 | 2 | 2 |
| 6 Recognisable | 4 | 3 | 4 | 3 |
| 7 Annotation | 3 | 3 | 3 | 3 |
| 8 Reviewability | 4 | 3 | 3 | 3 |

Average 3.0 (was 2.6). Cells went from about 1.4 to 2.8: the protection path, Kelvin sense and aliases are real gains.
What holds every sheet at 3 now is text collisions, floating parts, and empty page. USB got no attention this round and
is now the weakest sheet.

## 2. Status of round-1 items

1. Aliases: done. 2. Reference rail: done. 3. Path template: done (`fetpair`, `kelvin`). 4. Cell-tap ladder: not done.
5. Text placement and overlaps: partly done, and new collisions appeared. 6. Floating parts: not done.
7. Sideways shunts: partly done. 8. Page fill: partly done (paper fits content, but content is still unbalanced).

## 3. Changes now, in priority order

**1. Stop text collisions with a mechanism, not by eye (all sheets).** Collisions visible now:
- Cells U101 left side: TH101 ref/value on top of R113; TH104 text 40 mm away from its symbol ("TH104 10k B3435"
  floating at lower left); "C105 2.2u 50V" detached and sitting on the VC3 lane; `CELL_1N` label over pin 24's stub and
  over pin 23; `VCC` label touching R105; R115 text over `GAUGE_FUSE`; "R116 100" above R117 with no body of its own
  visible in the row.
- Cells protection: R111 text over Q102's value; R112 value over D103; C118 value over R125; `WAKE` label over TP113.
- Cells terminals: J120 text runs into J116's `CELL_4P` label.
- USB U403: R445 and R446 text on top of each other and on the bodies; R412-R414 ground stubs cross the neighbouring
  pin rows; U401/U405 bottom pin numbers piled up.

Write the overlap checker you skipped: in `Sheet`, record a bounding box for every `text`, `label`, symbol body and
ref/value field (width = chars x CH, height about 2 mm) and print each intersecting pair at the end of `write()`.
Run it on all sheets and drive the count to zero. This is one hour of work and it replaces zooming.
Then fix the cause in `draw_anchor`/`inline()`: when two adjacent pin rows (2.54 mm apart) both carry an inline part,
there is no room for ref-above/value-below. Rule: an inline part needs a free row above and below; if not, stagger
alternate rows outward in x (second part starts after the first part's end), each with its text directly above its own
body. Never place a ref/value more than about 3 mm from its body: a detached "TH104 10k B3435" is worse than a longer
wire.

**2. Floating support parts (USB first, then Cells, MCU).** Still islands: D401, U402, C451, C452/C404/C408, R432,
Q409, TP412 (USB); D101, J117, J119 and the terminal section (Cells); TP301 (MCU). Extend `attach_plan`:
(a) top and bottom pins of an IC may take hung parts (decoupling cap beside the supply pin stub: U405 VBIAS/VPWR, U402
VCC); (b) a part whose only non-ground net is already drawn as a wire gets a stub on that wire: D401 on VBUS next to
J401, D101 in series in front of R105 on the BAT row (it is `CELL_4P -> D101 -> R105 -> BAT`, draw it as that chain),
R432 on EN_5V1 at U404 EN, Q409 at U406 EN; (c) single-pin terminals and test points go where their net first appears
(J117/J119 on the TS2/TS3 pin rows, J109-J111 at the left end of the CELL1-3 ladder inputs, J116 on CELL_4P, TP301 on
the 3V3 rail). U402 sits to the right of U401's I2Cc pins, wired to I2CC_SCL/SDA with the pull-ups between them.
After this the "Cell and load wires" section should be almost empty.

**3. Cell-tap ladder (Cells U101 and U102).** Your blocker ("VC4 row is an inline part, not a lane") has a simple way
out: do not rework `lanes()`, add a `ladder` template like the others (`anchor` plus ordered `rows=[(R, C), ...]` and
the top row). Draw rows at equal spacing left of the IC: input label, series R, node, wire to the pin; each C vertical
between its row's node and the next row's node, bottom C to the ref rail. One template serves U101 (R101-R104,
C101-C104) and U102 (R119-R122, C112-C115). It removes the `VC4`/`VC3`/`VC2`/`V4`/`V3`/`V2` labels and the odd
C104/C115 extra column.

**4. Protection path should read as a straight line (Cells `fetpair`).** Now the sources leave the FET, drop 20 mm to a
lower bus and the drains meet on an upper line, so the current path is a U shape. Put F102, Q101, FET_MID, Q102 and
PACK_P on one y: rotate/mirror the FET symbols so S and D are on the left/right at the path height and the gate is
below or above, gate networks (R109/R110, R111/R112/D103) on the gate side only. C110/C111 and C107/C108 then hang
below the single path line. Also put the net names `CELL_P` and `FET_MID` on their segments.

**5. Sideways shunts and inline grounds (USB).** Not done: C401/C402 (U405 CC), C405 (LDO_1V5), C439 (U404 SS),
R412-R414 (U403 FSW/ICHG/ILIM). Use the same corner-and-downward-ground you added, but place the part beyond the other
pins' label column so the drop wire does not cross adjacent rows; for three adjacent rows stagger them (see item 1).

**6. Page balance.** Cells: the right half under "Current sense" and the area below the gauge are empty; USB: the
lower right quarter is empty and the row-2 sections have loose parts 60 mm under their IC; MCU: bottom third empty.
Once items 2-3 remove the leftover-cell rows, pack sections by columns (tallest first, fill the shortest column)
rather than shelves, and let a small section (Current sense, Gauge interrupt, Antenna match) sit under a short
neighbour. Order the USB sections along the power flow: connector/protection, PD controller, charger, four-switch
stage, then 5 V buck and 9 V supply.

**7. Small annotation gains.** Label the bridge and path segments (`SW1`, `SW2` are there; add `PPHV`/`PACK_P` side
notes "input"/"battery" is not needed, but a one-line note per template section from the block hint is cheap: e.g.
"R107/R108/C106: Kelvin filter to SRP/SRN"). Put the `OUT` alias on Cells as `U102_OUT`: bare `OUT` and `VCC`, `VDD`
labels are ambiguous on a sheet with two ICs.

## 4. Beliefs to correct

- "The VC4 row is an inline part, so the ladder needs the lane code reworked": no, a template bypasses both (item 3),
  exactly as `fetpair` bypassed the generic placer.
- "I checked by zooming renders": that missed at least ten collisions listed above. The checker is not optional polish;
  it is the fastest way to raise criterion 4 on three sheets.
- Aliases must be unique per sheet, not just per IC: `VCC`, `VDD`, `OUT`, `V3` vs `VC3` on one sheet invite misreading.
  Prefix with the ref whenever a sheet has more than one IC with auto-named nets.

## 5. Process

After each `make.sh`, look at every page (2, 3, 4, 5, 6), zoomed 2x per section, plus the overlap checker output for
all sheets. This round page 5/6 changed shape (now very wide) and gained collisions at U403 without being looked at.
Keep "NETLIST OK" at every step.
