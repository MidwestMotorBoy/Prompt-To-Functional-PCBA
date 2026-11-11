# RF and antenna modules

Contents: 1. Module placement · 2. Keep-outs · 3. Ground around the antenna · 4. Matching network · 5. 50 Ω feed
lines · 6. Things that detune antennas · 7. Bring-up · Sources

Most boards use a certified module (BLE/Wi-Fi) with an integrated PCB or chip antenna. Layout's job is to give the
antenna the environment the module vendor characterised it in.

## 1. Module placement

- Antenna end at a board edge, ideally in the middle of that edge, nothing beyond it.
- Follow the vendor's figure for ground-plane extent either side. Example: TI CC2340R5MODA (SWRS349A fig. 9-2) —
  ground dimensions A and B either side along the edge and C below should be ≥20 mm for best efficiency; ~50 %
  efficiency at 20 mm, ~25 % at 15 mm, ~10 % at 10 mm, "not recommended" below 10 mm.
- Module body flush with (or as close as the fab's edge clearance allows to) the edge.

## 2. Keep-outs

- Under the antenna: **no copper on any layer** (no pours, planes, traces, vias) over the vendor's keep-out area
  (CC2340R5MODA: 7.0 × 3.2 mm on all layers, narrowed to 5.4 mm between the pads on the top layer). No parts on
  the bottom layer there either.
- Put the keep-out in the module **footprint** as rule areas so it moves with the part and can't be forgotten.
- Don't add a board-level keep-out that removes ground beside the antenna if the vendor wants ground there (a
  different module's keep-out rules don't transfer).
- Solid ground plane under the rest of the module, with ground vias, but no signal traces under the module on the
  layer it is mounted on.

## 3. Ground around the antenna

- The ground plane is half the antenna. Keep it solid and continuous on all layers along the edge either side of
  the module for the vendor's distance; stitch layers together along the edge.
- Keep tall metal (headers, connectors, shields, batteries, holders) and probe-lead landing spots away from the
  antenna; they detune it and bring-up probes hanging off a header next to it change the result.

## 4. Matching network

- Most modules expose a pi or T match (e.g. CC2340R5MODA: series CA1, then Z60/Z61/Z62 pi). Place it right at the
  RF pins, components in signal order along the line, shunt parts with their ground pads straight to the plane by
  a via each.
- Use C0G/NP0 capacitors and the package size the vendor characterised (often 0201/0402); fit footprints even for
  DNP positions so you can tune.
- Keep the RF node tiny; no stubs; no other traces nearby.

## 5. 50 Ω feed lines (when there is a feed line)

- Coplanar waveguide with ground (CPWG) on the outer layer over the first ground plane is easiest to make 50 Ω on
  thin dielectric. Calculate with the fab's real stack-up; ask the fab for impedance control if it matters.
- Line of ground vias along both sides of the CPW (a via fence), spaced ≤λ/20 at the operating frequency (≈6 mm
  at 2.4 GHz in FR-4; tighter is common).
- No sharp bends (use arcs or 45° chamfers), no width changes except at component pads, no vias in the RF line.

## 6. Things that detune antennas

- Copper (any layer) within the keep-out; ground plane too small; enclosure plastic and hands (retune in the final
  enclosure); batteries and metal holders nearby; long unshielded cables near the antenna; nearby switching noise
  (place the radio away from converters).

## 7. Bring-up

- Measure range/RSSI in the real enclosure; retune the match (spectrum/VNA or iterative RSSI) with the DNP
  positions fitted as needed.

## Sources

- TI CC2340R5MODA datasheet SWRS349A §9.3 (fig. 9-2 keep-out, ground dimensions vs efficiency, matching network).
- General RF layout practice (CPWG, via fences, λ/20).
