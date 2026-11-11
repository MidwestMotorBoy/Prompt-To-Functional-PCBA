# Layout review checklist

Use at three gates: before routing (placement review), after routing, before ordering. When reviewing someone
else's board, report findings as: severity (must-fix / should-fix / nice-to-have), location (refs/nets/layer),
what's wrong and why (the physics), and the fix.

## A. Before routing (placement)

- [ ] Stack-up and per-layer pour plan written and agreed.
- [ ] Mechanical parts placed and locked; outline, holes, notches, keep-outs, antenna edge correct.
- [ ] Zones follow power/signal flow; noisy and sensitive areas separated; gutters between blocks.
- [ ] Every hot loop: HF cap straddles high-side drain / low-side source; bulk behind; same layer as FETs.
- [ ] Switch-node copper minimal; nothing placed in the FET–inductor gap.
- [ ] Controllers near their FETs, gate-drive pins facing them; programming parts on the quiet side at their pins.
- [ ] Sense resistors oriented for straight current flow; their filters at the IC.
- [ ] Decoupling at every supply pin, smallest nearest.
- [ ] TVS/ESD in-line at connectors; nothing blocking connector pin escapes.
- [ ] Antenna module at the edge with the vendor's keep-out and ground extents.
- [ ] Temperature sensors on the copper they measure.
- [ ] Test points for rails, switch nodes (stub off inductor far side), key signals; ground points beside probes.
- [ ] Repeated blocks identical by translation.
- [ ] Dense ICs (>20 pins or <0.8 mm pitch) have 1.5 mm clear round them (1 mm for small fine-pitch parts), decoupling excepted
      (`check_routing_rules.py`, fan-out section empty).
- [ ] Courtyards clean; DRC + schematic parity clean; placement render reviewed.

## B. After routing

Electrical:
- [ ] DRC: 0 errors; unconnected 0; parity 0; every warning understood.
- [ ] Ground plane(s) continuous under every critical trace (render each plane layer alone; look for slots and
      antipad rows).
- [ ] `check_routing_rules.py` clean: inner layers Manhattan (L3 vertical, L4 horizontal), nothing but GND on
      L2/L5, no via-row slots, no long outer-layer signal runs, every signal via has a GND via within 1 mm.
- [ ] No reference changes on clocks/sense.
- [ ] Hot-loop return in the plane directly under the loop; no traces on the plane layer under power stages.
- [ ] Gate drive paired with its return; no gate trace beside a sense trace. Measure it: driver pin to gate pad
      straight-line distance (aim ≤10 mm; a controller 15–34 mm from its FETs with 0.2 mm gate tracks is a
      placement finding for the next revision) and gate track width ≥0.5 mm (TI).
- [ ] Polarity marks match pad nets: trace the series chain through holder/connector pads (marks owned by the
      footprint rotate with the pads; board-level "+"/"−" text does not).
- [ ] Antenna keep-outs: no zone *fill* polygon intersects the rule areas on any layer (DRC checks tracks and vias
      there; test the fills with `SHAPE_POLY_SET.BooleanIntersection`).
- [ ] Silkscreen labels for test points actually placed (0.8 mm text does not fit a 2.54 mm loop grid; spread the
      grid or accept unlabeled loops).
- [ ] Kelvin pairs from pad ends, tight, no vias/test points, away from SW nodes.
- [ ] Second grounds (gauge VSS, AGND) joined at exactly one point; nothing crosses the gap.
- [ ] High-current paths: width with margin for etch tolerance, no necks, enough vias at each layer change, mirrored
      and stitched where planned.
- [ ] Thermal pads: via arrays, solid connections, paste windowpane.
- [ ] Differential pairs: impedance, matching, symmetric vias, continuous reference.
- [ ] Fills stitched; slivers and islands removed; board-edge stitching where planned.

Solved, not only rule-checked (`solver-verified-layout.md`; compare each number with the previous revision):
- [ ] Every plane net is one group over all layers, and each plane is one piece on its own layer wherever a part
      draws current from it (draw the pieces in different colours).
- [ ] Every power path's resistance on the fine grid (0.05 mm) is what it was before the last edit, or the change
      is explained. No via or track of another net sits in a pour neck.
- [ ] Every Kelvin tap reads within about 1 % on the 0.05 mm grid.
- [ ] Hot loops: effective inductance and the per-capacitor list match the previous run; no capacitor has
      dropped out of its loop.
- [ ] Gate loops solved; none several times larger than its neighbours.
- [ ] Coupling from switching copper: every signal over about 10 mV per edge is known and accepted (thermistor
      nodes at the FETs) or its via or stretch has been moved.
- [ ] No via carries more than its budget on any power path.

Manufacturing:
- [ ] Clearances and widths ≥ fab minimums with margin (2 oz outer layers!).
- [ ] Vias: standard sizes; via-in-pad only filled/capped; tented where under parts.
- [ ] Annular rings, hole sizes, copper-to-edge, mask dams on fine pitch.
- [ ] Fiducials, rails if needed; footprints medium density; polarity marks.
- [ ] Silkscreen readable, off pads; pin-1 and connector keys marked.

## C. Before ordering

- [ ] Gerbers and drill viewed; layer order and stack-up match the order form.
- [ ] Position file rotations verified in the fab's viewer; BOM complete; DNP/hand-fit excluded; one BOM line
      per LCSC number; stock checked.
- [ ] A "critical only" pass against the fab's live capability page: what stops the board working (opens, shorts,
      parity, polarity, keep-outs) and what the fab would reject (hole-to-hole, ring, track/space at the copper
      weight, slots, edge). Say which is which; everything else is advisory.
- [ ] A last render of every layer and a comparison with the vendor EVM layouts for each power stage.
