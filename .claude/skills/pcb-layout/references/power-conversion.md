# Switching converter layout

Contents: 1. Identify the three kinds of nets · 2. Hot loops by topology · 3. Capacitor placement · 4. Switch nodes ·
5. Gate drive and bootstrap · 6. Current sensing · 7. Controller, FB and compensation · 8. Grounds · 9. Inductors ·
10. Snubbers and tuning parts · 11. Thermal · 12. Layer usage on a multilayer board · 13. Checklist · Sources

## 1. Identify the three kinds of nets first (TI SLVAFJ3 §2.1)

Mark them on the schematic before placing anything:
- **High di/dt loops (hot loops)**: carry pulsed current that turns on and off every cycle. Their area sets the
  inductance that rings and radiates.
- **High dv/dt nodes**: switch nodes (SW), bootstrap nodes (BST/HB), gate-drive traces. Their copper area is a
  capacitor that couples noise into anything nearby.
- **Sensitive traces**: current-sense lines, voltage-sense/FB, compensation, soft-start, RT, references.

Layout aim: minimise hot-loop area, minimise dv/dt copper area, keep sensitive traces away from both and short.

## 2. Hot loops by topology

The hot loop is where current switches abruptly between two paths. Map it by drawing the current in both switch
states; the part that differs is the hot loop.

| Topology | Hot loop |
|---|---|
| Buck | input capacitor → high-side switch → low-side switch → back to input capacitor ground |
| Boost | output capacitor → high-side (rectifier) switch → low-side switch → back to output capacitor ground |
| 4-switch buck-boost | **two**: input cap + input half-bridge (active in buck mode), output cap + output half-bridge (boost mode). Both are first priority. |
| Inverting / SEPIC / flyback | switch + input cap loop, and rectifier + output cap loop |

The inductor current is (nearly) continuous, so the inductor is *not* in the hot loop; keep it close, but the
capacitor-to-switch loop comes first. TI SLVAFJ3: "Connect the negative terminal of the capacitor close to the
source of the low-side MOSFETs (at ground). Similarly, connect the positive terminal … close to the drain of the
high-side MOSFETs of both loops."

## 3. Capacitor placement

- The **smallest high-frequency ceramic (e.g. 0.1–1 µF 0402/0603)** goes nearest, its pads directly at the
  high-side drain and low-side source. Pick a package whose pad pitch matches the FET drain-to-source spacing so it
  straddles both. This is the loop that sets ringing at 100+ MHz.
- Bulk ceramics next (same strip of copper), polymer/electrolytic bulk behind them.
- Same layer as the FETs; ground pads of the caps and the low-side source share one top-layer copper island,
  dropped into the ground plane directly beneath with a cluster of vias at the cap pads.
- With a solid ground plane on layer 2 at 0.1–0.2 mm, the loop closes vertically and is very small even if the
  parts are a few mm apart — but the HF cap straddling the FETs still wins.
- Distribute bulk capacitance on both sides of a sense resistor if the vendor asks (BQ25756: bulk distributed
  "equally on either side of" RAC/RBAT).

## 4. Switch nodes

- Make SW copper only as large as the current needs: TI SLVAFJ3 "the areas of the switching nodes SW1 and SW2 need
  to be as small as possible. If … poured with big area copper planes, the high dv/dt noisy signal can couple into
  other traces nearby through capacitive coupling".
- Keep SW on the outer layer with the parts; don't mirror it on other layers; keep sensitive traces from running
  under it on any layer, and keep a ground plane between it and inner signal layers.
- Nothing in the FET-to-inductor copper gap (no test points, no vias of other nets). A SW test point hangs off the
  far side of the inductor pad as a short stub.
- Fewer vias in power paths: TI SLVAEP5 measured up to 10 dB less radiated EMI from minimising hot-plane area and
  keeping each trace on one layer.

## 5. Gate drive and bootstrap

- Gate drive is a loop: driver output → gate → source → back to driver return. Its inductance resonates with the
  gate capacitance; a few nH causes ringing that can cross Vth and cause false turn-on (SLVAFJ3 §2.4).
- Route drive and return **side by side** for the whole length (return "in the shadow of the drive trace").
  Stack them on adjacent layers only where both layers allow the same direction: the In2/In3 Manhattan pair
  doesn't (`routing-discipline.md`). HO with SW; LO with PGND. Short, ≥0.5 mm (20 mil) wide where possible.
- Don't run HO beside LO, and don't run either beside sense lines.
- Gate resistors at the FET gate. 0 Ω placeholders in gate and bootstrap lines let you tune edge rate later.
- Bootstrap capacitor directly between BST and SW pins of the controller, short loop; the bootstrap diode (if
  external) at the cap. VCC/REGN/DRV_SUP caps at their pins.
- High-side gates on controllers that hold one FET on at 100 % duty may run from an internal charge pump that can't
  drive gate pull-down resistors — check the vendor's notes before adding gate pull-downs.

## 6. Current sensing

- Kelvin connections: sense traces leave from the resistor pad ends (the quiet side, away from where current
  enters), not from the copper carrying the current. Run them as a parallel pair to the IC (SLVAFJ3 §2.3).
- Filter components (series R, differential C, common-mode C) **at the IC pins**, not at the shunt.
- Route the pair on a layer next to the ground plane, away from SW nodes and gate drives. If they must cross power
  copper, take them to an inner layer under the ground plane.
- If a sense node is electrically the same as a power node (e.g. CSA = SW1), use a **net tie** so the layout tool
  keeps the sense trace separate and defines exactly where it joins.
- Pad-order trick: list the pad order at the filter and at the IC; choose which net is the outer lane so the pair
  never crosses.

## 7. Controller, feedback and compensation

- Controller close to the FETs it drives (short gate loops), with a decent quiet area for its analog parts.
- FB divider at the FB pin; the top of the divider taken from the regulation point (output cap or load) by its own
  trace; short FB node.
- COMP, SS, RT, SLOPE, ILIM parts next to their pins, returning to the controller's AGND.
- Keep all of these away from SW, HO/LO, BST nodes (SLVAFJ3 §2.5) and shield them with the ground plane.

## 8. Grounds

- One ground plane under the whole stage. AGND (quiet) as a local pour around the controller's analog parts,
  joined to PGND at one point, usually the controller's exposed pad (SLVAFJ3 §2.6, "§3 tips").
- Two ground symbols + net tie in the schematic make the layout tool enforce the separation.
- Never route sensitive traces through the power-stage ground island.

## 9. Inductors

- Close to the switch node. Shielded or closed-core types radiate less (AN-1149 recommends ferrite closed-core).
- Don't route sensitive traces under the inductor on any layer; a ground plane under it is fine (and helps).
- Orient so the terminal current path is straight and short.

## 10. Snubbers and tuning parts

- RC snubber from SW to PGND across the low-side FET, right at the FET; size R and C from the measured ring
  frequency (C ≈ 3× node capacitance, R ≈ characteristic impedance). Resistor dissipation ≈ C·V²·f — size the
  package for it (0.3–0.75 W is common).
- Footprints for DNP snubbers and 0 Ω gate/boot resistors cost nothing on a prototype and save a respin.

## 11. Thermal

- FETs and inductors are the main loss. Give them copper area on the outer layers and thermal vias into the planes.
- Controllers with exposed pads: thermal via array into the ground plane (see `high-current-and-thermal.md`).
- Keep heat away from electrolytic/polymer caps and from cells and thermistors that should not read FET
  temperature (unless that is their job).

## 12. Layer usage on a multilayer board

| Layer | Power stage use |
|---|---|
| Outer (with parts) | hot-loop copper, SW, power pours, gate drive short runs |
| Layer 2 | solid ground: return for both hot loops; no traces under the stage |
| Next inner | sense pairs and low-side drive (under the ground plane); high-side drive side by side with its SW return on one Manhattan layer, in that layer's direction, if it can't stay on top |
| Opposite outer | mirror of power pours (not SW), ground fill |

## 13. Checklist

- [ ] Each hot loop's HF cap straddles drain/source; ground plane directly under.
- [ ] SW copper minimal; nothing sensitive under or beside it.
- [ ] Gate drive paired with its return; gate resistors at gates.
- [ ] Bootstrap and VCC caps at pins.
- [ ] Kelvin sense from resistor pad ends, paired, filtered at IC.
- [ ] FB divider at FB pin, top from regulation point.
- [ ] AGND island joined to PGND at the exposed pad.
- [ ] Thermal vias under FETs/ICs; enough vias at every high-current layer change.
- [ ] Vendor EVM layout compared side by side.

## Sources

- TI SLVAFJ3, *Layout Optimization of 4-Switch Buck-Boost Converters* (2023): critical nets, hot loops, net ties,
  gate drive routing, controller layout, AGND/PGND, thermal vias, tips.
- TI SLVAEP5A: minimising hot planes, one-layer traces, ground planes, chassis capacitors (measured dB).
- TI AN-1149 / SNVA021, *Layout Guidelines for Switching Power Supplies*.
- TI four-switch buck-boost layout tips 1–4 (SSZTAE5, SSZTAE3, …); ADI Analog Dialogue "4-Switch Buck-Boost
  Controller Layout for Low Emissions — Single vs Dual Hot Loop".
