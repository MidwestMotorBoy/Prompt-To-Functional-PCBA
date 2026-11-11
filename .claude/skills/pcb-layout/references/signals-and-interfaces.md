# Signals and interfaces

Contents: 1. Routing order and layer choice · 2. Kelvin sense and analog · 3. Battery gauges and BMS ·
4. I2C / SMBus and slow buses · 5. Interrupt and long nets · 6. Differential pairs and USB 2.0 · 7. Crosstalk ·
8. Decoupling · 9. Crystals and clocks · 10. Fine-pitch escape and fan-out · Sources

## 1. Routing order and layer choice

- Route critical signals before general ones: sense pairs, references, feedback, gate drive, RF feed, crystals,
  differential pairs; then buses; then everything else, shortest first.
- Route each signal on a layer adjacent to its reference plane, ideally a buried layer next to solid ground for
  anything sensitive (Ott objective 4). Prefer one layer for the whole run; if it must change, keep the same
  reference plane, else add a ground via within ~1 mm of the signal via.
- Keep traces at 45° or arcs; avoid acid-trap acute angles; keep a consistent width per net class.

## 2. Kelvin sensing and low-level analog

- Four-wire connection to every current-sense resistor and to every point whose voltage you need exactly (cell
  taps, regulation point). Tap the pad's quiet end; never let the router "connect" a sense line to the nearest
  copper of the same net.
- Route the pair together (tight, parallel) from source to filter; filter components at the IC pins.
- Avoid vias and test points in the sense path; if the pair must cross power copper, drop both to an inner layer
  under the ground plane, together.
- ADI: below ~3 mΩ, simple layouts aren't adequate — use split-pad / four-terminal footprints.
- Keep high-impedance analog nodes (dividers, references, filter mid-points) small and away from switching copper
  on every layer; shield with ground fill.

## 3. Battery gauges and BMS (TI BQ40Z50 §11 and similar)

- Separate high-current and low-level sections physically; ideally high current on the opposite side from the
  gauge electronics.
- Route high-current traces away from traces that enter the gauge; surges and ESD on the pack path couple
  magnetically and capacitively into the gauge's sense inputs.
- Kelvin-sense the shunt and the top and bottom cell voltages; route the shunt traces parallel to the filter;
  place all filter components close to the IC; add a ground shield around the filter network.
- Cell-tap traces are low current but at cell potentials: keep spacing and route them as a bundle to the VC
  filter ladder.
- Protect SMBus/comm lines at the connector with a spark gap (TI pattern: 0.2 mm point spacing).
- The gauge's VSS is the cell-side of the shunt — see `return-paths-and-grounding.md` §3.

## 4. I2C / SMBus and other slow buses

- Slow (100–400 kHz) but long buses still need a return path: route over the ground plane, as a pair (SCL beside
  SDA) with ground fill around.
- Pull-ups near the controller end; size for the bus capacitance (rise time). On long or many-device buses use
  100 kHz and lower-value pull-ups.
- Series resistors (e.g. 100 Ω) at a device that sits in a different ground domain or at a connector.
- A powered bus must never drive an unpowered device's pins above its abs-max (back-powering): check every device
  on a bus has the same supply, or isolate.

## 5. Interrupt lines and long nets

- Open-drain wire-OR lines: one pull-up, near the receiver; route as a single bus with stubs to each source.
- Long cross-board nets go on inner layers between planes; keep them out of power-stage areas and away from board
  edges.

## 6. Differential pairs and USB 2.0

- Route as a coupled pair: constant width and gap set for the target impedance (USB 2.0: 90 Ω differential
  ±15 %, ~45 Ω single-ended), over a continuous reference plane, no splits under them.
- Length-match within the pair (USB 2.0 guidance ranges ~0.15 mm to a few mm; tighter is easy, so do it); match
  where the skew is created (near the bend), not with a serpentine at the far end.
- Keep vias to a minimum and symmetric (both lines change layers together), with a ground via beside them.
- Keep the pair away from other signals (≥3W, more from clocks and switch nodes) and from board edges.
- ESD protection in-line at the connector, pads on the trace (no stubs).
- If the data lines aren't used (e.g. a USB-C port used only for power with D+/D− shorted for a charging signature),
  keep the short local at the connector.
- USB-C's interleaved D+/D− pins (A6/B6 D+, A7/B7 D−): run all four out, merge each polarity close to the
  connector; one hop to an inner layer for one line usually suffices.

## 7. Crosstalk

- Spacing is the main lever: the "3W" rule (centre-to-centre ≥3× width, i.e. gap ≥2W) is a conservative starting
  point; 4–5W for very sensitive or very fast nets. A closer reference plane lets you relax it.
- Coupled length matters: avoid long parallel runs of aggressor and victim; cross at 90° on adjacent layers.
- Guard traces only help when stitched to ground every few mm; otherwise prefer ground fill and spacing.
- Microstrip (outer) couples more far-end crosstalk than stripline (between planes).

## 8. Decoupling

- The loop is cap → its vias → plane → IC's ground via → IC: minimise it. Via right at each pad, one per pad (two
  for big caps), smallest value nearest the pin; mount on the side with the smallest loop (Archambeault).
- Mounting inductance (pads + vias) often exceeds the capacitor's own ESL; pad-to-via distance and via spacing
  dominate.
- With closely spaced planes (<0.5 mm) exact cap position matters less; on boards with thin dielectric to a solid
  plane it still pays to keep caps at the pins.
- Many parallel caps don't scale 1/N because of mutual via inductance; alternate pad polarity and spread them.

## 9. Crystals and clocks

- Crystal and load caps at the oscillator pins, on the same side, short traces, ground fill around (stitched),
  nothing routed under on the adjacent layer except ground.
- Clocks: route on one layer next to ground, no reference changes, spacing from everything (Ott's preference list).

## 10. Fine-pitch escape and fan-out

- Plan escapes at placement: 1.5 mm clear round dense ICs (`routing-discipline.md` §3), vias in staggered columns
  (~1 mm pitch), 0.15 mm tracks passing between. Fan out these parts before routing anything else.
- At 0.4–0.5 mm pitch the fab's 2 oz minimum track/space often won't fit a track between pads on outer layers:
  escape outward, or drop to an inner (thinner copper) layer through a via.
- Exposed-pad devices: route signal pins outward; the centre is for thermal vias to ground.
- Pin order on a driver edge rarely matches the FETs' gates: count lanes and decide layer plans before drawing.

## Sources

- TI BQ40Z50-R2 datasheet §11 (gauge layout, Kelvin, ground shield, spark gap 0.2 mm).
- TI SLVAFJ3 §2.3 (sense lines, net ties).
- ADI Analog Dialogue, "Optimize High-Current Sensing Accuracy" (Kelvin pads).
- H. Ott, PCB Stack-Up part 6 (routing preference list).
- USB 2.0 spec (90 Ω ±15 %); TI SLLA414A (USB layout); embeddedhardwaredesign, Renesas USB guidelines (matching).
- Altium/Cadence crosstalk articles (3W, guard traces); Archambeault IEEE EMC decoupling slides.
