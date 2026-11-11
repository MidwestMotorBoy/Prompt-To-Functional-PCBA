---
name: battery-protection-config
description: Design and configure Li-ion pack protection (fuel gauge/protector such as BQ40Z50, second-level OVP + chemical fuse, protection FETs, shunt) and the charger/PD defaults around it, including short-circuit FET stress and data-flash pitfalls. Use when picking protection FETs, setting gauge thresholds or data flash, checking short-circuit behaviour, or wiring cell taps and NTCs.
---

# Battery protection and gauge configuration

Drawn from a 4S1P 21700 pack with a TI BQ40Z50-R2 gauge, BSC007N04LS6 CHG/DSG FETs, a 1 mΩ shunt, and a BQ294700 second-level OVP that fires a chemical fuse. The concrete values are in `docs/spec.md` (Battery management and protection) and `docs/production/p0-bringup-and-training.md`; the short-circuit model is in `research_notes/protection-fets/`.

## 1. Layers, and what each one may assume

| Layer | Part | Must work when |
|---|---|---|
| 1. Gauge / protector | Gauge + CHG/DSG FETs + shunt | the MCU is dead or wrong |
| 2. Independent hardware | Per-cell OVP IC driving a chemical fuse | the gauge's config or firmware is wrong |
| 3. Firmware policy | MCU ramps and cross-checks | everything works; it is the smoothest layer, not the last line |

No layer may depend on the one above it. Write down, for each fault (overcharge, overdischarge, short, overtemperature, reversed or missing cell), which layer catches it first and which is the backstop.

## 2. Short circuit: size the FETs for the clearing event

1. **Prospective current.** Pack voltage over (cell AC impedance × cells + loop resistance). With 4 cells at ≤ 8 mΩ AC plus about 40 mΩ of loop, that is about 375–400 A. Lower-R FETs raise it slightly.
2. **Clearing time.** Detection (a few µs at this overdrive; assume about 15 µs) + the SCD delay setting + the gate falling to its Miller plateau through the gauge's gate resistor (TI's 5.1 kΩ).
3. **Stress per FET.**
   - (a) Fully on: I² · R_DS(on) for that time, in both FETs.
   - (b) Linear turn-off, in the DSG FET only: V_DS climbs while the loop limits I, so the peak is about (V/2)·(I/2). The time is Qgd divided by the gate current (about 0.75 mA through 5.1 kΩ).
   - Convert both to ΔTj with the FET's Zth curve. If the curve can't be read, model it and list "check SOA Diagram X" as an open item.
4. **Trade-offs.** A bigger die helps (a) and hurts (b). Choose low R_DS(on) *and* low Qgd. If needed, add a PNP turn-off speed-up on the DSG gate, but stay above about 3 µs, or the loop inductance drives the FET into avalanche. Try SCD delay = 0 on the first build: it about halves (a), at the risk of nuisance trips.
5. **Fuse.** Check the chemical fuse's I²t against the gauge-cleared event (here about 25 A²s against 270–600 A²s to melt), so the fuse isn't what clears a short. A FET that fails shorted is a gap no small fuse closes; say so.
6. **Shunt.** Smallest value that still resolves current (TI's advice). Check SRP/SRN stays inside ±0.3 V at the short current.

## 3. Gauge data flash: defaults that bite

Read the TRM's factory value of every field you rely on. Then write the field, read it back, and export the golden image to the repo.
- **Temperature faults that don't open the FETs.** On the BQ40Z50, FET Options (0x4887) defaults to 0x20, with OTFET = 0: OTC/OTD only set flags. Set 0x24.
- **Factory FET enable is off.** Mfg Status Init = 0x0000 (FET_EN = 0), so the FETs stay off until it's set. Toggle them for bring-up with MAC 0x001F (CHG) / 0x0020 (DSG). The FET charge pump needs BAT ≥ 2.2 V.
- **Permanent fail.** Leave PF_EN, FUSE_EN and the PF enables off until the board runs on real cells with the fuse-blow path fitted. Otherwise a floating tap or a cell simulator can latch a PF, which needs full access to clear and can try to blow the fuse.
- **Precharge as reversed-cell protection.** With no precharge FET, keep Precharge Start Voltage at about 2.5 V and Charging Voltage Low ≤ 2.5 V. The per-cell check is the only MCU-independent block against charging a reversed or dead cell.
- **Thresholds against real loads.** Set OCD1 / OCD2 above the full-power current at the *lowest* pack voltage (100 W from 11.2 V is about 9 A), or a single port trips near empty. OCC sits just above the maximum charge current.
- **Temperature.** Temperature Enable defaults to TS1 + TS2 (0x06), and an open input reads very cold. Enable every fitted sensor, and fit resistors on the unused ones during bring-up. Make the gauge's `Temperature()` the hottest sensor (CTEMP), because that's what its charge ranges use.
- **JEITA / charge temperature ranges** sit just *under* the firmware's own ramp, so the gauge is a backstop and doesn't make a step change in current.
- Second-level settings: COV delay, Min Blow Fuse Voltage.

## 4. Charger and PD defaults around the gauge

- Charge-inhibit pulled to "inhibit"; the MCU drives it to allow charging.
- A register-only charge limit (ICHG pin 0 Ω) needs readback and backstops (see `power-stage-design`).
- The charger's own JEITA stays off if its NTC sits on FET copper rather than the cells.
- The PD controller's boot config loads a safe charge current before the MCU runs.

## 5. Cell taps, assembly order and NTCs

- Connect taps bottom-up: pack−, 1N, cell taps in order, top tap, then pack+. A floating tap can trip the OVP IC.
- **Leave the fuse-blow resistors (or the OVP output link) unfitted** until all tap voltages read right at the pads, one cell step each, 2.5–4.2 V.
- Check the cell-tap filter resistors' power with a cell missing.
- **NTC placement.** Each control NTC must read **at or above** the hottest point of its cell in every load case. A sensor that reads low lets the pack run hot. Check the spot with a thermal model across cases (see `thermal-derating`). An NTC next to a load-dependent heat source (FETs, inductor) has an offset that changes with load and can't be calibrated out.

## 6. Training and records

- New cell chemistry: no chemistry ID in TI's database means a GPCCHEM run (slow discharge with rests), then a learning cycle per TI's procedure.
- Keep the MCU off the SMBus while BQStudio talks (hold it in reset, and hold charge-inhibit low if charging is needed). Never connect the EV2400 with the MCU unpowered: its pull-ups back-power the MCU.
- Commit the golden data-flash image and the calibration procedure to the repo.
