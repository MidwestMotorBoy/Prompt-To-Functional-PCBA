# Floorplan and placement

Contents: 1. Order of work · 2. Floorplanning · 3. Placing a block · 4. Making it look intentional · 5. Repeated
blocks · 6. Test points and debug · 7. Placement-for-routing checks · 8. Placement as data (scripting)

Placement decides most of a layout's quality. Hot loops, Kelvin connections, escape routing and thermal paths are
fixed at placement; routing can only spoil them. Spend the time here.

## 1. Order of work

1. Mechanical: outline, mounting holes, connectors, battery holders, switches, LEDs that must align with an
   enclosure, antenna edge. Lock them.
2. Floorplan zones (below).
3. Key ICs and power devices in each zone (power stage before its controller).
4. Their support passives, immediately at the pins they serve.
5. Secondary parts: indicator LEDs, test points, jumpers, headers.
6. Sanity check (section 7), render, review, iterate. Only then route.

Don't scatter every passive up front; leave routing channels between blocks.

## 2. Floorplanning

- Divide the board into functional zones: power entry/protection, each converter, battery/gauge, MCU/digital,
  RF, analog front ends, connectors.
- Lay zones out in **power and signal flow order** — connector → protection → converter → load — so current flows
  one way across the board without doubling back.
- Keep noisy zones (switching stages, motor drivers, clocks) away from sensitive zones (gauges, ADC inputs,
  references, RF) and away from connectors and board edges where cables pick up noise.
- High-current paths short and straight; heat sources spread out, away from temperature-sensitive parts
  (electrolytic caps, cells, crystals, thermistors that should read ambient).
- Give each zone a clear boundary and a gutter of free space to the next zone; dense cluster then gap reads as
  structure and leaves routing channels.

## 3. Placing a block (power stage example, then general)

Power stage (see `power-conversion.md` for the reasoning):
1. Place the switches (FETs or half-bridge) and the input/output capacitors first: the smallest HF ceramic across
   the high-side drain and low-side source pads, bulk caps one row behind.
2. Inductor next to the switch node(s), switch-node copper as small as possible.
3. Sense resistor in the current path, oriented so current flows straight through it; Kelvin taps at the far ends
   of its pads.
4. Controller close enough that gate-drive loops are short, oriented so gate-drive pins face the FETs; its
   programming parts (FB divider, compensation, RT, ILIM, soft-start) on the quiet side, next to their pins.
5. Bootstrap caps and driver supply caps at their pins.

General block:
- Decoupling caps at each supply pin, smallest value nearest the pin, on the same side as the IC.
- Filter components at the pin they filter (current-sense filters at the IC, not at the shunt).
- Pull-ups/downs next to the pin or test point they serve.
- Crystals right at the oscillator pins, nothing else nearby.
- Board temperature sensors at the thing they sense (FET copper, connector, heatsink pad), not beside the MCU.

## 4. Making it look intentional

What reviewers (and users) read as "designed" rather than "scattered":
- Orthogonal placement only (0/90/180/270). Align parts on shared edges or centre lines; use align/distribute.
- Coarse grid for ICs and connectors (e.g. 0.635/1.27 mm), finer for passives.
- Same rotation for like parts: diodes one way, polarised caps + one way, IC pin 1 one direction, resistor/cap
  rows all horizontal or all vertical within a block.
- Passives in tidy rows/columns at a fixed pitch, ordered by the pin they serve. For non-polarised two-pin parts,
  pick 0° vs 180° so the signal pad faces its pin — they look identical, so the row stays uniform.
- Test points and headers in rows along an edge or block border, not sprinkled.
- Silkscreen: refdes off pads, one size (~1 mm text, 0.15 mm line), readable in at most two orientations, block
  titles/outlines to show zones.
- Priority when tidying: electrical constraints first (hot loops, Kelvin, pin proximity), then alignment. Tidiness
  never moves a part away from its pin or loop.

## 5. Repeated blocks

Identical channels (two charger ports, several phases) should be identical copies, translated not re-placed. Place
one, then copy offsets and rotations exactly (KiCad: multichannel/replicate layout, or a script that applies the
offset). Place parts that belong to a connector relative to that connector; if two connectors sit at slightly
different offsets, the "identical" blocks won't be.

## 6. Test points and debug

- Every rail, every switch node (as a short stub off the far side of the inductor pad, never in the FET-to-
  inductor copper), key control signals, and ground points next to probe points.
- Scope-probe ground loops next to switch nodes so the probe loop is tiny.
- Header pin-1 marks and cable-key indication on silkscreen.
- Pull-ups placed under the test point they pull.
- Test-point labels: same position relative to every loop; space rows so labels don't collide (≈0.7 mm per
  character at 0.8 mm text).

## 7. Placement-for-routing checks (do these before routing)

- Orient each IC so each side faces where its nets go. For every side, list its pins' destinations; if a side's
  pins all leave the opposite way, rotate. On this board, turning a USB-PD controller 90° pointed its CC/SBU side
  at the CC protector (same pin order: four straight links), its VBUS/PPHV side at the power path, and its I2C
  side at the charger and MCU. No router setting came close to that.
- Put a protection or interface IC between the two things it joins (controller ↔ connector), with its two sides
  facing them, and check that its pin order matches both, so the links don't have to cross.
- Every IC pin row and connector pin row still has an escape path: no power copper, TVS or bulk cap parked across
  a pin row. Leave the area in front of connector signal pins free.
- ICs with more than 20 pins or pitch under 0.8 mm keep **1.5 mm clear all round** their courtyard (decoupling caps
  excepted, at the pins). Plan one via per signal pin in staggered columns, and fan them out before any other
  routing. `check_routing_rules.py` lists parts inside that area (`routing-discipline.md` §3).
- Gate-driver pin order vs FET gate positions: count crossings; plan which signals take an inner layer.
- Sense pairs: list pad order at both ends; pick which net is the outer lane so the pair doesn't cross.
- 0 Ω links/jumpers face the right way so their links don't cross.
- Courtyard check and DRC clean (no overlaps, no parity errors) before any copper.

## 8. Placement as data (scripting)

For scripted placement, describe placement as data rather than letting an auto-placer pick nearest free spots:
helpers like `fix(ref, x, y, rot)`, `col(refs, x, top, rot, gap)`, `row(refs, left, y, rot, gap)` that centre
courtyards, with rows ordered by the IC pin each part serves; an `at(ref, x, y, rot)` that tries rot and rot+180 and
keeps whichever puts pads nearer their nets. Place repeated blocks once and translate. After every pass: render,
courtyard-overlap check, DRC with schematic parity. A nearest-free-spot pass is a fallback for leftovers only.
