# Notes: readable Monolith sheets

`./make.sh` ends with `NETLIST OK` (285 shared parts, 168 nets, 0 differences). The sheets are still generated from `design/`.
ERC (kicad-cli) shows the same classes of finding as the starting point (library and footprint link notes, 3 no-connect and 13 power-pin
notes that were there before); no dangling wires or labels. The only increase is 14 `lib_symbol_issues`, from the symbols that the
scenes re-pin or stretch on purpose (see "Drawing liberties").

## What changed

### General (carries over to a new board)
- `design/sheet.py` (new): the drawing engine, moved out of `draw.py`. Adds: automatic junctions computed from wire ends, pins and
  pass-throughs; `\n` escaping (a raw newline in a note used to truncate the file and silently drop wires and junctions); mirror
  semantics that match KiCad (`mirror` "y" / "x" after rotation); stretched or re-pinned embedded symbols (`gaps=`: per-side pin pitch,
  `_custom` pins/rect/borrowed body graphics, optionally per unit as `NAME#unit`); text boxes and a **lint** (text on text, text on
  wire, wire through a body, text over a symbol, symbol overlap, wires over 90 mm) written to `out/lint/<sheet>.txt`; paper size from
  the content, grown if the content would sit under the title block; dashed group frames with a title.
- `design/lay.py` (new): a small toolkit for drawing "like a person": `v`/`h` two-pin parts at the grid with text on a free side,
  `ic` with pin-anchored placement and per-side stretch, motifs (`hang_row`, `ladder`, `pull`, `drop`, `out_pull`, `in_pull`, `gdrop`,
  `fet`, `pad`), `term`/`stub`/`finish` for the pins left over, and `group(title)` that draws the frame after the content is placed.
  Nets that leave the sheet become global labels or supply arrows, nets that stay become wires or short local labels.
- `design/draw.py`: dispatches each sheet to a scene program (`design/scenes_*.py`). The old engine and its templates are still in the file as
  the fallback (`LEGACY=1 python3 draw.py ...` draws the old style, which is how the baseline numbers below were made).
  The root sheet now says what each sheet is and how they connect.
- The rules the scenes follow: supplies up (arrow) and ground down, flow left to right, decoupling hangs from the rail at the pin it serves,
  pull-ups hang from a shared rail, programming resistors hang from their pin, series parts sit in the line, an RC filter is drawn as a filter,
  a half bridge is two MOSFETs in a column with the inductor between, group frames with a one-line title.

### Per sheet (the circuit knowledge lives here, deliberately)
- `scenes_3v3.py`: bulk bank and converter in two frames; textbook buck.
- `scenes_mcu.py`: pi match as one network, pull-ups on one rail, reset network, connectors in their own frame.
- `scenes_cells.py`: gauge with Kelvin cell taps and filters, pack path (fuse, back-to-back FETs drawn in line, ESD caps), second-level
  protector, current sense. `DISP` renames one auto-named net (`Net-(Q104-G)` is shown as `FUSE_G`).
- `scenes_usb.py`: one program for both ports (reference numbers come from the port base). Port differences (ADCIN1 strap) are read from
  the netlist, not hard-coded.

### Drawing liberties (each is a symbol edit in the embedded copy only, never in the circuit)
- Q101/Q102 (AGM404AP1) and the SiZ240DT units are drawn with MOSFET graphics and pins moved to D/S/G positions. U403 (BQ25756), U401, U404,
  U406 and U301/U101 are stretched so each pin has room for its parts. U405 and U402 have pins moved (RPD_G, VPWR, VBIAS, SCL/SDA, A0-WP).
  Pin names and numbers are untouched, so the netlist is the same; a reviewer comparing against a datasheet pinout sees different order or spacing.
- Net names in the drawing are friendly (`FUSE_G`, `DP/DN` is not drawn); `compare.py` checks pin partitions, not names.

## Measurements (`./measure.py DIR`, `./dev.sh`, `./crop.py page x0 y0 x1 y1 dpi`)
Baseline = the old engine on the same netlist (`LEGACY=1`); page sizes in the table are the original renders.

| sheet | page (baseline -> final, mm) | wire mm | wires > 40 mm | local labels | global labels | lint |
|---|---|---|---|---|---|---|
| 3V3 Rail | 297x210 -> 280x160 | 227 -> 231 | 1 -> 2 | 1 -> 1 | 4 -> 1 | 1 -> 0 |
| Cells and Gauge | 500x520 -> 480x300 | 1623 -> 1203 | 10 -> 3 | 93 -> 22 | 11 -> 3 | 3 -> 0 |
| MCU | 460x210 -> 300x220 | 439 -> 403 | 4 -> 1 | 13 -> 9 | 19 -> 10 | 2 -> 0 |
| USB Port 1/2 | 470x730 -> 490x380 | 3341 -> 2454 | 22 -> 13 | 99 -> 52 | 13 -> 7 | 4 -> 0 |

(Wires over 40 mm in the final USB sheets are the rails that carry hung parts; longest single wire 83 mm, the input bus with seven capacitors.)

## Scores, strict (baseline -> final), 0-5
Order: flow, grouping, wires vs labels, clutter, space, recognisable circuits, annotation, reviewability.
- 3V3 Rail: 4,3,3,4,2,4,3,3 -> 4,4,5,4,3,4,4,4
- Cells and Gauge: 2,2,1,2,1,2,3,2 -> 4,4,4,4,3,4,4,4
- MCU: 2,2,1,3,1,2,2,2 -> 4,4,4,4,3,4,4,4
- USB Port: 2,3,1,3,1,3,3,2 -> 4,4,4,4,3,4,4,4
Why not 5: the charger and PD controller are stretched symbols (reads well, differs from the datasheet outline); frames have some blank
interior (USB group 1 lower left, buck group, 3V3 frames, MCU connector frame); two stacked-pin-number clusters (U401 GND, U405 bottom) are
the library symbols' own overlap; a few GNDA labels on Cells are tight next to J118/J119; sheet-to-sheet nets are labels with no
sheet pins (unchanged from before).

## What I would do next
- Fill or shrink the remaining blank interior of frames (let `group` take a target aspect, pack groups automatically instead of by hand).
- Move the per-port numbers in `scenes_usb.py` (pitches, offsets) into a few named constants, and add a check that every pin of every
  IC is either wired or deliberately stubbed so a new part cannot be left unplaced silently (currently only the netlist check catches it).
- Make `Lay.fet`/half-bridge and the RC-filter/staircase motifs library functions with their own tests; they are generic but live in the scenes.
- Try a hierarchical sheet-pin version of the root sheet.

## Blocked / not done
- Nothing blocked. Not tested: opening the sheets in the KiCad GUI (only kicad-cli netlist, PDF and ERC were run).
- A hand-edit of any `.kicad_sch` is not possible and was not done.

## Round 2
Self-review and the five-item list are in `review-r2.md`. Changes: Cells TS rows re-spaced (no ground symbol or label touches another
row), right column pulled 18 mm left; USB sheets got a power-path line under the title and notes saying what sets the input window,
current limits, frequency, battery and 5 V/9 V voltages, the 9 V gating and the ADCIN1 address strap (reference numbers come from the
port base, so both ports are right). Lint is 0 on all sheets, `make.sh` ends with NETLIST OK. Still open: wire-vs-label links between
the USB charger and power stage, frame packing and dead margins.

## Round 3: automatic frame packer

- `Lay.pack(groups, top=, fixed=)` (design/lay.py). A scene now only lists its groups as `(title, fn(L, ox, oy))`; each fn
  draws relative to its origin. pack() draws each group once on a scratch sheet (`Lay.scratch`) to measure its frame, then
  tries every page width (and, unless `fixed=True`, every order) with a bottom-left skyline placer so a short frame fills the
  pocket beside a tall one. Cost is paper area, kept near landscape 1.45:1 (portrait is penalised hard), with the paper grown
  until the 112x36 mm title block clears every frame, plus a penalty for pairs of groups that stop reading in the given
  order (same column top to bottom, same row left to right). Frames stacked on one left edge with widths within 12 mm are
  made flush. The chosen paper is stored in `Sheet.force_paper`; `group()` gained `left=`/`right=`.
- Scenes became origin relative (3V3, MCU, Cells, USB). USB uses `fixed=True` with the groups in reading order, EEPROM last
  as the pocket filler. `PACKDBG=1` prints every candidate.
- EEPROM split from the PD frame into its own small frame (removes a 60 mm blank strip); the PD note moved under J401/U405.
- Forced equal frame bottoms removed (3V3, MCU); MCU pin gaps trimmed so the page drops to 200 mm tall; 3V3 and MCU notes now
  name what leaves the sheet and who uses 3V3.
- Paper: 3V3 280x160 -> 280x150, Cells 460x310 -> 440x310, MCU 300x220 -> 300x200, USB 490x410 -> 480x390.
- Scores before / after in review-r3.md. Open: gauge frame lower-right blank, charger-to-power-stage links are labels.

## Round 4

- Gauge TS2..PTC pin gaps tightened (15.24 / 22.86 / 17.78 / 12.7): Cells paper 440x310 -> 440x290. A gap is the space before
  that pin; TS3 needs 22.86 for the TS2 return pad and its ground label.
- 3V3 buck leads shortened (U204 offset 38.1, inductor 15.24, output run 15.24): paper 280x150 -> 270x150.
- Root sheet laid out in power-flow order via `POS` in design/draw.py, with text arrows naming the nets between boxes.
- Scores before and after in review-r4.md. Open: USB charger-to-power-stage links are labels; CELL_x taps to the protector
  are labels; PD frame blank under the connector.
