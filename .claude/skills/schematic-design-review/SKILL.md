---
name: schematic-design-review
description: Review a KiCad (or any) schematic for wiring, rating, configuration and fault-state bugs before layout or fab. Use when asked to review, audit or sanity-check a schematic, a netlist, a sheet change, or a new IC block.
---

# Schematic design review

A method for finding real defects in a schematic, not style nits. It was used on four dev-board reviews and the production board of a 4S Li-ion USB-PD power bank (`docs/devboard/schematic-review-*.md` in this repo). Every finding has to name a pin, a net or a register, and cite the datasheet section it comes from.

## Inputs to gather first

1. **The netlist.** Export it and don't read nets off the drawing: `kicad-cli sch export netlist --format kicadxml -o net.xml root.kicad_sch`. Parse it into `{(ref, pin): net}`.
2. **Every datasheet** for every IC, protector, FET and connector in scope. Keep them in the repo (`datasheets/`) so the next reviewer can cite the same revision. Where datasheets and memory disagree, the datasheet wins.
3. **ERC output** (`kicad-cli sch erc`). Triage every item: real, false positive, or accepted.
4. **The design intent**: the spec, the power tree and the operating cases (voltages, currents, temperatures, modes).

## Passes (do all of them; each one catches different bugs)

### 1. Pin-by-pin datasheet pass
For each IC, walk the datasheet pin table in order and check that pin's net, the strap value and any passives against the typical-application figure and the electrical table.
- **Custom symbols are the top source of bugs.** A symbol generated from a script or typed by hand can swap two pins. On this project a generated TPD6S300 symbol had pins 7 and 8 swapped, which put CC1 on GND on both USB ports. Check the symbol's pin numbers against the package drawing, not against another symbol.
- Check the exposed pad: its net, and the footprint EP size against the package (one footprint had a 2.8 mm EP for a 1.4 mm package pad).
- Check that "N.C." pins really are no-connects. Some datasheets say "connect to GND".
- Check strap and address pins by decoding them to the register value (I2C address, boot mode, dead-battery mode).

### 2. Net-by-net trace
- Every net with one pin is a bug, unless it's a test point.
- Every power net should have exactly one source, or an intended OR-ing.
- Every global or hierarchical label should appear on at least two sheets.
- Copied blocks (two identical ports) should be compared by script: same refs offset by the block number, same nets apart from the shared ones (GND, the main bus, the I2C bus). Look for wires or labels that were deleted from one copy. On this project a deleted GPIO6 to DRV9_OFF wire left a gate-drive enable floating.

### 3. Absolute-maximum and rating pass
For every pin, find the highest voltage its net can reach in any state, and compare it with the pin's absolute maximum.
- Enable pins tied to an input rail above their rating (an LDO EN tied to a 16.8 V pack).
- An LDO's EN pin can't sit above its own IN.
- Interrupt and open-drain lines pulled up to a rail the receiving MCU doesn't have.
- Hot-plug overshoot on VBUS. A live 20 V plug-in lands at about 27–29 V. Check every part on VBUS against that, and pick a TVS whose minimum breakdown sits above the highest *legal* voltage (21 V PPS). An 18 V TVS conducts in normal use.

### 4. Worst-case derating
- **MLCC DC bias.** Take the effective capacitance from the maker's DC-bias curve at the real voltage, not the nominal value. One review found a "22 µF" 1210 holding 5.9–6.8 µF at 20 V. The bank was 72–75 µF against an 80 µF minimum, and an earlier number had used the 15 V point.
- Ripple current per capacitor, against its rating at temperature.
- Resistor power in fault states (a missing cell puts the cell-tap filter resistors across a full cell).
- FET voltage stress as a percentage of V_DS, fuse ratings against the real fault current, and the sense-resistor voltage against the IC's input range during a short.

### 5. State and fault analysis
Write a table: one row per block, one column per state. Most of the serious bugs in this project were found here, not in the wiring.

| State | What to ask |
|---|---|
| Blank board (no firmware, blank EEPROMs, factory gauge) | What powers up? Does any converter run unconfigured? Is charging enabled by a default pull? |
| MCU in reset, hung or blank | Are the safety pulls in the safe direction? (A CHG_INH pulled up means "no charging" while the MCU is dead.) |
| Watchdog expiry / charger register reset | What does the hardware fall back to? A charge-current pin left at its hardware maximum (9–10 A here) is what the charger uses after a watchdog reset. |
| Dead battery, USB plugged in | Which rails come up, in what order? Can the gauge wake? |
| Debug probe attached with the target unpowered | Back-power through pull-ups and I/O clamps. Here the EV2400's own 20 kΩ pull-ups fed a dead MCU, so no "3V3 dead" gauge procedure was safe. |
| A cell missing, reversed or open; a tap wire off | Where does the current go? Can anything charge a reversed cell? |
| Output short | Peak current, which part clears it and how fast, and the energy in each FET (see `battery-protection-config`). |
| Inrush when a FET turns on into the bulk capacitance | Peak current, limited by loop resistance. |

### 6. Configuration and defaults pass
Many "hardware" protections live in non-volatile config. List each IC's factory defaults that matter and check them against the design:
- gauge data flash (whether a temperature fault actually opens the FETs, precharge thresholds, permanent-fail enables);
- charger registers at power-up and after a watchdog reset;
- PD controller boot mode with a blank EEPROM.

Record these as "configuration items" next to the hardware findings, so they reach the firmware and bring-up docs.

### 7. BOM pass
Every placed part has an MPN, an LCSC/JLC number or a "consign" note, a value that matches its Notes field, and a footprint that matches the MPN's package.

## Running it as a team (when subagents are allowed)

Split by sheet or function (MCU and buses; power stage; connector and PD; cells, gauge and protection). Then add a **challenge round**: each reviewer attacks the others' findings, and each finding is defended, re-graded or withdrawn. In this project's reviews the challenge round moved about a third of the majors, in both directions: one false alarm was withdrawn, one finding got worse, and new items came up. A lead re-checks every major against the datasheet before reporting.

## Grading and report

- **Critical:** damage or a safety hazard in normal use. **Major:** wrong behaviour, or damage in a plausible fault. **Minor:** margin or robustness. **Config/procedure.** **Documentation.**
- Each finding gives the evidence (pin, net, datasheet section, calculation), the consequence, and a concrete fix (part, value or register).
- End with a **"Checked and correct"** list (which ICs were pin-checked, which nets were traced, which ratings passed). It shows what the review covered, so a clean result means something.
- State plainly what wasn't checked (for example, an SOA graph that couldn't be read).

## Pitfalls seen
- A number taken from a search summary instead of the datasheet curve (a leakage figure was 10× off).
- Mixing up a fuse's rating with the current it has to carry.
- Copying a review's "typical" value into a worst-case check.
- Reviewing a stale export. Regenerate the netlist from the files you were given.
