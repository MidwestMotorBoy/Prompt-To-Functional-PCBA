# Notes

## Changed (design/draw.py, design/blocks/cells_gauge.py)
- Page shape: sections are packed for the page width that gives a paper-like aspect (was fixed 594 mm, giving tall sheets with empty bands). Text extents now count toward page size (titles were clipped).
- Zone choice for support parts: scored by net fan-out (1/pins on net, each IC counted once) with a bonus for the same section, instead of counting pins. Decoupling for the protector no longer lands on the gauge because both sit on CELL_1N. Bridge4-template ICs no longer capture cells. Pure connector / test-point cells keep their own section.
- Lane attachment ignores nets with more than 8 pins (ground-like rails such as CELL_1N), which had produced one long bus of unrelated caps.
- Divider chains tap only the pins on one side of the IC; far-side ends become labels. Q101 gate divider is now wired to the gate like Q102.
- Inline (same-row) parts are used only where the pin has no neighbouring pin within a row; otherwise they fan out on lanes. Removed the overlapping stack on the gauge BAT/VCC/PBI/PTCEN pins.
- Single-pad banks (wire points, test points) get spacing from label and text width; no more overlapping text.
- cells_gauge.py: the wire/test-point parts moved to the end of the block under one section "Wires and test points" (draw hint only; circuit unchanged).

## Next
- Real back-to-back FET drawing (Q101/Q102 facing each other with FET_MID between), and F102 / Q104 / R125 / C118 fuse-ignition circuit drawn as one cell.
- Lanes on the gauge are long (down-wire); a side-by-side column with buses would be shorter.
- MCU: antenna pi network as an in-line RFIO to ANT_IN path, VDDS decoupling beside the pin; 3V3 sheet is a small buck on a mostly empty A4.
- D101 still stands alone; USB-C connector / PD controller pins are still labels everywhere.
- Block-level order hints so sections follow signal flow (input left, output right).

## Round 2
- New kernel hint `ladder(start_net, [("s", ref), ("p", ref), ...])`: the section is drawn as one in-line path (used for the MCU antenna pi match: RFIO, C313, shunt C314, R321, shunt C315, ANT_IN).
- Cell attachment picks the pin net with the fewest pins first, so pull-ups land on their signal pin and VDDS decoupling on VDDS (glob nets are exempt from the fan-out limit).
- Small blocks are centred on their sheet (3V3 Rail).
- Self-review and remaining list: review-r2.md.

## Round 3
- `draw_as("fetpair", "Q101", q_out="Q102", left=[..], right=[..], zener="D103")`: back-to-back protection FETs drawn as one path (CELL_P rail, FET, FET_MID, FET, PACK_P rail) with each gate divider beside its gate.
- Auto net names (`Net-(U101-VC3)` etc.) renamed to readable ones (GAUGE_VC1.., PROT_V1.., BAT_FEED, FUSE_HTR, ESD_MID, ANT_MID); names only, netlist check still passes.
- F102 now sits with Q104 in "Chemical fuse and its ignition FET".
- A lone 2-pad part in series with a lane part follows it in line (D101 then R105 into the gauge BAT pin); lone parts in series with a placed part adopt its zone.
- Still open: loose decoupling cells at top/bottom pins and at template ICs (U404 SS cap, U405 VBIAS), the large empty areas on the USB sheets, long gauge lanes.

## Round 4
- Section packing is now a skyline packer (each section goes to the lowest, leftmost free spot), so small sections fill gaps beside tall ones; USB sheets are denser, Cells sheet reads in three bands.
- Less blank space under template ICs (buck) before their leftover cells.
- Open: leftover decoupling cells for pins on top/bottom or under a template (U404 SS cap, U405 VBIAS) still sit under their IC with a "for U404.SS" caption; F102 and Q104 share a section but are not one drawn circuit; gauge lanes are still long; no short prose notes under section titles.
- Review tables: review-r2.md, review-r3.md, review-r4.md.
