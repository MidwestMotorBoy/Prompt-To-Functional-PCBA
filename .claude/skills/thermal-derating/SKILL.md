---
name: thermal-derating
description: Set temperature-based charge and discharge derating for a sealed battery/power product, place the control sensors so they never read low, and size the policy with a thermal model fed by real part and copper losses. Use when designing charge/discharge limits, choosing NTC locations, tuning burst-vs-sustain power, or running thermal model batches.
---

# Thermal derating and sensor placement

From a sealed 91 Wh pack whose board heats the cells under it through a gap filler. See `docs/firmware/charge-and-thermal-policy.md` (structure), `docs/spec.md` (thresholds) and `research_notes/Pack thermal BAK 65E/` (3-D model, NTC studies).

## 1. Policy structure

- **Start from the cell's limits** (charge and discharge temperature windows, maximum currents), and stay on or under them at every temperature. Until the maker supplies a temperature-stepped charge table, use a conservative cap and say so.
- **Linear ramps, not steps.** Every limit goes from full to reduced across a band (for example 100 W at ≤ 44 °C, ramping to 40 W at 48 °C). Steps make the system oscillate.
- **Act on the hottest sensor.** In a pack heated from one side that is a specific cell. Put a sensor there and use the maximum.
- **Layer the limits.** Hardware ceilings → gauge protection (OTC / OTD) → firmware ramp. Firmware is the smoothest and acts first; the others are backstops set a few kelvin outside it.
- **Combine as a minimum.** `P_allow = min(max, cell_ramp(T_hottest_cell), board_ramp(T_board), low_voltage_limit(V_pack))`.
- **Change the contract, don't sag the output.** For USB-PD, re-advertise Source Capabilities in steps (5 W here). Go down at once; go up only after cooling (2 K) and a hold time (10 s), so a laptop isn't renegotiated every second.
- **Two numbers to tune:** where the ramp *starts* sets the burst length, and where it *ends* (the sustain power) sets how warm the cells sit for the rest of the discharge. Don't cap the offer below the maximum; move the start instead.
- **Shared budgets.** With several outputs, decide who gives way when the budget shrinks. Here a reserved minimum on the second port starved the first one at 35 °C ambient, so the recommendation was that the priority port keeps its power when derating.

## 2. Sensor placement: never read low

1. Model the candidate spots across all the load cases: high discharge, charge, pass-through, charge right after a full-power run.
2. For each spot, compute the sensor reading minus the hottest point of the cell it protects. **A spot qualifies only if that offset is ≥ 0 in every case** and roughly the same from case to case.
3. Avoid spots next to load-dependent heat sources (FETs, inductors): there the offset swings 8–10 K with load, and no calibration fixes it.
4. A board-mounted NTC reads the board. Keep the inner planes under it (an isolated copper island removed only about a third of the error) and give it its own low-side trace.
5. If the spot reads high by a consistent offset, raise the thresholds by that offset (here the ramp moved from 42→46 °C to 44→48 °C) rather than accepting a low-reading spot.
6. The spot depends on the layout. If the power stage moves, rerun the study.
7. On the first build, put thermocouples on the hot points and compare. If the sensors differ from the model's offsets by more than about 1 K, move the ramp by the difference.

## 3. The thermal model

- **Heat sources:** the cells' I²R (with the real DCR, refitted from a measurement once there is hardware), every board part's loss from the loss budget, and the copper loss from `pcb-copper-resistance`, mapped into the model's tiles.
- **Currents come from the case, not a fixed number.** For each case, I_USB = P / V_USB(PD contract), and the pack current follows from P / V_pack(SOC), where V_pack sags with SOC and I·R. Efficiency should come *out* of the part losses, not be assumed. Check the model's OCV curve against the datasheet nominal: here it averaged 3.59 V per cell against 3.5 V, so its currents ran 2–3 % low.
- **Boundary conditions:** state the ambient (25 °C and a hot case such as 35 °C) and the convection (still air, in a pack).
- **Output for each case:** time at full power, energy delivered in a fixed window (40 min), charge time, hottest cell, hottest part, outer skin temperature and sensor readings.
- **Run the policy inside the model** (time-stepped, with the real ramps), so the burst length and energy include the derate's effect.
- **Sensitivity before buying material.** Sweep uncertain inputs (filler conductivity 1.5 / 3 / 6 W/mK). Here past about 3 W/mK didn't help, which settled the material choice.

## 4. Running batches

A multi-case sweep is CPU-heavy (here about 15 min for two splits on 30 cores, and about 20 min for 8 runs on 4 cloud cores). If the person has a fast local machine set up for it, run batches there in parallel rather than in a small cloud container. Keep the runner and result files in the repo, or in a shared folder next to the model.

## 5. Reporting

Give a before/after table with the same code in both columns, so only the change differs. Say which way each number moved and why: extra copper heat showed up as a shorter burst and slower charging, not as higher temperatures, because the derate held the limits. Every number is a design value until it has been measured on hardware; say so.
