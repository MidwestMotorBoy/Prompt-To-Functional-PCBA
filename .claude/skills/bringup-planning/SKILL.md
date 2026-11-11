---
name: bringup-planning
description: Plan the first power-up and bring-up of a new board (battery, charger, PD, MCU) by working out from the netlist what each block does with blank firmware and factory configs, then staging power from unpowered checks to bench supply to real cells. Use when writing a bring-up or assembly procedure, asking "can this board power up without X", or ordering programming steps.
---

# Bring-up planning

From the bring-up plan for a pack board with no dev board before it (`docs/production/p0-bringup-and-training.md`, section 0, and `docs/production/p0-assembly.md`). The key idea: before writing any step, work out from the netlist and the datasheets what every block does in each power state, with **blank** firmware, EEPROMs and data flash. A step written as "connect X, check 3V3" fails when 3V3 can't come up on a fresh board.

## 1. Power-state table

Trace every rail's source from the netlist (enable pins included), then fill in a table like this:

| Block | Source A only, blank board | Source A, programmed | Bench supply on the main bus | Real cells |
|---|---|---|---|---|
| PD controller | ... | ... | ... | ... |
| Charger | ... | ... | ... | ... |
| Main buck / MCU | ... | ... | ... | ... |
| Gauge and its FETs | ... | ... | ... | ... |

Questions for each cell of the table:
- What powers it? Through which diode or FET body diode?
- What do the factory defaults do (PD SafeMode with a blank EEPROM, gauge FET_EN = 0, charger defaults)?
- Do pull-ups on inhibit lines go to a rail that's dead in this state? Then the default flips (a CE_N pull-up to a dead 3V3 *enables* charging).
- Does something cycle? (No battery: the charger charges the bus caps to its regulation voltage, terminates, sags and restarts. A blank MCU lets 3V3 come up and drop again.)

The answers decide where the first power has to go in. On this board USB alone powers only the PD controllers. So the first boot is a bench supply on the main-bus wire pads, which bypass the gauge.

## 2. Stage the power

1. **Unpowered:** resistance to GND on every rail; pack terminals and each tap; fit stand-in resistors on unused NTC inputs so they don't read as open.
2. **Optional smoke test** from the most current-limited source (a 5 V USB charger through a USB power meter).
3. **Bench supply on the main bus** at low voltage and 50 mA, then nominal at 100 mA. Check the rails, flash the MCU (with the debug probe set to "target supplied power"; the default LaunchPad config drives 3.3 V into the board), and write the PD EEPROMs. Read the chargers, but don't write gauge data flash yet.
4. **Cell simulator** (resistor ladder on a supply, connected with the supply off, all pins at once). Calibrate the tap voltages, toggle the gauge FETs and check the body-diode drop disappears, and test the second-level OVP with its fuse-blow path unfitted.
5. **Charger with a fake battery.** An electronic load in CV mode with about 2,000 µF, or a bench supply plus a CC load set above the programmed charge current (TI's EVM guide). Keep the gauge's CHG FET off so the charger can't push the ladder up. Then PD contracts at each voltage, charging at low then full current, gate-drive options, switch nodes on the scope at low power, and reverse mode.
6. **Real cells.** Taps in order, protection resistors fitted only after all taps read right, then gauge training.

## 3. Risks and rules table

Write one row per hazard, with its rule. Examples that apply to most battery boards:
- A bench supply on the main bus bypasses every protection layer. Its current limit is the only protection, so start at 50 mA.
- Keep the bus under the lowest-rated part on it (25 V caps, 28 V buck → ≤ 17 V).
- Leave permanent-fail and fuse enables off until real cells and the fuse path are in.
- Floating or partly connected taps: connect simulators unpowered, all at once.
- With the CHG FET on, anything driving the bus drives the cell ladder.
- Probe points behind high-value resistors to the cell stack: never on a debug probe.
- Debug adapters must not be connected while the target MCU is unpowered (back-power through pull-ups).

## 4. Checks that feed decisions

End the plan with a table: check, how to measure it, and which design or firmware decision it feeds. Examples: switch-node ringing → keep 0 Ω gate links or fit resistors/snubbers; FET and inductor temperature at the worst case → thermal limits; load step on the 5 V rail → output cap size; PD contract surviving an MCU reset → firmware sequencing; wake-on-plug → whether a manual wake pad stays; sleep current → firmware power states. Measurements without a decision attached tend not to get done.

## 5. Write it where it will be used

Put the procedure in the repo next to the assembly guide, and link it from the spec. Mark anything worked out on paper as "not yet tried on hardware", with the date and the sources (datasheets, TRM sections, EVM guides).
