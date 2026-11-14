# Notes

## Changed
- draw.py: sections are now packed on the page by a skyline packer (each section goes where it sits highest) instead of
  left-to-right rows. The page width is searched (120-700 mm) for the smallest area near a 1.45 aspect ratio, so
  sheets are denser and closer to a landscape page.
- draw.py: leftover single cells (test points, caps, wire pads) wrap at 95 mm instead of 180 mm, so they sit in compact
  blocks rather than spread across the sheet.
- draw.py: the sheet is 20 mm taller, so the title block no longer lands on drawing content.
- cells_gauge.py: the fuse, its ignition FET Q104 and R125/R126/C118 get their own section, "Chemical fuse and its
  ignition FET". They were under "Second-level protector".

## Next
- Cells sheet: the single-pin wire pads and test points still float. They should go into one tidy row, or sit next to
  the net they serve.
- Net labels such as Net-(U101-VC3) are ugly. Giving those nets real names in the block code would fix that, but
  it changes the frozen netlist.
- Q104/F102 and the protection-FET column have no real flow. They need a template for the FET pair.
- The USB sheets are still tall. They should be split into column groups.
- The gauge lanes still run far left of the IC.

## Blocked
Nothing blocked. I did not get to the MCU, USB and 3V3 sheets beyond the global packing.
