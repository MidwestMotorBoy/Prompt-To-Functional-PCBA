# Notes (gm-1)
Changes (all in design/draw.py, general):
- Auto-named local nets ("Net-(U101-VC3)") are drawn as "U101_VC3" (net names are not part of the netlist check).
- Sections are shelf-packed per page with the page width chosen for a balanced aspect (was a fixed 594 mm row width,
  which left pages mostly empty).
- ICs inside one section are packed side by side (was one stacked column).
- Page height now keeps content clear of the title block.
Not done / next: the antenna pi network (MCU) is still split into loose cells; sections of the USB sheets are still
sparse because lane spacing and label reservations are generous; text overlaps near some IC pins and a few TP/label
collisions remain; no automated overlap measurement was built; a "pi/series chain" template and tighter lane spacing
are the next steps. NETLIST OK after every change.
- Round 2: pin labels now sit on a 2.54 mm stub so they no longer overprint pin numbers. See review-r2.md for scores and open list.
- Round 3: skyline packing of sections, content-sized pages, wider in-section packing. Open: see review-r3.md.
- Round 4: single-pad cell spacing fixed (label collision). Final state NETLIST OK. Open items: review-r4.md.
