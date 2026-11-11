# Return paths, grounding and EMC

Contents: 1. Where return current flows · 2. One ground, partitioned · 3. When a second ground is unavoidable ·
4. AGND/PGND at a controller · 5. Layer changes and stitching · 6. Slots, gaps, antipads · 7. Ground fills and
stitching vias · 8. Board edges, cables, chassis · 9. Quick diagnostics · Sources

## 1. Where return current flows

- At DC and low frequency (below a few kHz) return current takes the lowest-resistance path and spreads across the
  plane.
- Above that, it takes the lowest-inductance path: directly under the outgoing trace, in the nearest plane,
  concentrated within a few dielectric thicknesses of the trace. (Ott: "the lowest impedance return path is in a
  plane directly underneath the signal trace.")
- Above ~30 MHz in 1 oz copper, skin effect confines current to surfaces, so the face of the plane nearest the
  trace carries it.
- Consequence: the plane is not "ground" in a lumped sense. It is the second conductor of every circuit. Anything
  that forces the return away from under its trace — a slot, a split, a dense via field, a trace on the plane layer
  — makes a loop.

Always ask Ott's question: **how and where do the return currents flow?**

## 2. One ground, partitioned (default)

- Ott: "It is almost always better to have only a single reference plane for a system!" Partition the *board*
  (analog area, digital area, power area) and keep each area's signals inside it; let the single plane carry
  everyone's returns under their own traces. Routing discipline must be 100 %: one digital trace through the
  analog area undoes it.
- Mixed-signal converters: datasheets that say "tie AGND and DGND together externally" mean "connect both pins to
  the one low-impedance plane right at the part". For ≥14-bit converters Ott allows isolated analog/digital ground
  regions solidly tied together under the converter, with no traces crossing the isolating slot on any layer.
- Power stages: their pulsed currents return in the plane right under the hot loop. Keep sensitive circuits
  physically away rather than splitting the plane.

## 3. When a second ground is unavoidable

Some circuits have a ground that must not carry other currents:

- **Battery gauge / BMS VSS** referenced to the cell negative side of a current-sense shunt (e.g. TI BQ40Z50): the
  pack's load current flows from cell− through the shunt to system ground. The gauge's low-level ground (VSS,
  filter caps) must connect at the cell side of the shunt only, so the shunt voltage is measured cleanly.
- **Chassis / shield ground** at connectors.
- **Isolated domains**.

How to do it:
- Give the second ground its own net name in the schematic and join the nets with the real joining component
  (shunt) or a **net tie** at the one intended point, so the layout tool cannot short them elsewhere.
- Pour it as local fill on the **outer and signal layers** under the circuits that use it, joined only at that
  point. Never cut it out of a ground plane: the planes stay solid system GND everywhere (`routing-discipline.md`
  §4). The second ground's milliamps don't need a plane; what matters is that no load current flows in its copper.
- Route nothing across the boundary except the few signals that must cross, and route those across the join
  point or with a stitching capacitor nearby. Slow buses (SMBus with series resistors) tolerate a small detour.
- TI's gauge guidance (BQ40Z50 §11): put high-current copper on the opposite side from the gauge electronics where
  possible, route high-current traces away from signal traces entering the gauge (surges couple magnetically and
  capacitively), and add a ground shield around the current-sense filter network.

## 4. AGND / PGND at a switching controller

TI SLVAFJ3 (4-switch buck-boost): AGND is the quiet reference for FB, COMP, SS, RT, SLOPE; PGND carries the
switching return. Give AGND its own small pour around the control components, connect AGND to PGND at one point —
**the controller's thermal pad** — and draw two ground symbols in the schematic joined by a net tie so the layout
keeps them separate until that point. On a multilayer board with a solid ground plane, the AGND pour is a local
top-layer island that drops to the plane only at the pad; the plane itself stays one net.

## 5. Layer changes and stitching

- When a signal changes layers and therefore changes reference plane, its return must jump planes too. Put a
  ground via next to the signal via: common guidance is within 1.27 mm (50 mil) for ordinary speeds, ~0.5 mm for
  multi-GHz (AtlasPCB), or within 2–3 via diameters.
- If the two reference planes are different nets (GND and a power plane), the jump is through a capacitor: a
  1–10 nF stitching cap near the via (its inductance limits it to a few hundred MHz). Ott puts the via-plus-cap
  return path at about 5–10 nH — better to avoid the reference change.
- Ott's ranked preference for critical traces: route on one layer adjacent to a plane; next best, two layers
  adjacent to the same plane; changing reference planes is the last resort.
- Differential pairs carry most return current in the partner trace; they tolerate reference changes better than
  single-ended lines, but keep a ground via beside the pair's vias anyway.

## 6. Slots, gaps and antipads

- Ott on slots: don't have them. If one exists, no trace on an adjacent layer may cross it. If a trace must cross,
  stitch the slot with small capacitors (1–10 nF) on either side of the trace within 2.5 mm (0.1").
- Accidental slots: rows of via antipads (clearances) in a plane merge into a slot. Keep plane clearance around
  vias at the fab minimum and stagger via rows so the plane stays connected between them; check plane continuity
  under every important trace in a render of that layer.
- A split that runs *parallel* to a trace and never under it is harmless; one that a trace crosses is not.
- Board cut-outs and connector notches are slots too: keep traces away from their edges.

## 7. Ground fills and stitching vias

- Fill unused areas of signal layers with ground and stitch to the planes. An unstitched fill (or a long thin
  sliver) is an antenna; remove islands and slivers narrower than ~2–3× track width.
- Stitching density: λ/20 at the highest frequency of concern is a common guide (≈1.5 mm at 10 GHz); for
  switch-mode boards with edges in the 100s of MHz, a 3–5 mm grid along fills and board edges is ample.
- Guard traces between sensitive and aggressive nets only help if stitched to ground frequently (every 2.5–5 mm);
  an unstitched guard can make coupling worse.
- Put a ground via at every ground pad of a decoupling cap, every IC ground pin, and around exposed pads.

## 8. Board edges, cables and chassis

- Cables are antennas driven by the voltage between the cable conductors and the reference they see. Filter or
  decouple at the connector; keep fast nets and switch nodes away from connectors and board edges.
- A row of ground stitching vias along the board edge (and ground fill on all layers to the edge, inset per the
  fab's copper-to-edge rule) reduces edge radiation from internal planes.
- TI SLVAEP5 measured another ~5 dB less radiated emission by adding high-frequency capacitors from input/output
  and ground planes to a chassis ground near the cable terminations.

## 9. Quick diagnostics on a finished layout

- Render each plane layer alone; look for slots, necks and islands under important traces.
- For every critical net, trace the return mentally from the load back to the source's ground pin: is it directly
  under or beside the outgoing path the whole way?
- For each switching loop, outline the loop area including its return; the smallest-area version is the target.
- For each layer change on a critical net, find the nearby ground via.

## Sources

- H. Ott, PCB Stack-Up part 6 (return path discontinuities) and "Grounding of Mixed Signal Systems"
  (hott.shielddigitaldesign.com/techtips).
- TI SLVAFJ3, *Layout Optimization of 4-Switch Buck-Boost Converters* (AGND/PGND, net ties, thermal-pad join).
- TI BQ40Z50-R2 datasheet §11 (gauge layout: separation, Kelvin, ground shield, spark gap).
- TI SLVAEP5A (chassis capacitors, ground planes).
- AtlasPCB, Schemalyzer, RF Essentials articles on via transitions and stitching distance (secondary).
