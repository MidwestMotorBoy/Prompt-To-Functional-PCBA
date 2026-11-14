# Self-review, start of round 2 (strict)
Criteria: 1 Flow, 2 Grouping, 3 Wires vs labels, 4 Clutter, 5 Space, 6 Circuits, 7 Annotation, 8 Reviewability
| Sheet | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 3 | 3 | 4 | 3 | 1 | 3 | 3 | 3 |
| Cells and Gauge | 2 | 2 | 2 | 2 | 2 | 2 | 3 | 2 |
| MCU | 2 | 3 | 3 | 2 | 2 | 2 | 3 | 2 |
| USB Port | 3 | 3 | 3 | 2 | 1 | 3 | 3 | 3 |
Evidence: 3V3 sheet has one row of content on a mostly empty page; Cells has loose connector/test-point cells and FET
parts scattered; MCU antenna pi split into three cells, J301/J302 far from the module; pin labels overlapped pin numbers
(fixed in round 2 by a stub wire); USB pages ~2100x2500 px with large empty bands.
Top five changes (priority):
1. Tighten spacing (lane pitch, cell heights, section gaps) so pages fill.
2. Series-chain template for the antenna pi network and for protection-FET gate networks.
3. Draw the FETs of the protection section as one path (Q101, Q102, R112, D103) instead of separate cells.
4. Move connectors/test points to the page edge as a titled column.
5. Automated overlap measure for text/symbol/wire collisions.
Done in round 2: item "pin label stub" (label no longer sits on the pin number); NETLIST OK.
