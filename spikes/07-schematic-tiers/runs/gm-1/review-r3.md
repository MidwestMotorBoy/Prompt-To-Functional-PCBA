# Review at start of round 3 (strict), then changes
| Sheet | Flow | Group | Wires/labels | Clutter | Space | Circuits | Annot | Review |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 3 | 3 | 4 | 3 | 1 | 3 | 3 | 3 |
| Cells and Gauge | 2 | 2 | 2 | 2 | 2 | 2 | 3 | 2 |
| MCU | 2 | 3 | 3 | 2 | 2 | 2 | 3 | 2 |
| USB Port | 3 | 3 | 3 | 3 | 2 | 3 | 3 | 3 |
Evidence: Cells page: connectors/test points are loose label-only parts; protection FET section is a row of
unrelated cells; U101 left side has a wide empty band; PACK_P labels collide with TP106/J113 text. MCU: antenna pi
split, C314 alone. USB: large empty areas between sections.
Open list: (1) tighten spacing inside sections, (2) pi/series-chain template, (3) protection FETs as one path,
(4) connectors in an edge column, (5) overlap measurement.
Done this round: skyline packing of sections (fills gaps beside tall sections), pages sized to content (3V3 sheet
now small instead of an A4 with one row), sections' ICs pack wider than tall. Items 1-5 above remain open.
